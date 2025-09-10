import os, re, bpy

__all__ = [
    'sanitize_component','sanitize_subpath','tokens','ensure_dir','scene_output_dir'
]

def sanitize_component(name: str) -> str:
    name = (name or '').strip()
    invalid = '<>:"/\\|?*'
    name = ''.join('_' if c in invalid else c for c in name)
    name = re.sub(r'\s+', ' ', name).strip().rstrip('.')
    upper = name.upper()
    reserved = {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if upper in reserved or not name:
        name = f"_{name}_" if name else 'untitled'
    return name

def sanitize_subpath(subpath: str) -> str:
    parts = [p for p in re.split(r'[\\/]+', subpath or '') if p not in ('', '.', '..')]
    safe = [sanitize_component(p) for p in parts]
    return os.path.join(*safe) if safe else ''

def tokens(text: str, scn, job_name, cam_name, node_name=None):
    t = text or ''
    t = t.replace('{scene}', scn.name if scn else '')
    t = t.replace('{camera}', cam_name or '')
    t = t.replace('{job}', job_name or '')
    t = t.replace('{node}', node_name or '')
    return t

def ensure_dir(path: str):
    try:
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return True, None
    except Exception as e:
        return False, str(e)

def scene_output_dir(scn):
    p = bpy.path.abspath(scn.render.filepath)
    if p.endswith(('/', '\\')) or os.path.isdir(p):
        return p
    return os.path.dirname(p) or '//'
