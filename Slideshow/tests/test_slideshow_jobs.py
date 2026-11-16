import tempfile
import json
from PIL import Image
import unittest
from unittest.mock import patch
from pathlib import Path
from slideshow_jobs import Slide, defaults, load_slides, save_slides, render_slides, load_project


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

    def test_native_render_writes_size_dpi_and_preserves_original(self):
        source = self.folder/'highlight/001.jpg'
        Image.new('RGB',(600,300),'red').save(source)
        original = source.read_bytes()
        self.assertEqual(render_slides(self.folder,[Slide('001.jpg')]),1)
        self.assertEqual(source.read_bytes(),original)
        with Image.open(self.folder/'slideshow/001.jpg') as image:
            self.assertEqual(image.size,(1920,1080))
            self.assertAlmostEqual(image.info['dpi'][0],300,delta=1)
            self.assertGreater(image.getpixel((960,540))[0],240)

    def test_highlight_project_persists_template_and_unicode(self):
        from template_render import default_template
        template = default_template()
        template['title']['size_pt'] = 20
        save_slides(self.folder,[Slide('001.jpg','Yesterday','Café, Cornwall')],template)
        project = load_project(self.folder)
        self.assertEqual(project['template']['title']['size_pt'],20)
        self.assertEqual(project['images'][0]['title'],'Café, Cornwall')
        self.assertEqual(load_slides(self.folder)[0].title,'Café, Cornwall')

    def test_legacy_csv_import_and_invalid_project_are_distinct(self):
        output = self.folder/'slideshow'
        output.mkdir()
        (output/'data.txt').write_text('Image,Date,Title\n001.jpg,Yesterday,Legacy title\n',encoding='utf-8-sig')
        self.assertEqual(load_slides(self.folder)[0].title,'Legacy title')
        project = self.folder/'highlight/slideshow.json'
        project.write_text('{broken',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Could not load'):
            load_slides(self.folder)
        self.assertEqual(project.read_text(),'{broken')

    def test_rejects_image_outside_highlights(self):
        with self.assertRaises(ValueError):
            render_slides(self.folder, [Slide('../outside.jpg')], renderer=lambda *args: None)


if __name__ == '__main__':
    unittest.main()
