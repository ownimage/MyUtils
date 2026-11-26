import math
import unittest
import bpy
from snake_tape.core import Settings
from snake_tape.geometry import build_tape
from snake_tape.validation import measure
from tests.fixtures import clear,make_rim,make_cylinder


class OneEdgeDimensionsTests(unittest.TestCase):
    def test_finished_depth_accounts_for_bend_material(self):
        settings=Settings(wrap_mode='ONE_EDGE',width_mm=10,wrap_depth_mm=3,fold_radius_mm=.2)
        dimensions=settings.one_edge_dimensions(8)
        self.assertAlmostEqual(dimensions['bend_allowance_mm'],math.pi*.1)
        self.assertAlmostEqual(dimensions['overhang_mm'],3+math.pi*.1)
        self.assertAlmostEqual(dimensions['flat_width_mm'],7-math.pi*.1)
        self.assertAlmostEqual(dimensions['flat_width_mm']+dimensions['overhang_mm'],10)

    def test_invalid_placement_and_dimensions_have_clear_errors(self):
        for settings in (Settings(wrap_mode='BAD'),Settings(wrap_edge='BAD'),
                         Settings(wrap_depth_mm=0)):
            with self.assertRaises(ValueError):settings.validate()
        for width,depth in ((3,4),(20,3),(10,.2)):
            with self.subTest(width=width,depth=depth),self.assertRaisesRegex(ValueError,'width|depth|selected'):
                Settings(wrap_mode='ONE_EDGE',width_mm=width,wrap_depth_mm=depth).one_edge_dimensions(8)


class OneEdgeGeometryTests(unittest.TestCase):
    def setUp(self):
        clear()
        bpy.context.scene.unit_settings.scale_length=1

    def test_unfolded_total_width_and_single_finished_wrap(self):
        source,ids=make_rim()
        before=[tuple(v.co) for v in source.data.vertices]
        settings=Settings(wrap_mode='ONE_EDGE',width_mm=6,wrap_depth_mm=3,mesh_detail='DETAILED')
        settings.stage='EXTENDED'
        flat,_=build_tape(source,ids,settings)
        self.assertAlmostEqual(measure(flat)['bounds_mm'][1],6,delta=.003)
        settings.stage='FOLDED'
        tape,data=build_tape(source,ids,settings)
        stats=measure(tape,source)
        self.assertAlmostEqual(stats['min_z_mm'],-3,delta=.055)
        self.assertLess(stats['bounds_mm'][1],3.2)
        self.assertEqual(data['side_count'],1)
        self.assertEqual(data['flaps'],12)
        self.assertEqual(stats['components'],1)
        self.assertEqual(stats['nonmanifold_edges'],0)
        self.assertEqual(stats['source_intersection_pairs'],0)
        self.assertEqual(stats['self_intersection_pairs'],0)
        self.assertEqual(before,[tuple(v.co) for v in source.data.vertices])
        flat_end=-2+data['flat_width_mm']
        end_points=[(tape.matrix_world@v.co)*1000 for v in tape.data.vertices
                    if abs((tape.matrix_world@v.co).y*1000-flat_end)<.002]
        self.assertTrue(end_points)
        self.assertLess(max(p.z for p in end_points),.115,'The unused edge must lie flat, not form a second raised shoulder')

    def test_edge_choice_stays_physical_when_reversing_overlap_order(self):
        for edge in ('A','B'):
            for reverse in (False,True):
                with self.subTest(edge=edge,reverse=reverse):
                    clear()
                    source,ids=make_cylinder()
                    tape,data=build_tape(source,ids,Settings(wrap_mode='ONE_EDGE',wrap_edge=edge,
                        width_mm=10,wrap_depth_mm=3,reverse=reverse,cut_stop_variation_mm=.48))
                    points=[(tape.matrix_world@v.co)*1000 for v in tape.data.vertices]
                    z=[p.z for p in points]
                    if edge=='A':
                        self.assertGreater(min(z),-3)
                        self.assertGreater(max(z),4)
                    else:
                        self.assertLess(max(z),3)
                        self.assertLess(min(z),-4)
                    stats=measure(tape,source)
                    for key in ('nonmanifold_edges','self_intersection_pairs','source_intersection_pairs','source_penetrating_vertices'):
                        self.assertEqual(stats[key],0,key)
                    self.assertEqual(data['wrapped_edge'],edge)
                    self.assertEqual(data['side_count'],1)

    def test_both_edge_defaults_remain_compatible(self):
        source,ids=make_rim()
        tape,data=build_tape(source,ids,Settings())
        self.assertEqual(data['side_count'],2)
        self.assertLess(measure(tape)['min_z_mm'],-9)
