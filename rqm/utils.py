"""Utility helpers for Render Queue Manager X.
Separated from monolithic script.
"""
from __future__ import annotations
import os, re
import bpy

__all__ = [
    'FILE_FORMAT_ITEMS',
    'scene_items',
    'camera_items',
    'engine_items',
    'view_layer_items',
    'view_layer_identifier_map',
    '_sanitize_component',
    '_sanitize_subpath',
    '_tokens',
    '_ensure_dir',
    '_scene_output_dir',
    '_valid_node_format',
    'apply_encoding_settings',
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

_re_view_layer_id = re.compile(r'[^A-Za-z0-9_]')


def _view_layer_id_base(name: str) -> str:
    cleaned = _re_view_layer_id.sub('_', name or '')
    cleaned = cleaned.strip('_') or 'VIEW_LAYER'
    if cleaned[0].isdigit():
        cleaned = f'_{cleaned}'
    return cleaned[:63]


def view_layer_identifier_map(scn):
    mapping = {}
    if not scn:
        return mapping
    used = set()
    try:
        for layer in scn.view_layers:
            base = _view_layer_id_base(layer.name)
            ident = base
            index = 1
            while ident in used:
                ident = f'{base}_{index}'
                index += 1
            used.add(ident)
            mapping[ident] = layer
    except Exception:
        return {}
    return mapping


def view_layer_items(self, context):
    scn = (
        bpy.data.scenes.get(getattr(self, 'scene_name', ''))
        if getattr(self, 'scene_name', None)
        else None
    )
    mapping = view_layer_identifier_map(scn)
    if not mapping:
        return [('', '<no view layers>', '')]
    return [(identifier, layer.name or identifier, '') for identifier, layer in mapping.items()]

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
    if 'BLENDER_WORKBENCH' not in seen:
        items.append(('BLENDER_WORKBENCH', 'Workbench', 'Workbench render engine'))
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


def apply_encoding_settings(image_settings, file_format, encoding):
    """Apply encoding settings to a Blender ImageFormatSettings-like object."""
    if not image_settings or encoding is None:
        return
    fmt = (file_format or getattr(image_settings, 'file_format', '') or '').upper()
    # Color mode (RGB / RGBA / BW)
    mode = getattr(encoding, 'color_mode', None)
    if mode:
        try:
            image_settings.color_mode = mode
        except Exception:
            pass
    # Color depth (8 / 16 / 32)
    depth = getattr(encoding, 'color_depth', None)
    if depth:
        try:
            image_settings.color_depth = depth
        except Exception:
            pass
    # Compression (PNG/TIFF/EXR)
    compression = getattr(encoding, 'compression', None)
    if compression is not None and fmt in {'PNG', 'TIFF', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        try:
            image_settings.compression = max(0, min(100, int(compression)))
        except Exception:
            pass
    # Quality (JPEG)
    quality = getattr(encoding, 'quality', None)
    if quality is not None and fmt in {'JPEG'}:
        try:
            image_settings.quality = max(0, min(100, int(quality)))
        except Exception:
            pass
    # EXR codec
    if fmt in {'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        codec = getattr(encoding, 'exr_codec', None)
        if codec:
            try:
                image_settings.exr_codec = codec
            except Exception:
                pass
