import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yearbook


class YearbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def photo(self, relative, data=b'photo content'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_depth_extensions_and_naming(self):
        first = self.photo('20260615 Holiday/slideshow/001.JPG')
        second = self.photo('Summer/20260801 Trip/slideshow/002.jpg')
        self.photo('Summer/Trip/Day/slideshow/too-deep.jpg')
        self.photo('20260615 Holiday/slideshow/nested/ignored.jpg')
        self.photo('20260615 Holiday/slideshow/ignored.jpeg')
        self.photo('20260615 Holiday/ignored.jpg')
        self.photo('yearbook/slideshow/ignored.jpg')
        plan = yearbook.scan_directory(self.root)
        self.assertEqual(plan.slideshows, 2)
        self.assertEqual(plan.ready_count, 2)
        self.assertEqual({item.source for item in plan.files}, {first, second})
        self.assertEqual({item.destination.name for item in plan.files},
                         {'20260615_001.JPG', '20260801_002.jpg'})

    def test_preview_does_not_create_output_and_copy_keeps_sources(self):
        source = self.photo('20260615 Holiday/slideshow/001.jpg')
        plan = yearbook.scan_directory(self.root)
        self.assertFalse(plan.output.exists())
        result = yearbook.copy_plan(plan)
        self.assertEqual((result.copied, result.skipped, result.errors), (1, 0, 0))
        self.assertEqual(source.read_bytes(), b'photo content')
        self.assertEqual((plan.output / '20260615_001.jpg').read_bytes(), source.read_bytes())
        self.assertEqual(yearbook.scan_directory(self.root).ready_count, 0)

    def test_existing_files_and_colliding_names_are_skipped(self):
        self.photo('20260615 A/slideshow/001.jpg')
        self.photo('20260615 B/slideshow/001.jpg', b'different photo')
        self.photo('20260615 A/slideshow/002.jpg')
        existing = self.photo('yearbook/20260615_002.jpg', b'existing output')
        plan = yearbook.scan_directory(self.root)
        self.assertEqual(plan.ready_count, 1)
        self.assertIn('same filename', plan.files[2].reason)
        result = yearbook.copy_plan(plan)
        self.assertEqual((result.copied, result.skipped), (1, 2))
        self.assertEqual(existing.read_bytes(), b'existing output')
        self.assertEqual((plan.output / '20260615_001.jpg').read_bytes(), b'photo content')

    def test_file_created_after_preview_is_not_replaced(self):
        self.photo('20260615/slideshow/001.jpg')
        plan = yearbook.scan_directory(self.root)
        existing = self.photo('yearbook/20260615_001.jpg', b'new output')
        result = yearbook.copy_plan(plan)
        self.assertEqual((result.copied, result.skipped), (0, 1))
        self.assertEqual(existing.read_bytes(), b'new output')

    def test_changed_source_reports_error_and_continues(self):
        source = self.photo('20260615/slideshow/001.jpg')
        self.photo('20260615/slideshow/002.jpg')
        plan = yearbook.scan_directory(self.root)
        source.write_bytes(b'changed since preview')
        result = yearbook.copy_plan(plan)
        self.assertEqual((result.copied, result.errors), (1, 1))
        self.assertFalse(plan.files[0].destination.exists())
        self.assertTrue(plan.files[1].destination.exists())

    def test_copy_error_removes_partial_output(self):
        self.photo('20260615/slideshow/001.jpg')
        plan = yearbook.scan_directory(self.root)

        def fail_copy(source, destination):
            destination.write(b'partial')
            raise OSError('disk full')

        with patch('yearbook.shutil.copyfileobj', side_effect=fail_copy):
            result = yearbook.copy_plan(plan)
        self.assertEqual(result.errors, 1)
        self.assertFalse(plan.files[0].destination.exists())
        self.assertTrue(plan.files[0].source.exists())

    def test_cancel_copy_between_files(self):
        self.photo('20260615/slideshow/001.jpg')
        self.photo('20260615/slideshow/002.jpg')
        plan = yearbook.scan_directory(self.root)
        completed = []
        result = yearbook.copy_plan(plan, on_file=lambda *args: completed.append(args),
                                    cancelled=lambda: bool(completed))
        self.assertTrue(result.cancelled)
        self.assertEqual(result.copied, 1)
        self.assertTrue(plan.files[0].destination.exists())
        self.assertFalse(plan.files[1].destination.exists())
        self.assertTrue(all(item.source.exists() for item in plan.files))

    def test_cancelled_preview_cannot_be_copied(self):
        self.photo('20260615/slideshow/001.jpg')
        plan = yearbook.scan_directory(self.root, cancelled=lambda: True)
        self.assertTrue(plan.cancelled)
        with self.assertRaisesRegex(ValueError, 'cancelled'):
            yearbook.copy_plan(plan)
        self.assertFalse(plan.output.exists())

    def test_output_blocked_by_file(self):
        self.photo('20260615/slideshow/001.jpg')
        self.photo('yearbook')
        plan = yearbook.scan_directory(self.root)
        self.assertEqual(plan.ready_count, 0)
        self.assertIn('blocks', plan.files[0].reason)

    def test_cli_still_replaces_existing_files(self):
        source = self.photo('20260615/slideshow/001.jpg')
        output = self.photo('yearbook/20260615_001.jpg', b'old')
        result = subprocess.run([sys.executable, str(Path(yearbook.__file__)), str(self.root)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), source.read_bytes())

    def test_import_needs_no_arguments_and_makes_no_files(self):
        result = subprocess.run([sys.executable, '-c', 'import yearbook'],
                                cwd=Path(yearbook.__file__).parent,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
