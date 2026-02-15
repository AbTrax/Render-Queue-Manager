"""Job application logic (scene setup, frame range, outputs, compositor sync)."""
from __future__ import annotations
import os
import bpy  # type: ignore
from .utils import _sanitize_component, _ensure_dir, view_layer_identifier_map
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
    try:
        selected_prop = getattr(job, 'view_layers', None)
        if isinstance(selected_prop, str):
            selected_ids = [selected_prop] if selected_prop else []
        elif isinstance(selected_prop, (set, list, tuple)):
            selected_ids = [s for s in selected_prop if s]
        else:
            selected_ids = []
        if selected_ids:
            mapping = view_layer_identifier_map(scn)
            if mapping:
                selected_lookup = set(selected_ids)
                for ident, layer in mapping.items():
                    should_enable = ident in selected_lookup
                    try:
                        layer.use = should_enable
                    except Exception:
                        pass
                for ident in selected_ids:
                    layer = mapping.get(ident)
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
    except Exception:
        pass
    scn.render.resolution_x = job.res_x
    scn.render.resolution_y = job.res_y
    scn.render.resolution_percentage = job.percent
    # Overscan margin: add extra pixels on each side for compositing
    if getattr(job, 'use_margin', False) and getattr(job, 'margin_pixels', 0) > 0:
        m = job.margin_pixels
        scn.render.resolution_x = job.res_x + (m * 2)
        scn.render.resolution_y = job.res_y + (m * 2)
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
