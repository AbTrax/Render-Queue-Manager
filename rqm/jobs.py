"""Job application logic (scene setup, frame range, outputs, compositor sync)."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import _ensure_dir, apply_encoding_settings, view_layer_identifier_map
from .comp import base_render_dir, sync_one_output, job_file_prefix
from .properties import RQM_Job, get_job_view_layer_names, sync_job_view_layers

__all__ = ['apply_job']

def _apply_frame_border(scn, job):
    render = getattr(scn, 'render', None)
    if not render:
        return
    border_enabled = bool(getattr(job, 'use_frame_border', False))
    border_px = int(getattr(job, 'frame_border_pixels', 0) or 0)
    if not border_enabled or border_px <= 0:
        try:
            render.use_border = False
            render.use_crop_to_border = False
            render.border_min_x = 0.0
            render.border_min_y = 0.0
            render.border_max_x = 1.0
            render.border_max_y = 1.0
        except Exception:
            pass
        return
    res_x = max(int(getattr(job, 'res_x', render.resolution_x) or render.resolution_x), 1)
    res_y = max(int(getattr(job, 'res_y', render.resolution_y) or render.resolution_y), 1)
    max_border_x = (res_x - 2) // 2
    max_border_y = (res_y - 2) // 2
    if max_border_x < 0 or max_border_y < 0:
        return
    px_x = min(border_px, max_border_x)
    px_y = min(border_px, max_border_y)
    norm_x = max(min(px_x / res_x, 0.499), 0.0)
    norm_y = max(min(px_y / res_y, 0.499), 0.0)
    try:
        render.use_border = True
        render.use_crop_to_border = False
        render.border_min_x = norm_x
        render.border_max_x = 1.0 - norm_x
        render.border_min_y = norm_y
        render.border_max_y = 1.0 - norm_y
    except Exception:
        pass

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
    persistent_flag = getattr(job, 'use_persistent_data', None)
    if persistent_flag is not None:
        try:
            if hasattr(scn.render, 'use_persistent_data'):
                scn.render.use_persistent_data = bool(persistent_flag)
        except Exception:
            pass
    if scn.render.engine == 'CYCLES':
        try:
            ops_cycles = getattr(bpy.ops, 'cycles', None)
            if ops_cycles and hasattr(ops_cycles, 'cache_reset'):
                # Reset cycles caches so each job starts clean when persistent data is enabled.
                ops_cycles.cache_reset()
        except Exception:
            pass
    if job.camera_name:
        cam_obj = bpy.data.objects.get(job.camera_name)
        if cam_obj and cam_obj.type == 'CAMERA':
            scn.camera = cam_obj
    mapping = view_layer_identifier_map(scn)
    try:
        selected_names = sync_job_view_layers(job, scn, mapping)
    except Exception:
        selected_names = get_job_view_layer_names(job)
    if selected_names and mapping:
        selected_lookup = set(selected_names)
        for layer in mapping.values():
            try:
                layer.use = layer.name in selected_lookup
            except Exception:
                pass
        for name in selected_names:
            layer = next((lay for lay in mapping.values() if getattr(lay, 'name', None) == name), None)
            if not layer:
                continue
            try:
                bpy.context.window.view_layer = layer
            except Exception:
                try:
                    bpy.context.view_layer = layer
                except Exception:
                    pass
                else:
                    break
            else:
                break
    scn.render.resolution_x = job.res_x
    scn.render.resolution_y = job.res_y
    scn.render.resolution_percentage = job.percent
    _apply_frame_border(scn, job)
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
        # Preserve actual frame numbers (no remap) so disparate ranges (e.g., 3-10 then 20-30) keep original numbering
        if getattr(job, 'link_timeline_markers', False):
            # Require both markers when the link option is on
            if not job.marker_name:
                return False, 'Start marker not selected.'
            if not job.end_marker_name:
                return False, 'End marker not selected.'
            ms = scn.timeline_markers.get(job.marker_name)
            me = scn.timeline_markers.get(job.end_marker_name)
            if not ms:
                return False, f"Start marker '{job.marker_name}' not found.".strip()
            if not me:
                return False, f"End marker '{job.end_marker_name}' not found.".strip()
            src_start = int(ms.frame) + int(job.marker_offset)
            src_end = int(me.frame) + int(job.end_marker_offset)
        else:
            # Backward-compatible: allow separate flags
            if getattr(job, 'link_marker', False):
                if not job.marker_name:
                    return False, 'Start marker enabled but not selected.'
                ms = scn.timeline_markers.get(job.marker_name)
                if not ms:
                    return False, f"Start marker '{job.marker_name}' not found.".strip()
                src_start = int(ms.frame) + int(job.marker_offset)
            else:
                src_start = int(job.frame_start)
            if getattr(job, 'link_end_marker', False):
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
        scn.frame_start = src_start
        scn.frame_end = src_end
        scn.frame_current = src_start
    else:
        # Single still: always frame 0 for consistent 0000 numbering
        scn.frame_start = 0
        scn.frame_end = 0
        scn.frame_current = 0
    scn.render.image_settings.file_format = job.file_format or 'PNG'
    try:
        apply_encoding_settings(
            getattr(scn.render, 'image_settings', None),
            job.file_format,
            getattr(job, 'encoding', None),
        )
    except Exception:
        pass
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
    # Ensure trailing separator then job/subfolder prefix so Blender writes '<Job>_<Sub> 0000.ext'
    render_prefix = job_file_prefix(job, bdir, 'base')
    scn.render.filepath = os.path.join(bdir, '') + render_prefix
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
