"""Render the production generator into a self-contained offline review gallery."""
import argparse
from dataclasses import asdict,replace
from datetime import datetime
import html
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from snake_tape.core import Settings
from snake_tape.geometry import build_tape
from snake_tape.validation import measure
from tests.fixtures import clear,make_rim,make_cylinder


def material(name,color):
    mat=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=.9
    return mat


def setup_render(width=720,height=480):
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=12
    scene.cycles.use_denoising=True
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.world=bpy.data.worlds.new('SnakeTape studio')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.36,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    return scene


def camera_and_lights(source):
    points=[source.matrix_world@Vector(p) for p in source.bound_box]
    lower=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    upper=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    centre=(lower+upper)*.5
    span=max(upper-lower)*1.5
    camera_data=bpy.data.cameras.new('Review camera')
    camera_data.type='ORTHO'
    camera_data.clip_start=.00001
    camera_data.clip_end=100
    camera=bpy.data.objects.new('Review camera',camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera=camera
    for index,offset in enumerate(((.5,-.7,1),(-.8,.4,.6))):
        data=bpy.data.lights.new(f'Studio {index}','AREA')
        data.energy=.12 if index==0 else .08
        data.shape='DISK'
        data.size=span*1.4
        obj=bpy.data.objects.new(data.name,data)
        bpy.context.collection.objects.link(obj)
        obj.location=centre+Vector(offset)*span*2
        obj.rotation_euler=(centre-obj.location).to_track_quat('-Z','Y').to_euler()
    return camera,centre,span


def render_view(path,camera,centre,span,direction=(1,-1,.9)):
    camera.location=centre+Vector(direction).normalized()*span*3
    camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.ortho_scale=span
    bpy.context.scene.render.filepath=str(path)
    print(f'Rendering {path.parent.name}/{path.name}',flush=True)
    # Keep native Cycles diagnostics in the run folder while the console shows
    # concise progress. Python-only redirect_stdout does not capture C++ output.
    with (path.parent/'render.log').open('a',encoding='utf8') as log:
        saved=os.dup(1)
        try:
            sys.stdout.flush()
            os.dup2(log.fileno(),1)
            bpy.ops.render.render(write_still=True)
            sys.stdout.flush()
        finally:
            os.dup2(saved,1)
            os.close(saved)


def corrugation(source):
    """Visible paper sheets over the separate, hidden solid contact/selection proxy."""
    source.hide_render=True
    mat=material('Corrugated kraft',(.38,.21,.085))
    verts=[]
    faces=[]
    for i in range(181):
        x=36*i/180
        y=1.72*math.sin(x*math.tau/4)
        verts.extend([(x*.001,y*.001,0),(x*.001,y*.001,-.016)])
        if i:
            faces.append((2*i-2,2*i,2*i+1,2*i-1))
    mesh=bpy.data.meshes.new('Fluted paper')
    mesh.from_pydata(verts,[],faces)
    obj=bpy.data.objects.new('Fluted paper',mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    modifier=obj.modifiers.new('Paper thickness','SOLIDIFY')
    modifier.thickness=.00015
    for y in (-.0019,.0019):
        bpy.ops.mesh.primitive_cube_add(size=1,location=(.018,y,-.008))
        skin=bpy.context.object
        skin.name='Outer liner'
        skin.dimensions=(.036,.0002,.016)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        skin.data.materials.append(mat)


def write_gallery(folder,cases):
    cards=[]
    for case in cases:
        figures=''.join(f'<figure><a href="{html.escape(image[0])}"><img loading="lazy" src="{html.escape(image[0])}" alt="{html.escape(image[1])}"></a><figcaption>{html.escape(image[1])}</figcaption></figure>' for image in case.get('images',[]))
        status=case.get('status','FAILED')
        metrics=case.get('metrics',{})
        badges=' '.join(f'<span>{html.escape(key)}: {html.escape(str(value))}</span>' for key,value in metrics.items() if key in ('source_intersection_pairs','source_penetrating_vertices','self_intersection_pairs','nonmanifold_edges','components'))
        generation=case.get('generation',{})
        if 'triangles_after' in generation:
            badges+=f"<span>Triangles: {generation['triangles_before']:,} → {generation['triangles_after']:,} ({generation['reduction_percent']:.0f}% fewer)</span><span>Checked shape error: {generation['shape_error_mm']:.4f} mm</span>"
        error=f'<pre>{html.escape(case["error"])}</pre>' if case.get('error') else ''
        cards.append(f'<section><h2>{html.escape(case["name"])} <small class="{status.lower()}">{status}</small></h2><p>{html.escape(case.get("description",""))}</p><div class="metrics">{badges}</div>{error}<div class="grid">{figures}</div><p><a href="{html.escape(case["slug"])}/metrics.json">Measurements and settings</a> · <a href="{html.escape(case["slug"])}/inspect.blend">Inspect scene in Blender</a></p></section>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SnakeTape geometry previews</title><style>
    body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#edf0f3;color:#202a34}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:36px;margin-bottom:0}section{background:white;border-radius:14px;padding:24px;margin:24px 0;box-shadow:0 2px 10px #16253512}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}figure{margin:0}img{width:100%;border-radius:8px;background:#ced1d6}figcaption{padding:6px 0}small{font-size:13px;padding:5px 9px;border-radius:8px}.pass{background:#dcf3e4}.failed{background:#ffdede}.metrics span{display:inline-block;background:#f0f3f6;padding:4px 8px;margin:0 8px 12px 0;border-radius:6px}a{color:#1957a6}pre{white-space:pre-wrap;color:#9a2020}.note{max-width:960px}</style><main><h1>SnakeTape geometry previews</h1><p class="note">Generated in Blender 4.4.3 using the same geometry pipeline as the add-on. Click an image for full size. These checks cover the displayed cases; artistic realism and interactive undo still need review. Diagnostic colours identify individual flaps, with the continuous sealing band in beige.</p>'''+''.join(cards)+'</main></html>'
    (folder/'index.html').write_text(page,encoding='utf8')
    (folder/'manifest.json').write_text(json.dumps(cases,indent=2),encoding='utf8')


def prepare_output(folder):
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError('Choose a new or empty preview output directory; previous results are preserved')
    folder.mkdir(parents=True,exist_ok=True)


def main():
    if bpy.app.version!=(4,4,3):
        raise RuntimeError(f'Blender 4.4.3 required, found {bpy.app.version_string}')
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-pause',action='store_true')
    parser.add_argument('--quick',action='store_true')
    parser.add_argument('--output')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    folder=Path(args.output) if args.output else ROOT/'generated'/'previews'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    prepare_output(folder)
    import snake_tape
    from snake_tape.ui import copy_settings
    snake_tape.register()
    specifications=[('Straight edge','straight'),('Convex and concave bend','bend'),('S bend','s_bend'),('Closed loop and seam','loop'),('Rotated and scaled edge','transformed'),('Corrugated cardboard','corrugated'),('Narrow 0.3 mm rim (automatic radius)','narrow'),('Cylinder side faces (reported scale)','cylinder')]
    specifications += [('Mixed full and short cuts','short_straight'),('Cylinder with irregular cut depth','short_cylinder')]
    specifications += [('Reported crease: root 0 mm, depth variation 0.48 mm','short_reported')]
    specifications += [('One edge: 6 mm tape / 3 mm finished wrap','one_straight'),
                       ('One edge: cylinder Edge A','one_cylinder_a'),
                       ('One edge: cylinder Edge B, reversed overlap order','one_cylinder_b')]
    if args.quick:
        specifications=specifications[:2]
    cases=[]
    for number,(name,kind) in enumerate(specifications):
        clear()
        bpy.context.scene.unit_settings.scale_length=1
        slug=f'{number+1:02d}-{kind}'
        case={'name':name,'slug':slug,'images':[],'status':'FAILED','description':'All four construction stages, followed by inspection views.'}
        directory=folder/slug
        directory.mkdir()
        try:
            fixture_kind='bend' if kind=='narrow' else kind if kind in ('bend','s_bend','loop') else 'straight'
            cylinder=kind in ('cylinder','short_cylinder','short_reported') or kind.startswith('one_cylinder')
            source,ids=make_cylinder() if cylinder else make_rim(fixture_kind,width=.3 if kind=='narrow' else 4)
            if kind.startswith('one_'):
                case['description']=('One edge only. Overall width includes the bend; Wrap depth is the finished distance on the adjacent surface. '
                    + ('10 mm overall / 3 mm depth, on the original 8 mm side-face band. Depth variation 0.48 mm. '
                       + ('Edge B with Reverse direction; the physical edge stays B.' if kind.endswith('_b') else 'Edge A; the opposite end stays uncovered.')
                       if cylinder else '6 mm overall / 3 mm depth, on a 4 mm selected band. The unused tape edge lies flat.'))
            if kind.startswith('short_'):
                case['description']='Uncut root 0 mm, Depth variation 1 mm: seeded full-depth cuts mixed with cuts stopping up to 1 mm short. The material below each short tip remains connected.'
            if kind=='short_reported':
                case['description']='Reported Optimized settings: Uncut root 0 mm / Depth variation 0.48 mm. Cut outlines are protected and the shoulder is triangulated across the bend.'
            if kind=='narrow':
                case['description']='A 0.3 mm rim with default 0.1 mm tape and automatic fold radius. This reproduces the narrow-band rejection fixed in 0.1.1.'
            if kind=='cylinder':
                case['description']='All 32 vertical side faces of a default cylinder, scaled X/Y 0.010 and Z 0.004, with the reported default tape settings. Flaps fold onto both end caps.'
            source.data.materials.append(material('Cardboard',(.38,.22,.095)))
            if kind=='transformed':
                source.rotation_euler=(.12,.08,.45)
                source.scale=(1.2,1.5,1)
                bpy.context.view_layer.update()
            if kind=='corrugated':
                corrugation(source)
                case['description']='Visible liners and flutes with a hidden solid rim/contact proxy; the central tape bridges the flute openings.'
            setup_render(480 if args.quick else 720,320 if args.quick else 480)
            camera,centre,span=camera_and_lights(source)
            if cylinder:
                span*=1.8
            tape=None
            for stage in ('BASE','EXTENDED','CUT','FOLDED'):
                if tape:
                    old_mesh=tape.data
                    bpy.data.objects.remove(tape,do_unlink=True)
                    if not old_mesh.users:
                        bpy.data.meshes.remove(old_mesh)
                settings=Settings(stage=stage,cut_stop_variation_mm=.48 if kind=='short_reported' else 1 if kind.startswith('short_') else 0)
                if kind.startswith('one_'):
                    settings=replace(settings,wrap_mode='ONE_EDGE',wrap_edge='B' if kind.endswith('_b') else 'A',
                        width_mm=10 if cylinder else 6,wrap_depth_mm=3,reverse=kind.endswith('_b'),
                        cut_stop_variation_mm=.48 if cylinder else 0)
                tape,generation=build_tape(source,ids,settings,diagnostic=True)
                tape.snaketape_source=source
                copy_settings(tape.snaketape_options,settings)
                indices=[p.material_index for p in tape.data.polygons]
                for p in tape.data.polygons:
                    p.material_index=0
                filename=stage.lower()+'.png'
                render_view(directory/filename,camera,centre,span)
                case['images'].append((f'{slug}/{filename}',stage.title()))
                if stage=='CUT' and kind.startswith('short_'):
                    from snake_tape.geometry import analyze_rim
                    rim=analyze_rim(source,ids)
                    a,b,_,t,n=rim.sample(rim.length*(.35 if kind=='short_straight' else .55))
                    out=(a-b).normalized()
                    focus=rim.origin+(a+out*1.5)/rim.unit_scale
                    render_view(directory/'cut-tips.png',camera,focus,.008,n)
                    case['images'].append((f'{slug}/cut-tips.png','Full and short cut tips before folding (8 mm field)'))
            stats=measure(tape,source)
            case['metrics']=stats
            case['generation']=generation
            case['settings']=asdict(settings)
            case['status']='PASS' if not any(stats.get(key,0) for key in ('nonmanifold_edges','nonfinite_vertices','source_intersection_pairs','source_penetrating_vertices','self_intersection_pairs')) else 'FAILED'
            if kind.startswith('short_'):
                tape.hide_render=True
                detailed,reference=build_tape(source,ids,replace(settings,mesh_detail='DETAILED'))
                render_view(directory/'detailed-reference.png',camera,centre,span)
                case['images'].append((f'{slug}/detailed-reference.png','Detailed reference before reduction (same paper bump)'))
                old_mesh=detailed.data
                bpy.data.objects.remove(detailed,do_unlink=True)
                if not old_mesh.users:
                    bpy.data.meshes.remove(old_mesh)
                tape.hide_render=False
            views=[('Front',(0,-1,.3)),('Back',(0,1,.3)),('Top',(0,0,1))]
            if kind.startswith('one_'):views.append(('Bottom',(0,0,-1)))
            for title,direction in views:
                filename=title.lower()+'.png'
                render_view(directory/filename,camera,centre,span,direction)
                case['images'].append((f'{slug}/{filename}',title))
            for p,index in zip(tape.data.polygons,indices):
                p.material_index=index
            filename='diagnostic.png'
            render_view(directory/filename,camera,centre,span)
            case['images'].append((f'{slug}/{filename}','Individual flaps / overlap order'))
            # A fixed crop around the middle of the selected rim reveals sub-mm relief.
            from snake_tape.geometry import analyze_rim
            rim=analyze_rim(source,ids)
            a,b,_,t,n=rim.sample(rim.length*.55)
            if kind.endswith('_b'):a,b=b,a
            focus=rim.origin+(a-n*3)/rim.unit_scale
            out=(a-b).normalized()
            render_view(directory/'closeup.png',camera,focus,.012,(out+n*.5+t*.4))
            case['images'].append((f'{slug}/closeup.png','Fold and overlap close-up (12 mm field)'))
            if kind=='one_straight':
                render_view(directory/'profile.png',camera,rim.origin+(a-n*.8)/rim.unit_scale,.009,t)
                case['images'].append((f'{slug}/profile.png','One-fold profile: finished depth and flat unused edge (9 mm field)'))
            if kind=='short_reported':
                a,b,_,t,n=rim.sample(rim.length*.12)
                focus=rim.origin+(a-n*.5+(a-b).normalized()*.12)/rim.unit_scale
                render_view(directory/'shoulder.png',camera,focus,.008,((a-b).normalized()+n*.6+t*.2))
                case['images'].append((f'{slug}/shoulder.png','Protected slit tips and smooth shoulder (8 mm field)'))
            bpy.ops.object.select_all(action='DESELECT')
            tape.select_set(True)
            bpy.context.view_layer.objects.active=tape
            camera.location=centre+Vector((1,-1,.9)).normalized()*span*3
            camera.rotation_euler=(centre-camera.location).to_track_quat('-Z','Y').to_euler()
            camera.data.ortho_scale=span
            for screen in bpy.data.screens:
                for area in screen.areas:
                    if area.type=='VIEW_3D':
                        space=area.spaces.active
                        space.clip_start=.00001
                        space.region_3d.view_location=centre
                        space.region_3d.view_distance=span
                        space.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
                        space.shading.color_type='MATERIAL'
            bpy.ops.wm.save_as_mainfile(filepath=str(directory/'inspect.blend'))
        except Exception:
            case['error']=traceback.format_exc()
            print(case['error'],flush=True)
        (directory/'metrics.json').write_text(json.dumps(case,indent=2),encoding='utf8')
        cases.append(case)
        write_gallery(folder,cases)
        print(f"PREVIEW {name}: {case['status']}",flush=True)
    print(f'\nPreview gallery: {folder / "index.html"}',flush=True)
    if any(case['status']!='PASS' for case in cases):
        raise RuntimeError('Some preview cases failed validation; review the gallery')


if __name__=='__main__':
    main()
