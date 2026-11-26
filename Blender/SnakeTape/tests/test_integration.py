import json
import os
from pathlib import Path
import tempfile
import unittest
import bpy
import snake_tape
from snake_tape.geometry import topology_signature
from tests.fixtures import clear,make_rim


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snake_tape.register()

    @classmethod
    def tearDownClass(cls):
        snake_tape.unregister()

    def setUp(self):
        if bpy.context.object and bpy.context.object.mode!='OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        clear()
        bpy.context.scene.unit_settings.scale_length=1
        from snake_tape.core import Settings
        from snake_tape.ui import copy_settings
        copy_settings(bpy.context.scene.snaketape_options,Settings())

    def create(self):
        source,ids=make_rim('bend')
        bpy.ops.object.mode_set(mode='EDIT')
        self.assertEqual(bpy.ops.mesh.snaketape_create(),{'FINISHED'})
        return source,bpy.context.object

    def test_create_update_and_source_reference(self):
        source,tape=self.create()
        self.assertEqual(tape.snaketape_source,source)
        tape.snaketape_options.width_mm=7
        count=len(bpy.data.objects)
        self.assertEqual(bpy.ops.mesh.snaketape_update(),{'FINISHED'})
        new=bpy.context.object
        self.assertEqual(len(bpy.data.objects),count)
        self.assertEqual(json.loads(new['snaketape_settings'])['width_mm'],7)

    def test_invalid_update_preserves_previous_geometry(self):
        source,tape=self.create()
        before=[tuple(v.co) for v in tape.data.vertices]
        tape.snaketape_options.width_mode='TOTAL'
        tape.snaketape_options.width_mm=1
        try:
            result=bpy.ops.mesh.snaketape_update()
            self.assertEqual(result,{'CANCELLED'})
        except RuntimeError:
            pass  # Blender raises when an operator reports an ERROR.
        self.assertIn(tape.name,bpy.data.objects)
        self.assertEqual(before,[tuple(v.co) for v in tape.data.vertices])

    def test_stale_topology_is_rejected(self):
        source,tape=self.create()
        source.data.vertices.add(1)
        self.assertNotEqual(topology_signature(source),tape['snaketape_topology'])
        with self.assertRaisesRegex(RuntimeError,'topology'):
            bpy.ops.mesh.snaketape_update()

    def test_save_reload_preserves_settings_and_pointer(self):
        bpy.context.scene.snaketape_options.cut_stop_mm=.5
        bpy.context.scene.snaketape_options.cut_stop_variation_mm=.5
        bpy.context.scene.snaketape_options.mesh_error_mm=.015
        bpy.context.scene.snaketape_options.paper_bump_mm=.005
        source,tape=self.create()
        source.name='Renamed cardboard'
        tape.snaketape_options.seed=37
        tape_name=tape.name
        with tempfile.TemporaryDirectory(prefix='SnakeTape-test-') as temp:
            path=str(Path(temp)/'roundtrip.blend')
            bpy.ops.wm.save_as_mainfile(filepath=path)
            bpy.ops.wm.open_mainfile(filepath=path)
            loaded=bpy.data.objects[tape_name]
            self.assertEqual(loaded.snaketape_options.seed,37)
            self.assertAlmostEqual(loaded.snaketape_options.cut_stop_mm,.5)
            self.assertAlmostEqual(loaded.snaketape_options.cut_stop_variation_mm,.5)
            self.assertEqual(loaded.snaketape_options.mesh_detail,'OPTIMIZED')
            self.assertAlmostEqual(loaded.snaketape_options.mesh_error_mm,.015)
            self.assertAlmostEqual(loaded.snaketape_options.paper_bump_mm,.005)
            self.assertTrue(loaded.data.has_custom_normals)
            self.assertEqual(loaded.snaketape_source.name,'Renamed cardboard')
            self.assertEqual(bpy.ops.mesh.snaketape_update(),{'FINISHED'})
            settings=json.loads(bpy.context.object['snaketape_settings'])
            self.assertEqual(settings['cut_stop_mm'],.5)
            self.assertEqual(settings['cut_stop_variation_mm'],.5)

    def test_create_runs_all_four_operations_even_with_saved_preview_stage(self):
        from snake_tape.validation import measure
        for stage in ('BASE','EXTENDED','CUT'):
            with self.subTest(stage=stage):
                clear()
                source,ids=make_rim()
                bpy.context.scene.snaketape_options.stage=stage
                bpy.ops.object.mode_set(mode='EDIT')
                self.assertEqual(bpy.ops.mesh.snaketape_create(),{'FINISHED'})
                tape=bpy.context.object
                self.assertLess(measure(tape)['min_z_mm'],-9)
                self.assertGreater(json.loads(tape['snaketape_metrics'])['flaps'],0)
                self.assertEqual(json.loads(tape['snaketape_settings'])['stage'],'FOLDED')

    def test_update_always_rebuilds_the_complete_tape(self):
        from snake_tape.validation import measure
        source,tape=self.create()
        tape.snaketape_options.stage='BASE'
        self.assertEqual(bpy.ops.mesh.snaketape_update(),{'FINISHED'})
        self.assertLess(measure(bpy.context.object)['min_z_mm'],-9)
        self.assertEqual(bpy.context.object.snaketape_options.stage,'FOLDED')

