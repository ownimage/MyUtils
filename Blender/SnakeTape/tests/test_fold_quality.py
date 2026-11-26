"""Geometric fold quality, beyond closed-shell and intersection checks."""
import math
import unittest
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
from snake_tape.core import Settings
from snake_tape.geometry import build_tape
from tests.fixtures import clear,make_cylinder


class FoldQualityTests(unittest.TestCase):
    def setUp(self):
        clear()
        bpy.context.scene.unit_settings.scale_length=1

    def test_short_cut_shoulders_do_not_form_spurious_crosswise_creases(self):
        self.check_shoulder('DETAILED',1)

    def test_reported_optimized_depth_variation_keeps_a_smooth_shoulder(self):
        self.check_shoulder('OPTIMIZED',.48)

    def test_optimization_preserves_cut_tips_and_shoulders(self):
        source,ids=make_cylinder()
        settings=Settings(cut_stop_variation_mm=.48,mesh_detail='DETAILED')
        detailed,_=build_tape(source,ids,settings)
        mesh=detailed.data
        skin=mesh.attributes['snaketape_surface'].data
        sheet=set();rim=set()
        for face in mesh.polygons:
            (sheet if skin[face.index].value else rim).update(face.vertices)
        outline=sheet&rim
        self.assertGreater(len(outline),100)
        settings.mesh_detail='OPTIMIZED'
        tape,data=build_tape(source,ids,settings)
        tree=KDTree(len(tape.data.vertices))
        for vertex in tape.data.vertices:
            tree.insert(vertex.co*1000,vertex.index)
        tree.balance()
        for i in outline:
            p=(detailed.matrix_world@mesh.vertices[i].co)*1000
            if math.hypot(p.x,p.y)<9.8:
                continue
            self.assertLess(tree.find(mesh.vertices[i].co*1000)[2],.0005,
                            'Reduction must keep slit tips and borders in place')
        self.assertLess(data['polygons_after'],data['polygons_before'])

    def check_shoulder(self,mode,variation):
        source,ids=make_cylinder()
        tape,data=build_tape(source,ids,Settings(cut_stop_variation_mm=variation,mesh_detail=mode))
        mesh=tape.data
        owners=mesh.attributes['snaketape_flap'].data
        skin=mesh.attributes['snaketape_surface'].data
        checked=0
        worst=1
        outer_radius=data['fold_radius_mm']+.05
        for face in mesh.polygons:
            if owners[face.index].value<0 or skin[face.index].value!=1:
                continue
            points=[(tape.matrix_world@mesh.vertices[i].co)*1000 for i in face.vertices]
            heights=[abs(p.z)-4 for p in points]
            if min(heights)<.03 or max(heights)>.245 or min(math.hypot(p.x,p.y) for p in points)<9.99:
                continue
            normals=[]
            for p,height in zip(points,heights):
                theta=math.asin(max(0,min(1,height/outer_radius)))
                radial=Vector((p.x,p.y,0)).normalized()
                normals.append(radial*math.cos(theta)+Vector((0,0,1 if p.z>0 else -1))*math.sin(theta))
            expected=sum(normals,Vector()).normalized()
            worst=min(worst,face.normal.dot(expected))
            checked+=1
        self.assertGreater(checked,100)
        self.assertGreater(worst,math.cos(math.radians(30)),
                           'The quarter-fold skin must follow the smooth shoulder, not acquire a crosswise tear-like crease')
