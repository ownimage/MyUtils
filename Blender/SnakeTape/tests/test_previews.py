import json
from pathlib import Path
import tempfile
import unittest
import struct
import bpy
from tools.gen_previews import write_gallery


class PreviewTests(unittest.TestCase):
    def test_previous_preview_results_cannot_be_overwritten(self):
        from tools.gen_previews import prepare_output
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            sentinel=folder/'index.html'
            sentinel.write_text('previous validated result')
            with self.assertRaisesRegex(FileExistsError,'empty'):
                prepare_output(folder)
            self.assertEqual(sentinel.read_text(),'previous validated result')

    def test_offline_gallery_records_failed_cases_and_escapes_text(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            cases=[{'name':'<Bad rim>','slug':'01-test','status':'FAILED','images':[],
                    'error':'Bad <geometry>','metrics':{'nonmanifold_edges':2}}]
            write_gallery(folder,cases)
            text=(folder/'index.html').read_text(encoding='utf8')
            self.assertIn('&lt;Bad rim&gt;',text)
            self.assertIn('FAILED',text)
            self.assertNotIn('https://',text)
            self.assertEqual(json.loads((folder/'manifest.json').read_text()),cases)

    def test_real_render_pipeline_produces_a_png(self):
        from tests.fixtures import clear,make_rim
        from snake_tape.geometry import build_tape
        from snake_tape.core import Settings
        from tools.gen_previews import setup_render,camera_and_lights,render_view
        clear()
        bpy.context.scene.unit_settings.scale_length=1
        source,ids=make_rim()
        build_tape(source,ids,Settings(stage='BASE'))
        setup_render(64,48)
        camera,centre,span=camera_and_lights(source)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'smoke.png'
            render_view(path,camera,centre,span)
            data=path.read_bytes()
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II',data[16:24]),(64,48))

