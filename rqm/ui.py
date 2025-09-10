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
                col.prop(job, 'frame_start')
                col.prop(job, 'frame_end')
            col.separator()
            col.prop(job, 'file_format')
            col.prop(job, 'output_path')
            col.prop(job, 'file_basename')
            col.separator()
            col.prop(job, 'use_comp_outputs')
            if job.use_comp_outputs:
                rowo = col.row(align=True)
                rowo.operator('rqm.output_add', text='', icon='ADD')
                rowo.operator('rqm.output_remove', text='', icon='REMOVE')
                rowo.operator('rqm.output_move', text='', icon='TRIA_UP').direction='UP'
                rowo.operator('rqm.output_move', text='', icon='TRIA_DOWN').direction='DOWN'
                col.template_list('RQM_UL_Outputs','', job, 'comp_outputs', job, 'comp_outputs_index', rows=3)
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
