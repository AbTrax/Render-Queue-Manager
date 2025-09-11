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
        if job.link_marker:
            if not job.marker_name:
                return False, 'Start marker enabled but not selected.'
            ms = scn.timeline_markers.get(job.marker_name)
            if not ms:
                return False, f"Start marker '{job.marker_name}' not found."
            start_frame = int(ms.frame) + int(job.marker_offset)
        else:
            start_frame = int(job.frame_start)
        if job.link_end_marker:
            if not job.end_marker_name:
                return False, 'End marker enabled but not selected.'
            me = scn.timeline_markers.get(job.end_marker_name)
            if not me:
                return False, f"End marker '{job.end_marker_name}' not found."
            end_frame = int(me.frame) + int(job.end_marker_offset)
        else:
            end_frame = int(job.frame_end)
        if end_frame < start_frame:
            end_frame = start_frame
        # Respect original frame numbering so filenames / data match expected frame numbers.
        scn.frame_start = start_frame
        scn.frame_end = end_frame
        scn.frame_current = start_frame
    else:
        # For single frame renders, ensure current frame is the requested start (or 1 fallback)
        scn.frame_current = int(job.frame_start) if getattr(job, 'frame_start', None) else scn.frame_current
    safe_base = _sanitize_component(job.file_basename or 'render')
    scn.render.image_settings.file_format = job.file_format or 'PNG'
    bdir = base_render_dir(job)
    _ensure_dir(bdir)
    # Ensure trailing separator then base name (Blender appends frame + view identifiers automatically)
    scn.render.filepath = os.path.join(bdir, '') + safe_base
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
