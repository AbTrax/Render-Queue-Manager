"""UI Lists and Panels for the add-on (legacy layout parity)."""

from __future__ import annotations

import os

import bpy  # type: ignore
from bpy.types import Panel, UIList  # type: ignore

from .comp import base_render_dir, job_file_prefix, resolve_base_dir
from .properties import get_job_view_layer_names
from .state import get_state

__all__ = ['RQM_UL_Queue', 'RQM_UL_Outputs', 'RQM_UL_Tags', 'RQM_PT_Panel']

_RENDER_EXTENSIONS = {
    'PNG': 'png',
    'JPEG': 'jpg',
    'JPG': 'jpg',
    'BMP': 'bmp',
    'TIFF': 'tiff',
    'TIF': 'tif',
    'OPEN_EXR': 'exr',
    'OPEN_EXR_MULTILAYER': 'exr',
}


def _frame_token(job):
    if getattr(job, 'use_animation', False):
        if getattr(job, 'rebase_numbering', False) and getattr(job, 'include_source_frame_number', True):
            return '####-####'
        return '####'
    return '0000'


def _standard_output_preview(job):
    try:
        base_dir = base_render_dir(job)
        prefix = job_file_prefix(job, base_dir, 'base')
        fmt = (getattr(job, 'file_format', '') or '').upper()
        ext = _RENDER_EXTENSIONS.get(fmt, fmt.lower() or 'ext')
        frame_token = _frame_token(job)
        sample_path = os.path.join(base_dir, f'{prefix}{frame_token}.{ext}')
        if str(getattr(job, 'output_path', '') or '').startswith('//'):
            try:
                return bpy.path.relpath(sample_path)
            except Exception:
                pass
        return os.path.normpath(sample_path)
    except Exception:
        return ''


def _compositor_output_preview(job, out, scn):
    if not out:
        return ''
    try:
        node_name = getattr(out, 'node_name', '') or 'File Output'
        base_dir, err = resolve_base_dir(scn, job, out, node_name)
        if err or not base_dir:
            return ''
        raw_base = base_dir
        abs_base = bpy.path.abspath(base_dir or '//')
        prefix = job_file_prefix(job, abs_base, 'comp', append_tokens=(node_name,))
        fmt = (getattr(job, 'file_format', '') or '').upper()
        ext = _RENDER_EXTENSIONS.get(fmt, fmt.lower() or 'ext')
        frame_token = _frame_token(job)
        sample_path = os.path.join(abs_base, f'{prefix}{frame_token}.{ext}')
        if str(raw_base).startswith('//'):
            try:
                return bpy.path.relpath(sample_path)
            except Exception:
                pass
        return os.path.normpath(sample_path)
    except Exception:
        return ''


def _draw_encoding_controls(layout, encoding, file_format):
    if not encoding:
        return
    fmt = (file_format or '').upper()
    layout.prop(encoding, 'color_mode')
    layout.prop(encoding, 'color_depth')
    if fmt in {'PNG', 'TIFF', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        layout.prop(encoding, 'compression')
    if fmt == 'JPEG':
        layout.prop(encoding, 'quality')
    if fmt in {'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}:
        layout.prop(encoding, 'exr_codec')


def _draw_stats_tab(layout, st):
    box = layout.box()
    try:
        has_queue = len(getattr(st, 'queue', [])) > 0
    except Exception:
        has_queue = False
    if (
        getattr(st, 'running', False)
        and getattr(st, 'current_job_index', -1) >= 0
        and has_queue
    ):
        try:
            job = st.queue[st.current_job_index]
            job_label = getattr(job, 'name', '') or f"{job.scene_name}:{job.camera_name or '<no cam>'}"
            box.label(text=f'Active Job: {job_label}', icon='RENDER_RESULT')
        except Exception:
            pass
    status = (getattr(st, 'stats_status', '') or 'Idle').strip()
    box.label(text=f'Status: {status}', icon='INFO')
    try:
        progress = float(getattr(st, 'stats_progress', 0.0) or 0.0)
    except Exception:
        progress = 0.0
    progress = max(0.0, min(progress, 1.0))
    progress_row = box.row()
    progress_row.enabled = False
    progress_row.prop(
        st,
        'stats_progress',
        text=f"Progress ({progress * 100:.1f}%)",
        slider=True,
    )
    lines = getattr(st, 'stats_lines', None)
    if not lines or len(lines) == 0:
        box.label(text='No render statistics available yet.', icon='TIME')
        return
    for entry in lines:
        label = (getattr(entry, 'label', '') or '').strip()
        value = (getattr(entry, 'value', '') or '').strip()
        row = box.row(align=True)
        if label and value:
            display_label = label if label.endswith(':') else f'{label}:'
            row.label(text=display_label)
            row.label(text=value)
        elif value:
            row.label(text=value)
        else:
            row.label(text=label or '-')


def _draw_queue_controls(layout, st):
    layout.separator()
    controls = layout.row(align=True)
    if not getattr(st, 'running', False):
        controls.operator('rqm.start_queue', icon='RENDER_ANIMATION')
    else:
        controls.operator('rqm.stop_queue', icon='CANCEL')
    if getattr(st, 'running', False) and getattr(st, 'current_job_index', -1) >= 0 and len(getattr(st, 'queue', [])) > 0:
        total = len(st.queue)
        display_idx = min(max(st.current_job_index, 0) + 1, total)
        layout.label(text=f'Running. Job {display_idx}/{total}')
    else:
        layout.label(text='Idle')


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
    bl_label = 'Render Queue Manager X'
    bl_idname = 'RQM_PT_panel'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'output'

    def draw(self, context):
        layout = self.layout
        st = get_state(context)
        if st is None:
            box = layout.box()
            box.label(text='Render Queue Manager X not initialized.', icon='ERROR')
            box.label(text='Try disabling & re-enabling the add-on.')
            return

        tab_row = layout.row(align=True)
        tab_row.prop(st, 'ui_tab', expand=True)
        if getattr(st, 'ui_tab', 'QUEUE') == 'STATS':
            _draw_stats_tab(layout, st)
            _draw_queue_controls(layout, st)
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
                selected_count = 0
                try:
                    selected_names = [name for name in get_job_view_layer_names(job) if name]
                    selected_count = len(selected_names)
                except Exception:
                    selected_names = []
                if not selected_count:
                    try:
                        raw_sel = getattr(job, 'view_layers', set())
                        if isinstance(raw_sel, str):
                            selected_count = 1 if raw_sel else 0
                        else:
                            selected_count = len({item for item in raw_sel if item})
                    except Exception:
                        selected_count = 0
                label = 'View Layers'
                if selected_count:
                    label = f'View Layers ({selected_count})'
                # prop_menu_enum opens a dropdown menu where items can be toggled (ENUM_FLAG)
                row.prop_menu_enum(job, 'view_layers', text=label, icon='DOWNARROW_HLT')

            row = box.row()
            row.prop(job, 'engine', text='Render Engine')
            if hasattr(job, 'use_persistent_data'):
                pd_row = box.row()
                pd_row.enabled = job.engine == 'CYCLES'
                pd_row.prop(job, 'use_persistent_data', text='Persistent Data (Cycles)')

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
            if hasattr(job, 'file_basename'):
                col.prop(job, 'file_basename', text='Filename prefix')
            if hasattr(job, 'prefix_files_with_job_name'):
                col.prop(job, 'prefix_files_with_job_name')
            preview = _standard_output_preview(job)
            if preview:
                col.label(text=f'Example file: {preview}', icon='FILE')
            enc_box = col.box()
            enc_box.label(text='Encoding', icon='COLOR')
            _draw_encoding_controls(enc_box, getattr(job, 'encoding', None), job.file_format)
            if hasattr(job, 'suffix_output_folders_with_job'):
                col.prop(job, 'suffix_output_folders_with_job')
            if job.use_animation and hasattr(job, 'rebase_numbering'):
                col.prop(job, 'rebase_numbering')
                if getattr(job, 'rebase_numbering', False) and hasattr(job, 'include_source_frame_number'):
                    col.prop(job, 'include_source_frame_number')

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
                    sub.prop(out, 'use_custom_encoding')
                    enc_info = sub.box()
                    if out.use_custom_encoding:
                        enc_info.label(text='Encoding', icon='COLOR')
                        _draw_encoding_controls(
                            enc_info,
                            getattr(out, 'encoding', None),
                            job.file_format if out.override_node_format else job.file_format,
                        )
                    elif out.override_node_format:
                        enc_info.label(text='Follows job encoding', icon='INFO')
                    else:
                        enc_info.label(text='Uses node encoding', icon='INFO')
                    sub.separator()
                    sub.label(text='Save location', icon='FILE_FOLDER')
                    sub.prop(out, 'base_source', text='Base')
                    if out.base_source == 'FROM_FILE':
                        sub.prop(out, 'base_file')
                    sub.prop(out, 'use_node_named_subfolder')
                    sub.prop(out, 'extra_subfolder')
                    sub.prop(out, 'ensure_dirs')
                    preview = _compositor_output_preview(job, out, scn_for_job)
                    if preview:
                        sub.label(text=f'Example file: {preview}', icon='FILE')

        _draw_queue_controls(layout, st)
