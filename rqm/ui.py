"""UI Lists and Panels for the add-on."""
from __future__ import annotations
import bpy
from bpy.types import UIList, Panel
from bpy.props import StringProperty
from .state import get_state

__all__ = ['RQM_UL_Queue','RQM_UL_Outputs','RQM_PT_Panel']

class RQM_UL_Queue(UIList):
    bl_idname = 'RQM_UL_queue'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'name', text='', emboss=False)
            row.label(text=item.camera_name or '⟨no cam⟩')
            seg = f"{item.res_x}x{item.res_y}@{item.percent}%"
            row.label(text=seg)
        else:
            layout.label(text=item.name)

class RQM_UL_Outputs(UIList):
    bl_idname = 'RQM_UL_outputs'
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT','COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            row.prop(item, 'node_name', text='', emboss=True)
            row.label(text=item.base_source)
        else:
            layout.label(text=item.node_name or '<unnamed>')

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
            layout.label(text='State missing. Re-register add-on.', icon='ERROR')
            return
        row = layout.row(align=True)
        row.operator('rqm.add_from_current', icon='ADD')
        row.operator('rqm.add_cameras_in_scene', icon='OUTLINER_OB_CAMERA')
        row.operator('rqm.clear_queue', icon='TRASH')
        layout.template_list('RQM_UL_Queue','', st, 'queue', st, 'active_index', rows=6)
        if 0 <= st.active_index < len(st.queue):
            job = st.queue[st.active_index]
            box = layout.box()
            col = box.column(align=True)
            col.prop(job, 'name')
            col.prop(job, 'scene_name')
            col.prop(job, 'camera_name')
            col.prop(job, 'engine')
            col.separator()
            col.label(text='Resolution:')
            rowr = col.row(align=True)
            rowr.prop(job, 'res_x')
            rowr.prop(job, 'res_y')
            col.prop(job, 'percent')
            col.separator()
            col.prop(job, 'use_animation')
            if job.use_animation:
                sub = col.box()
                sub.label(text='Frame Range / Markers')
                rowf = sub.row(align=True)
                rowf.prop(job, 'frame_start')
                rowf.prop(job, 'frame_end')
                sub.prop(job, 'link_marker')
                if job.link_marker:
                    r = sub.row(align=True)
                    r.prop(job, 'marker_name')
                    r.prop(job, 'marker_offset')
                sub.prop(job, 'link_end_marker')
                if job.link_end_marker:
                    r2 = sub.row(align=True)
                    r2.prop(job, 'end_marker_name')
                    r2.prop(job, 'end_marker_offset')
            col.separator()
            col.label(text='Standard Render Output', icon='FILE_FOLDER')
            col.prop(job, 'file_format')
            col.prop(job, 'output_path')
            col.prop(job, 'file_basename')
            col.separator()
            col.label(text='Compositor Outputs', icon='NODE_COMPOSITING')
            col.prop(job, 'use_comp_outputs')
            if job.use_comp_outputs:
                col.prop(job, 'comp_outputs_non_blocking')
                rowo = col.row(align=True)
                rowo.operator('rqm.output_add', text='', icon='ADD')
                rowo.operator('rqm.output_remove', text='', icon='REMOVE')
                rowo.operator('rqm.output_move', text='', icon='TRIA_UP').direction='UP'
                rowo.operator('rqm.output_move', text='', icon='TRIA_DOWN').direction='DOWN'
                col.template_list('RQM_UL_Outputs','', job, 'comp_outputs', job, 'comp_outputs_index', rows=3)
                if 0 <= job.comp_outputs_index < len(job.comp_outputs):
                    out = job.comp_outputs[job.comp_outputs_index]
                    od = col.box()
                    od.label(text='Selected Output Settings')
                    od.prop(out, 'enabled')
                    scn_for_job = bpy.data.scenes.get(job.scene_name)
                    if scn_for_job and scn_for_job.node_tree:
                        od.prop_search(out, 'node_name', scn_for_job.node_tree, 'nodes', text='File Output Node')
                    else:
                        od.prop(out, 'node_name')
                    od.prop(out, 'create_if_missing')
                    od.prop(out, 'override_node_format')
                    od.separator()
                    od.label(text='Folder Logic', icon='FILE_FOLDER')
                    od.prop(out, 'base_source')
                    if out.base_source == 'FROM_FILE':
                        od.prop(out, 'base_file')
                    od.prop(out, 'use_node_named_subfolder')
                    od.prop(out, 'extra_subfolder')
                    od.prop(out, 'ensure_dirs')
        layout.separator()
        row = layout.row(align=True)
        if not st.running:
            row.operator('rqm.start_queue', icon='RENDER_ANIMATION')
        else:
            row.operator('rqm.stop_queue', icon='CANCEL')
        if st.running and st.current_job_index >= 0:
            layout.label(text=f'Running job {st.current_job_index+1}/{len(st.queue)}')
        else:
            layout.label(text='Idle')
