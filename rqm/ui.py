import bpy
from bpy.types import UIList, Panel
from .properties import RQM_State

__all__ = ['QueueUI','OutputsUI','MainPanel']

class QueueUI(UIList):
    bl_idname = 'RQM_UL_Queue'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False, icon='RENDER_RESULT')
            row.label(text=f"{item.scene_name} / {item.camera_name or '<no cam>'}")
        else:
            layout.alignment = 'CENTER'; layout.label(text='', icon='RENDER_RESULT')

class OutputsUI(UIList):
    bl_idname = 'RQM_UL_Outputs'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            row.prop(item, 'node_name', text='', emboss=True, icon='NODE_COMPOSITING')
        else:
            layout.alignment = 'CENTER'; layout.label(text='', icon='NODE_COMPOSITING')

class MainPanel(Panel):
    bl_label = 'Render Queue Manager'
    bl_idname = 'RQM_PT_panel'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'output'
    def draw(self, context):
        layout = self.layout
        st = getattr(context.scene, 'rqm_state', None)
        if st is None:
            box = layout.box(); box.label(text='RQM not initialized', icon='ERROR')
            return
        row = layout.row(align=True)
        row.operator('rqm.add_from_current', icon='ADD')
        row.operator('rqm.add_cameras_in_scene', icon='OUTLINER_OB_CAMERA')
        row.operator('rqm.clear_queue', icon='TRASH')
        layout.template_list('RQM_UL_Queue', '', st, 'queue', st, 'active_index', rows=6)
        if 0 <= st.active_index < len(st.queue):
            job = st.queue[st.active_index]
            box = layout.box(); box.prop(job, 'name')
            row = box.row(); row.prop(job, 'scene_name'); row.prop(job, 'camera_name')
            row = box.row(); row.prop(job, 'engine')
            col = box.column(align=True)
            col.label(text='Resolution')
            rr = col.row(align=True); rr.prop(job, 'res_x'); rr.prop(job, 'res_y'); rr.prop(job, 'percent')
            col.separator(); col.prop(job, 'use_animation')
            if job.use_animation:
                fr = col.box()
                ar = fr.row(align=True); ar.prop(job, 'frame_start'); ar.prop(job, 'frame_end')
                fr.separator(); fr.label(text='Use timeline markers (optional)', icon='MARKER_HLT')
                fr.prop(job, 'link_marker')
                if job.link_marker:
                    if getattr(job, 'marker_picker', ''):
                        rmk = fr.row(align=True); rmk.prop(job, 'marker_picker'); rmk.prop(job, 'marker_offset')
                    else:
                        rmk = fr.row(align=True); rmk.prop(job, 'marker_name'); rmk.prop(job, 'marker_offset')
                fr.prop(job, 'link_end_marker')
                if job.link_end_marker:
                    if getattr(job, 'end_marker_picker', ''):
                        rme = fr.row(align=True); rme.prop(job, 'end_marker_picker'); rme.prop(job, 'end_marker_offset')
                    else:
                        rme = fr.row(align=True); rme.prop(job, 'end_marker_name'); rme.prop(job, 'end_marker_offset')
                apply_row = fr.row(align=True)
                apply_row.operator('rqm.apply_active_job', icon='CHECKMARK')
            col.separator(); col.label(text='Standard Output', icon='FILE_FOLDER')
            col.prop(job, 'file_format'); col.prop(job, 'output_path'); col.prop(job, 'file_basename')
            col.separator(); col.label(text='Stereoscopy', icon='CAMERA_STEREO')
            sr = col.row(align=True); sr.prop(job, 'use_stereoscopy', text='Enable Stereo')
            if job.use_stereoscopy:
                col.prop(job, 'stereo_views_format')
            col.separator(); col.label(text='Compositor Outputs', icon='NODE_COMPOSITING')
            col.prop(job, 'use_comp_outputs')
            if job.use_comp_outputs:
                col.prop(job, 'comp_outputs_non_blocking')
                rowo = col.row()
                rowo.template_list('RQM_UL_Outputs','', job, 'comp_outputs', job, 'comp_outputs_index', rows=3)
                col2 = rowo.column(align=True)
                col2.operator('rqm.output_add', icon='ADD', text='')
                col2.operator('rqm.output_remove', icon='REMOVE', text='')
                col2.separator()
                up = col2.operator('rqm.output_move', icon='TRIA_UP', text=''); up.direction='UP'
                dn = col2.operator('rqm.output_move', icon='TRIA_DOWN', text=''); dn.direction='DOWN'
                if 0 <= job.comp_outputs_index < len(job.comp_outputs):
                    out = job.comp_outputs[job.comp_outputs_index]
                    sub = col.box(); sub.prop(out, 'enabled')
                    scn_for_job = bpy.data.scenes.get(job.scene_name)
                    if scn_for_job and scn_for_job.node_tree:
                        sub.prop_search(out, 'node_name', scn_for_job.node_tree, 'nodes', text='File Output Node')
                    else:
                        sub.prop(out, 'node_name', text='File Output Node')
                    sub.prop(out, 'create_if_missing')
                    sub.prop(out, 'override_node_format')
                    sub.separator(); sub.label(text='Save Location', icon='FILE_FOLDER')
                    sub.prop(out, 'base_source')
                    if out.base_source == 'FROM_FILE':
                        sub.prop(out, 'base_file')
                    sub.prop(out, 'use_node_named_subfolder')
                    sub.prop(out, 'extra_subfolder')
                    sub.label(text='Tokens: {scene} {camera} {job} {node}', icon='INFO')
                    sub.prop(out, 'ensure_dirs')
        layout.separator()
        rowb = layout.row(align=True)
        if not st.running:
            rowb.operator('rqm.start_queue', icon='RENDER_ANIMATION')
        else:
            rowb.operator('rqm.stop_queue', icon='CANCEL')
        if st.running and st.current_job_index >= 0:
            layout.label(text=f"Running… Job {st.current_job_index + 1}/{len(st.queue)}")
        else:
            layout.label(text='Idle')

CLASSES = (QueueUI, OutputsUI, MainPanel)

def register():
    for c in CLASSES: bpy.utils.register_class(c)

def unregister():
    for c in reversed(CLASSES): bpy.utils.unregister_class(c)
