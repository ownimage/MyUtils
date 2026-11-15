import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import reorg


def make_image(path, date='2025:01:14 12:34:56', *, original=None, image_format=None):
    exif = Image.Exif()
    if date:
        exif[306] = date
    if original:
        exif[34665] = {36867: original}
    Image.new('RGB', (8, 8), '#507f69').save(
        path, format=image_format or ('TIFF' if path.suffix.lower() in {'.nef', '.tif'} else 'JPEG'),
        exif=exif,
    )


class ReorgTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_preview_does_not_modify_files(self):
        source = self.root / 'photo.JPG'
        make_image(source)
        before = source.read_bytes()
        plan = reorg.scan_directory(self.root)
        self.assertEqual(plan.ready_count, 1)
        self.assertEqual(plan.files[0].destination, self.root / '20250114' / 'origJPG' / source.name)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [source])

    def test_capture_date_precedes_modification_date(self):
        source = self.root / 'original.jpg'
        make_image(source, original='2024:12:25 10:00:00')
        self.assertEqual(reorg.extract_file_create_date(source), '20241225')

    def test_invalid_original_date_falls_back_to_valid_datetime(self):
        source = self.root / 'fallback.jpg'
        make_image(source, original='0000:00:00 00:00:00')
        self.assertEqual(reorg.extract_file_create_date(source), '20250114')

    def test_nef_metadata_without_decoding_raw_pixels(self):
        # NEF uses TIFF EXIF. This synthetic fixture tests metadata parsing,
        # not a particular Nikon camera's RAW pixel format.
        source = self.root / 'metadata.NEF'
        make_image(source)
        self.assertEqual(reorg.extract_file_create_date(source), '20250114')
        self.assertEqual(reorg.scan_directory(self.root).files[0].destination,
                         self.root / '20250114' / source.name)

    def test_move_jpeg_and_nef_preserves_contents(self):
        sources = [self.root / 'photo.JPEG', self.root / 'photo.NEF']
        for source in sources:
            make_image(source)
        plan = reorg.scan_directory(self.root)
        contents = {item.source.name: item.source.read_bytes() for item in plan.files}
        result = reorg.apply_plan(plan)
        self.assertEqual((result.moved, result.skipped, result.errors), (2, 0, 0))
        for item in plan.files:
            self.assertFalse(item.source.exists())
            self.assertEqual(item.destination.read_bytes(), contents[item.source.name])
        self.assertFalse(reorg.scan_directory(self.root).files)

    def test_missing_invalid_and_empty_files_are_skipped(self):
        make_image(self.root / 'undated.jpg', date=None)
        make_image(self.root / 'invalid.jpg', date='2025:99:99 25:00:00')
        (self.root / 'empty.NEF').touch()
        (self.root / 'broken.jpg').write_bytes(b'not a photo')
        plan = reorg.scan_directory(self.root)
        self.assertEqual(len(plan.files), 4)
        self.assertEqual(plan.ready_count, 0)
        self.assertTrue(all(item.reason for item in plan.files))
        self.assertEqual(reorg.apply_plan(plan).skipped, 4)

    def test_other_files_and_subfolders_are_ignored(self):
        (self.root / 'notes.txt').write_text('notes')
        nested = self.root / 'nested'
        nested.mkdir()
        make_image(nested / 'photo.jpg')
        plan = reorg.scan_directory(self.root)
        self.assertEqual(plan.ignored, 2)
        self.assertFalse(plan.files)

    def test_existing_destination_is_never_overwritten(self):
        make_image(self.root / 'photo.jpg')
        destination = self.root / '20250114' / 'origJPG' / 'photo.jpg'
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b'existing file')
        plan = reorg.scan_directory(self.root)
        self.assertEqual(plan.ready_count, 0)
        self.assertIn('already exists', plan.files[0].reason)
        self.assertEqual(reorg.apply_plan(plan).skipped, 1)
        self.assertEqual(destination.read_bytes(), b'existing file')
        self.assertTrue((self.root / 'photo.jpg').exists())

    def test_destination_created_after_preview_is_preserved(self):
        source = self.root / 'photo.jpg'
        make_image(source)
        plan = reorg.scan_directory(self.root)
        destination = plan.files[0].destination
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b'appeared later')
        result = reorg.apply_plan(plan)
        self.assertEqual((result.moved, result.skipped), (0, 1))
        self.assertTrue(source.exists())
        self.assertEqual(destination.read_bytes(), b'appeared later')

    def test_collision_at_move_time_is_preserved(self):
        source = self.root / 'photo.jpg'
        make_image(source)
        plan = reorg.scan_directory(self.root)
        actual_move = reorg._move_without_overwrite

        def racing_move(original, destination):
            destination.write_bytes(b'race winner')
            return actual_move(original, destination)

        with patch('reorg._move_without_overwrite', side_effect=racing_move):
            result = reorg.apply_plan(plan)
        self.assertEqual(result.skipped, 1)
        self.assertTrue(source.exists())
        self.assertEqual(plan.files[0].destination.read_bytes(), b'race winner')

    def test_changed_file_stays_in_place(self):
        source = self.root / 'photo.jpg'
        make_image(source)
        plan = reorg.scan_directory(self.root)
        source.write_bytes(source.read_bytes() + b'changed')
        messages = []
        result = reorg.apply_plan(plan, on_file=lambda *args: messages.append(args))
        self.assertEqual(result.errors, 1)
        self.assertTrue(source.exists())
        self.assertIn('changed', messages[0][2])

    def test_move_failure_does_not_stop_other_files(self):
        for name in ('a.jpg', 'b.jpg'):
            make_image(self.root / name)
        plan = reorg.scan_directory(self.root)
        actual_move = reorg._move_without_overwrite

        def fail_one(source, destination):
            if source.name == 'a.jpg':
                raise PermissionError('File is locked')
            actual_move(source, destination)

        with patch('reorg._move_without_overwrite', side_effect=fail_one):
            result = reorg.apply_plan(plan)
        self.assertEqual((result.moved, result.errors), (1, 1))
        self.assertTrue((self.root / 'a.jpg').exists())

    def test_cancel_import_keeps_remaining_sources(self):
        for name in ('a.jpg', 'b.jpg'):
            make_image(self.root / name)
        plan = reorg.scan_directory(self.root)
        processed = []
        result = reorg.apply_plan(plan, on_file=lambda *args: processed.append(args),
                                  cancelled=lambda: bool(processed))
        self.assertTrue(result.cancelled)
        self.assertEqual(result.moved, 1)
        self.assertFalse((self.root / 'a.jpg').exists())
        self.assertTrue((self.root / 'b.jpg').exists())

    def test_cancelled_scan_cannot_be_applied(self):
        make_image(self.root / 'photo.jpg')
        plan = reorg.scan_directory(self.root, cancelled=lambda: True)
        self.assertTrue(plan.cancelled)
        with self.assertRaises(ValueError):
            reorg.apply_plan(plan)
        self.assertTrue((self.root / 'photo.jpg').exists())

    def test_destination_folder_is_a_file(self):
        make_image(self.root / 'photo.jpg')
        (self.root / '20250114').write_text('not a folder')
        plan = reorg.scan_directory(self.root)
        self.assertEqual(plan.ready_count, 0)
        self.assertIn('not a folder', plan.files[0].reason)

    def test_redirected_folder_is_rejected(self):
        make_image(self.root / 'photo.jpg')
        with tempfile.TemporaryDirectory() as external:
            link = self.root / '20250114'
            if os.name == 'nt':
                # Junctions need no administrator privileges on Windows.
                import _winapi
                _winapi.CreateJunction(external, str(link))
            else:
                link.symlink_to(external, target_is_directory=True)
            try:
                plan = reorg.scan_directory(self.root)
                self.assertEqual(plan.ready_count, 0)
                self.assertEqual(list(Path(external).iterdir()), [])
            finally:
                if os.name == 'nt':
                    link.rmdir()
                else:
                    link.unlink()

    def test_cli_dry_run_preserves_sources(self):
        source = self.root / 'photo.jpg'
        make_image(source)
        output = io.StringIO()
        with redirect_stdout(output):
            reorg.reorg(self.root, dry_run=True)
        self.assertIn('No files moved', output.getvalue())
        self.assertTrue(source.exists())

    def test_invalid_input(self):
        with self.assertRaises(FileNotFoundError):
            reorg.scan_directory(self.root / 'missing')
        file = self.root / 'file.txt'
        file.touch()
        with self.assertRaises(NotADirectoryError):
            reorg.scan_directory(file)


if __name__ == '__main__':
    unittest.main()
