import tempfile
import unittest
from pathlib import Path
from slideshow_jobs import Slide, defaults, load_slides, save_slides, render_slides


class SlideshowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / '20260615 Holiday'
        (self.folder / 'highlight').mkdir(parents=True)
        (self.folder / 'highlight' / '001.jpg').write_bytes(b'original')
        (self.folder / 'highlight' / '002.JPG').write_bytes(b'second')

    def test_override_round_trip_quotes_and_unicode(self):
        slides = [Slide('001.jpg', 'Yesterday', 'Café, Cornwall'), Slide('002.JPG')]
        save_slides(self.folder, slides)
        self.assertEqual(load_slides(self.folder), slides)
        self.assertEqual(defaults(self.folder), ('2026 06 15', 'Holiday'))

    def test_render_restarts_from_originals_and_applies_defaults(self):
        seen = []
        def renderer(target, title, date):
            seen.append((target.read_bytes(), title, date))
            target.write_bytes(b'rendered')
        slides = [Slide('001.jpg')]
        for _ in range(2):
            self.assertEqual(render_slides(self.folder, slides, renderer=renderer), 1)
        self.assertEqual(seen, [(b'original', 'Holiday', '2026 06 15')] * 2)
        self.assertEqual((self.folder / 'highlight/001.jpg').read_bytes(), b'original')
        self.assertEqual((self.folder / 'slideshow/001.jpg').read_bytes(), b'rendered')

    def test_failure_preserves_existing_slide(self):
        output = self.folder / 'slideshow'
        output.mkdir()
        (output / '001.jpg').write_bytes(b'previous')
        def renderer(*args):
            raise RuntimeError('Photoshop unavailable')
        with self.assertRaisesRegex(RuntimeError, 'Photoshop unavailable'):
            render_slides(self.folder, [Slide('001.jpg')], renderer=renderer)
        self.assertEqual((output / '001.jpg').read_bytes(), b'previous')
        self.assertEqual([p.name for p in output.iterdir()], ['001.jpg'])

    def test_cancel_between_images(self):
        completed = []
        count = render_slides(self.folder, load_slides(self.folder),
            renderer=lambda *args: None, cancelled=lambda: bool(completed),
            progress=lambda *args: completed.append(args))
        self.assertEqual(count, 1)
        self.assertFalse((self.folder / 'slideshow/002.JPG').exists())

    def test_rejects_image_outside_highlights(self):
        with self.assertRaises(ValueError):
            render_slides(self.folder, [Slide('../outside.jpg')], renderer=lambda *args: None)


if __name__ == '__main__':
    unittest.main()
