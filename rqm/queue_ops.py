import bpy, os
from bpy.types import Operator
from .properties import RQM_State, RQM_Job
from .outputs import sync_one_output, base_render_dir
from .utils import sanitize_component, ensure_dir

__all__ = [
    'apply_job','get_state',
    'AddFromCurrent','AddCamerasInScene','RemoveJob','ClearQueue','MoveJob',
    'StartQueue','StopQueue','OutputAdd','OutputRemove','OutputMove','ApplyActiveJob',
    'register_handlers','JOB_PREPROCESSORS'
]

JOB_PREPROCESSORS = []  # functions(job, scene) -> (ok,msg) or (True,'')

# Global timer tracking (avoid setattr on WindowManager / Timer objects)
# Legacy versions stored a reference on the WindowManager as _rqm_active_timer / _rqm_active_run_id
# to simplify cleanup. New approach uses module globals (Blender can recreate WindowManager objects
# between sessions, so setattr was fragile). We keep a migration shim so existing sessions that still
# have the old attributes won't crash with AttributeError.
_RQM_ACTIVE_TIMER = None
_RQM_ACTIVE_RUN_ID = None

def _migrate_legacy_timer(wm):
    """If an older loaded version stored timer attributes on the WindowManager, migrate them.

    This prevents AttributeErrors when user updates the add-on without reloading Blender, where
    old operator instances may still reference the previous attribute-based storage.
    """
    global _RQM_ACTIVE_TIMER, _RQM_ACTIVE_RUN_ID
    migrated = False
    # Timer
    if _RQM_ACTIVE_TIMER is None and hasattr(wm, '_rqm_active_timer'):
        try:
            _RQM_ACTIVE_TIMER = getattr(wm, '_rqm_active_timer', None)
            delattr(wm, '_rqm_active_timer')
            migrated = True
        except Exception:
            pass
    # Run id
    if _RQM_ACTIVE_RUN_ID is None and hasattr(wm, '_rqm_active_run_id'):
        try:
            _RQM_ACTIVE_RUN_ID = getattr(wm, '_rqm_active_run_id', None)
            delattr(wm, '_rqm_active_run_id')
            migrated = True
        except Exception:
            pass
    return migrated

def get_state(context):
    scn = context.scene
    if not hasattr(scn, 'rqm_state'): return None
    return scn.rqm_state

def apply_job(job: RQM_Job):
    # Map picker selections to stored names (if enums present)
    if getattr(job, 'marker_picker', ''):
        job.marker_name = job.marker_picker
    if getattr(job, 'end_marker_picker', ''):
        job.end_marker_name = job.end_marker_picker

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

    # Stereo rename handler (per frame if supported else on render_post)
    import re
    def _stereo_rename():
        scn = bpy.context.scene
        st = getattr(scn, 'rqm_state', None)
        if not st or not st.running or st.current_job_index < 0 or st.current_job_index >= len(st.queue):
            return
        try:
            job = st.queue[st.current_job_index]
        except Exception:
            return
        if not getattr(job, 'use_stereoscopy', False):
            return
        if not getattr(job, 'stereo_view_before_frame', False):
            return
        try:
            from .outputs import base_render_dir
            from .utils import sanitize_component
            base_dir = base_render_dir(job)
            prefix = sanitize_component(job.file_basename or 'render')
        except Exception:
            return
        if not os.path.isdir(base_dir):
            return
        pat = re.compile(rf'^{re.escape(prefix)}(\d+)([A-Za-z]+)(\.[^.]+)$')
        try:
            for fname in os.listdir(base_dir):
                if not fname.startswith(prefix):
                    continue
                if ' ' in fname:
                    continue
                m = pat.match(fname)
                if not m:
                    continue
                frame, view, ext = m.groups()
                new_name = f"{prefix}{view} {frame}{ext}"
                src = os.path.join(base_dir, fname); dst = os.path.join(base_dir, new_name)
                if os.path.exists(dst):
                    continue
                try:
                    os.rename(src, dst)
                except Exception:
                    pass
        except Exception:
            pass

    # Prefer per-frame handler if available
    has_render_frame_post = hasattr(bpy.app.handlers, 'render_frame_post')
    target_list = None
    if has_render_frame_post:
        target_list = bpy.app.handlers.render_frame_post
        tag_name = 'frame'
    else:
        # Fallback: rename after each full render (single frame still fine, animation less granular)
        target_list = bpy.app.handlers.render_post
        tag_name = 'post'

    if not _tagged(target_list):
        def _on_any(_):
            _stereo_rename()
        _on_any._rqm_tag = True
        target_list.append(_on_any)

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
    _timer_tag = '_rqm_queue_timer'  # legacy tag string retained for compatibility (no attribute set on Timer now)

    def _schedule_next(self, wm, st):
        global _RQM_ACTIVE_TIMER, _RQM_ACTIVE_RUN_ID
        # Migrate any legacy attributes if user updated add-on without restarting Blender
        _migrate_legacy_timer(wm)
        # Remove existing queued timer if present
        if _RQM_ACTIVE_TIMER is not None:
            try:
                wm.event_timer_remove(_RQM_ACTIVE_TIMER)
            except Exception:
                pass
        timer = wm.event_timer_add(0.25, window=None)
        _RQM_ACTIVE_TIMER = timer
        _RQM_ACTIVE_RUN_ID = st.run_id
        wm.modal_handler_add(self)

    def _cleanup_timer(self, wm):
        global _RQM_ACTIVE_TIMER, _RQM_ACTIVE_RUN_ID
        # Also migrate (harmless if nothing to migrate) so we pick up legacy timer ref for removal
        _migrate_legacy_timer(wm)
        if _RQM_ACTIVE_TIMER is not None:
            try:
                wm.event_timer_remove(_RQM_ACTIVE_TIMER)
            except Exception:
                pass
        _RQM_ACTIVE_TIMER = None
        _RQM_ACTIVE_RUN_ID = None

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
        # Guard: stale timer from previous run using module globals
        from . import queue_ops as _qmod  # self-module reference for globals
        run_id = _qmod._RQM_ACTIVE_RUN_ID
        if run_id is not None and run_id != st.run_id:
            return {'CANCELLED'}
        if st.current_job_index >= len(st.queue):
            st.running = False; st.current_job_index = -1
            # Cleanup timer when finished
            self._cleanup_timer(context.window_manager)
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
        # Cleanup any active timer
        try:
            starter = StartQueue
            starter()._cleanup_timer(context.window_manager)
        except Exception:
            pass
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

class ApplyActiveJob(Operator):
    bl_idname = 'rqm.apply_active_job'
    bl_label = 'Apply Now'
    bl_description = 'Apply the active job settings (useful after changing marker offsets)'
    bl_options = {'REGISTER'}
    def execute(self, context):
        st = get_state(context)
        if st is None or not (0 <= st.active_index < len(st.queue)):
            self.report({'WARNING'}, 'No active job')
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        ok,msg = apply_job(job)
        if not ok:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}
        self.report({'INFO'}, 'Job applied')
        return {'FINISHED'}

CLASSES = (
    AddFromCurrent, AddCamerasInScene, RemoveJob, ClearQueue, MoveJob,
    StartQueue, StopQueue, OutputAdd, OutputRemove, OutputMove, ApplyActiveJob
)

def register():
    for c in CLASSES:
        bpy.utils.register_class(c)

def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    # Ensure any active timer is cleaned up if addon is disabled
    try:
        from . import queue_ops as _qmod
        if _qmod._RQM_ACTIVE_TIMER is not None:
            wm = bpy.context.window_manager if getattr(bpy.context, 'window_manager', None) else None
            if wm is not None:
                try:
                    wm.event_timer_remove(_qmod._RQM_ACTIVE_TIMER)
                except Exception:
                    pass
        _qmod._RQM_ACTIVE_TIMER = None
        _qmod._RQM_ACTIVE_RUN_ID = None
    except Exception:
        pass
