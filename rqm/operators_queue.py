"""Queue management operators."""

from __future__ import annotations

import os
import subprocess
import sys

import bpy  # type: ignore
from bpy.props import EnumProperty, IntProperty  # type: ignore
from bpy.types import Operator  # type: ignore

from .handlers import register_handlers
from .jobs import apply_job
from .properties import (
    RQM_Job,
    _sync_stereo_tags_from_scene,
    get_job_view_layer_names,
    set_job_view_layer_names,
    sync_job_view_layers,
)
from .state import get_state
from .utils import _sanitize_component, view_layer_identifier_map

_STALL_POLL_THRESHOLD = 12


def _iter_layer_collections(lc):
    """Recursively yield all layer collections."""
    yield lc
    for child in lc.children:
        yield from _iter_layer_collections(child)


# ---- Local item callbacks (avoid lambda for Blender EnumProperty) ----
def _operator_scene_items(self, context):
    items = [(s.name, s.name, '') for s in bpy.data.scenes]
    return items or [('', '<no scenes>', '')]


def _enabled_view_layer_ids(mapping):
    selected = []
    for ident, layer in mapping.items():
        try:
            if getattr(layer, 'use', True):
                selected.append(ident)
        except Exception:
            selected.append(ident)
    return selected


def _prefill_job_view_layers(job, scn, mapping, fallback_layer):
    if not hasattr(job, 'view_layers'):
        return
    if not mapping:
        set_job_view_layer_names(job, scn, [])
        return
    identifiers = _enabled_view_layer_ids(mapping)
    if identifiers:
        names = [mapping[ident].name for ident in identifiers if ident in mapping]
        set_job_view_layer_names(job, scn, names, mapping)
        return
    if not fallback_layer:
        return
    fallback_name = getattr(fallback_layer, 'name', None)
    if fallback_name:
        set_job_view_layer_names(job, scn, [fallback_name], mapping)


__all__ = [
    'RQM_OT_AddFromCurrent',
    'RQM_OT_AddCamerasInScene',
    'RQM_OT_RemoveJob',
    'RQM_OT_ClearQueue',
    'RQM_OT_MoveJob',
    'RQM_OT_StartQueue',
    'RQM_OT_StopQueue',
    'RQM_OT_DuplicateJob',
    'RQM_OT_EnableAll',
    'RQM_OT_DisableAll',
    'RQM_OT_OpenOutputFolder',
    'RQM_OT_CreateFolders',
    'RQM_OT_SyncStereoTags',
    'RQM_OT_ToggleIndirectOnly',
    'RQM_OT_ToggleIndirectOnlyAll',
]


class RQM_OT_AddFromCurrent(Operator):
    bl_idname = 'rqm.add_from_current'
    bl_label = 'Add Job (Use current scene & camera)'
    bl_description = 'Add a job using the current scene, camera, and render settings'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = get_state(context)
        if st is None:
            self.report({'ERROR'}, 'Add-on not initialized.')
            return {'CANCELLED'}
        scn = context.scene
        job = st.queue.add()
        job.scene_name = scn.name
        job.camera_name = scn.camera.name if scn.camera else ''
        job.engine = scn.render.engine
        if hasattr(job, 'view_layers'):
            mapping = view_layer_identifier_map(scn)
            fallback_layer = None
            try:
                fallback_layer = context.view_layer if context.view_layer else None
            except Exception:
                fallback_layer = None
            _prefill_job_view_layers(job, scn, mapping, fallback_layer)
        job.res_x = scn.render.resolution_x
        job.res_y = scn.render.resolution_y
        job.percent = scn.render.resolution_percentage
        if hasattr(scn.render, "use_persistent_data"):
            job.use_persistent_data = bool(scn.render.use_persistent_data)
        else:
            job.use_persistent_data = False
        job.use_animation = False
        job.frame_start = scn.frame_start
        job.frame_end = scn.frame_end
        job.zero_index_numbering = True
        job.file_format = 'PNG'
        existing = scn.render.filepath or '//renders/'
        if (
            existing
            and not existing.endswith(('/', '\\'))
            and not os.path.isdir(bpy.path.abspath(existing))
        ):
            existing = os.path.dirname(existing) + os.sep
        job.output_path = existing or '//renders/'
        job.file_basename = 'render'
        job.use_comp_outputs = False
        job.comp_outputs_non_blocking = True
        job.comp_outputs.clear()
        # Stereoscopy defaults
        if hasattr(job, 'use_stereoscopy'):
            job.use_stereoscopy = False
        if hasattr(job, 'stereo_views_format'):
            job.stereo_views_format = 'STEREO_3D'
        cam_part = job.camera_name or 'noCam'
        job.name = f'{job.scene_name}_{cam_part}'
        st.active_index = len(st.queue) - 1
        self.report({'INFO'}, 'Job added.')
        return {'FINISHED'}


class RQM_OT_AddCamerasInScene(Operator):
    bl_idname = 'rqm.add_cameras_in_scene'
    bl_label = 'Add Jobs for all cameras in a scene'
    bl_description = 'Create one job per camera in the chosen scene'
    bl_options = {'REGISTER', 'UNDO'}
    scene_name: EnumProperty(name='Scene', items=_operator_scene_items)

    def invoke(self, context, event):
        if not self.scene_name and context.scene:
            self.scene_name = context.scene.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        st = get_state(context)
        if st is None:
            self.report({'ERROR'}, 'Add-on not initialized.')
            return {'CANCELLED'}
        scn = bpy.data.scenes.get(self.scene_name)
        if not scn:
            self.report({'ERROR'}, f"Scene '{self.scene_name}' not found.")
            return {'CANCELLED'}
        cams = [o for o in scn.objects if o.type == 'CAMERA']
        if not cams:
            self.report({'WARNING'}, 'No cameras in that scene.')
            return {'CANCELLED'}
        for cam in cams:
            job = st.queue.add()
            job.scene_name = scn.name
            job.camera_name = cam.name
            job.engine = scn.render.engine
            if hasattr(job, 'view_layers'):
                mapping = view_layer_identifier_map(scn)
                active_layer = None
                try:
                    active_layer = getattr(scn.view_layers, 'active', None)
                except Exception:
                    active_layer = None
                if not active_layer:
                    try:
                        active_layer = scn.view_layers[0]
                    except Exception:
                        active_layer = None
                _prefill_job_view_layers(job, scn, mapping, active_layer)
            job.res_x = scn.render.resolution_x
            job.res_y = scn.render.resolution_y
            job.percent = scn.render.resolution_percentage
            if hasattr(scn.render, "use_persistent_data"):
                job.use_persistent_data = bool(scn.render.use_persistent_data)
            else:
                job.use_persistent_data = False
            job.use_animation = False
            job.frame_start = scn.frame_start
            job.frame_end = scn.frame_end
            job.zero_index_numbering = True
            job.file_format = 'PNG'
            existing = scn.render.filepath or '//renders/'
            if (
                existing
                and not existing.endswith(('/', '\\'))
                and not os.path.isdir(bpy.path.abspath(existing))
            ):
                existing = os.path.dirname(existing) + os.sep
            job.output_path = existing or '//renders/'
            job.file_basename = cam.name
            job.name = f'{job.scene_name}_{_sanitize_component(cam.name)}'
            if hasattr(job, 'use_stereoscopy'):
                job.use_stereoscopy = False
            if hasattr(job, 'stereo_views_format'):
                job.stereo_views_format = 'STEREO_3D'
        st.active_index = len(st.queue) - 1
        self.report({'INFO'}, f'Added {len(cams)} jobs.')
        return {'FINISHED'}


class RQM_OT_RemoveJob(Operator):
    bl_idname = 'rqm.remove_job'
    bl_label = 'Remove Job'
    bl_description = 'Remove the selected job from the queue'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=-1)

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else st.active_index
        if 0 <= idx < len(st.queue):
            st.queue.remove(idx)
            st.active_index = min(idx, len(st.queue) - 1)
            self.report({'INFO'}, 'Job removed.')
            return {'FINISHED'}
        return {'CANCELLED'}


class RQM_OT_ClearQueue(Operator):
    bl_idname = 'rqm.clear_queue'
    bl_label = 'Clear All Jobs'
    bl_description = 'Remove all jobs from the queue'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        st.queue.clear()
        st.active_index = 0
        self.report({'INFO'}, 'Queue cleared.')
        return {'FINISHED'}


class RQM_OT_DuplicateJob(Operator):
    bl_idname = 'rqm.duplicate_job'
    bl_label = 'Duplicate Job'
    bl_description = 'Duplicate the selected job and its settings'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=-1)

    def execute(self, context):
        st = get_state(context)
        if st is None or not st.queue:
            return {'CANCELLED'}
        src_idx = self.index if self.index >= 0 else st.active_index
        if not (0 <= src_idx < len(st.queue)):
            return {'CANCELLED'}
        src = st.queue[src_idx]
        dst = st.queue.add()
        # Copy simple attributes
        for attr in [
            'enabled',
            'scene_name',
            'camera_name',
            'view_layers',
            'view_layer_selection',
            'engine',
            'res_x',
            'res_y',
            'percent',
            'use_persistent_data',
            'use_animation',
            'frame_start',
            'frame_end',
            'link_timeline_markers',
            'link_marker',
            'marker_name',
            'marker_offset',
            'link_end_marker',
            'end_marker_name',
            'end_marker_offset',
            'file_format',
            'output_path',
            'file_basename',
            'prefix_files_with_job_name',
            'suffix_output_folders_with_job',
            'rebase_numbering',
            'include_source_frame_number',
            'use_comp_outputs',
            'comp_outputs_non_blocking',
            'use_stereoscopy',
            'stereo_views_format',
            'stereo_extra_tags',
            'stereo_keep_plain',
            'use_tag_collection',
            'notes',
            'use_samples_override',
            'samples',
            'use_margin',
            'margin',
        ]:
            if hasattr(dst, attr) and hasattr(src, attr):
                setattr(dst, attr, getattr(src, attr))
        # Copy compositor outputs
        if hasattr(src, 'comp_outputs'):
            for out in src.comp_outputs:
                new_out = dst.comp_outputs.add()
                for a in [
                    'enabled',
                    'node_name',
                    'create_if_missing',
                    'base_source',
                    'base_file',
                    'use_node_named_subfolder',
                    'extra_subfolder',
                    'ensure_dirs',
                    'override_node_format',
                    'file_basename',
                ]:
                    if hasattr(out, a):
                        setattr(new_out, a, getattr(out, a))
                if hasattr(new_out, 'use_custom_encoding') and hasattr(out, 'use_custom_encoding'):
                    new_out.use_custom_encoding = out.use_custom_encoding
                if hasattr(new_out, 'encoding') and hasattr(out, 'encoding'):
                    try:
                        new_out.encoding.color_mode = out.encoding.color_mode
                        new_out.encoding.color_depth = out.encoding.color_depth
                        new_out.encoding.compression = out.encoding.compression
                        new_out.encoding.quality = out.encoding.quality
                        new_out.encoding.exr_codec = out.encoding.exr_codec
                    except Exception:
                        pass
        # Sync encoding
        if hasattr(dst, 'encoding') and hasattr(src, 'encoding'):
            try:
                dst.encoding.color_mode = src.encoding.color_mode
                dst.encoding.color_depth = src.encoding.color_depth
                dst.encoding.compression = src.encoding.compression
                dst.encoding.quality = src.encoding.quality
                dst.encoding.exr_codec = src.encoding.exr_codec
            except Exception:
                pass
        # Ensure view layer storage aligns with new scene
        target_scene = bpy.data.scenes.get(dst.scene_name) if dst.scene_name else None
        if target_scene:
            sync_job_view_layers(dst, target_scene)
        # Copy tag collection
        if hasattr(src, 'stereo_tags'):
            for t in src.stereo_tags:
                nt = dst.stereo_tags.add()
                nt.name = t.name
                nt.enabled = t.enabled
        dst.name = src.name + '_dup'
        st.active_index = len(st.queue) - 1
        self.report({'INFO'}, 'Job duplicated.')
        return {'FINISHED'}


class RQM_OT_MoveJob(Operator):
    bl_idname = 'rqm.move_job'
    bl_label = 'Move Job'
    bl_description = 'Move the selected job up or down in the queue'
    bl_options = {'REGISTER', 'UNDO'}
    direction: EnumProperty(items=[('UP', 'Up', ''), ('DOWN', 'Down', '')])

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        idx = st.active_index
        if self.direction == 'UP' and idx > 0:
            st.queue.move(idx, idx - 1)
            st.active_index -= 1
            return {'FINISHED'}
        if self.direction == 'DOWN' and idx < len(st.queue) - 1:
            st.queue.move(idx, idx + 1)
            st.active_index += 1
            return {'FINISHED'}
        return {'CANCELLED'}


class RQM_OT_StartQueue(Operator):
    bl_idname = 'rqm.start_queue'
    bl_label = 'Start Render Queue'
    bl_description = 'Start rendering all jobs in the queue in order'
    bl_options = {'REGISTER'}

    def execute(self, context):
        st = get_state(context)
        if st is None or st.running or not st.queue:
            return {'CANCELLED'}
        # Auto-save before rendering
        if getattr(st, 'auto_save', True):
            try:
                if bpy.data.is_saved:
                    bpy.ops.wm.save_mainfile()
            except Exception:
                pass
        # Reset job statuses
        for job in st.queue:
            if job.enabled:
                job.status = 'PENDING'
            else:
                job.status = 'SKIPPED'
        register_handlers()
        st.ui_prev_tab = getattr(st, 'ui_tab', 'QUEUE')
        st.ui_tab = 'STATS'
        st.running = True
        st.current_job_index = 0
        st.render_in_progress = False
        st.stall_polls = 0
        try:
            st.stats_lines.clear()
        except Exception:
            pass
        try:
            st.stats_progress = 0.0
            st.stats_status = 'Waiting for Blender render'
            st.stats_raw = ''
        except Exception:
            pass
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, 'Render queue started.')
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        st = get_state(context)
        if st is None or not st.running:
            return {'CANCELLED'}
        # Safety: ensure handlers stay registered (some Blender sessions may clear them on reload)
        try:
            register_handlers()
        except Exception:
            pass
        # Process jobs sequentially
        while st.current_job_index < len(st.queue) and not st.queue[st.current_job_index].enabled:
            st.current_job_index += 1
        if st.current_job_index >= len(st.queue):
            st.running = False
            st.current_job_index = -1
            st.stall_polls = 0
            try:
                st.ui_tab = getattr(st, 'ui_prev_tab', 'QUEUE') or 'QUEUE'
            except Exception:
                st.ui_tab = 'QUEUE'
            self.report({'INFO'}, 'Queue complete.')
            return {'FINISHED'}
        # Fallback: if we think a render is in progress but Blender reports none, advance
        if st.render_in_progress:
            job_running = True
            try:
                job_running = bpy.app.is_job_running('RENDER')
            except Exception:
                job_running = True
            if job_running:
                st.stall_polls = 0
                return {'PASS_THROUGH'}
            polls = max(0, getattr(st, 'stall_polls', 0)) + 1
            st.stall_polls = polls
            if polls < _STALL_POLL_THRESHOLD:
                return {'PASS_THROUGH'}
            st.stall_polls = 0
            print('[RQM] Detected stalled render flag, auto-advancing queue.')
            st.skip_increment = True  # prevent handler increment duplication
            st.render_in_progress = False
            st.current_job_index += 1
            return {'PASS_THROUGH'}
        job = st.queue[st.current_job_index]
        ok, msg = apply_job(job)
        if not ok:
            self.report({'ERROR'}, msg)
            job.status = 'FAILED'
            st.current_job_index += 1
            return {'PASS_THROUGH'}
        job.status = 'RENDERING'
        st.render_in_progress = True
        st.stall_polls = 0
        try:
            # Use EXEC_DEFAULT to avoid needing the Image Editor
            # foreground; more reliable unattended.
            if job.use_animation:
                bpy.ops.render.render('EXEC_DEFAULT', animation=True)
            else:
                bpy.ops.render.render('EXEC_DEFAULT', write_still=True)
            print(
                f"[RQM] Started render for job {st.current_job_index+1}/{len(st.queue)}: {job.name}"
            )
        except Exception as e:
            self.report({'ERROR'}, str(e))
            job.status = 'FAILED'
            st.render_in_progress = False
            st.current_job_index += 1
        return {'PASS_THROUGH'}


class RQM_OT_StopQueue(Operator):
    bl_idname = 'rqm.stop_queue'
    bl_label = 'Stop Render Queue'
    bl_description = 'Stop the render queue and reset state'
    bl_options = {'REGISTER'}

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        # Restore any margin-modified cameras
        try:
            from .jobs import restore_margin_cameras
            restore_margin_cameras()
        except Exception:
            pass
        st.running = False
        st.current_job_index = -1
        st.render_in_progress = False
        st.stall_polls = 0
        try:
            st.stats_lines.clear()
        except Exception:
            pass
        try:
            st.stats_progress = 0.0
            st.stats_status = 'Idle'
            st.stats_raw = ''
        except Exception:
            pass
        try:
            st.ui_tab = getattr(st, 'ui_prev_tab', 'QUEUE') or 'QUEUE'
        except Exception:
            st.ui_tab = 'QUEUE'
        self.report({'INFO'}, 'Queue stopped.')
        return {'FINISHED'}


class RQM_OT_EnableAll(Operator):
    bl_idname = 'rqm.enable_all'
    bl_label = 'Enable All Jobs'
    bl_description = 'Enable all jobs in the queue'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        for job in st.queue:
            job.enabled = True
        self.report({'INFO'}, 'All jobs enabled.')
        return {'FINISHED'}


class RQM_OT_DisableAll(Operator):
    bl_idname = 'rqm.disable_all'
    bl_label = 'Disable All Jobs'
    bl_description = 'Disable all jobs in the queue'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        for job in st.queue:
            job.enabled = False
        self.report({'INFO'}, 'All jobs disabled.')
        return {'FINISHED'}


class RQM_OT_CreateFolders(Operator):
    bl_idname = 'rqm.create_folders'
    bl_label = 'Create Folders'
    bl_description = 'Pre-create output directories for all enabled jobs'
    bl_options = {'REGISTER'}

    def execute(self, context):
        st = get_state(context)
        if st is None or not st.queue:
            self.report({'WARNING'}, 'No jobs in queue.')
            return {'CANCELLED'}
        from .comp import base_render_dir, comp_root_dir, job_root_dir, resolve_base_dir
        from .utils import _ensure_dir
        created = 0
        errors = []
        for job in st.queue:
            if not job.enabled:
                continue
            ok, err = _ensure_dir(job_root_dir(job))
            if not ok:
                errors.append(err)
                continue
            _ensure_dir(base_render_dir(job))
            if job.use_comp_outputs:
                _ensure_dir(comp_root_dir(job))
                for out in job.comp_outputs:
                    if not out.enabled:
                        continue
                    scn = bpy.data.scenes.get(job.scene_name)
                    if scn:
                        node_name = out.node_name or 'File Output'
                        base_dir, _ = resolve_base_dir(scn, job, out, node_name)
                        if base_dir:
                            _ensure_dir(bpy.path.abspath(base_dir))
            created += 1
        if errors:
            self.report({'WARNING'}, f'Created folders for {created} jobs, {len(errors)} errors.')
        else:
            self.report({'INFO'}, f'Created folders for {created} jobs.')
        return {'FINISHED'}


class RQM_OT_SyncStereoTags(Operator):
    bl_idname = 'rqm.sync_stereo_tags'
    bl_label = 'Sync Stereo Tags'
    bl_description = "Populate the active job's stereo tags from the scene's render views"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        st = get_state(context)
        if st is None or not (0 <= st.active_index < len(st.queue)):
            self.report({'WARNING'}, 'No job selected.')
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        _sync_stereo_tags_from_scene(job)
        self.report({'INFO'}, 'Stereo tags synced from scene.')
        return {'FINISHED'}


class RQM_OT_ToggleIndirectOnly(Operator):
    bl_idname = 'rqm.toggle_indirect_only'
    bl_label = 'Toggle Indirect (Layer)'
    bl_description = (
        'Exclude or include indirect-only collections in the active job\'s view layers'
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json

        st = get_state(context)
        if st is None or not (0 <= st.active_index < len(st.queue)):
            self.report({'WARNING'}, 'No job selected.')
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        scn = bpy.data.scenes.get(job.scene_name) if job.scene_name else None
        if not scn:
            self.report({'WARNING'}, 'Job scene not found.')
            return {'CANCELLED'}
        vl_names = get_job_view_layer_names(job)
        if not vl_names:
            vl_names = [vl.name for vl in scn.view_layers]

        try:
            tracked = json.loads(st.indirect_disabled_collections or '{}')
        except Exception:
            tracked = {}

        toggled = 0
        for vl in scn.view_layers:
            if vl.name not in vl_names:
                continue
            for lc in _iter_layer_collections(vl.layer_collection):
                if not getattr(lc, 'indirect_only', False):
                    continue
                key = f'{scn.name}|{vl.name}|{lc.name}'
                if key in tracked:
                    lc.exclude = False
                    del tracked[key]
                else:
                    lc.exclude = True
                    tracked[key] = True
                toggled += 1

        st.indirect_disabled_collections = json.dumps(tracked)
        self.report({'INFO'}, f'Toggled {toggled} indirect-only collections.')
        return {'FINISHED'}


class RQM_OT_ToggleIndirectOnlyAll(Operator):
    bl_idname = 'rqm.toggle_indirect_only_all'
    bl_label = 'Toggle Indirect (All)'
    bl_description = (
        'Exclude or include indirect-only collections across all view layers in the scene'
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json

        st = get_state(context)
        if st is None or not (0 <= st.active_index < len(st.queue)):
            self.report({'WARNING'}, 'No job selected.')
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        scn = bpy.data.scenes.get(job.scene_name) if job.scene_name else None
        if not scn:
            self.report({'WARNING'}, 'Job scene not found.')
            return {'CANCELLED'}

        try:
            tracked = json.loads(st.indirect_disabled_collections or '{}')
        except Exception:
            tracked = {}

        toggled = 0
        for vl in scn.view_layers:
            for lc in _iter_layer_collections(vl.layer_collection):
                if not getattr(lc, 'indirect_only', False):
                    continue
                key = f'{scn.name}|{vl.name}|{lc.name}'
                if key in tracked:
                    lc.exclude = False
                    del tracked[key]
                else:
                    lc.exclude = True
                    tracked[key] = True
                toggled += 1

        st.indirect_disabled_collections = json.dumps(tracked)
        self.report({'INFO'}, f'Toggled {toggled} indirect-only collections.')
        return {'FINISHED'}


class RQM_OT_OpenOutputFolder(Operator):
    bl_idname = 'rqm.open_output_folder'
    bl_label = 'Open Output Folder'
    bl_description = "Open the selected job's output folder in the file explorer"

    def execute(self, context):
        st = get_state(context)
        if not st or not (0 <= st.active_index < len(st.queue)):
            self.report({'WARNING'}, 'No job selected.')
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        from .comp import job_root_dir
        folder = job_root_dir(job)
        if not os.path.isdir(folder):
            folder = bpy.path.abspath(job.output_path or '//renders/')
        if not os.path.isdir(folder):
            self.report({'WARNING'}, f'Folder does not exist yet: {folder}')
            return {'CANCELLED'}
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}
