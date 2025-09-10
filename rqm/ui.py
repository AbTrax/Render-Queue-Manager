"""UI Lists and Panels for the add-on (legacy layout parity)."""
from __future__ import annotations
import bpy
from bpy.types import UIList, Panel
from .state import get_state

__all__ = ['RQM_UL_Queue','RQM_UL_Outputs','RQM_PT_Panel']

class RQM_UL_Queue(UIList):
    bl_idname = 'RQM_UL_Queue'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False, icon='RENDER_RESULT')
            cam_part = item.camera_name or '<no cam>'
            row.label(text=f"{item.scene_name} / {cam_part}")
        else:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='RENDER_RESULT')

class RQM_UL_Outputs(UIList):
    bl_idname = 'RQM_UL_Outputs'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            row.prop(item, 'node_name', text='', emboss=True, icon='NODE_COMPOSITING')
        else:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='NODE_COMPOSITING')

class RQM_PT_Panel(Panel):
    bl_label = 'Render Queue Manager'
    bl_idname = 'RQM_PT_panel'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'output'
    def draw(self, context):
        layout = self.layout
        st = get_state(context)
        if st is None:
            box = layout.box()
            box.label(text='Render Queue Manager not initialized.', icon='ERROR')
            box.label(text='Try disabling & re-enabling the add-on.')
            return

        row = layout.row(align=True)
        row.operator('rqm.add_from_current', icon='ADD')
        row.operator('rqm.add_cameras_in_scene', icon='OUTLINER_OB_CAMERA')
        row.operator('rqm.clear_queue', icon='TRASH')

        layout.template_list('RQM_UL_Queue', '', st, 'queue', st, 'active_index', rows=6)

        if 0 <= st.active_index < len(st.queue):
            job = st.queue[st.active_index]
            scn_for_job = bpy.data.scenes.get(job.scene_name)

            box = layout.box()
            box.prop(job, 'name')

            row = box.row()
            row.prop(job, 'scene_name', text='Scene')
            row.prop(job, 'camera_name', text='Camera')

            row = box.row()
            row.prop(job, 'engine', text='Render Engine')

            col = box.column(align=True)
            col.label(text='Resolution')
            rr = col.row(align=True)
            rr.prop(job, 'res_x'); rr.prop(job, 'res_y'); rr.prop(job, 'percent')

            col.separator()
            col.prop(job, 'use_animation')
            if job.use_animation:
                rr = col.row(align=True)
                rr.prop(job, 'frame_start'); rr.prop(job, 'frame_end')

                col.separator(); col.label(text='Use timeline markers (optional)', icon='MARKER_HLT')
                col.prop(job, 'link_marker')
                if job.link_marker:
                    r = col.row(align=True)
                    if scn_for_job:
                        r.prop_search(job, 'marker_name', scn_for_job, 'timeline_markers', text='Start Marker')
                    else:
                        r.prop(job, 'marker_name', text='Start Marker')
                    r.prop(job, 'marker_offset')
                col.prop(job, 'link_end_marker')
                if job.link_end_marker:
                    r2 = col.row(align=True)
                    if scn_for_job:
                        r2.prop_search(job, 'end_marker_name', scn_for_job, 'timeline_markers', text='End Marker')
                    else:
                        r2.prop(job, 'end_marker_name', text='End Marker')
                    r2.prop(job, 'end_marker_offset')

            col.separator()
            col.label(text='Standard Render Output', icon='FILE_FOLDER')
            col.prop(job, 'file_format'); col.prop(job, 'output_path'); col.prop(job, 'file_basename')

            col.separator()
            col.label(text='Compositor Outputs (optional)', icon='NODE_COMPOSITING')
            col.prop(job, 'use_comp_outputs')
            if job.use_comp_outputs:
                col.prop(job, 'comp_outputs_non_blocking')
                row = col.row()
                row.template_list('RQM_UL_Outputs', '', job, 'comp_outputs', job, 'comp_outputs_index', rows=3)
                col2 = row.column(align=True)
                col2.operator('rqm.output_add', icon='ADD', text='')
                col2.operator('rqm.output_remove', icon='REMOVE', text='')
                col2.separator()
                up = col2.operator('rqm.output_move', icon='TRIA_UP', text=''); up.direction='UP'
                dn = col2.operator('rqm.output_move', icon='TRIA_DOWN', text=''); dn.direction='DOWN'

                if 0 <= job.comp_outputs_index < len(job.comp_outputs):
                    out = job.comp_outputs[job.comp_outputs_index]
                    sub = col.box()
                    sub.prop(out, 'enabled')
                    if scn_for_job and scn_for_job.node_tree:
                        sub.prop_search(out, 'node_name', scn_for_job.node_tree, 'nodes', text='File Output Node')
                    else:
                        sub.prop(out, 'node_name', text='File Output Node')
                    sub.prop(out, 'create_if_missing')
                    sub.prop(out, 'override_node_format')

                    sub.separator(); sub.label(text='Save location', icon='FILE_FOLDER')
                    sub.prop(out, 'base_source', text='Base folder')
                    if out.base_source == 'FROM_FILE':
                        sub.prop(out, 'base_file')
                    sub.prop(out, 'use_node_named_subfolder')
                    sub.prop(out, 'extra_subfolder')
                    sub.prop(out, 'ensure_dirs')

        layout.separator()
        row = layout.row(align=True)
        if not st.running:
            row.operator('rqm.start_queue', icon='RENDER_ANIMATION')
        else:
            row.operator('rqm.stop_queue', icon='CANCEL')

        if st.running and st.current_job_index >= 0:
            layout.label(text=f'Running… Job {st.current_job_index + 1}/{len(st.queue)}')
        else:
            layout.label(text='Idle')
