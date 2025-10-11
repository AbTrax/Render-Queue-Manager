"""Compositor output and path resolution logic (ported from monolithic version)."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import (
    _sanitize_component, _sanitize_subpath, _tokens,
    _ensure_dir, _scene_output_dir, _valid_node_format, apply_encoding_settings
)
from .properties import RQM_CompOutput, RQM_Job

__all__ = [
    'job_root_dir','base_render_dir','comp_root_dir',
    'get_file_output_node','resolve_base_dir','sync_one_output',
    'job_file_prefix'
]


def _append_job_suffix(folder: str, job: RQM_Job, token: str | None = None) -> str:
    """
    Ensure the final folder component follows the job-prefixed convention when enabled.
    token: optional raw tail name to prefer over the existing folder basename.
    """
    stripped = (folder or '').rstrip('/\\')
    if not stripped:
        return folder
    parent = os.path.dirname(stripped)
    existing_tail = os.path.basename(stripped)
    safe_tail = _sanitize_component(token or existing_tail)
    safe_job = _sanitize_component(job.name or 'job')
    if not safe_tail:
        safe_tail = existing_tail or 'output'
    if getattr(job, 'suffix_output_folders_with_job', False):
        # New convention: prefix tail with job name unless already present
        job_lower = safe_job.lower()
        tail_lower = safe_tail.lower()
        if not tail_lower.startswith(job_lower):
            safe_tail = f'{safe_job}_{safe_tail}'
    if parent:
        return os.path.join(parent, safe_tail)
    return safe_tail


def _remove_job_prefix(token: str, safe_job: str) -> str:
    """Strip the job name prefix from a token if present (case-insensitive)."""
    token = (token or '').strip('_ -')
    if not token:
        return ''
    lower = token.lower()
    job_lower = safe_job.lower()
    if lower == job_lower:
        return ''
    if lower.startswith(job_lower):
        remainder = token[len(safe_job):].lstrip('_- ')
        return remainder.strip('_ -')
    return token


def _derive_subfolder_token(job: RQM_Job, base_dir: str, *fallback_tokens: str) -> str:
    """Determine the subfolder component (without job prefix) used for filenames."""
    safe_job = _sanitize_component(job.name or 'job')
    candidates = []
    stripped = (base_dir or '').rstrip('/\\')
    if stripped:
        leaf = _sanitize_component(os.path.basename(stripped))
        if leaf:
            candidates.append(_remove_job_prefix(leaf, safe_job))
    for token in fallback_tokens:
        if token:
            safe_token = _sanitize_component(token)
            candidates.append(_remove_job_prefix(safe_token, safe_job))
    file_base = _sanitize_component(getattr(job, 'file_basename', '') or '')
    if file_base:
        candidates.append(_remove_job_prefix(file_base, safe_job))
    for candidate in candidates:
        clean = (candidate or '').strip('_ -')
        if clean:
            return clean
    return 'output'


def job_file_prefix(job: RQM_Job, base_dir: str, *fallback_tokens: str) -> str:
    """Build the filename prefix `<job>_<subfolder> ` for render and compositor outputs."""
    safe_job = _sanitize_component(job.name or 'job')
    sub_token = _derive_subfolder_token(job, base_dir, *fallback_tokens)
    safe_sub = _sanitize_component(sub_token or '')
    if not safe_sub or safe_sub.lower() == safe_job.lower():
        prefix = safe_job
    else:
        prefix = f'{safe_job}_{safe_sub}'
    if not prefix.endswith(' '):
        prefix = prefix + ' '
    return prefix

def job_root_dir(job: RQM_Job) -> str:
    root = bpy.path.abspath(job.output_path)
    return os.path.join(root, _sanitize_component(job.name or 'job'))

def base_render_dir(job: RQM_Job) -> str:
    base = os.path.join(job_root_dir(job), 'base')
    return _append_job_suffix(base, job, 'base')

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
    leaf_hint = None
    node_hint = None
    if out.use_node_named_subfolder:
        node_sub = _sanitize_component(node_name or 'Composite')
        base_dir = os.path.join(base_dir, node_sub)
        node_hint = node_sub
        leaf_hint = node_sub
    if out.extra_subfolder.strip():
        raw = _tokens(out.extra_subfolder, scn, job.name, job.camera_name, node_name=node_name).strip()
        sub = _sanitize_subpath(raw)
        if sub:
            base_dir = os.path.join(base_dir, sub)
            leaf_hint = os.path.basename(sub.rstrip('/\\'))
    if out.base_source == 'JOB_OUTPUT':
        token = leaf_hint or node_hint or 'comp'
        base_dir = _append_job_suffix(base_dir, job, token)
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
    fmt = getattr(node, 'format', None)
    if fmt:
        if out.override_node_format:
            try:
                fmt.file_format = _valid_node_format(job.file_format or 'PNG')
            except Exception:
                pass
        encoding_source = None
        if getattr(out, 'use_custom_encoding', False):
            encoding_source = getattr(out, 'encoding', None)
        elif out.override_node_format:
            encoding_source = getattr(job, 'encoding', None)
        if encoding_source:
            try:
                apply_encoding_settings(fmt, fmt.file_format, encoding_source)
            except Exception:
                pass
    extra_hint = ''
    if out.extra_subfolder.strip():
        raw = _tokens(out.extra_subfolder, scn, job.name, job.camera_name, node_name=node.name).strip()
        sub = _sanitize_subpath(raw)
        if sub:
            extra_hint = os.path.basename(sub.rstrip('/\\'))
    node_hint = node.name if out.use_node_named_subfolder else ''
    target_prefix = job_file_prefix(job, base_dir, extra_hint, node_hint, 'comp')
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
