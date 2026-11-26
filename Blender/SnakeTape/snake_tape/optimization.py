"""Reduce the validated solid, retaining a safe dense result when necessary."""
import math
import bpy
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .validation import measure


def _tree(mesh,scale):
    mesh.calc_loop_triangles()
    vertices=[v.co*scale for v in mesh.vertices]
    triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
    return BVHTree.FromPolygons(vertices,triangles,all_triangles=True),vertices


def _samples(mesh,vertices):
    yield from vertices
    for triangle in mesh.loop_triangles:
        yield sum((vertices[i] for i in triangle.vertices),vertices[0]*0)/3


def _smooth(mesh):
    """Smooth the paper surface while retaining sharp thickness/cut edges."""
    for face in mesh.polygons:
        face.use_smooth=True
    neighbours={}
    for face in mesh.polygons:
        for edge in face.edge_keys:
            neighbours.setdefault(tuple(sorted(edge)),[]).append(face.index)
    for edge in mesh.edges:
        faces=neighbours.get(tuple(sorted(edge.vertices)),[])
        edge.use_edge_sharp=(len(faces)!=2 or mesh.polygons[faces[0]].normal.dot(mesh.polygons[faces[1]].normal)<math.cos(math.radians(45)))
    mesh.update()


def _outline_vertices(mesh):
    collar=mesh.attributes.get('snaketape_protect')
    if collar:
        return {i for i,item in enumerate(collar.data) if item.value}
    neighbours={}
    for face in mesh.polygons:
        for edge in face.edge_keys:
            neighbours.setdefault(tuple(sorted(edge)),[]).append(face.index)
    protected=set()
    for edge,faces in neighbours.items():
        if len(faces)!=2 or mesh.polygons[faces[0]].normal.dot(mesh.polygons[faces[1]].normal)<math.cos(math.radians(55)):
            protected.update(edge)
    return protected


def _transfer_normals(dense,low,tree,scale):
    """Carry smooth high-resolution shading in the reduced mesh's corner normals."""
    _smooth(dense)
    dense.calc_loop_triangles()
    _smooth(low)
    fallback=[n.vector.copy() for n in low.corner_normals]
    normals=[]
    corner_normals=dense.corner_normals
    for face in low.polygons:
        for loop_index in face.loop_indices:
            vertex=low.vertices[low.loops[loop_index].vertex_index]
            query=vertex.co.lerp(face.center,.0001)*scale
            point,_,index,_=tree.find_nearest(query)
            triangle=dense.loop_triangles[index]
            a,b,c=(dense.vertices[i].co*scale for i in triangle.vertices)
            na,nb,nc=(corner_normals[i].vector for i in triangle.loops)
            normal=barycentric_transform(point,a,b,c,na,nb,nc).normalized()
            # At a slit or overlap, the closest high-resolution triangle can
            # belong to a perpendicular wall or another tape layer. Preserve
            # the low mesh's own smooth normal when that correspondence is wrong.
            if normal.dot(fallback[loop_index])<math.cos(math.radians(30)):
                normal=fallback[loop_index]
            if normal.dot(face.normal)<.5:
                normal=face.normal.copy()
            normals.append(normal)
        face.use_smooth=True
    low.normals_split_custom_set(normals)


def finish_mesh(obj,source,settings,unit_scale):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    dense=bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph),depsgraph=depsgraph,preserve_all_data_layers=True)
    dense.calc_loop_triangles()
    before=len(dense.loop_triangles)
    result={'triangles_before':before,'triangles_after':before,'polygons_before':len(dense.polygons),
            'polygons_after':len(dense.polygons),'reduction_percent':0.0,'shape_error_mm':0.0}
    if settings.mesh_detail=='DETAILED' or settings.stage!='FOLDED':
        bpy.data.meshes.remove(dense)
        return result
    tree,vertices=_tree(dense,unit_scale)
    original_data=obj.data
    candidate=None
    # Freeze the renderer's exact diagonals before collapse. Decimate's implicit
    # quad triangulation can otherwise change a twisted sheet before reducing it.
    trial_mesh=bpy.data.meshes.new('SnakeTape reduction input')
    trial_mesh.from_pydata([v.co for v in dense.vertices],[],[tuple(t.vertices) for t in dense.loop_triangles])
    for material in dense.materials:
        trial_mesh.materials.append(material)
    for face,triangle in zip(trial_mesh.polygons,dense.loop_triangles):
        face.material_index=dense.polygons[triangle.polygon_index].material_index
    for name in ('snaketape_flap','snaketape_surface'):
        original=dense.attributes.get(name)
        if original:
            values=trial_mesh.attributes.new(name,'INT','FACE')
            for item,triangle in zip(values.data,dense.loop_triangles):
                item.value=original.data[triangle.polygon_index].value
    trial_mesh.update()
    trial=bpy.data.objects.new('SnakeTape reduction trial',trial_mesh)
    bpy.context.collection.objects.link(trial)
    trial.matrix_world=obj.matrix_world.copy()
    decimate=trial.modifiers.new('SnakeTape reduction','DECIMATE')
    decimate.use_collapse_triangulate=True
    protected=_outline_vertices(dense)
    group=trial.vertex_groups.new(name='SnakeTape outline constraints')
    group.add(list(range(len(trial_mesh.vertices))),1,'REPLACE')
    if protected:
        group.add(list(protected),0,'REPLACE')
    decimate.vertex_group=group.name
    decimate.vertex_group_factor=1
    try:
        for ratio in (.25,.35,.45,.6,.75,.9):
            decimate.ratio=ratio
            bpy.context.view_layer.update()
            candidate=bpy.data.meshes.new_from_object(trial.evaluated_get(depsgraph),depsgraph=depsgraph,preserve_all_data_layers=True)
            # A mild reduction of an all-quad mesh can otherwise increase the
            # visible polygon count by publishing triangles. Never do that.
            if len(candidate.polygons)>=result['polygons_before']:
                bpy.data.meshes.remove(candidate)
                candidate=None
                continue
            low_tree,low_vertices=_tree(candidate,unit_scale)
            error=0.0
            # Sample actual triangles: a nonplanar quad's vertex average can lie
            # off its surface even before reduction. The separate
            # full triangle-intersection check rejects newly crossing thin layers.
            for points,target in ((_samples(dense,vertices),low_tree),(_samples(candidate,low_vertices),tree)):
                for point in points:
                    error=max(error,target.find_nearest(point)[3])
                    if error>settings.mesh_error_mm:
                        break
                if error>settings.mesh_error_mm:
                    break
            if error<=settings.mesh_error_mm:
                check=bpy.data.objects.new('SnakeTape reduction check',candidate)
                bpy.context.collection.objects.link(check)
                check.vertex_groups.new(name=group.name)
                check.matrix_world=obj.matrix_world.copy()
                try:
                    bpy.context.view_layer.update()
                    stats=measure(check,source)
                finally:
                    check.vertex_groups.clear()
                    bpy.data.objects.remove(check,do_unlink=True)
                if stats['components']==1 and not any(stats[k] for k in (
                        'nonmanifold_edges','nonfinite_vertices','degenerate_triangles',
                        'self_intersection_pairs','source_intersection_pairs','source_penetrating_vertices')):
                    _transfer_normals(dense,candidate,tree,unit_scale)
                    result.update(triangles_after=len(candidate.loop_triangles),polygons_after=len(candidate.polygons),
                                  reduction_percent=100*(1-len(candidate.loop_triangles)/before),shape_error_mm=error)
                    # Publish only the checked mesh; failed candidates leave the
                    # original mesh/modifiers available for the next attempt.
                    obj.modifiers.clear()
                    obj.data=candidate
                    if 'snaketape_shell_vertices' in obj:
                        del obj['snaketape_shell_vertices']
                    if original_data.users==0:
                        bpy.data.meshes.remove(original_data)
                    candidate=None
                    return result
            bpy.data.meshes.remove(candidate)
            candidate=None
    finally:
        bpy.data.objects.remove(trial,do_unlink=True)
        bpy.data.meshes.remove(trial_mesh)
        if candidate is not None and candidate.users==0:
            bpy.data.meshes.remove(candidate)
        bpy.data.meshes.remove(dense)
    return result
