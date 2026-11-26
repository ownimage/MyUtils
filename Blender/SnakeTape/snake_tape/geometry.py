"""Quad-rim analysis and staged, finite-thickness tape generation.

All solver coordinates are millimetres relative to a nearby reference origin.
The source is read only; generated meshes have unit object scale.
"""
import bisect
from dataclasses import asdict,replace
import hashlib
import json
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .core import cuts


def topology_signature(obj):
    topology = [tuple(p.vertices) for p in obj.data.polygons]
    return hashlib.sha256(repr((len(obj.data.vertices),topology)).encode()).hexdigest()


class Rim:
    def __init__(self, rails, closed, normals):
        self.rails = rails
        self.closed = closed
        self.distances = [0.0]
        self.centres = [(a+b)*.5 for a,b in rails]
        for a,b in zip(self.centres,self.centres[1:]):
            self.distances.append(self.distances[-1]+(b-a).length)
        self.length = self.distances[-1]
        if self.length < 1e-6:
            raise ValueError('The rim has zero length')
        self.normals = normals
        segment_tangents=[(b-a).normalized() for a,b in zip(self.centres,self.centres[1:])]
        self.tangents=[]
        for i in range(len(self.centres)):
            if closed:
                j=i%len(segment_tangents)
                tangent=segment_tangents[j-1]+segment_tangents[j]
            elif i==0:
                tangent=segment_tangents[0].copy()
            elif i==len(self.centres)-1:
                tangent=segment_tangents[-1].copy()
            else:
                tangent=segment_tangents[i-1]+segment_tangents[i]
            if tangent.length<1e-8:
                raise ValueError('The rim doubles back on itself')
            self.tangents.append(tangent.normalized())

    def sample(self, distance):
        s = distance % self.length if self.closed else max(0,min(distance,self.length))
        i = min(len(self.distances)-2,max(0,bisect.bisect_right(self.distances,s)-1))
        f = (s-self.distances[i])/max(1e-9,self.distances[i+1]-self.distances[i])
        a = self.rails[i][0].lerp(self.rails[i+1][0],f)
        b = self.rails[i][1].lerp(self.rails[i+1][1],f)
        across = (b-a).normalized()
        tangent = self.tangents[i].lerp(self.tangents[i+1],f).normalized()
        normal = tangent.cross(across).normalized()
        if normal.dot(self.normals[i]) < 0:
            normal.negate()
        tangent = across.cross(normal).normalized()
        return a,b,(b-a).length,tangent,normal


def analyze_rim(obj, face_indices, reverse=False):
    if obj is None or obj.type != 'MESH':
        raise ValueError('Select a mesh object and a connected row of rim faces')
    if obj.mode == 'EDIT':
        obj.update_from_editmode()
    if obj.matrix_world.determinant()<=0:
        raise ValueError('Apply mirrored/zero scale and recalculate outward normals before selecting the rim')
    ids = sorted(set(face_indices))
    mesh = obj.data
    if not ids or ids[0] < 0 or ids[-1] >= len(mesh.polygons):
        raise ValueError('Select valid connected rim faces')
    if any(len(mesh.polygons[i].vertices) != 4 for i in ids):
        raise ValueError('The rim must be a single row of quad faces; dissolve triangulation first')
    scale = 1000*bpy.context.scene.unit_settings.scale_length
    if scale <= 0:
        raise ValueError('Scene scale must be positive')
    origin = obj.matrix_world @ mesh.vertices[mesh.polygons[ids[0]].vertices[0]].co
    coords = [(obj.matrix_world@v.co-origin)*scale for v in mesh.vertices]
    edges_by_face = {i:{tuple(sorted(e)) for e in mesh.polygons[i].edge_keys} for i in ids}
    edge_faces = {}
    for i,edges in edges_by_face.items():
        for edge in edges:
            edge_faces.setdefault(edge,[]).append(i)
    adjacency = {i:[] for i in ids}
    shared = {}
    for edge, fs in edge_faces.items():
        if len(fs) > 2:
            raise ValueError('Non-manifold selection')
        if len(fs) == 2:
            a,b = fs
            adjacency[a].append(b)
            adjacency[b].append(a)
            shared[frozenset(fs)] = edge
    if any(len(v)>2 for v in adjacency.values()):
        raise ValueError('The selected faces branch; select one row of rim quads')
    ends = [i for i in ids if len(adjacency[i]) == 1]
    closed = len(ids)>2 and not ends
    if len(ids)>1 and not closed and len(ends)!=2:
        raise ValueError('The selected faces must form one connected rim')
    order, previous, current = [],None,(min(ends) if ends else ids[0])
    while current not in order:
        order.append(current)
        following = [x for x in adjacency[current] if x != previous]
        if not following:
            break
        previous,current = current,min(following)
    if len(order)!=len(ids):
        raise ValueError('The selection contains disconnected faces')
    if reverse:
        order.reverse()
    def opposite(face, edge):
        options = [e for e in edges_by_face[face] if not set(e)&set(edge)]
        if len(options)!=1:
            raise ValueError('Rim quads must connect through opposite edges')
        return options[0]
    if len(order)==1:
        edge = min(edges_by_face[order[0]],key=lambda e:(coords[e[1]]-coords[e[0]]).length)
        sections = [edge,opposite(order[0],edge)]
    elif closed:
        sections = [shared[frozenset((order[-1],order[0]))]]
        sections += [shared[frozenset((a,b))] for a,b in zip(order,order[1:])]
        sections += [sections[0]]
    else:
        sections = [opposite(order[0],shared[frozenset(order[:2])])]
        sections += [shared[frozenset((a,b))] for a,b in zip(order,order[1:])]
        sections += [opposite(order[-1],sections[-1])]
    for i,face in enumerate(order):
        if set(sections[i])&set(sections[i+1]):
            raise ValueError('Rim quads must connect through opposite edges')
    rails=[]
    for edge in sections:
        a,b = (coords[x].copy() for x in edge)
        if rails and (a-rails[-1][0]).length+(b-rails[-1][1]).length > (b-rails[-1][0]).length+(a-rails[-1][1]).length:
            a,b=b,a
        rails.append((a,b))
    normals=[]
    for face in order:
        p=[coords[x] for x in mesh.polygons[face].vertices]
        normal=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
        normals.append(normal)
    tangent=(sum(rails[1],Vector())-sum(rails[0],Vector())).normalized()
    if tangent.cross(rails[0][1]-rails[0][0]).dot(normals[0])<0:
        rails=[(b,a) for a,b in rails]
    rim=Rim(rails,closed,normals)
    rim.origin=origin
    rim.unit_scale=scale
    rim.face_indices=ids
    return rim


class Surface:
    def __init__(self,weld_tolerance=None):
        self.vertices=[]
        self.faces=[]
        self.materials=[]
        self.owners=[]
        self.vertex_info={}
        self.shell_normals={}
        self.protected_vertices=set()
        self.lookup={}
        self.weld_tolerance=weld_tolerance
        self.buckets={}

    def vertex(self,p):
        if self.weld_tolerance:
            tolerance=self.weld_tolerance
            cell=tuple(math.floor(x/tolerance) for x in p)
            for x in (-1,0,1):
                for y in (-1,0,1):
                    for z in (-1,0,1):
                        for index in self.buckets.get((cell[0]+x,cell[1]+y,cell[2]+z),()):
                            if (self.vertices[index]-p).length<=tolerance:
                                return index
            index=len(self.vertices)
            self.vertices.append(p.copy())
            self.buckets.setdefault(cell,[]).append(index)
            return index
        key=tuple(round(x,7) for x in p)
        if key not in self.lookup:
            self.lookup[key]=len(self.vertices)
            self.vertices.append(p.copy())
        return self.lookup[key]

    def face(self,ps,material=0,owner=-1):
        ids=[self.vertex(p) for p in ps]
        if len(set(ids))==len(ids):
            self.faces.append(ids)
            self.materials.append(material)
            self.owners.append(owner)


def _source_tree(obj,rim):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        vertices=[(evaluated.matrix_world@v.co-rim.origin)*rim.unit_scale for v in mesh.vertices]
        triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
        return BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
    finally:
        evaluated.to_mesh_clear()


def _grid_positions(start,end,resolution,breaks=()):
    # A shell over a faceted surface must pass through its original corners.
    # Otherwise a triangle joining two valid offset vertices can chord through
    # the source, even though neither vertex is inside it.
    tolerance=min(.005,resolution*.01)
    anchors=[start]+[s for s in breaks if start+tolerance<s<end-tolerance]+[end]
    anchors=sorted(set(anchors))
    result=[]
    for a,b in zip(anchors,anchors[1:]):
        count=max(1,math.ceil((b-a)/resolution))
        result.extend(a+(b-a)*i/count for i in range(count))
    result.append(end)
    return result


def _one_edge_rim(source,face_indices,rim,settings):
    available=min(rim.sample(s)[2] for s in rim.distances)
    dimensions=settings.one_edge_dimensions(available)
    reference=analyze_rim(source,face_indices,False) if settings.reverse else rim
    target=reference.rails[0][0 if settings.wrap_edge=='A' else 1]+(reference.origin-rim.origin)*rim.unit_scale
    distances=[min((rail[side]-target).length for rail in rim.rails) for side in (0,1)]
    side=0 if distances[0]<distances[1] else 1
    flat=dimensions['flat_width_mm']
    rails=[]
    for a,b in rim.rails:
        across=(b-a).normalized()
        rails.append((a,a+across*flat) if side==0 else (b-across*flat,b))
    trimmed=Rim(rails,rim.closed,rim.normals)
    for key in ('origin','unit_scale','face_indices'):
        setattr(trimmed,key,getattr(rim,key))
    effective=replace(settings,width_mode='PER_SIDE',width_mm=dimensions['overhang_mm'],
                      fold_radius_mm=dimensions['fold_radius_mm'])
    return trimmed,effective,(side,),dict(dimensions,selected_band_width_mm=available,
                                         wrapped_edge=settings.wrap_edge,side_count=1,wrap_mode='ONE_EDGE')


def build_tape(source,face_indices,settings,name='SnakeTape',diagnostic=False):
    settings.validate()
    requested_settings=settings
    if settings.stage=='FOLDED':
        settings=replace(settings,resolution_mm=min(settings.resolution_mm,.65,settings.spacing_mm/4))
    if any(m.show_viewport and m.type not in {'WEIGHTED_NORMAL','NORMAL_EDIT'} for m in source.modifiers):
        raise ValueError('Apply geometry/deformation modifiers on a duplicate before selecting the rim')
    rim=analyze_rim(source,face_indices,settings.reverse)
    sides=(0,1)
    placement={'wrap_mode':'BOTH','side_count':2}
    if settings.wrap_mode=='ONE_EDGE':
        rim,settings,sides,placement=_one_edge_rim(source,face_indices,rim,settings)
    for distance in rim.distances:
        width=rim.sample(distance)[2]
        if width<=settings.thickness_mm*2:
            raise ValueError(
                f'The selected rim is {width:.4g} mm wide; {settings.thickness_mm:.4g} mm tape '
                f'needs a rim wider than {settings.thickness_mm*2:.4g} mm. '
                'Check the model size/Scene Unit Scale or reduce Thickness.')
        settings.overhang(width)
    mid=settings.thickness_mm*.5+settings.clearance_mm
    min_band_width=min(rim.sample(s)[2] for s in rim.distances)
    folded=settings.stage=='FOLDED'
    # Auto used to pick 2*thickness and then reject its own choice on narrow
    # bands. Adapt the default to the band; an explicit radius is not constrained
    # by band width because the bend is outside the cardboard corner.
    minimum_auto_radius=max(mid,settings.thickness_mm*1.5)
    automatic_radius=max(minimum_auto_radius,min(settings.thickness_mm*2,min_band_width*.4))
    radius=max(mid,settings.fold_radius_mm or automatic_radius) if folded else automatic_radius
    if folded:
        min_overhang=min(settings.overhang(rim.sample(s)[2]) for s in rim.distances)
        material_budget=min_overhang-settings.thickness_mm
        max_radius=min((material_budget-.2)*2/math.pi,material_budget/(math.pi/2+3))
        if not settings.fold_radius_mm:
            radius=max(minimum_auto_radius,min(radius,max_radius))
        if radius>max_radius:
            raise ValueError(
                f'Fold radius {radius:.4g} mm needs {radius*math.pi/2+max(.2,3*radius):.4g} mm to bend and settle; '
                f'the available overhang is {min_overhang:.4g} mm. '
                f'Increase tape width or use a radius at most {max(0,max_radius):.4g} mm '
                'to leave material for attachment.')
    positions,angles=cuts(rim.length,settings,rim.closed)
    source_corners=[rim.distances[i] for i in range(1,len(rim.normals))
                    if rim.normals[i-1].dot(rim.normals[i])<.999999]
    sampling=[_grid_positions(a,b,settings.resolution_mm,source_corners) for a,b in zip(positions,positions[1:])]
    short_cuts=(settings.cut_stop_mm>0 or settings.cut_stop_variation_mm>0) and settings.stage in ('CUT','FOLDED')
    surface=Surface(max(1e-5,settings.thickness_mm*.001) if short_cuts else None)
    root_height=radius if folded else mid
    def roots(s):
        a,b,width,tangent,normal=rim.sample(s)
        return a+normal*root_height,b+normal*root_height
    for samples in sampling:
        for s,t in zip(samples,samples[1:]):
            a,b=roots(s)
            c,d=roots(t)
            if folded:
                ns=rim.sample(s)[4]
                nt=rim.sample(t)[4]
                width_steps=max(4,math.ceil((b-a).length/settings.resolution_mm))
                def belt(p,q,n,f):
                    if settings.wrap_mode=='ONE_EDGE':
                        distance=(q-p).length*(f if sides[0]==0 else 1-f)
                        blend=min(1,distance/max(.5,3*radius))
                        return p.lerp(q,f)-n*((root_height-mid)*blend*blend*(3-2*blend))
                    # A thin rim has no room for a deep centre dip between the
                    # two shoulders. Bridge it smoothly instead of forcing a
                    # sub-thickness crease into the middle of the sealing band.
                    dip_factor=max(0,min(1,((q-p).length-4*radius)/(4*radius)))
                    return p.lerp(q,f)-n*((root_height-mid)*dip_factor*(1-abs(2*f-1)**4))
                for j in range(width_steps):
                    f,g=j/width_steps,(j+1)/width_steps
                    surface.face([belt(a,b,ns,f),belt(c,d,nt,f),belt(c,d,nt,g),belt(a,b,ns,g)])
            else:
                surface.face([a,c,d,b])
    source_tree=_source_tree(source,rim) if folded else None
    previous_vertices=[]
    previous_triangles=[]
    flap_count=0
    raised_vertices=0
    depth_data={}
    if short_cuts:
        from .short_cuts import add_short_flaps
        flap_count,depth_data=add_short_flaps(surface,rim,settings,positions,angles,sampling,radius,mid,source_tree,diagnostic,sides=sides)
    elif settings.stage!='BASE':
        for side in sides:
            previous_vertices.clear()
            previous_triangles.clear()
            previous_tree=None
            for index,samples in enumerate(sampling):
                start,end=positions[index:index+2]
                centre=(start+end)*.5
                ac,bc,band_width,tangent,normal=rim.sample(centre)
                across=(bc-ac).normalized()
                outward=across*(-1 if side==0 else 1)
                centre_root=ac if side==0 else bc
                overhang=settings.overhang(band_width)
                count=max(3,math.ceil(overhang/settings.resolution_mm))
                if folded:
                    count=max(count,6)
                row_distances=sorted(set([overhang*i/count for i in range(count+1)]+
                    ([min(overhang,radius*math.pi*j/12) for j in range(1,7)] if folded else [])))
                grid=[]
                displacements=[]
                gap=settings.cut_gap_mm if settings.stage in ('CUT','FOLDED') else 0
                for v in row_distances:
                    row=[]
                    displacement_row=[]
                    for s in samples:
                        fraction=(s-start)/(end-start)
                        angle=(1-fraction)*angles[index]+fraction*angles[index+1]
                        shift=max(-(end-start)*.22,min((end-start)*.22,v*math.tan(angle))) if settings.stage in ('CUT','FOLDED') else 0
                        shift += gap*.5*min(1,v/max(.05,radius*math.pi/2))*(1-2*fraction)
                        ss=s+shift
                        a,b,width,local_tangent,local_normal=rim.sample(ss)
                        local_out=(b-a).normalized()*(-1 if side==0 else 1)
                        rail=a if side==0 else b
                        if not folded:
                            p=rail+local_out*v+local_normal*mid
                            displacement=0
                        else:
                            flat=rail+local_out*v-centre_root
                            along=flat.dot(tangent)
                            root_deviation=rail-centre_root-tangent*(rail-centre_root).dot(tangent)
                            angle_fold=min(math.pi/2,v/radius)
                            lateral=radius*math.sin(angle_fold)
                            depth=radius*math.cos(angle_fold)-max(0,v-radius*math.pi/2)
                            if v>radius*math.pi/2:
                                blend=min(1,(v-radius*math.pi/2)/max(.2,3*radius))
                                lateral=radius+(mid-radius)*(blend*blend*(3-2*blend))
                            p=centre_root+tangent*along+outward*lateral+normal*depth+root_deviation*math.exp(-v/.5)
                            if v<1e-8:
                                p=rail+local_normal*radius
                            displacement=0
                            if v>radius*math.pi/2+.01:
                                reach=overhang*2+band_width+5
                                hit=source_tree.ray_cast(p+outward*reach,-outward,reach*2)
                                if hit[0] is not None and hit[1].dot(outward)>.2:
                                    fitted=hit[0]+outward*((mid+settings.thickness_mm*.3)/max(.2,hit[1].dot(outward)))
                                    if blend>=1:
                                        p=fitted
                                    else:
                                        # During the settling arc only push away
                                        # from obstacles; pulling straight onto
                                        # the wall here would collapse a large
                                        # radius into a sharp, intersecting fold.
                                        p+=outward*max(0,(fitted-p).dot(outward))
                                if previous_tree:
                                    hit=previous_tree.ray_cast(p+outward*reach,-outward,reach*2)
                                    if hit[0] is not None and hit[1].dot(outward)>.15:
                                        required=(hit[0]-p).dot(outward)+(settings.thickness_mm+settings.clearance_mm+.015)/max(.2,hit[1].dot(outward))
                                        displacement=max(0,required)
                                    # A vertex can miss an overlap narrower than a mesh
                                    # cell. Support nearby strip edges conservatively,
                                    # so the connecting triangle bridges above them.
                                    q,n,_,distance=previous_tree.find_nearest(p)
                                    if q is not None and n.dot(outward)>.15 and local_out.dot(outward)<.99999:
                                        lateral_error=(q-p-outward*(q-p).dot(outward)).length
                                        if lateral_error<settings.resolution_mm*1.6:
                                            required=(q-p).dot(outward)+(settings.thickness_mm+settings.clearance_mm+.025)/max(.2,n.dot(outward))
                                            displacement=max(displacement,required,0)
                        row.append(p)
                        displacement_row.append(displacement)
                    grid.append(row)
                    displacements.append(displacement_row)
                if folded:
                    # A one-sided slope envelope bridges existing tape edges without
                    # smoothing a contact constraint back through the supporting flap.
                    for _ in range(3):
                        old=[r[:] for r in displacements]
                        for j in range(2,len(grid)):
                            for i in range(len(samples)):
                                for jj,ii in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
                                    if 1<=jj<len(grid) and 0<=ii<len(samples):
                                        limit=(grid[j][i]-grid[jj][ii]).length*.15
                                        displacements[j][i]=max(displacements[j][i],old[jj][ii]-limit)
                    for j,row in enumerate(grid):
                        for i,p in enumerate(row):
                            if displacements[j][i]>.00001:
                                raised_vertices+=1
                            row[i]=p+outward*max(0,displacements[j][i])
                material=1+(index%7) if diagnostic else 0
                for j in range(len(grid)-1):
                    for i in range(len(samples)-1):
                        quad=[grid[j][i],grid[j][i+1],grid[j+1][i+1],grid[j+1][i]]
                        if side==0:
                            quad.reverse()
                        surface.face(quad,material,flap_count)
                        if folded:
                            base=len(previous_vertices)
                            previous_vertices.extend(quad)
                            previous_triangles.extend([(base,base+1,base+2),(base,base+2,base+3)])
                for j,row in enumerate(grid):
                    for point in row:
                        vertex=surface.vertex(point)
                        if row_distances[j]>1e-7:
                            surface.vertex_info[vertex]=(flap_count,outward.copy(),min(1,row_distances[j]/.5))
                if folded:
                    previous_tree=BVHTree.FromPolygons(previous_vertices,previous_triangles,all_triangles=True)
                flap_count+=1
    mesh=bpy.data.meshes.new(name)
    obj=None
    try:
        mesh.from_pydata([v/rim.unit_scale for v in surface.vertices],[],surface.faces)
        mesh.update()
        if short_cuts:
            from .short_cuts import thicken
            shell_owners,shell_materials=thicken(surface,mesh,settings.thickness_mm,rim.unit_scale)
            skin=mesh.attributes.new('snaketape_surface','INT','FACE')
            count=len(surface.faces)
            for i,item in enumerate(skin.data):
                item.value=1 if i<count else -1 if i<2*count else 0
            protected=mesh.attributes.new('snaketape_protect','BOOLEAN','POINT')
            for i in surface.protected_vertices:
                protected.data[i].value=True
                protected.data[i+len(surface.vertices)].value=True
        ownership=mesh.attributes.new('snaketape_flap','INT','FACE')
        for item,value in zip(ownership.data,shell_owners if short_cuts else surface.owners):
            item.value=value
        obj=bpy.data.objects.new(name,mesh)
        bpy.context.collection.objects.link(obj)
        obj.location=rim.origin
        for material in _materials(settings,rim.unit_scale):
            mesh.materials.append(material)
        for p,material in zip(mesh.polygons,shell_materials if short_cuts else surface.materials):
            p.material_index=material
        if short_cuts:
            obj['snaketape_shell_vertices']=len(surface.vertices)
        else:
            solidify=obj.modifiers.new('Tape thickness','SOLIDIFY')
            solidify.thickness=settings.thickness_mm/rim.unit_scale
            solidify.offset=0
            solidify.use_even_offset=True
            solidify.use_quality_normals=True
            solidify.use_rim=True
        obj['snaketape_settings']=json.dumps(asdict(requested_settings),sort_keys=True)
        obj['snaketape_faces']=json.dumps(list(face_indices))
        obj['snaketape_topology']=topology_signature(source)
        obj['snaketape_source_name']=source.name
        obj['snaketape_version']=1
        repairs=_resolve_shell_contacts(obj,surface,rim,settings,source_tree) if folded else 0
        data={'length_mm':rim.length,'flaps':flap_count,'raised_vertices':raised_vertices,'contact_iterations':repairs,
              'min_band_width_mm':min_band_width,'fold_radius_mm':radius if folded else None,
              'surface_vertices':len(surface.vertices),'closed':rim.closed,'stage':settings.stage}
        data.update(depth_data)
        data.update(placement)
        from .optimization import finish_mesh
        data.update(finish_mesh(obj,source,settings,rim.unit_scale))
        mesh=obj.data
        obj['snaketape_metrics']=json.dumps(data)
        bpy.context.view_layer.update()
        return obj,data
    except Exception:
        if obj:
            bpy.data.objects.remove(obj,do_unlink=True)
        if mesh.users==0:
            bpy.data.meshes.remove(mesh)
        raise


def _resolve_shell_contacts(obj,surface,rim,settings,source_tree,max_iterations=60):
    """Resolve sub-cell collisions on the evaluated solid, preserving pinned roots.

    The broad contact fit is followed by local, one-sided relief. Final validation
    uses triangle intersections, not only the sampled support vertices.
    """
    owners_to_vertices={}
    for index,(owner,direction,weight) in surface.vertex_info.items():
        owners_to_vertices.setdefault(owner,[]).append(index)
    for iteration in range(max_iterations):
        bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            vertices=[v.co*rim.unit_scale for v in mesh.vertices]
            triangles=[tuple(t.vertices) for t in mesh.loop_triangles]
            attribute=mesh.attributes.get('snaketape_flap')
            tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True)
            contacts={}
            remaining=0
            self_intersections=0
            source_intersections=0
            for a,b in tree.overlap(tree):
                if a>=b or set(triangles[a])&set(triangles[b]):
                    continue
                remaining+=1
                self_intersections+=1
                oa=attribute.data[mesh.loop_triangles[a].polygon_index].value
                ob=attribute.data[mesh.loop_triangles[b].polygon_index].value
                owner=max(oa,ob)
                if owner<0 or oa==ob:
                    continue
                ta=triangles[a] if oa==owner else triangles[b]
                centre=sum((vertices[i] for i in ta),Vector())/3
                contacts.setdefault(owner,[]).append(centre)
            for a,b in tree.overlap(source_tree):
                remaining+=1
                source_intersections+=1
                owner=attribute.data[mesh.loop_triangles[a].polygon_index].value
                if owner>=0:
                    centre=sum((vertices[i] for i in triangles[a]),Vector())/3
                    contacts.setdefault(owner,[]).append(centre)
            if not remaining:
                return iteration
        finally:
            evaluated.to_mesh_clear()
        if not contacts:
            if source_intersections:
                raise ValueError(f'The sealing band intersects the source surface ({source_intersections} triangle pairs); check the selected rim geometry')
            raise ValueError(f'Fold geometry intersects itself ({remaining} triangle pairs); increase fold radius or mesh density')
        footprint=settings.resolution_mm*2.5
        moved=0
        for owner,points in contacts.items():
            for index in owners_to_vertices.get(owner,[]):
                _,direction,weight=surface.vertex_info[index]
                p=obj.data.vertices[index].co*rim.unit_scale
                distance=min((p-q-direction*(p-q).dot(direction)).length for q in points)
                falloff=max(0,1-(distance/footprint)**2)
                shift=falloff*weight*settings.thickness_mm*.6
                if shift>1e-6:
                    obj.data.vertices[index].co+=direction*(shift/rim.unit_scale)
                    if 'snaketape_shell_vertices' in obj:
                        obj.data.vertices[index+obj['snaketape_shell_vertices']].co+=direction*(shift/rim.unit_scale)
                    moved+=1
        obj.data.update()
        if not moved:
            break
    raise ValueError(f'Could not resolve contact ({self_intersections} tape/tape and {source_intersections} tape/source triangle pairs); reduce width/angle or use a gentler bend')


def _materials(settings,unit_scale):
    colors=[(.83,.71,.43,1),(.27,.62,.85,1),(.92,.45,.22,1),(.35,.72,.45,1),
            (.73,.38,.79,1),(.9,.73,.2,1),(.2,.73,.74,1),(.84,.4,.51,1)]
    materials=[]
    for i,color in enumerate(colors):
        name='SnakeTape Masking tape' if i==0 else f'SnakeTape Diagnostic {i}'
        name+=' (paper grain)' if settings.paper_bump_mm else ' (plain)'
        key=f'{i}:{settings.paper_bump_mm:.9g}:{unit_scale:.9g}'
        material=next((m for m in bpy.data.materials if m.get('snaketape_material_key')==key),None)
        if material is None:
            material=bpy.data.materials.new(name)
            material['snaketape_material_key']=key
        material.diffuse_color=color
        material.use_nodes=True
        shader=material.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Base Color'].default_value=color
        shader.inputs['Roughness'].default_value=.78
        if settings.paper_bump_mm>0 and not material.node_tree.nodes.get('SnakeTape paper bump'):
            nodes=material.node_tree.nodes
            noise=nodes.new('ShaderNodeTexNoise')
            noise.name='SnakeTape paper grain'
            noise.inputs['Scale'].default_value=unit_scale*5
            noise.inputs['Detail'].default_value=2
            noise.inputs['Roughness'].default_value=.7
            bump=nodes.new('ShaderNodeBump')
            bump.name='SnakeTape paper bump'
            bump.inputs['Distance'].default_value=settings.paper_bump_mm/unit_scale
            bump.inputs['Strength'].default_value=.35
            coords=nodes.new('ShaderNodeTexCoord')
            material.node_tree.links.new(coords.outputs['Object'],noise.inputs['Vector'])
            material.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
            material.node_tree.links.new(bump.outputs['Normal'],shader.inputs['Normal'])
        materials.append(material)
    return materials
