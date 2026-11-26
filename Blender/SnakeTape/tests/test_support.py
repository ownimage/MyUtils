import json
from pathlib import Path
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
import bpy
import snake_tape
from tests.fixtures import clear,make_cylinder


class SupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):snake_tape.register()
    @classmethod
    def tearDownClass(cls):snake_tape.unregister()
    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        clear()
        bpy.context.scene.unit_settings.scale_length=1
        from snake_tape.ui import copy_settings
        from snake_tape.core import Settings
        copy_settings(bpy.context.scene.snaketape_options,Settings())

    def test_clipboard_report_includes_every_setting_and_source_context(self):
        from dataclasses import fields
        from snake_tape.core import Settings
        from snake_tape.support import copy_support_settings
        source,ids=make_cylinder()
        bpy.context.scene.snaketape_options.wrap_mode='ONE_EDGE'
        bpy.context.scene.snaketape_options.wrap_edge='B'
        bpy.context.scene.snaketape_options.wrap_depth_mm=3
        bpy.ops.object.mode_set(mode='EDIT')
        wm=SimpleNamespace(clipboard='original')
        context=SimpleNamespace(object=source,scene=bpy.context.scene,window_manager=wm)
        copy_support_settings(context)
        report=json.loads(wm.clipboard)
        self.assertEqual(set(report['settings']),{f.name for f in fields(Settings)})
        self.assertEqual(report['settings']['wrap_edge'],'B')
        self.assertEqual(report['source']['face_indices'],ids)
        self.assertEqual(report['source']['name'],source.name)
        self.assertAlmostEqual(report['source']['scale'][2],.004)
        self.assertEqual(report['blender_version'],'4.4.3')
        manifest=Path(__file__).resolve().parents[1]/'snake_tape/blender_manifest.toml'
        self.assertEqual(report['addon_version'],tomllib.loads(manifest.read_text(encoding='utf8'))['version'])
        self.assertEqual(source.mode,'EDIT')

    def test_swap_updates_tape_and_report_tracks_pending_edits(self):
        from snake_tape.support import copy_support_settings
        source,ids=make_cylinder()
        options=bpy.context.scene.snaketape_options
        options.wrap_mode='ONE_EDGE'
        options.width_mm=10
        options.wrap_depth_mm=3
        bpy.ops.object.mode_set(mode='EDIT')
        self.assertEqual(bpy.ops.mesh.snaketape_create(),{'FINISHED'})
        count=len(bpy.data.objects)
        self.assertEqual(bpy.ops.mesh.snaketape_swap_edge(),{'FINISHED'})
        tape=bpy.context.object
        self.assertEqual(tape.snaketape_options.wrap_edge,'B')
        self.assertEqual(len(bpy.data.objects),count)
        self.assertEqual(tape.snaketape_source,source)
        self.assertEqual(json.loads(tape['snaketape_metrics'])['wrapped_edge'],'B')
        tape.snaketape_options.wrap_depth_mm=3.5
        wm=SimpleNamespace(clipboard='')
        copy_support_settings(SimpleNamespace(object=tape,scene=bpy.context.scene,window_manager=wm))
        report=json.loads(wm.clipboard)
        self.assertTrue(report['settings_changed_since_build'])
        self.assertEqual(report['settings']['wrap_depth_mm'],3.5)
        self.assertEqual(report['last_generated_settings']['wrap_depth_mm'],3)
        self.assertEqual(report['metrics']['wrapped_edge'],'B')

    def test_swap_failure_retains_original_tape_and_edge(self):
        from unittest.mock import patch
        from snake_tape.ui import swap_edge
        source,ids=make_cylinder()
        options=bpy.context.scene.snaketape_options
        options.wrap_mode='ONE_EDGE'
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.snaketape_create()
        tape=bpy.context.object
        with patch('snake_tape.ui.generate',side_effect=ValueError('cannot wrap')):
            with self.assertRaises(ValueError):swap_edge(bpy.context)
        self.assertEqual(tape.snaketape_options.wrap_edge,'A')
        self.assertIn(tape.name,bpy.data.objects)

    def test_one_edge_settings_and_swap_survive_save_reload(self):
        source,ids=make_cylinder()
        options=bpy.context.scene.snaketape_options
        options.wrap_mode='ONE_EDGE'
        options.wrap_edge='B'
        options.wrap_depth_mm=3.5
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.snaketape_create()
        name=bpy.context.object.name
        with tempfile.TemporaryDirectory(prefix='SnakeTape-one-edge-') as temp:
            path=str(Path(temp)/'one-edge.blend')
            bpy.ops.wm.save_as_mainfile(filepath=path)
            bpy.ops.wm.open_mainfile(filepath=path)
            tape=bpy.data.objects[name]
            self.assertEqual(tape.snaketape_options.wrap_mode,'ONE_EDGE')
            self.assertEqual(tape.snaketape_options.wrap_edge,'B')
            self.assertEqual(tape.snaketape_options.wrap_depth_mm,3.5)
            self.assertEqual(bpy.ops.mesh.snaketape_swap_edge(),{'FINISHED'})
            self.assertEqual(bpy.context.object.snaketape_options.wrap_edge,'A')

    def test_copy_settings_without_active_object_uses_scene_values(self):
        from snake_tape.support import copy_support_settings
        wm=SimpleNamespace(clipboard='')
        copy_support_settings(SimpleNamespace(object=None,scene=bpy.context.scene,window_manager=wm))
        report=json.loads(wm.clipboard)
        self.assertIsNone(report['source'])
        self.assertIsNone(report['tape'])
        self.assertEqual(report['settings']['wrap_mode'],'BOTH')
