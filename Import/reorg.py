"""Plan and perform camera imports, shared by the command line and Qt front end."""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import exifread
from PIL import Image


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff', '.webp', '.nef'}


@dataclass(frozen=True)
class PlannedFile:
    source: Path
    destination: Path | None = None
    date: str = ''
    reason: str = ''
    size: int = 0
    modified_ns: int = 0

    @property
    def ready(self) -> bool:
        return self.destination is not None and not self.reason


@dataclass
class ScanResult:
    directory: Path
    files: list[PlannedFile] = field(default_factory=list)
    ignored: int = 0
    cancelled: bool = False

    @property
    def ready_count(self) -> int:
        return sum(item.ready for item in self.files)


@dataclass
class MoveResult:
    moved: int = 0
    skipped: int = 0
    errors: int = 0
    cancelled: bool = False


def get_file_extension(file_path):
    return Path(file_path).suffix


def is_image(file_path):
    return get_file_extension(file_path).lower() in IMAGE_EXTENSIONS


def is_jpg(file_path):
    return get_file_extension(file_path).lower() in {'.jpg', '.jpeg'}


def _parse_date(value) -> str | None:
    if isinstance(value, bytes):
        value = value.decode('ascii', errors='replace')
    try:
        return datetime.strptime(str(value).strip(' \x00'), '%Y:%m:%d %H:%M:%S').strftime('%Y%m%d')
    except (ValueError, TypeError):
        return None


def extract_file_create_date(image_path):
    """Prefer the capture date; never substitute the filesystem timestamp.

    ExifRead reads NEF metadata without decoding RAW pixels. Pillow provides
    a fallback for image formats whose EXIF ExifRead cannot read.
    """
    with open(image_path, 'rb') as image_file:
        try:
            tags = exifread.process_file(image_file, details=False, extract_thumbnail=False)
        except Exception:
            tags = {}
    for name in ('EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime'):
        parsed = _parse_date(tags.get(name))
        if parsed:
            return parsed
    try:
        with Image.open(image_path) as image:
            exif = image.getexif()
            try:
                capture = exif.get_ifd(34665)
            except (KeyError, ValueError, TypeError, OSError):
                capture = {}
            for value in (capture.get(36867), exif.get(36867), capture.get(36868),
                          exif.get(36868), exif.get(306)):
                parsed = _parse_date(value)
                if parsed:
                    return parsed
    except (OSError, ValueError, SyntaxError):
        pass
    return None


def _check_destination(directory: Path, destination: Path) -> None:
    """Reject date/origJPG links and files in place of destination folders."""
    relative = destination.relative_to(directory)
    parent = directory
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError(f'Destination folder is a link or is not a folder: {parent.name}')
        # Also covers Windows junctions that are not reported as symlinks.
        if parent.resolve() != parent:
            raise ValueError(f'Destination folder redirects elsewhere: {parent.name}')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('Destination already exists; original left in place')


def scan_directory(directory, *, on_file: Callable | None = None,
                   on_progress: Callable | None = None,
                   cancelled: Callable[[], bool] = lambda: False) -> ScanResult:
    """Read top-level images and build a preview without changing any files."""
    root = Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f'Not a folder: {root}')
    result = ScanResult(root)
    paths = sorted(root.iterdir(), key=lambda path: path.name.casefold())
    for index, path in enumerate(paths, 1):
        if cancelled():
            result.cancelled = True
            break
        if not is_image(path) or path.is_dir():
            result.ignored += 1
        else:
            try:
                if path.is_symlink():
                    raise ValueError('Symbolic links are skipped')
                stat = path.stat()
                date = extract_file_create_date(path)
                if not date:
                    raise ValueError('No readable EXIF date; file left in place')
                destination = root / date
                if is_jpg(path):
                    destination /= 'origJPG'
                destination /= path.name
                try:
                    _check_destination(root, destination)
                    reason = ''
                except (OSError, ValueError) as error:
                    reason = str(error)
                item = PlannedFile(path, destination, date, reason, stat.st_size, stat.st_mtime_ns)
            except Exception as error:
                item = PlannedFile(path, reason=str(error) or type(error).__name__)
            result.files.append(item)
            if on_file:
                on_file(item)
        if on_progress:
            on_progress(index, len(paths))
    return result


def _move_without_overwrite(source: Path, destination: Path) -> None:
    if os.name == 'nt':
        # Windows rename fails if a destination appears after the preview.
        os.rename(source, destination)
        return
    # POSIX rename replaces existing files. Exclusive creation avoids that.
    created = False
    try:
        with source.open('rb') as original, destination.open('xb') as target:
            created = True
            shutil.copyfileobj(original, target)
            target.flush()
            os.fsync(target.fileno())
        shutil.copystat(source, destination)
        source.unlink()
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def apply_plan(plan: ScanResult, *, on_file: Callable | None = None,
               on_progress: Callable | None = None,
               cancelled: Callable[[], bool] = lambda: False) -> MoveResult:
    """Move exactly the previewed files; recheck safety before each move."""
    if plan.cancelled:
        raise ValueError('The preview was cancelled. Preview the folder again first.')
    result = MoveResult()
    for row, item in enumerate(plan.files):
        if cancelled():
            result.cancelled = True
            break
        status, message = 'Skipped', item.reason
        if not item.ready:
            result.skipped += 1
        else:
            try:
                if item.source.parent != plan.directory or item.source.is_symlink():
                    raise ValueError('Source is no longer a regular file in the import folder')
                stat = item.source.stat()
                if (stat.st_size, stat.st_mtime_ns) != (item.size, item.modified_ns):
                    raise ValueError('File changed since the preview; preview again')
                _check_destination(plan.directory, item.destination)
                item.destination.parent.mkdir(parents=True, exist_ok=True)
                _check_destination(plan.directory, item.destination)
                _move_without_overwrite(item.source, item.destination)
                result.moved += 1
                status, message = 'Moved', str(item.destination.relative_to(plan.directory))
            except FileExistsError:
                result.skipped += 1
                message = 'Destination already exists; original left in place'
            except Exception as error:
                result.errors += 1
                status, message = 'Error', str(error) or type(error).__name__
        if on_file:
            on_file(row, status, message)
        if on_progress:
            on_progress(row + 1, len(plan.files))
    return result


def reorg(directory, *, dry_run=False):
    """Retain the original reorg(directory) entry point and CLI workflow."""
    plan = scan_directory(directory)
    if dry_run:
        for item in plan.files:
            detail = str(item.destination.relative_to(plan.directory)) if item.ready else item.reason
            print(f'{"READY" if item.ready else "SKIP"}  {item.source.name}: {detail}')
        print(f'{plan.ready_count} ready; {len(plan.files) - plan.ready_count} skipped; '
              f'{plan.ignored} other entries ignored. No files moved.')
        return plan
    result = apply_plan(plan, on_file=lambda row, status, message:
                        print(f'{status}: {plan.files[row].source.name} — {message}'))
    print(f'Finished: {result.moved} moved, {result.skipped} skipped, {result.errors} errors.')
    return result


def main():
    parser = argparse.ArgumentParser(description='Organise camera images into YYYYMMDD folders.')
    parser.add_argument('directory', help='Folder containing the imported images')
    parser.add_argument('--dry-run', action='store_true', help='Preview without moving any files')
    args = parser.parse_args()
    try:
        result = reorg(args.directory, dry_run=args.dry_run)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Error: {error}\n')
    return 1 if isinstance(result, MoveResult) and result.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
