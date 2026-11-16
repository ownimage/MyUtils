"""Prepare slides from untouched highlights and per-image data.txt overrides."""
from __future__ import annotations

import csv
import os
import shutil
import json
import tempfile
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Event
from PySide6.QtGui import QImage
from dataclasses import dataclass
from pathlib import Path

from template_render import (validate_template, ensure_fonts, preferred_template,
                             render_overlay, render_prepared_file, missing_fonts)

ROOT = Path(__file__).resolve().parent
TEMPLATE_FILE = 'template.json'
CSV_FILE = 'data.txt'
LEGACY_PROJECT_FILE = 'slideshow.json'


@dataclass
class Slide:
    image: str
    date: str = ''
    title: str = ''


def event_folder(directory):
    folder = Path(directory).expanduser().resolve(strict=True)
    if folder.name.lower() in ('highlight', 'slideshow'):
        folder = folder.parent
    if not folder.is_dir() or not (folder / 'highlight').is_dir():
        raise ValueError('Choose an event folder containing a highlight folder.')
    return folder


def defaults(folder):
    name = Path(folder).name
    date = f'{name[:4]} {name[4:6]} {name[6:8]}' if len(name) >= 8 and name[:8].isdigit() else ''
    title = name[9:].strip(' -_') if date else name
    return date, title


def _legacy_project(folder):
    path = folder / 'highlight' / LEGACY_PROJECT_FILE
    if not path.exists():
        return None
    try:
        project = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as error:
        raise ValueError(f'Could not load older slideshow settings: {error}') from error
    if not isinstance(project, dict) or project.get('version') != 1 or not isinstance(project.get('images'), list):
        raise ValueError('Unsupported older slideshow settings format.')
    for row in project['images']:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in ('image','date','title')):
            raise ValueError('Invalid image overrides in older slideshow settings.')
    return project


def load_project(folder):
    folder = event_folder(folder)
    path = folder / 'highlight' / TEMPLATE_FILE
    if path.exists():
        try:
            template = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError) as error:
            raise ValueError(f'Could not load highlight/{TEMPLATE_FILE}: {error}') from error
    else:
        legacy = _legacy_project(folder)
        template = legacy['template'] if legacy is not None else preferred_template()
    return {'version': 1, 'template': validate_template(template)}


def _load_overrides(folder):
    # Prefer the saved highlight CSV; old slideshow CSVs remain importable.
    for data in (folder / 'highlight' / CSV_FILE, folder / 'slideshow' / CSV_FILE):
        if data.exists():
            overrides = {}
            with data.open(newline='', encoding='utf-8-sig') as stream:
                reader = csv.reader(stream)
                next(reader, None)
                for row in reader:
                    if row:
                        overrides[row[0].casefold()] = tuple((row + ['', ''])[1:3])
            return overrides
    legacy = _legacy_project(folder)
    if legacy is not None:
        return {row['image'].casefold(): (row['date'], row['title']) for row in legacy['images']}
    return {}


def load_slides(folder):
    folder = event_folder(folder)
    overrides = _load_overrides(folder)
    result = []
    for image in sorted((folder / 'highlight').iterdir(), key=lambda p: p.name.casefold()):
        if image.is_file() and image.suffix.lower() in ('.jpg', '.jpeg'):
            date, title = overrides.get(image.name.casefold(), ('', ''))
            result.append(Slide(image.name, date, title))
    return result


def _atomic_text(path, write):
    path.parent.mkdir(exist_ok=True)
    descriptor, filename = tempfile.mkstemp(dir=path.parent, prefix='.slideshow-', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', newline='', encoding='utf-8') as stream:
            write(stream)
        os.replace(filename, path)
    finally:
        Path(filename).unlink(missing_ok=True)


def save_template(folder, template):
    folder = event_folder(folder)
    template = validate_template(template)
    _atomic_text(folder / 'highlight' / TEMPLATE_FILE,
                 lambda stream: json.dump(template, stream, ensure_ascii=False, indent=2))


def save_slides(folder, slides, template=None):
    folder = event_folder(folder)
    slides = list(slides)
    template = validate_template(template if template is not None else load_project(folder)['template'])
    # Only layout belongs in JSON; date/title overrides remain ordinary CSV.
    def write_csv(stream):
        writer = csv.writer(stream)
        writer.writerow(['Image', 'Date', 'Title'])
        writer.writerows((slide.image, slide.date, slide.title) for slide in slides)
    _atomic_text(folder / 'highlight' / CSV_FILE, write_csv)
    save_template(folder, template)
    _atomic_text(folder / 'slideshow' / CSV_FILE, write_csv)


def render_worker_count(total, max_workers=None):
    if max_workers is not None and (isinstance(max_workers,bool) or not isinstance(max_workers,int) or max_workers < 1):
        raise ValueError('Worker count must be a positive integer.')
    return min(max(1,total), max_workers or os.cpu_count() or 1)


def _render_one(source, target, title, date, template, overlay, renderer, stopping):
    if stopping.is_set():
        return None
    if not source.is_file() or source.is_symlink():
        raise ValueError('Missing or linked highlight image: ' + source.name)
    target.parent.mkdir()
    shutil.copy2(source,target)
    if stopping.is_set():
        return None
    if renderer is not None:
        renderer(target,title,date)
    else:
        render_prepared_file(target,overlay,template)
    return target


def render_slides(folder, slides, *, cancelled=lambda: False, progress=lambda *args: None,
                  renderer=None, template=None, max_workers=None):
    folder = event_folder(folder)
    slides = list(slides)
    workers = render_worker_count(len(slides),max_workers)
    if not slides or cancelled():
        return 0
    default_date, default_title = defaults(folder)
    template = validate_template(template if template is not None else load_project(folder)['template'])
    names = set()
    for slide in slides:
        if Path(slide.image).name != slide.image or '/' in slide.image or '\\' in slide.image:
            raise ValueError('Invalid image filename: ' + slide.image)
        key = slide.image.casefold()
        if key in names:
            raise ValueError('Duplicate slideshow filename: ' + slide.image)
        names.add(key)
    if renderer is None:
        ensure_fonts()
        absent = missing_fonts(template)
        if absent:
            raise ValueError('Missing font: ' + ', '.join(absent) + '. Choose another font in Edit template.')
    output = folder / 'slideshow'
    output.mkdir(exist_ok=True)
    completed = 0
    stopping = Event()
    # Nothing is published by workers. They only prepare isolated image copies.
    with tempfile.TemporaryDirectory(prefix='.render-',dir=output) as temporary:
        staging = Path(temporary)
        overlay_directory = staging / 'overlays'
        overlay_directory.mkdir()
        memory_cache = OrderedDict()
        saved_overlays = {}

        def get_overlay(title,date):
            key = (title,date)
            if key in memory_cache:
                image = memory_cache.pop(key)
            elif key in saved_overlays:
                image = QImage(str(saved_overlays[key]))
                if image.isNull():
                    raise OSError('Could not read cached text overlay.')
            else:
                # Only this coordinator creates fonts, paths and text/glow pixels.
                image = render_overlay(title,date,template)
                path = overlay_directory / (str(len(saved_overlays))+'.png')
                if not image.save(str(path),'PNG'):
                    raise OSError('Could not save cached text overlay.')
                saved_overlays[key] = path
            memory_cache[key] = image
            # PNGs retain every distinct overlay without unbounded image RAM.
            while len(memory_cache) > min(workers,8):
                memory_cache.popitem(last=False)
            return image

        executor = ThreadPoolExecutor(max_workers=workers,thread_name_prefix='slideshow')
        pending = {}
        next_index = 0
        try:
            while next_index < len(slides) or pending:
                if cancelled():
                    break
                while next_index < len(slides) and len(pending) < workers:
                    if cancelled():
                        break
                    slide = slides[next_index]
                    title, date = slide.title or default_title, slide.date or default_date
                    overlay = get_overlay(title,date) if renderer is None else None
                    if cancelled():
                        break
                    source = folder / 'highlight' / slide.image
                    target = staging / str(next_index) / slide.image
                    future = executor.submit(_render_one,source,target,title,date,
                                             template,overlay,renderer,stopping)
                    pending[future] = (next_index,slide)
                    next_index += 1
                if cancelled() or not pending:
                    break
                done, _ = wait(pending,timeout=.05,return_when=FIRST_COMPLETED)
                for future in sorted(done,key=lambda item:pending[item][0]):
                    if cancelled():
                        break
                    _,slide = pending.pop(future)
                    target = future.result()
                    if target is None:
                        continue
                    if completed == 0:
                        _atomic_text(output / TEMPLATE_FILE,
                                     lambda stream: json.dump(template,stream,ensure_ascii=False,indent=2))
                    os.replace(target,output / slide.image)
                    completed += 1
                    progress(completed,len(slides),slide.image)
        finally:
            stopping.set()
            for future in pending:
                future.cancel()
            # In-flight image work finishes in staging, then is discarded on cancel/error.
            executor.shutdown(wait=True,cancel_futures=True)
    return completed
