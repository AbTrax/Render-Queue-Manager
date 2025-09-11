"""Compositor output and path resolution logic (ported from monolithic version)."""
from __future__ import annotations
import os
import bpy
from .utils import (
    _sanitize_component, _sanitize_subpath, _tokens,
    _ensure_dir, _scene_output_dir, _valid_node_format
)
from .properties import RQM_CompOutput, RQM_Job

__all__ = [
    'job_root_dir','base_render_dir','comp_root_dir',
    'get_file_output_node','resolve_base_dir','sync_one_output'
]

def job_root_dir(job: RQM_Job) -> str:
    root = bpy.path.abspath(job.output_path)
    return os.path.join(root, _sanitize_component(job.name or 'job'))

def base_render_dir(job: RQM_Job) -> str:
    return os.path.join(job_root_dir(job), 'base')

def comp_root_dir(job: RQM_Job) -> str:
    # Flatten structure: compositor outputs share job root (no separate 'comp' folder)
    return job_root_dir(job)

def get_file_output_node(scn, out: RQM_CompOutput):
    if not scn:
        return None, 'No scene.'
    if not scn.use_nodes:
        scn.use_nodes = True
    nt = scn.node_tree
    if not nt:
        return None, 'Scene has no node tree.'

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
        node.location = (400, 200)
        out.node_name = node.name
    if not node:
        return None, "Pick a File Output node (or enable 'Create if missing')."
    return node, None

def resolve_base_dir(scn, job: RQM_Job, out: RQM_CompOutput, node_name: str):
    if out.base_source == 'JOB_OUTPUT':
        base_dir = comp_root_dir(job)
    elif out.base_source == 'SCENE_OUTPUT':
        base_dir = _scene_output_dir(scn)
    else:
        if not out.base_file:
            return None, "You chose 'Folder of a chosen file' but no file was picked."
        base_dir = os.path.dirname(bpy.path.abspath(out.base_file))

    if out.use_node_named_subfolder:
        node_sub = _sanitize_component(node_name or 'Composite')
        base_dir = os.path.join(base_dir, node_sub)
    if out.extra_subfolder.strip():
        raw = _tokens(out.extra_subfolder, scn, job.name, job.camera_name, node_name=node_name).strip()
        sub = _sanitize_subpath(raw)
        if sub:
            base_dir = os.path.join(base_dir, sub)
    return base_dir, None

def _ensure_min_slot(node, fallback_name: str):
    if len(node.file_slots) == 0:
        node.file_slots.new(fallback_name or 'render')

def sync_one_output(scn, job: RQM_Job, out: RQM_CompOutput):
    node, err = get_file_output_node(scn, out)
    if not node:
        return False, err
    base_dir, err = resolve_base_dir(scn, job, out, node.name)
    if err:
        return False, err
    base_dir = bpy.path.abspath(base_dir or '//')
    try:
        node.base_path = base_dir
    except Exception as e:
        return False, f"Couldn't set File Output base path: {e}".strip()
    if out.ensure_dirs:
        ok, e2 = _ensure_dir(base_dir)
        if not ok:
            return False, f"Couldn't create folder '{base_dir}': {e2}".strip()
    if out.override_node_format and hasattr(node, 'format'):
        try:
            node.format.file_format = _valid_node_format(job.file_format or 'PNG')
        except Exception:
            pass
    safe_job = _sanitize_component(job.name or 'job')
    safe_base = _sanitize_component(job.file_basename or 'render')
    # Avoid duplicate job name if basename already starts with it
    if safe_base.lower().startswith(safe_job.lower() + '_'):
        target_prefix = safe_base
    else:
        target_prefix = f'{safe_job}_{safe_base}'
    # Ensure a space at end so frames become '<prefix> 0000'
    if not target_prefix.endswith(' '):
        target_prefix = target_prefix + ' '
    _ensure_min_slot(node, target_prefix)
    # Only override default/empty slot names ('', 'image', 'render') to avoid clobbering user custom slot paths
    try:
        for fs in node.file_slots:
            if not fs.path or fs.path.lower() in {'image','render'}:
                fs.path = target_prefix
            # If user custom path lacks trailing space, optionally keep as-is (don't force)
    except Exception:
        pass
    # Auto-link first unlinked input to Render Layers if possible (helps ensure node writes files)
    try:
        nt = scn.node_tree
        rl = None
        for n in nt.nodes:
            if n.bl_idname in {'CompositorNodeRLayers','CompositorNodeRenderLayers'}:
                rl = n; break
        if rl and node.inputs:
            for sock in node.inputs:
                if not sock.is_linked and rl.outputs:
                    nt.links.new(rl.outputs[0], sock)
                    break
    except Exception:
        pass
    print(f"[RQM] Compositor node '{node.name}' -> {base_dir}")
    try:
        for fs in node.file_slots:
            print(f"[RQM]   slot '{fs.path}'")
    except Exception:
        pass
    return True, 'OK'
