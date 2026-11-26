"""Performance budgets and surface fidelity are user-visible requirements."""
from dataclasses import replace
import unittest
from unittest.mock import patch
import bpy
from mathutils.bvhtree import BVHTree
from snake_tape.core import Settings
from snake_tape.geometry import build_tape
from snake_tape.validation import measure
from tests.fixtures import clear,make_rim,make_cylinder


class OptimizationTests(unittest.TestCase):
    def setUp(self):
        clear()
        bpy.context.scene.unit_settings.scale_length=1

    def test_optimized_geometry_reduces_triangles_and_preserves_the_solid(self):
        for kind in ('straight','cylinder'):
            with self.subTest(kind=kind):
                clear()
                source,ids=make_cylinder() if kind=='cylinder' else make_rim()
                settings=Settings(cut_stop_variation_mm=1)
                dense,_=build_tape(source,ids,replace(settings,mesh_detail='DETAILED'))
                lean,data=build_tape(source,ids,settings)
                dg=bpy.context.evaluated_depsgraph_get()
                a=dense.evaluated_get(dg).to_mesh()
                b=lean.evaluated_get(dg).to_mesh()
                try:
                    a.calc_loop_triangles();b.calc_loop_triangles()
                    budget=.65 if kind=='cylinder' else .5
                    self.assertLess(len(b.loop_triangles),len(a.loop_triangles)*budget)
                    self.assertLess(len(b.vertices),len(a.vertices)*budget)
                    tree=BVHTree.FromPolygons([v.co*1000 for v in b.vertices],
                                             [tuple(t.vertices) for t in b.loop_triangles],all_triangles=True)
                    for v in list(a.vertices)[::max(1,len(a.vertices)//200)]:
                        self.assertLessEqual(tree.find_nearest(v.co*1000)[3],settings.mesh_error_mm)
                finally:
                    dense.evaluated_get(dg).to_mesh_clear()
                    lean.evaluated_get(dg).to_mesh_clear()
                stats=measure(lean,source)
                for key in ('nonmanifold_edges','self_intersection_pairs','source_intersection_pairs','source_penetrating_vertices'):
                    self.assertEqual(stats[key],0,key)
                self.assertEqual(stats['components'],1)
                self.assertTrue(lean.data.has_custom_normals)
                self.assertTrue(all(not vertex.groups for vertex in lean.data.vertices),
                                'Temporary simplification weights must not leak into the result')
                for face in lean.data.polygons:
                    for loop in face.loop_indices:
                        self.assertGreaterEqual(lean.data.corner_normals[loop].vector.dot(face.normal),.49,
                                                'Transferred normals must not shade a paper surface like a cut wall')
                self.assertLess(data['triangles_after'],data['triangles_before']*budget)

    def test_paper_bump_has_physical_scale_without_adding_geometry(self):
        source,ids=make_rim()
        a,_=build_tape(source,ids,Settings(paper_bump_mm=0))
        b,_=build_tape(source,ids,Settings(paper_bump_mm=.003))
        self.assertEqual([tuple(v.co) for v in a.data.vertices],[tuple(v.co) for v in b.data.vertices])
        shader=b.data.materials[0].node_tree
        bump=next(n for n in shader.nodes if n.type=='BUMP')
        self.assertAlmostEqual(bump.inputs['Distance'].default_value*1000,.003,places=6)
        self.assertTrue(bump.inputs['Height'].is_linked)
        self.assertTrue(next(n for n in shader.nodes if n.type=='BSDF_PRINCIPLED').inputs['Normal'].is_linked)
        bpy.context.scene.unit_settings.scale_length=.001
        source.scale=(1000,1000,1000)
        bpy.context.view_layer.update()
        scaled,_=build_tape(source,ids,Settings(stage='BASE',paper_bump_mm=.003))
        scaled_bump=next(n for n in scaled.data.materials[0].node_tree.nodes if n.type=='BUMP')
        self.assertAlmostEqual(scaled_bump.inputs['Distance'].default_value,.003,places=6)
        self.assertNotEqual(scaled.data.materials[0],b.data.materials[0])

    def test_new_controls_validate(self):
        for settings in (Settings(mesh_detail='UNKNOWN'),Settings(paper_bump_mm=-.001),
                         Settings(mesh_error_mm=0),Settings(mesh_error_mm=.11)):
            with self.assertRaises(ValueError):
                settings.validate()

    def test_unsafe_reductions_retain_the_original_mesh(self):
        source,ids=make_rim()
        detailed,_=build_tape(source,ids,Settings(mesh_detail='DETAILED'))
        rejected={'components':2}
        with patch('snake_tape.optimization.measure',return_value=rejected):
            tape,data=build_tape(source,ids,Settings())
        self.assertEqual(data['triangles_before'],data['triangles_after'])
        self.assertEqual(data['reduction_percent'],0)
        self.assertEqual([tuple(v.co) for v in detailed.data.vertices],[tuple(v.co) for v in tape.data.vertices])
        self.assertEqual(len(bpy.data.objects),3,'Temporary reduction objects must not be retained')

    def test_full_depth_tape_is_also_reduced(self):
        source,ids=make_rim()
        tape,data=build_tape(source,ids,Settings())
        self.assertLess(data['triangles_after'],data['triangles_before']*.5)
        self.assertEqual(measure(tape,source)['self_intersection_pairs'],0)

    def test_optimization_never_increases_polygons_on_a_quad_loop(self):
        source,ids=make_rim('loop')
        tape,data=build_tape(source,ids,Settings(),diagnostic=True)
        self.assertLessEqual(data['polygons_after'],data['polygons_before'])
        self.assertEqual(measure(tape,source)['self_intersection_pairs'],0)
