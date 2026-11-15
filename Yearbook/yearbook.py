"""Collect slideshow JPGs into a yearbook, with a preview API for the desktop app."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class PlannedFile:
    source: Path
    destination: Path
    reason: str = ''
    size: int = 0
    modified_ns: int = 0

    @property
    def ready(self):
        return not self.reason


@dataclass
class ScanResult:
    directory: Path
    files: list[PlannedFile] = field(default_factory=list)
    slideshows: int = 0
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False

    @property
    def output(self):
        return self.directory / 'yearbook'

    @property
    def ready_count(self):
        return sum(item.ready for item in self.files)


@dataclass
class CopyResult:
    copied: int = 0
    skipped: int = 0
    errors: int = 0
    cancelled: bool = False


def _redirected(path: Path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def scan_directory(directory, *, on_file: Callable | None = None,
                   cancelled: Callable = lambda: False):
    """Preview JPGs in slideshow folders at levels 0..3; create no files."""
    directory = Path(directory).expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise ValueError('Choose a year folder, rather than a file.')
    result = ScanResult(directory)
    destinations = set()

    def visit(folder, level):
        if cancelled():
            result.cancelled = True
            return
        try:
            children = sorted(folder.iterdir(), key=lambda path: path.name.casefold())
            if folder.name.casefold() == 'slideshow':
                result.slideshows += 1
                prefix = folder.parent.name[:8] + '_'
                for source in children:
                    if cancelled():
                        result.cancelled = True
                        return
                    if source.suffix.casefold() != '.jpg' or not source.is_file():
                        continue
                    item = PlannedFile(source, result.output / (prefix + source.name))
                    key = item.destination.name.casefold()
                    try:
                        if _redirected(source):
                            item.reason = 'Linked image; skipped.'
                        elif _redirected(result.output):
                            item.reason = 'The yearbook folder is a link or junction.'
                        elif result.output.exists() and not result.output.is_dir():
                            item.reason = 'A file named yearbook blocks the output folder.'
                        elif key in destinations:
                            item.reason = 'Another slideshow produces the same filename.'
                        elif os.path.lexists(item.destination):
                            item.reason = 'Already exists in yearbook; kept unchanged.'
                        else:
                            stat = source.stat()
                            item.size, item.modified_ns = stat.st_size, stat.st_mtime_ns
                            destinations.add(key)
                    except OSError as error:
                        item.reason = str(error)
                    result.files.append(item)
                    if on_file:
                        on_file(item)
            elif level < 3:
                for child in children:
                    if cancelled():
                        result.cancelled = True
                        return
                    if child == result.output:
                        continue
                    if child.is_dir():
                        if _redirected(child):
                            result.warnings.append(f'Linked folder skipped: {child}')
                        else:
                            visit(child, level + 1)
        except OSError as error:
            if folder == directory:
                raise
            result.warnings.append(f'Could not read {folder}: {error}')

    visit(directory, 0)
    return result


def copy_plan(plan: ScanResult, *, on_file: Callable | None = None,
              on_progress: Callable | None = None, cancelled: Callable = lambda: False):
    """Copy a preview without replacing existing files. Cancellation is between files."""
    if plan.cancelled:
        raise ValueError('Preview was cancelled. Preview again before creating the yearbook.')
    result = CopyResult()
    total = len(plan.files)
    for index, item in enumerate(plan.files):
        if cancelled():
            result.cancelled = True
            break
        status, message = 'Skipped', item.reason
        if not item.ready:
            result.skipped += 1
        else:
            created = False
            try:
                # Recheck the path and source in case either changed after preview.
                if _redirected(plan.output) or plan.output.resolve() != plan.output:
                    raise ValueError('The yearbook output path has changed or is redirected.')
                if item.destination.parent != plan.output:
                    raise ValueError('The destination is outside the yearbook folder.')
                if _redirected(item.source) or item.source.resolve() != item.source:
                    raise ValueError('The source path has changed or is redirected.')
                stat = item.source.stat()
                if (stat.st_size, stat.st_mtime_ns) != (item.size, item.modified_ns):
                    raise ValueError('The source changed since preview. Preview again.')
                plan.output.mkdir(exist_ok=True)
                with item.source.open('rb') as source:
                    # Exclusive creation also protects files added after preview.
                    with item.destination.open('xb') as destination:
                        created = True
                        shutil.copyfileobj(source, destination)
                result.copied += 1
                status, message = 'Copied', str(item.destination)
            except FileExistsError:
                result.skipped += 1
                message = 'Destination now exists; kept unchanged. Preview again.'
            except (OSError, ValueError) as error:
                result.errors += 1
                status, message = 'Error', str(error)
                if created:
                    try:
                        item.destination.unlink()
                    except OSError as cleanup_error:
                        message += f' Could not remove incomplete copy: {cleanup_error}'
        if on_file:
            on_file(index, status, message)
        if on_progress:
            on_progress(index + 1, total)
    return result


# Keep the original command-line functions and replacement behaviour available.
def yearbook(yearbook_dir, dir_name):
    process_dir(yearbook_dir, Path(dir_name), 0)


def process_dir(yearbook_dir, directory, level):
    print(f'Processing {directory}, level={level}')
    if directory.name == 'slideshow':
        process_slideshow(yearbook_dir, directory)
    elif level < 3:
        for subdir in (path for path in directory.iterdir() if path.is_dir()):
            process_dir(yearbook_dir, subdir, level + 1)


def process_slideshow(yearbook_dir, dir_name):
    directory = Path(dir_name)
    print(f'### Processing Slideshow {directory} to {yearbook_dir}')
    prefix = directory.parent.name[:8] + '_'
    print(f'prefix = {prefix}')
    for source in directory.glob('*.jpg'):
        print(f'### ### {source.name}')
        shutil.copyfile(source, Path(yearbook_dir) / (prefix + source.name))


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description='Copy slideshow JPGs into a yearbook folder.')
    parser.add_argument('directory', help='Year folder containing slideshow subfolders')
    args = parser.parse_args(argv)
    directory = Path(args.directory).expanduser().resolve(strict=True)
    output = directory / 'yearbook'
    output.mkdir(exist_ok=True)
    yearbook(output, directory)
    return 0


if __name__ == '__main__':
    sys.exit(main())
