"""Prepare slides from untouched highlights and per-image data.txt overrides."""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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


def load_slides(folder):
    folder = event_folder(folder)
    overrides = {}
    data = folder / 'slideshow' / 'data.txt'
    if data.exists():
        with data.open(newline='', encoding='utf-8-sig') as stream:
            reader = csv.reader(stream)
            next(reader, None)
            for row in reader:
                if row:
                    overrides[row[0].casefold()] = (row + ['', ''])[1:3]
    result = []
    for image in sorted((folder / 'highlight').iterdir(), key=lambda p: p.name.casefold()):
        if image.is_file() and image.suffix.lower() in ('.jpg', '.jpeg'):
            date, title = overrides.get(image.name.casefold(), ('', ''))
            result.append(Slide(image.name, date, title))
    return result


def save_slides(folder, slides):
    folder = event_folder(folder)
    output = folder / 'slideshow'
    output.mkdir(exist_ok=True)
    descriptor, filename = tempfile.mkstemp(dir=output, prefix='.data-', suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Image', 'Date', 'Title'])
            writer.writerows((slide.image, slide.date, slide.title) for slide in slides)
        os.replace(filename, output / 'data.txt')
    finally:
        Path(filename).unlink(missing_ok=True)


def render_slides(folder, slides, *, cancelled=lambda: False, progress=lambda *args: None,
                  renderer=None):
    folder = event_folder(folder)
    default_date, default_title = defaults(folder)
    output = folder / 'slideshow'
    output.mkdir(exist_ok=True)
    completed = 0
    for slide in slides:
        if cancelled():
            break
        # Only direct highlight children may be rendered, even for edited data files.
        if Path(slide.image).name != slide.image or '/' in slide.image or '\\' in slide.image:
            raise ValueError('Invalid image filename: ' + slide.image)
        source = folder / 'highlight' / slide.image
        if not source.is_file() or source.is_symlink():
            raise ValueError('Missing or linked highlight image: ' + slide.image)
        # Render a fresh copy every time. A failure leaves an existing slide intact.
        with tempfile.TemporaryDirectory(prefix='.render-', dir=output) as temporary:
            target = Path(temporary) / slide.image
            shutil.copy2(source, target)
            date, title = slide.date or default_date, slide.title or default_title
            if renderer is not None:
                renderer(target, title, date)
            else:
                python = ROOT / 'venv' / 'Scripts' / 'python.exe'
                if not python.is_file():
                    raise RuntimeError('Slideshow Python environment is missing. See README.md.')
                command = [str(python), str(ROOT / 'render_slide.py'), str(target), title, date]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                        errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode:
                    raise RuntimeError(f'{slide.image}: {result.stderr.strip() or result.stdout.strip()}')
            os.replace(target, output / slide.image)
        completed += 1
        progress(completed, len(slides), slide.image)
    return completed
