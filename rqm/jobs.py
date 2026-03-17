"""Job application logic — scene setup, frame range, outputs, compositor sync."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import _ensure_dir, apply_encoding_settings, view_layer_identifier_map
from .comp import base_render_dir, comp_root_dir, sync_one_output, job_file_prefix
from .properties import RQM_Job, get_job_view_layer_names, sync_job_view_layers

__all__ = ['apply_job', 'restore_margin_cameras']

# Store original camera FOV angle when margin is applied, keyed by camera data name
_margin_originals = {}


def restore_margin_cameras():
    """Restore original FOV angle for all margin-modified cameras."""
    for cam_name, orig_angle in list(_margin_originals.items()):
        cam = bpy.data.cameras.get(cam_name)
        if cam:
            cam.angle = orig_angle
    _margin_originals.clear()


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
    # Apply samples override before rendering
    if getattr(job, 'use_samples_override', False):
        samples_val = getattr(job, 'samples', 128)
        try:
            if scn.render.engine == 'CYCLES' and hasattr(scn, 'cycles'):
                scn.cycles.samples = samples_val
            elif hasattr(scn, 'eevee'):
                eevee = scn.eevee
                for attr in ('taa_render_samples', 'samples'):
                    if hasattr(eevee, attr):
                        setattr(eevee, attr, samples_val)
                        break
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
    # Restore any margin-modified cameras from a previous job
    restore_margin_cameras()
    scn.render.resolution_x = job.res_x
    scn.render.resolution_y = job.res_y
    scn.render.resolution_percentage = job.percent
    # Apply margin (overscan) — increase resolution, adjust camera FOV and sensor
    if getattr(job, 'use_margin', False) and getattr(job, 'margin', 0) > 0:
        margin_px = job.margin
        new_x = job.res_x + margin_px * 2
        new_y = job.res_y + margin_px * 2
        scn.render.resolution_x = new_x
        scn.render.resolution_y = new_y
        cam_data = scn.camera.data if scn.camera else None
        if cam_data:
            import math
            _margin_originals[cam_data.name] = cam_data.angle
            # Use correct trigonometric FOV scaling based on sensor_fit
            if cam_data.sensor_fit == 'VERTICAL':
                scale = new_y / job.res_y
            elif cam_data.sensor_fit == 'HORIZONTAL':
                scale = new_x / job.res_x
            else:  # AUTO — Blender uses the larger dimension
                if new_x >= new_y:
                    scale = new_x / job.res_x
                else:
                    scale = new_y / job.res_y
            cam_data.angle = 2 * math.atan(math.tan(cam_data.angle / 2) * scale)
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
    # Pre-create compositor root to reduce race conditions for File Output nodes
    try:
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
