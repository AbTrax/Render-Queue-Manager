import bpy, os
from bpy.types import Operator
from .properties import RQM_State, RQM_Job
from .outputs import sync_one_output, base_render_dir
from .utils import sanitize_component, ensure_dir

__all__ = [
    'apply_job','get_state',
    'AddFromCurrent','AddCamerasInScene','RemoveJob','ClearQueue','MoveJob',
    'StartQueue','StopQueue','OutputAdd','OutputRemove','OutputMove',
    'register_handlers','JOB_PREPROCESSORS'
]

JOB_PREPROCESSORS = []  # functions(job, scene) -> (ok,msg) or (True,'')

def get_state(context):
    scn = context.scene
    if not hasattr(scn, 'rqm_state'): return None
    return scn.rqm_state

def apply_job(job: RQM_Job):
    scn = bpy.data.scenes.get(job.scene_name)
    if not scn: return False, f"Scene '{job.scene_name}' not found."
    try:
        bpy.context.window.scene = scn
    except Exception:
        pass
    try:
        scn.render.engine = job.engine
    except Exception:
        return False, f"Engine '{job.engine}' not available."
    if job.camera_name:
        cam_obj = bpy.data.objects.get(job.camera_name)
        if cam_obj and cam_obj.type == 'CAMERA':
            scn.camera = cam_obj
    scn.render.resolution_x = job.res_x
    scn.render.resolution_y = job.res_y
    scn.render.resolution_percentage = job.percent
    if job.use_animation:
        if job.link_marker:
            if not job.marker_name: return False, 'Missing start marker.'
            ms = scn.timeline_markers.get(job.marker_name)
            if not ms: return False, f"Start marker '{job.marker_name}' not found."
            start_frame = int(ms.frame) + int(job.marker_offset)
        else:
            start_frame = int(job.frame_start)
        if job.link_end_marker:
            if not job.end_marker_name: return False, 'Missing end marker.'
            me = scn.timeline_markers.get(job.end_marker_name)
            if not me: return False, f"End marker '{job.end_marker_name}' not found."
            end_frame = int(me.frame) + int(job.end_marker_offset)
        else:
            end_frame = int(job.frame_end)
        if end_frame < start_frame: end_frame = start_frame
        length = (end_frame - start_frame) + 1
        scn.frame_start = 0
        scn.frame_end = max(0, length-1)
        scn.frame_current = 0
    else:
        scn.frame_current = 0
    safe_base = sanitize_component(job.file_basename or 'render')
    scn.render.image_settings.file_format = job.file_format or 'PNG'
    brd = base_render_dir(job)
    ensure_dir(brd)
    scn.render.filepath = os.path.join(brd, '') + safe_base
    # Stereoscopy
    try:
        if job.use_stereoscopy:
            scn.render.use_multiview = True
            scn.render.views_format = job.stereo_views_format
        else:
            scn.render.use_multiview = False
    except Exception:
        pass
    # Preprocessors
    for fn in JOB_PREPROCESSORS:
        try:
            ok,msg = fn(job, scn)
            if not ok:
                return False, msg or 'Preprocessor failed'
        except Exception as e:
            print('[RQM Preprocessor Error]', e)
    if job.use_comp_outputs and len(job.comp_outputs) > 0:
        errors = []
        for out in job.comp_outputs:
            if not out.enabled: continue
            ok,msg = sync_one_output(scn, job, out)
            if not ok: errors.append(msg)
        if errors:
            for e in errors: print('[RQM Warning]', e)
            if not job.comp_outputs_non_blocking:
                return False, '; '.join(errors)
    return True, 'OK'

# ---------------- Handlers ----------------

def _tagged(hlist):
    return any(getattr(h, '_rqm_tag', False) for h in hlist)

def register_handlers():
    if not _tagged(bpy.app.handlers.render_complete):
        def _on_render_complete(_):
            st = bpy.context.scene.rqm_state
            st.render_in_progress = False
            if st.running and st.current_job_index < len(st.queue):
                st.current_job_index += 1
        _on_render_complete._rqm_tag = True
        bpy.app.handlers.render_complete.append(_on_render_complete)

    if not _tagged(bpy.app.handlers.render_cancel):
        def _on_render_cancel(_):
            st = bpy.context.scene.rqm_state
            st.render_in_progress = False
            if st.running and st.current_job_index < len(st.queue):
                st.current_job_index += 1
        _on_render_cancel._rqm_tag = True
        bpy.app.handlers.render_cancel.append(_on_render_cancel)

# ---------------- Operators ----------------
class AddFromCurrent(Operator):
    bl_idname = 'rqm.add_from_current'
    bl_label = 'Add Job (Current Scene/Camera)'
    bl_description = 'Add a new render job using the active scene and its current camera, copying basic render settings.'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if st is None:
            self.report({'ERROR'}, 'Addon not initialized')
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
        job.file_format = 'PNG'
        existing = scn.render.filepath or '//renders/'
        if existing and not existing.endswith(('/', '\\')) and not os.path.isdir(bpy.path.abspath(existing)):
            existing = os.path.dirname(existing) + os.sep
        job.output_path = existing or '//renders/'
        job.file_basename = 'render'
        job.use_comp_outputs = False
        job.comp_outputs_non_blocking = True
        job.comp_outputs.clear()
        cam_part = job.camera_name or 'noCam'
        job.name = f'{job.scene_name}_{cam_part}'
        st.active_index = len(st.queue)-1
        self.report({'INFO'}, 'Job added')
        return {'FINISHED'}

class AddCamerasInScene(Operator):
    bl_idname = 'rqm.add_cameras_in_scene'
    bl_label = 'Add Jobs for all cameras in a scene'
    bl_description = 'Create one job per camera found in the chosen scene.'
    bl_options = {'REGISTER','UNDO'}
    scene_name: bpy.props.EnumProperty(name='Scene', items=lambda self, ctx: [(s.name,s.name,'') for s in bpy.data.scenes])
    def invoke(self, context, event):
        if not self.scene_name and context.scene:
            self.scene_name = context.scene.name
        return context.window_manager.invoke_props_dialog(self)
    def execute(self, context):
        st = get_state(context)
        if st is None:
            self.report({'ERROR'}, 'Addon not initialized')
            return {'CANCELLED'}
        scn = bpy.data.scenes.get(self.scene_name)
        if not scn:
            self.report({'ERROR'}, f"Scene '{self.scene_name}' not found")
            return {'CANCELLED'}
        cams = [o for o in scn.objects if o.type == 'CAMERA']
        if not cams:
            self.report({'WARNING'}, 'No cameras in that scene')
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
            job.file_format = 'PNG'
            existing = scn.render.filepath or '//renders/'
            if existing and not existing.endswith(('/', '\\')) and not os.path.isdir(bpy.path.abspath(existing)):
                existing = os.path.dirname(existing) + os.sep
            job.output_path = existing or '//renders/'
            job.file_basename = cam.name
            job.use_comp_outputs = False
            job.comp_outputs_non_blocking = True
            job.comp_outputs.clear()
            job.name = f'{scn.name}_{cam.name}'
        st.active_index = len(st.queue)-1
        self.report({'INFO'}, f'Added {len(cams)} jobs')
        return {'FINISHED'}

class RemoveJob(Operator):
    bl_idname = 'rqm.remove_job'
    bl_label = 'Remove Job'
    bl_description = 'Remove the currently selected job from the queue.'
    bl_options = {'REGISTER','UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        st = get_state(context)
        if st is None: return {'CANCELLED'}
        idx = self.index if self.index >= 0 else st.active_index
        if 0 <= idx < len(st.queue):
            st.queue.remove(idx)
            st.active_index = max(0, min(st.active_index, len(st.queue)-1))
            return {'FINISHED'}
        return {'CANCELLED'}

class ClearQueue(Operator):
    bl_idname = 'rqm.clear_queue'
    bl_label = 'Clear All Jobs'
    bl_description = 'Remove all jobs from the queue.'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if st is None: return {'CANCELLED'}
        st.queue.clear(); st.active_index = 0
        return {'FINISHED'}

class MoveJob(Operator):
    bl_idname = 'rqm.move_job'
    bl_label = 'Move Job'
    bl_description = 'Move the selected job up or down in the queue order.'
    bl_options = {'REGISTER','UNDO'}
    direction: bpy.props.EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
    def execute(self, context):
        st = get_state(context)
        if st is None: return {'CANCELLED'}
        idx = st.active_index
        if self.direction=='UP' and idx>0:
            st.queue.move(idx, idx-1); st.active_index -= 1; return {'FINISHED'}
        if self.direction=='DOWN' and idx < len(st.queue)-1:
            st.queue.move(idx, idx+1); st.active_index += 1; return {'FINISHED'}
        return {'CANCELLED'}

class StartQueue(Operator):
    bl_idname = 'rqm.start_queue'
    bl_label = 'Start Render Queue'
    bl_description = 'Begin processing jobs sequentially until complete or stopped.'
    bl_options = {'REGISTER'}
    _timer_tag = '_rqm_queue_timer'

    def _schedule_next(self, wm, st):
        # Remove existing timer first
        for t in getattr(wm, 'event_timers', []):
            if getattr(t, self._timer_tag, False):
                wm.event_timer_remove(t)
        timer = wm.event_timer_add(0.25, window=None)
        setattr(timer, self._timer_tag, True)
        # Store run id reference on timer so old timers self-cancel if mismatched
        timer._rqm_run_id = st.run_id
        wm.modal_handler_add(self)

    def execute(self, context):
        st = get_state(context)
        if st is None:
            self.report({'ERROR'}, 'Addon not initialized')
            return {'CANCELLED'}
        if st.running:
            self.report({'WARNING'}, 'Queue already running')
            return {'CANCELLED'}
        if not st.queue:
            self.report({'WARNING'}, 'No jobs in the queue')
            return {'CANCELLED'}
        register_handlers()
        st.run_id += 1
        st.running = True; st.current_job_index = 0; st.render_in_progress = False
        self._schedule_next(context.window_manager, st)
        self.report({'INFO'}, 'Render queue started')
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        st = get_state(context)
        if st is None:
            return {'CANCELLED'}
        if not st.running:
            return {'FINISHED'}
        # Guard: stale timer from previous run
        if getattr(event, 'timer', None) and hasattr(event.timer, '_rqm_run_id'):
            if event.timer._rqm_run_id != st.run_id:
                return {'CANCELLED'}
        if st.current_job_index >= len(st.queue):
            st.running = False; st.current_job_index = -1
            self.report({'INFO'}, 'Render queue finished')
            return {'FINISHED'}
        if st.render_in_progress:
            return {'PASS_THROUGH'}
        job = st.queue[st.current_job_index]
        ok, msg = apply_job(job)
        if not ok:
            self.report({'WARNING'}, f'Skipping job: {msg}')
            st.current_job_index += 1
            return {'PASS_THROUGH'}
        st.render_in_progress = True
        # Render invocation: attempt to find a suitable window/area if context invalid
        try:
            # Prefer using override context to avoid dependency on current active area being Properties
            win = bpy.context.window
            area = None
            for a in win.screen.areas:
                if a.type in {'VIEW_3D','PROPERTIES'}:
                    area = a; break
            if area is not None:
                override = {'window': win, 'screen': win.screen, 'area': area, 'scene': bpy.context.scene}
                if job.use_animation:
                    bpy.ops.render.render(override, animation=True)
                else:
                    bpy.ops.render.render(override, write_still=True)
            else:
                if job.use_animation:
                    bpy.ops.render.render('INVOKE_DEFAULT', animation=True)
                else:
                    bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
        except Exception as e:
            self.report({'ERROR'}, f'Render failed: {e}')
            st.render_in_progress = False; st.current_job_index += 1
        return {'PASS_THROUGH'}

class StopQueue(Operator):
    bl_idname = 'rqm.stop_queue'
    bl_label = 'Stop Render Queue'
    bl_description = 'Stop the running render queue after the current render finishes or immediately if idle.'
    bl_options = {'REGISTER'}
    def execute(self, context):
        st = get_state(context)
        if st is None: return {'CANCELLED'}
        st.running = False; st.current_job_index = -1; st.render_in_progress = False
        self.report({'INFO'}, 'Queue stopped')
        return {'FINISHED'}

class OutputAdd(Operator):
    bl_idname = 'rqm.output_add'
    bl_label = 'Add Compositor Output'
    bl_description = 'Append a new Compositor File Output configuration to this job.'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)): return {'CANCELLED'}
        job = st.queue[st.active_index]
        out = job.comp_outputs.add()
        out.enabled = True
        out.create_if_missing = True
        out.base_source = 'JOB_OUTPUT'
        out.use_node_named_subfolder = True
        out.extra_subfolder = ''
        out.ensure_dirs = True
        out.override_node_format = True
        job.comp_outputs_index = len(job.comp_outputs)-1
        job.use_comp_outputs = True
        return {'FINISHED'}

class OutputRemove(Operator):
    bl_idname = 'rqm.output_remove'
    bl_label = 'Remove Compositor Output'
    bl_description = 'Delete the selected Compositor File Output configuration from this job.'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)): return {'CANCELLED'}
        job = st.queue[st.active_index]
        idx = job.comp_outputs_index
        if 0 <= idx < len(job.comp_outputs):
            job.comp_outputs.remove(idx)
            job.comp_outputs_index = max(0, min(job.comp_outputs_index, len(job.comp_outputs)-1))
        return {'FINISHED'}

class OutputMove(Operator):
    bl_idname = 'rqm.output_move'
    bl_label = 'Move Compositor Output'
    bl_description = 'Reorder a Compositor File Output configuration (move up or down).'
    bl_options = {'REGISTER','UNDO'}
    direction: bpy.props.EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)): return {'CANCELLED'}
        job = st.queue[st.active_index]
        idx = job.comp_outputs_index
        if self.direction=='UP' and idx>0:
            job.comp_outputs.move(idx, idx-1); job.comp_outputs_index -= 1; return {'FINISHED'}
        if self.direction=='DOWN' and idx < len(job.comp_outputs)-1:
            job.comp_outputs.move(idx, idx+1); job.comp_outputs_index += 1; return {'FINISHED'}
        return {'CANCELLED'}

CLASSES = (
    AddFromCurrent, AddCamerasInScene, RemoveJob, ClearQueue, MoveJob,
    StartQueue, StopQueue, OutputAdd, OutputRemove, OutputMove
)

def register():
    for c in CLASSES:
        bpy.utils.register_class(c)

def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
