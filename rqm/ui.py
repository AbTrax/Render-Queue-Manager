"""UI Lists and Panels for the add-on (legacy layout parity)."""

from __future__ import annotations

import bpy  # type: ignore
from bpy.types import Panel, UIList  # type: ignore

from .state import get_state

__all__ = ['RQM_UL_Queue', 'RQM_UL_Outputs', 'RQM_UL_Tags', 'RQM_PT_Panel']


class RQM_UL_Queue(UIList):
    bl_idname = 'RQM_UL_Queue'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            sub = row.row(align=True)
            sub.enabled = item.enabled
            sub.prop(item, 'name', text='', emboss=False, icon='RENDER_RESULT')
            cam_part = item.camera_name or '<no cam>'
            sub.label(text=f"{item.scene_name}:{cam_part}")
        else:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='RENDER_RESULT')


class RQM_UL_Outputs(UIList):
    bl_idname = 'RQM_UL_Outputs'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            # show as shorter label + editable text button
            split = row.split(factor=0.65, align=True)
            split.prop(item, 'node_name', text='', emboss=True, icon='NODE_COMPOSITING')
        else:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='NODE_COMPOSITING')


class RQM_UL_Tags(UIList):
    bl_idname = 'RQM_UL_Tags'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            row.prop(item, 'name', text='', emboss=True, icon='VIEW_CAMERA')
        else:
            layout.label(text=item.name)


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

        header = layout.row(align=True)
        header.operator('rqm.add_from_current', icon='ADD')
        header.operator('rqm.add_cameras_in_scene', icon='OUTLINER_OB_CAMERA')
        header.operator('rqm.clear_queue', icon='TRASH')

        row_list = layout.row()
        row_list.template_list('RQM_UL_Queue', '', st, 'queue', st, 'active_index', rows=6)
        side = row_list.column(align=True)
        if 0 <= st.active_index < len(st.queue):
            dup = side.operator('rqm.duplicate_job', text='', icon='DUPLICATE')
            dup.index = st.active_index
            rem = side.operator('rqm.remove_job', text='', icon='X')
            rem.index = st.active_index

        if 0 <= st.active_index < len(st.queue):
            job = st.queue[st.active_index]
            scn_for_job = bpy.data.scenes.get(job.scene_name)

            box = layout.box()
            top_row = box.row(align=True)
            # Make the Name field more flush with minimal left padding
            try:
                top_row.use_property_split = False
                top_row.use_property_decorate = False
            except Exception:
                pass
            top_row.prop(job, 'enabled', text='')
            top_row.prop(job, 'name', text='Name')

            row = box.row()
            row.prop(job, 'scene_name', text='Scene')
            row.prop(job, 'camera_name', text='Camera')
            if hasattr(job, 'view_layers'):
                # Cleaner multi-select as a dropdown with dynamic label
                row = box.row()
                try:
                    sel = getattr(job, 'view_layers', set())
                    if isinstance(sel, str):
                        selected = {sel} if sel else set()
                    else:
                        selected = set(sel)
                except Exception:
                    selected = set()
                label = 'View Layers'
                if selected:
                    label = f'View Layers ({len(selected)})'
                # prop_menu_enum opens a dropdown menu where items can be toggled (ENUM_FLAG)
                row.prop_menu_enum(job, 'view_layers', text=label, icon='DOWNARROW_HLT')

            row = box.row()
            row.prop(job, 'engine', text='Render Engine')

            col = box.column(align=True)
            col.label(text='Resolution')
            rr = col.row(align=True)
            rr.prop(job, 'res_x')
            rr.prop(job, 'res_y')
            rr.prop(job, 'percent')

            col.separator()
            col.prop(job, 'use_animation')
            if job.use_animation:
                fr = col.row(align=True)
                fr.enabled = not getattr(job, 'link_timeline_markers', False)
                fr.prop(job, 'frame_start')
                fr.prop(job, 'frame_end')
                col.separator()
                col.label(text='Timeline markers', icon='MARKER_HLT')
                col.prop(job, 'link_timeline_markers', text='Link timeline markers')
                if getattr(job, 'link_timeline_markers', False):
                    r = col.row(align=True)
                    if scn_for_job:
                        r.prop_search(
                            job, 'marker_name', scn_for_job, 'timeline_markers', text='Start'
                        )
                    else:
                        r.prop(job, 'marker_name', text='Start')
                    r.prop(job, 'marker_offset')
                    r2 = col.row(align=True)
                    if scn_for_job:
                        r2.prop_search(
                            job, 'end_marker_name', scn_for_job, 'timeline_markers', text='End'
                        )
                    else:
                        r2.prop(job, 'end_marker_name', text='End')
                    r2.prop(job, 'end_marker_offset')

            col.separator()
            col.label(text='Standard Output', icon='FILE_FOLDER')
            col.prop(job, 'file_format')
            col.prop(job, 'output_path')
            col.prop(job, 'file_basename')
            if hasattr(job, 'suffix_output_folders_with_job'):
                col.prop(job, 'suffix_output_folders_with_job')
            if job.use_animation and hasattr(job, 'rebase_numbering'):
                col.prop(job, 'rebase_numbering')

            col.separator()
            col.label(text='Stereoscopy', icon='CAMERA_STEREO')
            col.prop(job, 'use_stereoscopy')
            if getattr(job, 'use_stereoscopy', False):
                if hasattr(job, 'stereo_views_format'):
                    col.prop(job, 'stereo_views_format', text='Views')
                col.prop(job, 'stereo_extra_tags')
                col.prop(job, 'stereo_keep_plain')
                tag_row = col.row(align=True)
                if hasattr(job, 'use_tag_collection'):
                    tag_row.prop(job, 'use_tag_collection', text='Use Tag List')
                if getattr(job, 'use_tag_collection', False):
                    tag_box = col.box()
                    tag_box.template_list(
                        'RQM_UL_Tags', '', job, 'stereo_tags', job, 'stereo_tags_index', rows=3
                    )

            col.separator()
            col.label(text='Compositor Outputs', icon='NODE_COMPOSITING')
            col.prop(job, 'use_comp_outputs')
            if job.use_comp_outputs:
                col.prop(job, 'comp_outputs_non_blocking')
                row = col.row()
                row.template_list(
                    'RQM_UL_Outputs', '', job, 'comp_outputs', job, 'comp_outputs_index', rows=3
                )
                col2 = row.column(align=True)
                col2.operator('rqm.output_add', icon='ADD', text='')
                col2.operator('rqm.output_remove', icon='REMOVE', text='')
                col2.separator()
                up = col2.operator('rqm.output_move', icon='TRIA_UP', text='')
                up.direction = 'UP'
                dn = col2.operator('rqm.output_move', icon='TRIA_DOWN', text='')
                dn.direction = 'DOWN'
                if 0 <= job.comp_outputs_index < len(job.comp_outputs):
                    out = job.comp_outputs[job.comp_outputs_index]
                    sub = col.box()
                    sub.prop(out, 'enabled')
                    if scn_for_job and scn_for_job.node_tree:
                        sub.prop_search(
                            out,
                            'node_name',
                            scn_for_job.node_tree,
                            'nodes',
                            text='File Output Node',
                        )
                    else:
                        sub.prop(out, 'node_name', text='File Output Node')
                    sub.prop(out, 'create_if_missing')
                    sub.prop(out, 'override_node_format')
                    sub.separator()
                    sub.label(text='Save location', icon='FILE_FOLDER')
                    sub.prop(out, 'base_source', text='Base')
                    if out.base_source == 'FROM_FILE':
                        sub.prop(out, 'base_file')
                    sub.prop(out, 'use_node_named_subfolder')
                    sub.prop(out, 'extra_subfolder')
                    sub.prop(out, 'ensure_dirs')

        layout.separator()
        controls = layout.row(align=True)
        if not st.running:
            controls.operator('rqm.start_queue', icon='RENDER_ANIMATION')
        else:
            controls.operator('rqm.stop_queue', icon='CANCEL')
        if st.running and st.current_job_index >= 0:
            layout.label(text=f'Running… Job {st.current_job_index + 1}/{len(st.queue)}')
        else:
            layout.label(text='Idle')
