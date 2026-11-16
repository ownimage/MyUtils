import tempfile
import json
from PIL import Image
import unittest
from unittest.mock import patch
from pathlib import Path
from threading import Barrier, Event, Lock, get_ident
from slideshow_jobs import Slide, defaults, load_slides, save_slides, render_slides, load_project


class SlideshowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.defaults_patch = patch('template_render.USER_DEFAULT_PATH',Path(self.temporary.name)/'user-default.json')
        self.defaults_patch.start()
        self.addCleanup(self.defaults_patch.stop)
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
            raise RuntimeError('Renderer unavailable')
        with self.assertRaisesRegex(RuntimeError, 'Renderer unavailable'):
            render_slides(self.folder, [Slide('001.jpg')], renderer=renderer)
        self.assertEqual((output / '001.jpg').read_bytes(), b'previous')
        self.assertEqual([p.name for p in output.iterdir()], ['001.jpg'])

    def test_cancel_between_images(self):
        completed = []
        count = render_slides(self.folder, load_slides(self.folder),
            renderer=lambda *args: None, cancelled=lambda: bool(completed),
            progress=lambda *args: completed.append(args))
        self.assertEqual(count, 1)
        # Completion order is deliberately not filename order in parallel mode.
        self.assertEqual(sum((self.folder/'slideshow'/name).exists()
                             for name in ('001.jpg','002.JPG')),1)

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
        self.assertFalse((self.folder/'highlight/slideshow.json').exists())
        saved = json.loads((self.folder/'highlight/template.json').read_text())
        self.assertNotIn('images',saved)
        self.assertEqual((self.folder/'highlight/data.txt').read_bytes(),
                         (self.folder/'slideshow/data.txt').read_bytes())
        self.assertEqual(load_slides(self.folder)[0].title,'Café, Cornwall')

    def test_legacy_csv_import_and_invalid_template_are_distinct(self):
        output = self.folder/'slideshow'
        output.mkdir()
        (output/'data.txt').write_text('Image,Date,Title\n001.jpg,Yesterday,Legacy title\n',encoding='utf-8-sig')
        self.assertEqual(load_slides(self.folder)[0].title,'Legacy title')
        template = self.folder/'highlight/template.json'
        template.write_text('{broken',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Could not load'):
            load_project(self.folder)
        self.assertEqual(load_slides(self.folder)[0].title,'Legacy title')
        self.assertEqual(template.read_text(),'{broken')

    def test_csv_edits_take_priority_over_older_json(self):
        from template_render import default_template
        old = {'version':1,'template':default_template(),
               'images':[{'image':'001.jpg','date':'Old date','title':'Old JSON title'}]}
        legacy = self.folder/'highlight/slideshow.json'
        legacy.write_text(json.dumps(old),encoding='utf-8')
        self.assertEqual(load_slides(self.folder)[0].title,'Old JSON title')
        save_slides(self.folder,load_slides(self.folder))
        data = self.folder/'highlight/data.txt'
        data.write_text('Image,Date,Title\n001.jpg,New date,CSV edited title\n',encoding='utf-8')
        self.assertEqual(load_slides(self.folder)[0].title,'CSV edited title')
        self.assertEqual(load_slides(self.folder)[0].date,'New date')
        self.assertEqual(json.loads(legacy.read_text()),old)
        # Saved template and CSV remain usable even if the abandoned JSON is bad.
        legacy.write_text('{broken',encoding='utf-8')
        self.assertEqual(load_project(self.folder)['template'],default_template())
        self.assertEqual(load_slides(self.folder)[0].title,'CSV edited title')

    def test_csv_quoting_newlines_unicode_and_two_column_rows(self):
        slides = [Slide('001.jpg','Yesterday','Café, Cornwall\nSecond line')]
        save_slides(self.folder,slides)
        self.assertEqual(load_slides(self.folder)[0],slides[0])
        data = self.folder/'highlight/data.txt'
        data.write_text('Image,Date,Title\n001.jpg,Custom date\n',encoding='utf-8-sig')
        self.assertEqual(load_slides(self.folder)[0],Slide('001.jpg','Custom date',''))

    def test_user_default_applies_to_new_events_and_local_template_wins(self):
        from template_render import default_template,save_user_default
        user = default_template()
        user['title']['size_pt'] = 19
        save_user_default(user)
        self.assertEqual(load_project(self.folder)['template'],user)
        event = default_template()
        event['title']['size_pt'] = 21
        save_slides(self.folder,load_slides(self.folder),event)
        user['title']['size_pt'] = 23
        save_user_default(user)
        self.assertEqual(load_project(self.folder)['template'],event)

    def test_render_records_exact_template_snapshot_and_refreshes_it(self):
        from template_render import default_template
        template = default_template()
        template['title']['size_pt'] = 19
        slides = [Slide('001.jpg')]
        render_slides(self.folder,slides,template=template,renderer=lambda *args:None)
        path = self.folder/'slideshow/template.json'
        self.assertEqual(json.loads(path.read_text()),template)
        template['date']['x'] = 100
        render_slides(self.folder,slides,template=template,renderer=lambda *args:None)
        self.assertEqual(json.loads(path.read_text()),template)
        self.assertFalse((self.folder/'highlight/template.json').exists())
        self.assertNotIn('images',json.loads(path.read_text()))

    def test_cancelled_partial_run_keeps_its_template_snapshot(self):
        from template_render import default_template
        template = default_template()
        template['date']['x'] = 90
        completed = []
        count = render_slides(self.folder,load_slides(self.folder),template=template,
            renderer=lambda *args:None,cancelled=lambda:bool(completed),
            progress=lambda *args:completed.append(args))
        self.assertEqual(count,1)
        self.assertEqual(json.loads((self.folder/'slideshow/template.json').read_text()),template)

    def test_snapshot_save_failure_does_not_replace_existing_image(self):
        output = self.folder/'slideshow'
        output.mkdir()
        image = output/'001.jpg'
        image.write_bytes(b'previous slide')
        with patch('slideshow_jobs._atomic_text',side_effect=PermissionError('Read only')):
            with self.assertRaises(PermissionError):
                render_slides(self.folder,[Slide('001.jpg')],renderer=lambda *args:None)
        self.assertEqual(image.read_bytes(),b'previous slide')
        self.assertEqual((self.folder/'highlight/001.jpg').read_bytes(),b'original')

    def _many_slides(self, count):
        slides = []
        for index in range(count):
            name = f'{index+1:03}.jpg'
            (self.folder/'highlight'/name).write_bytes(b'original')
            slides.append(Slide(name))
        return slides

    def test_worker_count_uses_all_logical_cpus_and_available_photos(self):
        from slideshow_jobs import render_worker_count
        with patch('slideshow_jobs.os.cpu_count',return_value=64):
            self.assertEqual(render_worker_count(100),64)
            self.assertEqual(render_worker_count(3),3)
        with patch('slideshow_jobs.os.cpu_count',return_value=None):
            self.assertEqual(render_worker_count(10),1)
        with self.assertRaises(ValueError):
            render_worker_count(10,0)

    def test_multiple_photos_are_rendered_concurrently(self):
        slides = self._many_slides(4)
        barrier = Barrier(4,timeout=5)
        threads = set()
        lock = Lock()
        def render(target,title,date):
            with lock:
                threads.add(get_ident())
            barrier.wait()
            target.write_bytes(b'rendered')
        with patch('slideshow_jobs.os.cpu_count',return_value=4):
            count = render_slides(self.folder,slides,renderer=render)
        self.assertEqual(count,4)
        self.assertEqual(len(threads),4)
        self.assertNotIn(get_ident(),threads)

    def test_parallel_cancel_does_not_publish_inflight_images(self):
        slides = self._many_slides(12)
        barrier = Barrier(4,timeout=5)
        cancelled = Event()
        started = []
        def render(target,title,date):
            started.append(target.name)
            barrier.wait()
            target.write_bytes(b'rendered')
        count = render_slides(self.folder,slides,max_workers=4,renderer=render,
            cancelled=cancelled.is_set,progress=lambda *args:cancelled.set())
        self.assertEqual(count,1)
        self.assertEqual(len(started),4)
        output = self.folder/'slideshow'
        self.assertEqual(len(list(output.glob('*.jpg'))),1)
        self.assertFalse(list(output.glob('.render-*')))
        self.assertTrue(all((self.folder/'highlight'/s.image).read_bytes()==b'original' for s in slides))

    def test_native_workers_reuse_overlays_and_never_render_fonts(self):
        from template_render import render_overlay,render_prepared_file,text_path
        slides = self._many_slides(4)
        for slide in slides:
            Image.new('RGB',(500,300),'red').save(self.folder/'highlight'/slide.image)
        slides[2].title = slides[3].title = 'Another title'
        caller = get_ident()
        font_threads, worker_threads = [],[]
        def font(*args,**kwargs):
            font_threads.append(get_ident())
            return text_path(*args,**kwargs)
        def prepared(*args,**kwargs):
            worker_threads.append(get_ident())
            return render_prepared_file(*args,**kwargs)
        with patch('slideshow_jobs.render_overlay',wraps=render_overlay) as overlay, \
             patch('template_render.text_path',side_effect=font), \
             patch('slideshow_jobs.render_prepared_file',side_effect=prepared):
            self.assertEqual(render_slides(self.folder,slides,max_workers=4),4)
        self.assertEqual(overlay.call_count,2)
        self.assertEqual(set(font_threads),{caller})
        self.assertTrue(worker_threads)
        self.assertNotIn(caller,worker_threads)
        parallel = {s.image:(self.folder/'slideshow'/s.image).read_bytes() for s in slides}
        render_slides(self.folder,slides,max_workers=1)
        self.assertEqual(parallel,{s.image:(self.folder/'slideshow'/s.image).read_bytes() for s in slides})

    def test_evicted_overlays_are_read_from_png_without_rerendering_text(self):
        from template_render import render_overlay
        slides = self._many_slides(11)
        for index,slide in enumerate(slides):
            slide.title = 'Title '+str(index % 10)
        with patch('slideshow_jobs.render_overlay',wraps=render_overlay) as overlay, \
             patch('slideshow_jobs.render_prepared_file'):
            self.assertEqual(render_slides(self.folder,slides,max_workers=2),11)
        self.assertEqual(overlay.call_count,10)

    def test_overlay_is_transparent_outside_text_and_glow(self):
        from template_render import render_overlay,default_template
        overlay = render_overlay('Title','2026 06 15',default_template())
        self.assertTrue(overlay.hasAlphaChannel())
        self.assertEqual(overlay.pixelColor(960,540).alpha(),0)

    def test_parallel_duplicate_destinations_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            render_slides(self.folder,[Slide('001.jpg'),Slide('001.JPG')],renderer=lambda *args:None)

    def test_rejects_image_outside_highlights(self):
        with self.assertRaises(ValueError):
            render_slides(self.folder, [Slide('../outside.jpg')], renderer=lambda *args: None)


if __name__ == '__main__':
    unittest.main()
