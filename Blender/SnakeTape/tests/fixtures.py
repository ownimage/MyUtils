import math
import bpy
from mathutils import Matrix, Vector


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def make_cylinder(sides=32,scale=(.01,.01,.004)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=1,depth=2)
    obj=bpy.context.object
    obj.scale=scale
    bpy.context.view_layer.update()
    selected=[p.index for p in obj.data.polygons if len(p.vertices)==4]
    for vertex in obj.data.vertices:
        vertex.select=False
    for edge in obj.data.edges:
        edge.select=False
    for polygon in obj.data.polygons:
        polygon.select=polygon.index in selected
    bpy.context.scene.tool_settings.mesh_select_mode=(False,False,True)
    return obj,selected


def make_rim(kind='straight', name='Cardboard', length=36, width=4):
    closed = kind == 'loop'
    if closed:
        points = [Vector((18*math.cos(i*math.tau/48), 18*math.sin(i*math.tau/48), 0)) for i in range(48)]
    elif kind == 'bend':
        points = [Vector((20*math.sin(i*math.pi/32), 20*(1-math.cos(i*math.pi/32)), 0)) for i in range(17)]
    elif kind == 's_bend':
        points = [Vector((i*2, 4*math.sin(i*math.pi/12), 0)) for i in range(25)]
    else:
        points = [Vector((i*length/6, 0, 0)) for i in range(7)]
    n = len(points)
    a, b = [], []
    for i, p in enumerate(points):
        tangent = (points[(i+1) % n] - points[(i-1) % n]) if closed else (points[min(i+1,n-1)]-points[max(i-1,0)])
        tangent.normalize()
        across = Vector((-tangent.y, tangent.x, 0))
        a.append(p-across*width*.5)
        b.append(p+across*width*.5)
    vertices = a+b+[v-Vector((0,0,16)) for v in a+b]
    faces, selected = [], []
    for i in range(n if closed else n-1):
        j = (i+1) % n
        selected.append(len(faces))
        faces.extend([(i,j,n+j,n+i), (j,i,2*n+i,2*n+j),
                      (n+i,n+j,3*n+j,3*n+i), (2*n+i,3*n+i,3*n+j,2*n+j)])
    if not closed:
        faces.extend([(0,n,3*n,2*n), (n-1,3*n-1,4*n-1,2*n-1)])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([v*.001 for v in vertices], [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for vertex in mesh.vertices:
        vertex.select=False
    for edge in mesh.edges:
        edge.select=False
    for p in mesh.polygons:
        p.select = p.index in selected
    bpy.context.scene.tool_settings.mesh_select_mode=(False,False,True)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj, selected
