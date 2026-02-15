"""Compositor output and path resolution logic (ported from monolithic version)."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import (
    _sanitize_component, _sanitize_subpath, _tokens,
    _ensure_dir, _scene_output_dir, _valid_node_format
)
from .properties import RQM_CompOutput, RQM_Job

__all__ = [
    'job_root_dir','base_render_dir','comp_root_dir',
    'get_file_output_node','resolve_base_dir','sync_one_output',
    'get_slot_subdirs','_get_compositor_node_tree',
]


# ---- Blender 5 compatibility helpers ----

def _is_blender5() -> bool:
    """Return True when running on Blender 5.0 or newer."""
    try:
        return bpy.app.version >= (5, 0, 0)
    except Exception:
        return False


def _set_node_base_path(node, path: str):
    """Set the output directory on a File Output node (B5+ uses *directory*)."""
    if _is_blender5() and hasattr(node, 'directory'):
        node.directory = path
    else:
        node.base_path = path


def _get_node_slots(node):
    """Return the iterable of output slots (file_output_items on B5+, file_slots otherwise)."""
    if _is_blender5() and hasattr(node, 'file_output_items'):
        return node.file_output_items
    return node.file_slots


def _node_slot_count(node) -> int:
    """Return number of output slots on the node."""
    try:
        return len(_get_node_slots(node))
    except Exception:
        return 0


def _new_node_slot(node, name: str):
    """Add a new output slot to the File Output node."""
    if _is_blender5() and hasattr(node, 'file_output_items'):
        return node.file_output_items.new('RGBA', name)
    return node.file_slots.new(name)


def _get_compositor_node_tree(scn):
    """Return the compositor node tree for *scn* (B5+ vs B3/B4).

    Blender 5.0 moved the compositor from ``scene.node_tree`` to
    ``scene.compositing_node_group``.  This helper returns the correct
    one, or *None* if compositing is not set up.
    """
    if _is_blender5():
        # B5: compositing_node_group is the new data-block
        nt = getattr(scn, 'compositing_node_group', None)
        if nt is not None:
            return nt
    # B3/B4 (and fallback for B5 scenes that haven't created one yet)
    return getattr(scn, 'node_tree', None)


def _get_slot_path(slot) -> str:
    """Read the sub-path / name from a slot (works on both old and new API)."""
    # B5 file_output_items have .name; old file_slots have .path
    if hasattr(slot, 'path'):
        return slot.path or ''
    if hasattr(slot, 'name'):
        return slot.name or ''
    return ''


def _set_slot_path(slot, value: str):
    """Write the sub-path / name on a slot."""
    if hasattr(slot, 'path'):
        slot.path = value
    elif hasattr(slot, 'name'):
        slot.name = value


def _set_node_format(node, fmt: str):
    """Set the file format on the node (handles both old and new API)."""
    safe_fmt = _valid_node_format(fmt or 'PNG')
    # B5+: try per-item format first, then fall back to node.format
    if _is_blender5():
        try:
            slots = _get_node_slots(node)
            for item in slots:
                if hasattr(item, 'format'):
                    item.format.file_format = safe_fmt
        except Exception:
            pass
    # B3/B4: node.format.file_format
    if hasattr(node, 'format'):
        try:
            node.format.file_format = safe_fmt
        except Exception:
            pass


def _enable_compositor(scn):
    """Ensure the scene's compositor / nodes are enabled (B5-safe).

    On Blender 5.0+ ``use_nodes`` is deprecated (always True, setting
    it is a no-op), so we create a ``compositing_node_group`` if one
    doesn't exist yet.
    """
    if _is_blender5():
        # Ensure a compositing node group exists
        if getattr(scn, 'compositing_node_group', None) is None:
            try:
                # Blender auto-creates one when the user opens the compositor;
                # we can also create one via bpy.data.node_groups.new()
                import bpy
                ng = bpy.data.node_groups.new(f'{scn.name}_Compositing', 'CompositorNodeTree')
                scn.compositing_node_group = ng
            except Exception:
                pass
    else:
        try:
            if hasattr(scn, 'use_nodes'):
                if not scn.use_nodes:
                    scn.use_nodes = True
        except Exception:
            pass


# ---- Directory helpers ----

def _append_job_suffix(folder: str, job: RQM_Job) -> str:
    if not getattr(job, 'suffix_output_folders_with_job', False):
        return folder
    safe_job = _sanitize_component(job.name or 'job')
    if not safe_job:
        return folder
    stripped = folder.rstrip('/\\')
    if not stripped:
        return folder
    tail = os.path.basename(stripped)
    if not tail:
        return folder
    if tail.lower() == safe_job.lower() or tail.lower().endswith('_' + safe_job.lower()):
        return folder
    parent = os.path.dirname(stripped)
    new_tail = f'{tail}_{safe_job}'
    if parent:
        return os.path.join(parent, new_tail)
    return new_tail

def job_root_dir(job: RQM_Job) -> str:
    root = bpy.path.abspath(job.output_path)
    return os.path.join(root, _sanitize_component(job.name or 'job'))

def base_render_dir(job: RQM_Job) -> str:
    base = os.path.join(job_root_dir(job), 'base')
    return _append_job_suffix(base, job)

def comp_root_dir(job: RQM_Job) -> str:
    # Flatten structure: compositor outputs share job root (no separate 'comp' folder)
    return job_root_dir(job)

def get_file_output_node(scn, out: RQM_CompOutput):
    if not scn:
        return None, 'No scene.'
    _enable_compositor(scn)
    nt = _get_compositor_node_tree(scn)
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
    base_dir = _append_job_suffix(base_dir, job)

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
    if _node_slot_count(node) == 0:
        _new_node_slot(node, fallback_name or 'render')

def sync_one_output(scn, job: RQM_Job, out: RQM_CompOutput):
    node, err = get_file_output_node(scn, out)
    if not node:
        return False, err
    base_dir, err = resolve_base_dir(scn, job, out, node.name)
    if err:
        return False, err
    base_dir = bpy.path.abspath(base_dir or '//')
    try:
        _set_node_base_path(node, base_dir)
    except Exception as e:
        return False, f"Couldn't set File Output base path: {e}".strip()
    if out.ensure_dirs:
        ok, e2 = _ensure_dir(base_dir)
        if not ok:
            return False, f"Couldn't create folder '{base_dir}': {e2}".strip()
    if out.override_node_format:
        _set_node_format(node, job.file_format or 'PNG')
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
        for fs in _get_node_slots(node):
            sp = _get_slot_path(fs)
            if not sp or sp.lower() in {'image', 'render'}:
                _set_slot_path(fs, target_prefix)
            # If user custom path lacks trailing space, optionally keep as-is (don't force)
    except Exception:
        pass
    # Auto-link first unlinked input to Render Layers if possible (helps ensure node writes files)
    try:
        nt = _get_compositor_node_tree(scn)
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
        for fs in _get_node_slots(node):
            print(f"[RQM]   slot '{_get_slot_path(fs)}'")
    except Exception:
        pass
    return True, 'OK'


def get_slot_subdirs(scn, job: RQM_Job, out: RQM_CompOutput):
    """Return a list of full directory paths for each slot in the File Output node.

    This enables pre-creating the exact folder tree before rendering starts.
    """
    dirs = []
    node, err = get_file_output_node(scn, out)
    if not node:
        return dirs
    base_dir, err = resolve_base_dir(scn, job, out, node.name)
    if err or not base_dir:
        return dirs
    base_dir = bpy.path.abspath(base_dir or '//')
    dirs.append(base_dir)
    # Each slot may define a sub-path that becomes a subdirectory
    try:
        for slot in _get_node_slots(node):
            sp = _get_slot_path(slot).rstrip('/ \\')
            if not sp or sp == '.':
                continue
            # Slot paths can contain directory separators (e.g. "passes/diffuse")
            slot_dir = os.path.join(base_dir, os.path.dirname(sp)) if os.path.dirname(sp) else base_dir
            if slot_dir not in dirs:
                dirs.append(slot_dir)
    except Exception:
        pass
    return dirs
