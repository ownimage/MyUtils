"""Native Blender menus, settings, and atomic Create/Update operators."""
from dataclasses import fields,replace
import json
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from .core import Settings
from .geometry import build_tape,topology_signature


class SnakeTapeOptions(bpy.types.PropertyGroup):
    thickness_mm: FloatProperty(name='Thickness (mm)',default=.1,min=.005,max=5,precision=3)
    width_mode: EnumProperty(name='Width mode',items=[('PER_SIDE','Each side','Add this width to each side'),('TOTAL','Total tape','Include the original band in the total width')])
    width_mm: FloatProperty(name='Width (mm)',default=10,min=.01,max=1000,precision=2)
    spacing_mm: FloatProperty(name='Cut spacing (mm)',default=3,min=.2,max=1000,precision=2)
    variation: FloatProperty(name='Spacing randomness',default=.25,min=0,max=.8,subtype='FACTOR')
    angle_deg: FloatProperty(name='Cut angle (deg)',description='Maximum seeded variation in cut angle',default=10,min=0,max=45)
    cut_stop_mm: FloatProperty(name='Uncut root (mm)',description='Material left joined between the fold line and each cut tip; zero reaches the fold',default=0,min=0,max=1000,precision=2)
    cut_stop_variation_mm: FloatProperty(name='Depth variation (mm)',description='Random plus/minus change in uncut root; zero root with variation mixes full and shorter cuts',default=0,min=0,max=1000,precision=2)
    wave_strength: FloatProperty(name='Wave strength',default=.2,min=0,max=.8,subtype='FACTOR')
    wave_length_mm: FloatProperty(name='Wave length (mm)',default=25,min=.1,max=10000)
    seed: IntProperty(name='Seed',default=1,min=0,max=2147483647)
    fold_radius_mm: FloatProperty(name='Fold radius (mm)',description='Zero automatically fits the radius to tape thickness, rim width and available overhang',default=0,min=0,max=100,precision=3)
    clearance_mm: FloatProperty(name='Clearance (mm)',description='Minimum requested contact clearance; overlap relief can raise the tape further',default=.01,min=0,max=10,precision=3)
    cut_gap_mm: FloatProperty(name='Cut gap (mm)',default=.06,min=0,max=5,precision=3)
    resolution_mm: FloatProperty(name='Mesh spacing (mm)',default=.65,min=.1,max=10,precision=2)
    mesh_detail: EnumProperty(name='Mesh detail',items=[('OPTIMIZED','Optimized','Reduce the finished solid and preserve its smooth normals; validate contacts and shape'),('DETAILED','Detailed','Keep the dense construction mesh')],default='OPTIMIZED')
    mesh_error_mm: FloatProperty(name='Shape tolerance (mm)',description='Maximum checked simplification error; retains more geometry when needed for contacts',default=.02,min=.001,max=.1,precision=3)
    paper_bump_mm: FloatProperty(name='Paper bump (mm)',description='Fine procedural paper grain; zero disables it without changing the mesh',default=.003,min=0,max=.1,precision=3)
    stage: EnumProperty(name='Stage',items=[('BASE','1 Base','Original rim with tape thickness'),('EXTENDED','2 Extended','Full width without cuts'),('CUT','3 Cut','Slit overhangs before folding'),('FOLDED','4 Folded','Conformed flaps with overlap relief')],default='FOLDED',options={'HIDDEN'})
    reverse: BoolProperty(name='Reverse direction',description='Reverse rim traversal and overlap placement order',default=False)


def read_settings(options):
    return Settings(**{f.name:getattr(options,f.name) for f in fields(Settings)})


def copy_settings(options,settings):
    for f in fields(Settings):
        setattr(options,f.name,getattr(settings,f.name))


def _activate(obj):
    if bpy.context.object and bpy.context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for other in bpy.context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj


def generate(context,old=None):
    if old:
        source=old.snaketape_source
        if source is None:
            raise ValueError('The source object was removed; select a new rim and Create Tape')
        if topology_signature(source)!=old.get('snaketape_topology'):
            raise ValueError('Source topology changed; reselect the rim faces and Create Tape')
        indices=json.loads(old['snaketape_faces'])
        settings=read_settings(old.snaketape_options)
    else:
        source=context.object
        source.update_from_editmode()
        indices=[p.index for p in source.data.polygons if p.select]
        settings=read_settings(context.scene.snaketape_options)
    # Stage values remain readable for older .blend files and diagnostic scripts.
    # The user action always performs the entire tape-making operation.
    settings=replace(settings,stage='FOLDED')
    new,metrics=build_tape(source,indices,settings)
    new.snaketape_source=source
    copy_settings(new.snaketape_options,settings)
    if old:
        name=old.name
        old_mesh=old.data
        for collection in list(new.users_collection):
            collection.objects.unlink(new)
        for collection in old.users_collection:
            collection.objects.link(new)
        bpy.data.objects.remove(old,do_unlink=True)
        if old_mesh.users==0:
            bpy.data.meshes.remove(old_mesh)
        new.name=name
    _activate(new)
    return new,metrics


class SNAKETAPE_OT_create(bpy.types.Operator):
    bl_idname='mesh.snaketape_create'
    bl_label='SnakeTape: Create Tape'
    bl_description='Create complete tape: add thickness, extend, cut and fold onto both sides'
    bl_options={'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return context.object is not None and context.object.type=='MESH' and context.object.mode=='EDIT'

    def execute(self,context):
        try:
            _,metrics=generate(context)
        except (ValueError,KeyError) as error:
            self.report({'ERROR'},str(error))
            return {'CANCELLED'}
        self.report({'INFO'},f"Created tape: {metrics['flaps']} flaps")
        return {'FINISHED'}


class SNAKETAPE_OT_update(bpy.types.Operator):
    bl_idname='mesh.snaketape_update'
    bl_label='SnakeTape: Update Tape'
    bl_description='Rebuild the selected tape from its saved source and current settings'
    bl_options={'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return context.object is not None and 'snaketape_version' in context.object and context.object.mode=='OBJECT'

    def execute(self,context):
        try:
            generate(context,context.object)
        except (ValueError,KeyError) as error:
            self.report({'ERROR'},str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class SNAKETAPE_MT_menu(bpy.types.Menu):
    bl_label='SnakeTape'
    bl_idname='SNAKETAPE_MT_menu'
    def draw(self,context):
        self.layout.operator('mesh.snaketape_create',text='Create Tape')


class SNAKETAPE_PT_panel(bpy.types.Panel):
    bl_label='SnakeTape'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='SnakeTape'

    def draw(self,context):
        layout=self.layout
        tape=context.object if context.object and 'snaketape_version' in context.object else None
        options=tape.snaketape_options if tape else context.scene.snaketape_options
        if tape:
            layout.label(text='Settings for: '+tape.name)
            layout.prop(tape,'snaketape_source',text='Source')
        else:
            layout.label(text='Select one row of rim quad faces')
            layout.label(text='in Edit Mode, then Create Tape.')
        for key in ('thickness_mm','width_mode','width_mm','spacing_mm','variation','angle_deg','cut_stop_mm','cut_stop_variation_mm','wave_strength','wave_length_mm','seed','fold_radius_mm','mesh_detail','reverse'):
            layout.prop(options,key)
        box=layout.box()
        box.label(text='Advanced')
        box.prop(options,'mesh_error_mm')
        box.prop(options,'paper_bump_mm')
        for key in ('clearance_mm','cut_gap_mm','resolution_mm'):
            box.prop(options,key)
        if tape:
            layout.operator('mesh.snaketape_update',text='Update Tape',icon='FILE_REFRESH')
            metrics=json.loads(tape.get('snaketape_metrics','{}'))
            if 'triangles_after' in metrics:
                layout.label(text=f"{metrics['triangles_after']:,} triangles ({metrics['reduction_percent']:.0f}% fewer)")
        else:
            layout.operator('mesh.snaketape_create',text='Create Tape',icon='MOD_SOLIDIFY')


def draw_mesh_menu(self,context):
    self.layout.menu('SNAKETAPE_MT_menu')


classes=(SnakeTapeOptions,SNAKETAPE_OT_create,SNAKETAPE_OT_update,SNAKETAPE_MT_menu,SNAKETAPE_PT_panel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snaketape_options=PointerProperty(type=SnakeTapeOptions)
    bpy.types.Object.snaketape_options=PointerProperty(type=SnakeTapeOptions)
    bpy.types.Object.snaketape_source=PointerProperty(type=bpy.types.Object)
    bpy.types.VIEW3D_MT_edit_mesh.append(draw_mesh_menu)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh.remove(draw_mesh_menu)
    del bpy.types.Object.snaketape_source
    del bpy.types.Object.snaketape_options
    del bpy.types.Scene.snaketape_options
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
