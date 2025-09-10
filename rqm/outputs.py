import bpy, os
from .utils import sanitize_component, sanitize_subpath, tokens, ensure_dir, scene_output_dir
from .properties import RQM_CompOutput, RQM_Job

__all__ = ['sync_one_output']

VALID_NODE_FORMATS = {'PNG','OPEN_EXR','OPEN_EXR_MULTILAYER','JPEG','BMP','TIFF'}

def _valid_node_format(fmt: str) -> str:
    return fmt if fmt in VALID_NODE_FORMATS else 'PNG'

def get_file_output_node(scn, out: RQM_CompOutput):
    if not scn: return None, 'No scene.'
    if not scn.use_nodes: scn.use_nodes = True
    nt = scn.node_tree
    if not nt: return None, 'Scene has no node tree.'
    node = None
    if out.node_name:
        n = nt.nodes.get(out.node_name)
        if n and n.bl_idname == 'CompositorNodeOutputFile':
            node = n
    if not node and out.create_if_missing:
        node = nt.nodes.new('CompositorNodeOutputFile')
        node.label = 'RQM File Output'
        base = 'RQM_File_Output'; name = base; i = 1
        while nt.nodes.get(name):
            i += 1; name = f'{base}_{i}'
        node.name = name
        node.location = (400,200)
        out.node_name = node.name
    if not node:
        return None, "Pick a File Output node (or enable 'Create if missing')."
    return node, None

def job_root_dir(job: RQM_Job):
    root = bpy.path.abspath(job.output_path)
    return os.path.join(root, sanitize_component(job.name or 'job'))

def comp_root_dir(job: RQM_Job):
    return os.path.join(job_root_dir(job), 'comp')

def base_render_dir(job: RQM_Job):
    return os.path.join(job_root_dir(job), 'base')

def resolve_base_dir(scn, job: RQM_Job, out: RQM_CompOutput, node_name: str):
    if out.base_source == 'JOB_OUTPUT':
        base_dir = comp_root_dir(job)
    elif out.base_source == 'SCENE_OUTPUT':
        base_dir = scene_output_dir(scn)
    else:
        if not out.base_file:
            return None, 'No file chosen.'
        base_dir = os.path.dirname(bpy.path.abspath(out.base_file))
    if out.use_node_named_subfolder:
        base_dir = os.path.join(base_dir, sanitize_component(node_name or 'Composite'))
    if out.extra_subfolder.strip():
        raw = tokens(out.extra_subfolder, scn, job.name, job.camera_name, node_name=node_name).strip()
        sub = sanitize_subpath(raw)
        if sub:
            base_dir = os.path.join(base_dir, sub)
    return base_dir, None

def _ensure_min_slot(node, fallback_name: str):
    if len(node.file_slots) == 0:
        node.file_slots.new(fallback_name or 'render')

def sync_one_output(scn, job: RQM_Job, out: RQM_CompOutput):
    node, err = get_file_output_node(scn, out)
    if not node: return False, err
    base_dir, err = resolve_base_dir(scn, job, out, node.name)
    if err: return False, err
    base_dir = bpy.path.abspath(base_dir or '//')
    try:
        node.base_path = base_dir
    except Exception as e:
        return False, f'Could not set base path: {e}'
    if out.ensure_dirs:
        ok,e2 = ensure_dir(base_dir)
        if not ok:
            return False, f"Couldn't create folder '{base_dir}': {e2}"
    if out.override_node_format and hasattr(node,'format'):
        try:
            node.format.file_format = _valid_node_format(job.file_format or 'PNG')
        except Exception:
            pass
    safe_job = sanitize_component(job.name or 'job')
    safe_base = sanitize_component(job.file_basename or 'render')
    target_prefix = f'{safe_job}_{safe_base}'
    _ensure_min_slot(node, target_prefix)
    try:
        for fs in node.file_slots:
            if not fs.path or fs.path.lower() in {'image','render'}:
                fs.path = target_prefix
    except Exception:
        pass
    return True, 'OK'
