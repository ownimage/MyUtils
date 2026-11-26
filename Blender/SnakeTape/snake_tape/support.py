"""Clipboard diagnostics without exporting scene geometry or directory paths."""
from dataclasses import asdict
import json
from pathlib import Path
import tomllib
import bpy
from .geometry import topology_signature


def _saved(obj,key):
    try:
        return json.loads(obj.get(key,'null'))
    except (ValueError,TypeError):
        return None


def support_report(context):
    from .ui import read_settings
    obj=context.object
    tape=obj if obj and 'snaketape_version' in obj else None
    options=tape.snaketape_options if tape else context.scene.snaketape_options
    current=asdict(read_settings(options))
    source=tape.snaketape_source if tape else obj
    indices=_saved(tape,'snaketape_faces') if tape else None
    source_data=None
    if source and source.type=='MESH':
        if source.mode=='EDIT':source.update_from_editmode()
        if indices is None:indices=[p.index for p in source.data.polygons if p.select]
        scale=1000*context.scene.unit_settings.scale_length
        source_data={'name':source.name,'mode':source.mode,'face_indices':indices,
            'vertex_count':len(source.data.vertices),'face_count':len(source.data.polygons),
            'scale':list(source.scale),'dimensions_mm':[v*scale for v in source.dimensions],
            'matrix_world':[list(row) for row in source.matrix_world],
            'topology_signature':topology_signature(source),
            'modifiers':[{'name':m.name,'type':m.type,'show_viewport':m.show_viewport} for m in source.modifiers]}
    last=_saved(tape,'snaketape_settings') if tape else None
    manifest=tomllib.loads(Path(__file__).with_name('blender_manifest.toml').read_text(encoding='utf8'))
    return {'report':'SnakeTape support settings','schema_version':1,'addon_version':manifest['version'],
        'blender_version':bpy.app.version_string,'blend_file':Path(bpy.data.filepath).name or None,
        'scene':{'unit_system':context.scene.unit_settings.system,
                 'unit_scale':context.scene.unit_settings.scale_length,'frame':context.scene.frame_current},
        'settings':current,'last_generated_settings':last,'settings_changed_since_build':last is not None and last!=current,
        'source':source_data,'tape':{'name':tape.name,'vertices':len(tape.data.vertices),
                                   'polygons':len(tape.data.polygons)} if tape else None,
        'metrics':_saved(tape,'snaketape_metrics') if tape else None}


def copy_support_settings(context):
    text=json.dumps(support_report(context),indent=2,ensure_ascii=False)
    context.window_manager.clipboard=text
    return text
