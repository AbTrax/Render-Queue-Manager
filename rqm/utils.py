"""Utility helpers for Render Queue Manager.
Separated from monolithic script.
"""
from __future__ import annotations
import os, re
import bpy

__all__ = [
    'FILE_FORMAT_ITEMS','scene_items','camera_items','engine_items',
    '_sanitize_component','_sanitize_subpath','_tokens','_ensure_dir',
    '_scene_output_dir','_valid_node_format'
]

FILE_FORMAT_ITEMS = [
    ('PNG', 'PNG', ''), ('JPEG', 'JPEG', ''), ('OPEN_EXR', 'OpenEXR', ''),
    ('BMP', 'BMP', ''), ('TIFF', 'TIFF', '')
]

def scene_items(self, context):
    return [(s.name, s.name, '') for s in bpy.data.scenes]

def camera_items(self, context):
    scn = bpy.data.scenes.get(getattr(self, 'scene_name', '')) if getattr(self, 'scene_name', None) else None
    cams = []
    if scn:
        for ob in scn.objects:
            if ob.type == 'CAMERA':
                cams.append((ob.name, ob.name, ''))
    return cams or [('', '<no cameras>', '')]

def engine_items(self, context):
    seen, items = set(), []
    try:
        enum = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
        for e in enum:
            items.append((e.identifier, e.name, e.description or ''))
            seen.add(e.identifier)
    except Exception:
        pass
    if 'CYCLES' not in seen:
        items.append(('CYCLES', 'Cycles', 'Cycles Render Engine'))
    return items or [('BLENDER_EEVEE', 'Eevee', 'Eevee Render Engine')]

_valid_node_formats = {'PNG','OPEN_EXR','OPEN_EXR_MULTILAYER','JPEG','BMP','TIFF'}
_valid_job_formats = {'PNG','OPEN_EXR','JPEG','BMP','TIFF'}

def _valid_node_format(fmt: str) -> str:
    return fmt if fmt in _valid_node_formats else ('PNG' if fmt not in _valid_job_formats else fmt)

INVALID_CHARS = '<>:"/\\|?*'
_reserved = { 'CON','PRN','AUX','NUL', *[f'COM{i}' for i in range(1,10)], *[f'LPT{i}' for i in range(1,10)] }

_def_re_space = re.compile(r'\s+')
_split_path = re.compile(r'[\\/]+')

def _sanitize_component(name: str) -> str:
    name = (name or '').strip()
    name = ''.join('_' if c in INVALID_CHARS else c for c in name)
    name = _def_re_space.sub(' ', name).strip().rstrip('.')
    if not name:
        return 'untitled'
    if name.upper() in _reserved:
        return f'_{name}_'
    return name

def _sanitize_subpath(subpath: str) -> str:
    parts = [p for p in _split_path.split(subpath or '') if p not in ('', '.', '..')]
    safe = [_sanitize_component(p) for p in parts]
    return os.path.join(*safe) if safe else ''

def _tokens(text: str, scn, job_name, cam_name, node_name=None):
    t = text or ''
    t = t.replace('{scene}', scn.name if scn else '')
    t = t.replace('{camera}', cam_name or '')
    t = t.replace('{job}', job_name or '')
    t = t.replace('{node}', node_name or '')
    return t

def _ensure_dir(path: str):
    try:
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return True, None
    except Exception as e:
        return False, str(e)

def _scene_output_dir(scn):
    p = bpy.path.abspath(scn.render.filepath)
    if p.endswith(('/', '\\')) or os.path.isdir(p):
        return p
    return os.path.dirname(p) or '//'
