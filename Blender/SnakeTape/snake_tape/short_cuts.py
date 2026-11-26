"""Local slit-tip topology for partially connected tape overhangs."""
import math
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from mathutils.bvhtree import BVHTree
from .core import cut_stops


def thicken(surface,mesh,thickness,unit_scale):
    """Closed shell with stable material-frame normals at narrow slit tips."""
    n=len(surface.vertices)
    vertices=[(p+surface.shell_normals.get(i,mesh.vertices[i].normal)*(sign*thickness*.5))/unit_scale
              for sign in (1,-1) for i,p in enumerate(surface.vertices)]
    faces=list(surface.faces)+[[i+n for i in reversed(f)] for f in surface.faces]
    owners=list(surface.owners)*2
    materials=list(surface.materials)*2
    boundary={}
    for face,owner,material in zip(surface.faces,surface.owners,surface.materials):
        for a,b in zip(face,face[1:]+face[:1]):
            key=tuple(sorted((a,b)))
            if key in boundary:
                boundary[key]=None
            else:
                boundary[key]=(a,b,owner,material)
    for edge in boundary.values():
        if edge is not None:
            a,b,owner,material=edge
            faces.append([b,a,a+n,b+n])
            owners.append(owner)
            materials.append(material)
    mesh.clear_geometry()
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    return owners,materials


def _tip_mesh(samples, start, end, rows, stops, gap, overhang, warp, ends=(False,False)):
    """Triangulate transverse rows, preserving matching nodes along shared webs.

    A cut tip must not add a thin row all the way across unrelated strips.
    Keeping the input coordinates also avoids float32 CDT rounding at welds.
    """
    coords=[]
    columns=[]
    edges=[]
    column_values=[]
    for i,s in enumerate(samples):
        values=list(rows)
        if i in (0,len(samples)-1) and not ends[0 if i==0 else 1]:
            stop=stops[0 if i==0 else 1]
            anchors=[stop]+[min(overhang,stop+gap*.5*f) for f in (.333333,.666667,1)]
            values=[v for v in values if all(abs(v-a)>.005 for a in anchors) or v in (0,overhang)]
            values+=anchors
        column_values.append(set(values))
    # Give each cut-tip node a transverse connection. With only longitudinal
    # constraints CDT can make an ear from three successive curved boundary
    # points; bending that skinny ear creates a false crease across the web.
    if len(samples)>2:
        column_values[1].update(column_values[0])
        column_values[-2].update(column_values[-1])
    for column_index,(s,values) in enumerate(zip(samples,column_values)):
        column={}
        for v in sorted(values):
            # Warping interior columns can form a skinny ear along their curved
            # chain. Keep the samples straight; only the actual slit border moves.
            point=warp(s-start,v) if column_index in (0,len(samples)-1) else (s-start,v)
            if 0<column_index<len(samples)-1 and not warp(0,v)[0]<point[0]<warp(end-start,v)[0]:
                continue
            column[v]=len(coords)
            coords.append(point)
        columns.append(column)
    for v in rows:
        row=[c[v] for c in columns if v in c]
        edges.extend(zip(row,row[1:]))
    for boundary,order in ((0,range(1,len(columns))),(-1,range(len(columns)-2,-1,-1))):
        for v,vertex in columns[boundary].items():
            inside=next((i for i in order if v in columns[i]),None)
            if inside is not None:
                edges.append((vertex,columns[inside][v]))
    ordered=[list(c.values()) for c in columns]
    perimeter=[c[0] for c in columns]
    perimeter.extend(ordered[-1][1:])
    perimeter.extend(c[overhang] for c in columns[-2:0:-1] if overhang in c)
    perimeter.append(columns[0][overhang])
    perimeter.extend(ordered[0][-2:0:-1])
    vertices,_,faces,origins,_,_=delaunay_2d_cdt(
        [Vector(p) for p in coords],edges,[perimeter],1,1e-7,True)
    points=[coords[ids[0]] if ids else tuple(p) for p,ids in zip(vertices,origins)]
    counts={}
    for face in faces:
        for a,b in zip(face,face[1:]+face[:1]):
            edge=tuple(sorted((a,b)))
            counts[edge]=counts.get(edge,0)+1
    boundary={i for edge,count in counts.items() if count==1 for i in edge}
    return points,faces,boundary


def add_short_flaps(surface,rim,settings,positions,angles,sampling,radius,mid,source_tree,diagnostic):
    folded=settings.stage=='FOLDED'
    min_overhang=min(settings.overhang(rim.sample(s)[2]) for s in rim.distances)
    if settings.cut_stop_mm>=min_overhang:
        raise ValueError(f'Uncut root must be less than the available {min_overhang:.4g} mm overhang')
    if settings.cut_gap_mm<=0:
        raise ValueError('Short cuts need a positive Cut gap to keep the slit sides separate')
    depth_sets=[cut_stops(positions,settings,rim.closed,side,
                         max_stop=max(0,min_overhang-settings.thickness_mm)) for side in (0,1)]
    flap_count=0
    widths=[b-a for a,b in zip(positions,positions[1:])]
    limits=[min(widths[max(0,i-1)],widths[min(i,len(widths)-1)])*.22 for i in range(len(positions))]
    if rim.closed:
        limits[0]=limits[-1]=min(widths[0],widths[-1])*.22
    for side,stops in enumerate(depth_sets):
        # The common web bends coherently. Independent flap expansion is released
        # smoothly after the web, rather than pulling shared vertices apart.
        release_start=max(stops)
        release_length=max(2,4*radius,2*settings.resolution_mm)
        settle_start=max(radius*math.pi/2,release_start+.25)
        settle_length=max(2,3*radius)
        previous_vertices=[]
        previous_triangles=[]
        previous_tree=None
        for index,samples in enumerate(sampling):
            start,end=positions[index:index+2]
            centre=(start+end)*.5
            ac,bc,band_width,tangent,normal=rim.sample(centre)
            outward=(bc-ac).normalized()*(-1 if side==0 else 1)
            centre_root=ac if side==0 else bc
            overhang=min_overhang
            reach=overhang*2+band_width+5
            count=max(6,math.ceil(overhang/settings.resolution_mm))
            rows=sorted(set([overhang*i/count for i in range(count+1)]+
                        ([min(overhang,radius*math.pi*j/12) for j in range(1,7)]+
                         [min(overhang,.05*j) for j in range(1,math.ceil((radius*math.pi/2+max(.2,3*radius))/.05)+1)] if folded else [])))
            rows=sorted(set(rows+[min(overhang,settle_start+settle_length*j/8) for j in range(9)]))
            ends=(not rim.closed and index==0,not rim.closed and index==len(sampling)-1)
            tip_depths=[stops[i]*overhang/settings.overhang(rim.sample(positions[i])[2]) for i in (index,index+1)]
            def warp(u,v):
                actual_v=v*settings.overhang(rim.sample(start+u)[2])/overhang
                fraction=u/(end-start)
                shifts=[]
                for boundary in (index,index+1):
                    if not rim.closed and boundary in (0,len(positions)-1):
                        shifts.append(0)
                        continue
                    run=max(0,actual_v-stops[boundary])
                    if run<1e-6:
                        run=0
                    cap=min(1,run/(settings.cut_gap_mm*.5))
                    half_gap=settings.cut_gap_mm*.5*math.sqrt(max(0,2*cap-cap*cap))
                    shift=max(-limits[boundary],min(limits[boundary],run*math.tan(angles[boundary])))
                    shifts.append(shift+half_gap*(1 if boundary==index else -1))
                return (u+shifts[0]*(1-fraction)+shifts[1]*fraction,v)
            # Triangulate the actual concave slit outline. Triangulating a
            # rectangle then moving its boundary can put triangles across a tip.
            uv,faces,boundary=_tip_mesh(samples,start,end,rows,tip_depths,settings.cut_gap_mm,overhang,warp,ends)
            points=[]
            info=[]
            displacements=[]
            physical_depths=[]
            for u,v in uv:
                ss=start+u
                v*=settings.overhang(rim.sample(ss)[2])/overhang
                physical_depths.append(v)
                a,b,width,local_tangent,local_normal=rim.sample(ss)
                local_out=(b-a).normalized()*(-1 if side==0 else 1)
                rail=a if side==0 else b
                if not folded:
                    p=rail+local_out*v+local_normal*mid
                    direction=local_normal
                    displacement=0
                else:
                    theta=min(math.pi/2,v/radius)
                    lateral=radius*math.sin(theta)
                    depth=radius*math.cos(theta)-max(0,v-radius*math.pi/2)
                    blend=0
                    if v>settle_start:
                        blend=min(1,(v-settle_start)/settle_length)
                        lateral=radius+(mid+settings.thickness_mm*.3-radius)*(blend*blend*(3-2*blend))
                    common=rail+local_out*lateral+local_normal*depth
                    flat=rail+local_out*v-centre_root
                    root_deviation=rail-centre_root-tangent*(rail-centre_root).dot(tangent)
                    free=centre_root+tangent*flat.dot(tangent)+outward*lateral+normal*depth+root_deviation*math.exp(-v/.5)
                    release=max(0,min(1,(v-release_start)/release_length))
                    release=release*release*(3-2*release)
                    p=common.lerp(free,release)
                    direction=(local_out*math.sin(theta)+local_normal*math.cos(theta)).normalized()
                    if v>radius*math.pi/2:
                        slope=(mid+settings.thickness_mm*.3-radius)*6*blend*(1-blend)/settle_length
                        direction=(local_out.lerp(outward,release)+local_normal.lerp(normal,release)*slope).normalized()
                    if v>radius*math.pi/2+.01:
                        cast_direction=local_out.lerp(outward,release).normalized()
                        hit=source_tree.ray_cast(p+cast_direction*reach,-cast_direction,reach*2)
                        if hit[0] is not None and hit[1].dot(cast_direction)>.2:
                            fitted=hit[0]+cast_direction*((mid+settings.thickness_mm*.3)/max(.2,hit[1].dot(cast_direction)))
                            p+=cast_direction*max(0,(fitted-p).dot(cast_direction))
                    displacement=0
                    if previous_tree and v>release_start+.05:
                        hit=previous_tree.ray_cast(p+direction*reach,-direction,reach*2)
                        if hit[0] is not None and hit[1].dot(direction)>.15:
                            displacement=max(0,(hit[0]-p).dot(direction)+
                                             (settings.thickness_mm+settings.clearance_mm+.02)/max(.2,hit[1].dot(direction)))
                        q,n,_,_=previous_tree.find_nearest(p)
                        if q is not None and n.dot(direction)>.15 and local_out.dot(outward)<.99999:
                            lateral_error=(q-p-direction*(q-p).dot(direction)).length
                            if lateral_error<settings.resolution_mm*1.6:
                                displacement=max(displacement,(q-p).dot(direction)+
                                                 (settings.thickness_mm+settings.clearance_mm+.025)/max(.2,n.dot(direction)),0)
                points.append(p)
                relief=max(0,min(1,(v-release_start)/max(.5,2*radius,settings.resolution_mm))) if folded else 1
                relief=relief*relief*(3-2*relief)
                info.append((direction,relief))
                displacements.append(displacement)
            if folded:
                neighbours=[set() for _ in points]
                for face in faces:
                    for a,b in zip(face,face[1:]+face[:1]):
                        neighbours[a].add(b)
                        neighbours[b].add(a)
                for _ in range(3):
                    old=displacements[:]
                    for i,adjacent in enumerate(neighbours):
                        if physical_depths[i]>release_start+.05:
                            for j in adjacent:
                                displacements[i]=max(displacements[i],old[j]-(points[i]-points[j]).length*.15)
                points=[p+info[i][0]*max(0,displacements[i])*info[i][1] for i,p in enumerate(points)]
            material=1+(index%7) if diagnostic else 0
            for face in faces:
                polygon=[points[i] for i in face]
                if side==0:
                    polygon.reverse()
                surface.face(polygon,material,flap_count)
                if folded:
                    base=len(previous_vertices)
                    previous_vertices.extend(polygon)
                    previous_triangles.extend((base,base+j,base+j+1) for j in range(1,len(polygon)-1))
            for point_index,(p,(direction,weight)) in enumerate(zip(points,info)):
                surface.shell_normals[surface.vertex(p)]=direction
                if point_index in boundary and physical_depths[point_index]<=max(release_start,radius*math.pi/2)+max(.3,4*settings.thickness_mm):
                    surface.protected_vertices.add(surface.vertex(p))
                if weight>0:
                    surface.vertex_info[surface.vertex(p)]=(flap_count,direction,weight)
            if folded:
                previous_tree=BVHTree.FromPolygons(previous_vertices,previous_triangles,all_triangles=True)
            flap_count+=1
    values=[v for depths in depth_sets for v in depths]
    return flap_count,{'min_cut_stop_mm':min(values),'max_cut_stop_mm':max(values),'cut_stops_mm':depth_sets}
