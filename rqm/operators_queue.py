"""Queue management operators."""
from __future__ import annotations
import os
import bpy  # type: ignore
from bpy.types import Operator
from bpy.props import IntProperty, EnumProperty
from .state import get_state
from .properties import RQM_Job
from .handlers import register_handlers
from .utils import _sanitize_component, _ensure_dir
from .comp import base_render_dir
from .jobs import apply_job

# ---- Local item callbacks (avoid lambda for Blender EnumProperty) ----
def _operator_scene_items(self, context):
    items = [(s.name, s.name, '') for s in bpy.data.scenes]
    return items or [('','<no scenes>','')]

__all__ = [
    'RQM_OT_AddFromCurrent','RQM_OT_AddCamerasInScene','RQM_OT_RemoveJob','RQM_OT_ClearQueue',
    'RQM_OT_MoveJob','RQM_OT_StartQueue','RQM_OT_StopQueue'
]

class RQM_OT_AddFromCurrent(Operator):
    bl_idname = 'rqm.add_from_current'
    bl_label = 'Add Job (Use current scene & camera)'
    bl_options = {'REGISTER','UNDO'}
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
        job.res_x = scn.render.resolution_x
        job.res_y = scn.render.resolution_y
        job.percent = scn.render.resolution_percentage
        job.use_animation = False
        job.frame_start = scn.frame_start
        job.frame_end = scn.frame_end
        job.zero_index_numbering = True
        job.file_format = 'PNG'
        existing = scn.render.filepath or '//renders/'
        if existing and not existing.endswith(('/', '\\')) and not os.path.isdir(bpy.path.abspath(existing)):
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
        st.active_index = len(st.queue)-1
        self.report({'INFO'}, 'Job added.')
        return {'FINISHED'}

class RQM_OT_AddCamerasInScene(Operator):
    bl_idname = 'rqm.add_cameras_in_scene'
    bl_label = 'Add Jobs for all cameras in a scene'
    bl_options = {'REGISTER','UNDO'}
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
            job.res_x = scn.render.resolution_x
            job.res_y = scn.render.resolution_y
            job.percent = scn.render.resolution_percentage
            job.use_animation = False
            job.frame_start = scn.frame_start
            job.frame_end = scn.frame_end
            job.zero_index_numbering = True
            job.file_format = 'PNG'
            existing = scn.render.filepath or '//renders/'
            if existing and not existing.endswith(('/', '\\')) and not os.path.isdir(bpy.path.abspath(existing)):
                existing = os.path.dirname(existing) + os.sep
            job.output_path = existing or '//renders/'
            job.file_basename = cam.name
            job.name = f'{job.scene_name}_{_sanitize_component(cam.name)}'
            if hasattr(job, 'use_stereoscopy'):
                job.use_stereoscopy = False
            if hasattr(job, 'stereo_views_format'):
                job.stereo_views_format = 'STEREO_3D'
        st.active_index = len(st.queue)-1
        self.report({'INFO'}, f'Added {len(cams)} jobs.')
        return {'FINISHED'}

class RQM_OT_RemoveJob(Operator):
    bl_idname = 'rqm.remove_job'
    bl_label = 'Remove Job'
    bl_options = {'REGISTER','UNDO'}
    index: IntProperty(default=-1)
    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else st.active_index
        if 0 <= idx < len(st.queue):
            st.queue.remove(idx)
            st.active_index = min(idx, len(st.queue)-1)
            self.report({'INFO'}, 'Job removed.')
            return {'FINISHED'}
        return {'CANCELLED'}

class RQM_OT_ClearQueue(Operator):
    bl_idname = 'rqm.clear_queue'
    bl_label = 'Clear All Jobs'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        st.queue.clear(); st.active_index = 0
        self.report({'INFO'}, 'Queue cleared.')
        return {'FINISHED'}

class RQM_OT_MoveJob(Operator):
    bl_idname = 'rqm.move_job'
    bl_label = 'Move Job'
    bl_options = {'REGISTER','UNDO'}
    direction: EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        idx = st.active_index
        if self.direction == 'UP' and idx > 0:
            st.queue.move(idx, idx-1)
            st.active_index -= 1
            return {'FINISHED'}
        if self.direction == 'DOWN' and idx < len(st.queue)-1:
            st.queue.move(idx, idx+1)
            st.active_index += 1
            return {'FINISHED'}
        return {'CANCELLED'}

 # apply_job now imported from jobs module

class RQM_OT_StartQueue(Operator):
    bl_idname = 'rqm.start_queue'
    bl_label = 'Start Render Queue'
    bl_options = {'REGISTER'}
    def execute(self, context):
        st = get_state(context)
        if st is None or st.running or not st.queue:
            return {'CANCELLED'}
        register_handlers()
        st.running = True; st.current_job_index = 0; st.render_in_progress = False
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
        if st.current_job_index >= len(st.queue):
            st.running = False
            st.current_job_index = -1
            self.report({'INFO'}, 'Queue complete.')
            return {'FINISHED'}
        # Fallback: if we think a render is in progress but Blender reports none, advance
        if st.render_in_progress:
            try:
                # bpy.app.is_job_running('RENDER') returns False when no render
                if not bpy.app.is_job_running('RENDER'):
                    print('[RQM] Detected stalled render flag, auto-advancing queue.')
                    st.render_in_progress = False
                    st.current_job_index += 1
                    return {'PASS_THROUGH'}
            except Exception:
                pass
            return {'PASS_THROUGH'}
        job = st.queue[st.current_job_index]
        ok, msg = apply_job(job)
        if not ok:
            self.report({'ERROR'}, msg)
            st.current_job_index += 1
            return {'PASS_THROUGH'}
        st.render_in_progress = True
        try:
            # Use EXEC_DEFAULT for reliability when non-interactive / background focus loss
            if job.use_animation:
                bpy.ops.render.render('EXEC_DEFAULT', animation=True)
            else:
                bpy.ops.render.render('EXEC_DEFAULT', write_still=True)
            print(f"[RQM] Started render for job {st.current_job_index+1}/{len(st.queue)}: {job.name}")
        except Exception as e:
            self.report({'ERROR'}, str(e))
            st.render_in_progress = False
            st.current_job_index += 1
        return {'PASS_THROUGH'}

class RQM_OT_StopQueue(Operator):
    bl_idname = 'rqm.stop_queue'
    bl_label = 'Stop Render Queue'
    bl_options = {'REGISTER'}
    def execute(self, context):
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        st.running = False; st.current_job_index = -1; st.render_in_progress = False
        self.report({'INFO'}, 'Queue stopped.')
        return {'FINISHED'}
