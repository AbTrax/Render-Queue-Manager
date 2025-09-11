"""Job application logic (scene setup, frame range, outputs, compositor sync)."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import _sanitize_component, _ensure_dir
from .comp import base_render_dir, sync_one_output
from .properties import RQM_Job

__all__ = ['apply_job']

def apply_job(job: RQM_Job):
    scn = bpy.data.scenes.get(job.scene_name)
    if not scn:
        return False, f"Scene '{job.scene_name}' not found."
    try:
        bpy.context.window.scene = scn
    except Exception:
        pass
    try:
        scn.render.engine = job.engine
    except Exception:
        return False, f"Engine '{job.engine}' not available on this build."
    if job.camera_name:
        cam_obj = bpy.data.objects.get(job.camera_name)
        if cam_obj and cam_obj.type == 'CAMERA':
            scn.camera = cam_obj
    scn.render.resolution_x = job.res_x
    scn.render.resolution_y = job.res_y
    scn.render.resolution_percentage = job.percent
    # Stereoscopy (multiview) handling
    try:
        if getattr(job, 'use_stereoscopy', False):
            scn.render.use_multiview = True
            # If user wants plain stereo 3D and Blender supports setting views_format
            if getattr(job, 'stereo_views_format', 'STEREO_3D') == 'STEREO_3D' and hasattr(scn.render, 'views_format'):
                try:
                    scn.render.views_format = 'STEREO_3D'
                except Exception:
                    pass
            # MULTIVIEW: leave as-is (scene configured views)
        else:
            if hasattr(scn.render, 'use_multiview'):
                scn.render.use_multiview = False
    except Exception:
        pass
    if job.use_animation:
        # Derive source start/end (could be marker-linked) then remap to 0-based range for consistent file numbering
        if job.link_marker:
            if not job.marker_name:
                return False, 'Start marker enabled but not selected.'
            ms = scn.timeline_markers.get(job.marker_name)
            if not ms:
                return False, f"Start marker '{job.marker_name}' not found.".strip()
            src_start = int(ms.frame) + int(job.marker_offset)
        else:
            src_start = int(job.frame_start)
        if job.link_end_marker:
            if not job.end_marker_name:
                return False, 'End marker enabled but not selected.'
            me = scn.timeline_markers.get(job.end_marker_name)
            if not me:
                return False, f"End marker '{job.end_marker_name}' not found.".strip()
            src_end = int(me.frame) + int(job.end_marker_offset)
        else:
            src_end = int(job.frame_end)
        if src_end < src_start:
            src_end = src_start
        length = (src_end - src_start) + 1
        scn.frame_start = 0
        scn.frame_end = max(0, length - 1)
        scn.frame_current = 0
    else:
        # Single still: always frame 0 for consistent 0000 numbering
        scn.frame_start = 0
        scn.frame_end = 0
        scn.frame_current = 0
    safe_base = _sanitize_component(job.file_basename or 'render')
    scn.render.image_settings.file_format = job.file_format or 'PNG'
    # Ensure compositing enabled so File Output nodes run
    try:
        if hasattr(scn.render, 'use_compositing'):
            scn.render.use_compositing = True
    except Exception:
        pass
    bdir = base_render_dir(job)
    _ensure_dir(bdir)
    # Pre-create compositor root as well to reduce race conditions for File Output nodes
    try:
        from .comp import comp_root_dir
        _ensure_dir(comp_root_dir(job))
    except Exception:
        pass
    # Ensure trailing separator then base name (Blender appends frame + view identifiers automatically)
    # Add space after base so Blender writes 'basename 0000.ext'
    base_with_space = safe_base + ' ' if not safe_base.endswith(' ') else safe_base
    scn.render.filepath = os.path.join(bdir, '') + base_with_space
    if job.use_comp_outputs and len(job.comp_outputs) > 0:
        errors = []
        for out in job.comp_outputs:
            if not out.enabled:
                continue
            ok, msg = sync_one_output(scn, job, out)
            if not ok:
                errors.append(msg)
        if errors:
            for e in errors:
                print('[RQM Warning]', e)
            if not job.comp_outputs_non_blocking:
                return False, '; '.join(errors)
    return True, 'OK'
