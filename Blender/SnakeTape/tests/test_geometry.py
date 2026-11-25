import math
import unittest
import bpy
from mathutils import Matrix
from snake_tape.core import Settings
from snake_tape.geometry import analyze_rim, build_tape, topology_signature
from snake_tape.validation import measure
from tests.fixtures import clear, make_rim, make_cylinder


class GeometryTests(unittest.TestCase):
    def setUp(self):
        clear()
        bpy.context.scene.unit_settings.scale_length = 1

    def test_rim_length_width_and_closure(self):
        for kind in ('straight', 'bend', 'loop'):
            obj, ids = make_rim(kind)
            rim = analyze_rim(obj, ids)
            self.assertEqual(rim.closed, kind == 'loop')
            self.assertGreater(rim.length, 20)
            self.assertAlmostEqual(rim.sample(rim.length*.5)[2], 4, delta=.05)

    def test_final_shell_is_closed_and_has_real_thickness(self):
        obj, ids = make_rim()
        tape, data = build_tape(obj, ids, Settings(stage='BASE'))
        stats = measure(tape, obj)
        self.assertEqual(stats['boundary_edges'], 0)
        self.assertEqual(stats['nonmanifold_edges'], 0)
        self.assertAlmostEqual(stats['bounds_mm'][2], .1, delta=.002)
        self.assertEqual(data['flaps'], 0)

    def test_extended_and_total_width_bounds(self):
        obj, ids = make_rim()
        for settings, expected in ((Settings(stage='EXTENDED'),24),
                                    (Settings(stage='EXTENDED',width_mode='TOTAL',width_mm=20),20)):
            tape, _ = build_tape(obj, ids, settings)
            self.assertAlmostEqual(measure(tape)['bounds_mm'][1], expected, delta=.002)

    def test_source_is_unchanged_and_tape_is_separate(self):
        obj, ids = make_rim()
        before = ([tuple(v.co) for v in obj.data.vertices], topology_signature(obj))
        tape, _ = build_tape(obj, ids, Settings())
        self.assertIsNot(tape.data, obj.data)
        self.assertEqual(before, ([tuple(v.co) for v in obj.data.vertices], topology_signature(obj)))

    def test_seed_reproduces_geometry(self):
        obj, ids = make_rim('bend')
        a, _ = build_tape(obj, ids, Settings(seed=9))
        b, _ = build_tape(obj, ids, Settings(seed=9))
        self.assertEqual([tuple(v.co) for v in a.data.vertices], [tuple(v.co) for v in b.data.vertices])

    def test_fold_reaches_both_sides(self):
        obj, ids = make_rim()
        tape, _ = build_tape(obj, ids, Settings(variation=0,angle_deg=0,wave_strength=0))
        stats = measure(tape, obj)
        self.assertLess(stats['min_z_mm'], -9)
        self.assertLess(stats['bounds_mm'][1], 4.65)
        self.assertEqual(stats['nonmanifold_edges'],0)
        self.assertEqual(stats['nonfinite_vertices'],0)

    def test_connected_sealing_band_survives_cuts(self):
        obj, ids = make_rim()
        tape, _ = build_tape(obj, ids, Settings(stage='CUT'))
        self.assertEqual(measure(tape)['components'],1)
        self.assertEqual(measure(tape)['boundary_edges'],0)

    def test_transform_and_scene_scale(self):
        obj, ids = make_rim()
        obj.scale = (2,3,1)
        bpy.context.view_layer.update()
        rim = analyze_rim(obj, ids)
        self.assertAlmostEqual(rim.length,72,delta=.001)
        self.assertAlmostEqual(rim.sample(10)[2],12,delta=.001)
        tape, _ = build_tape(obj, ids, Settings(stage='BASE'))
        self.assertEqual(tuple(tape.scale),(1,1,1))
        self.assertAlmostEqual(measure(tape)['bounds_mm'][2],.1,delta=.002)
        obj.scale = (1,1,1)
        bpy.context.scene.unit_settings.scale_length = .001
        bpy.context.view_layer.update()
        self.assertAlmostEqual(analyze_rim(obj,ids).length,.036,delta=1e-6)

    def test_invalid_selection_does_not_create_output(self):
        obj, ids = make_rim()
        before = len(bpy.data.objects)
        for invalid in ([], [ids[0],ids[-1]], [9999]):
            with self.assertRaises(ValueError):
                build_tape(obj,invalid,Settings())
        self.assertEqual(len(bpy.data.objects),before)

    def test_closed_loop_and_concave_bend_remain_valid(self):
        for kind in ('bend','s_bend','loop'):
            with self.subTest(kind=kind):
                clear()
                obj, ids = make_rim(kind)
                tape, data = build_tape(obj,ids,Settings(resolution_mm=1))
                stats = measure(tape,obj)
                self.assertEqual(stats['nonmanifold_edges'],0)
                self.assertEqual(stats['components'],1)
                self.assertEqual(stats['nonfinite_vertices'],0)
                self.assertGreater(data['flaps'],10)

    def test_final_volume_has_no_intersections_on_reference_bends(self):
        for kind in ('straight','bend','s_bend','loop'):
            for seed in (1,7,19):
                with self.subTest(kind=kind,seed=seed):
                    clear()
                    obj,ids=make_rim(kind)
                    tape,_=build_tape(obj,ids,Settings(seed=seed))
                    stats=measure(tape,obj)
                    self.assertEqual(stats['self_intersection_pairs'],0)
                    self.assertEqual(stats['source_intersection_pairs'],0)
                    self.assertEqual(stats['source_penetrating_vertices'],0)

    def test_reverse_changes_overlap_order_without_breaking_shell(self):
        obj,ids=make_rim('bend')
        tape,data=build_tape(obj,ids,Settings(reverse=True))
        stats=measure(tape,obj)
        self.assertEqual(stats['self_intersection_pairs'],0)
        self.assertEqual(stats['source_intersection_pairs'],0)
        self.assertEqual(stats['nonmanifold_edges'],0)

    def test_mirrored_scale_is_rejected_with_actionable_message(self):
        obj,ids=make_rim()
        obj.scale.x=-1
        bpy.context.view_layer.update()
        with self.assertRaisesRegex(ValueError,'scale'):
            build_tape(obj,ids,Settings())

    def test_automatic_radius_accepts_narrow_rims(self):
        for kind in ('straight','bend','loop'):
            with self.subTest(kind=kind):
                clear()
                obj,ids=make_rim(kind,width=.3)
                tape,data=build_tape(obj,ids,Settings())
                stats=measure(tape,obj)
                self.assertEqual(stats['components'],1)
                self.assertEqual(stats['nonmanifold_edges'],0)
                self.assertEqual(stats['self_intersection_pairs'],0)
                self.assertEqual(stats['source_intersection_pairs'],0)
                self.assertLess(stats['min_z_mm'],-9)

    def test_unused_radius_cannot_block_intermediate_preview_stages(self):
        for stage in ('BASE','EXTENDED','CUT'):
            with self.subTest(stage=stage):
                clear()
                obj,ids=make_rim()
                tape,_=build_tape(obj,ids,Settings(stage=stage,fold_radius_mm=8))
                self.assertEqual(measure(tape)['nonmanifold_edges'],0)

    def test_auto_radius_uses_physical_width_with_scene_and_object_scale(self):
        obj,ids=make_rim()
        bpy.context.scene.unit_settings.scale_length=.001
        obj.scale=(1000,75,1000)
        bpy.context.view_layer.update()
        tape,data=build_tape(obj,ids,Settings())
        self.assertAlmostEqual(data['min_band_width_mm'],.3,delta=.001)
        self.assertAlmostEqual(data['fold_radius_mm'],.15,delta=.001)
        stats=measure(tape,obj)
        self.assertEqual(stats['self_intersection_pairs'],0)
        self.assertEqual(stats['source_intersection_pairs'],0)

    def test_explicit_radius_is_limited_by_overhang_not_band_width(self):
        obj,ids=make_rim()
        tape,_=build_tape(obj,ids,Settings(fold_radius_mm=2))
        stats=measure(tape,obj)
        self.assertEqual(stats['self_intersection_pairs'],0)
        self.assertEqual(stats['source_intersection_pairs'],0)

    def test_radius_error_describes_actual_dimensions_and_available_material(self):
        obj,ids=make_rim()
        with self.assertRaisesRegex(ValueError,r'(?i)radius.*mm.*overhang.*mm'):
            build_tape(obj,ids,Settings(fold_radius_mm=10))

    def test_cylinder_frames_are_continuous_across_original_face_boundaries(self):
        source,ids=make_cylinder()
        rim=analyze_rim(source,ids)
        for s in rim.distances[:-1]:
            before=rim.sample(s-.00001)[4]
            after=rim.sample(s+.00001)[4]
            self.assertGreater(before.dot(after),.99999)

    def test_cylinder_side_faces_with_reported_scale_and_defaults(self):
        source,ids=make_cylinder()
        before=[tuple(v.co) for v in source.data.vertices]
        tape,data=build_tape(source,ids,Settings())
        stats=measure(tape,source)
        self.assertEqual(stats['self_intersection_pairs'],0)
        self.assertEqual(stats['source_intersection_pairs'],0)
        self.assertEqual(stats['nonmanifold_edges'],0)
        self.assertEqual(stats['components'],1)
        self.assertEqual(before,[tuple(v.co) for v in source.data.vertices])
        self.assertAlmostEqual(data['min_band_width_mm'],8,delta=.001)
        self.assertGreater(stats['bounds_mm'][2],8)

    def test_cylinder_variants_preserve_valid_final_volume(self):
        cases=((16,1,False,False),(64,7,False,False),
               (32,1,True,False),(32,19,False,True))
        for sides,seed,apply_scale,reverse in cases:
            with self.subTest(sides=sides,seed=seed,applied=apply_scale,reverse=reverse):
                clear()
                source,ids=make_cylinder(sides=sides)
                if apply_scale:
                    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
                tape,_=build_tape(source,ids,Settings(seed=seed,reverse=reverse))
                stats=measure(tape,source)
                self.assertEqual(stats['self_intersection_pairs'],0)
                self.assertEqual(stats['source_intersection_pairs'],0)
                self.assertEqual(stats['source_penetrating_vertices'],0)
                self.assertEqual(stats['nonmanifold_edges'],0)


if __name__ == '__main__':
    unittest.main()
