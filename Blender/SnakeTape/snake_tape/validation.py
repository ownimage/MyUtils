"""Independent measurements on Blender's evaluated final shell."""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def measure(obj,source=None):
    scale=1000*bpy.context.scene.unit_settings.scale_length
    depsgraph=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        origin=obj.matrix_world.translation
        vertices=[(obj.matrix_world@v.co-origin)*scale for v in mesh.vertices]
        counts={}
        parent=list(range(len(vertices)))
        def root(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]]
                i=parent[i]
            return i
        for polygon in mesh.polygons:
            for a,b in polygon.edge_keys:
                key=tuple(sorted((a,b)))
                counts[key]=counts.get(key,0)+1
                parent[root(a)]=root(b)
        bounds=[max(v[i] for v in vertices)-min(v[i] for v in vertices) for i in range(3)]
        stats={'vertices':len(vertices),'faces':len(mesh.polygons),
               'boundary_edges':sum(v==1 for v in counts.values()),
               'nonmanifold_edges':sum(v!=2 for v in counts.values()),
               'components':len({root(i) for i in range(len(vertices))}),
               'nonfinite_vertices':sum(not all(math.isfinite(x) for x in v) for v in vertices),
               'bounds_mm':bounds,'min_z_mm':min(v.z for v in vertices)+origin.z*scale,
               'degenerate_triangles':sum(t.area<1e-16 for t in mesh.loop_triangles)}
        triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
        tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
        stats['self_intersection_pairs']=sum(1 for a,b in tree.overlap(tree)
            if a<b and not set(triangles[a])&set(triangles[b]))
        if source:
            other=source.evaluated_get(depsgraph)
            other_mesh=other.to_mesh()
            try:
                other_mesh.calc_loop_triangles()
                vs=[(other.matrix_world@v.co-origin)*scale for v in other_mesh.vertices]
                ts=[tuple(t.vertices) for t in other_mesh.loop_triangles]
                tree=BVHTree.FromPolygons(vs,ts,all_triangles=True)
                tape_tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
                stats['source_intersection_pairs']=len(tape_tree.overlap(tree))
                distances=[]
                penetrations=[]
                for p in vertices:
                    q,n,_,distance=tree.find_nearest(p)
                    if q is not None:
                        signed=(p-q).dot(n)
                        distances.append(distance)
                        if signed<-.005:
                            penetrations.append(-signed)
                stats['source_penetrating_vertices']=len(penetrations)
                stats['max_source_penetration_mm']=max(penetrations,default=0)
                stats['min_source_distance_mm']=min(distances,default=0)
            finally:
                other.to_mesh_clear()
        return stats
    finally:
        evaluated.to_mesh_clear()
