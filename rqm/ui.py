"""UI Lists and Panels for Render Queue Manager X."""

from __future__ import annotations

import os

import bpy  # type: ignore
from bpy.types import Panel, UIList  # type: ignore

from .comp import base_render_dir, get_compositor_node_tree, job_file_prefix, resolve_base_dir
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
    # Queue progress and estimated time
    if getattr(st, 'running', False) and has_queue:
        total = len(st.queue)
        completed = sum(
            1 for j in st.queue if getattr(j, 'status', '') == 'COMPLETED'
        )
        enabled_total = sum(1 for j in st.queue if j.enabled)
        box.label(
            text=f'Queue: {completed}/{enabled_total} jobs completed',
            icon='SEQUENCE',
        )
        total_time = sum(
            getattr(j, 'last_render_time', 0.0)
            for j in st.queue
            if getattr(j, 'status', '') == 'COMPLETED'
        )
        if completed > 0:
            avg_time = total_time / completed
            remaining = sum(
                1 for j in st.queue
                if j.enabled and getattr(j, 'status', '') in ('PENDING', 'RENDERING')
            )
            eta = avg_time * remaining
            if eta >= 3600:
                eta_str = f'{eta / 3600:.1f}h'
            elif eta >= 60:
                eta_str = f'{eta / 60:.1f}m'
            else:
                eta_str = f'{eta:.0f}s'
            box.label(text=f'Estimated remaining: ~{eta_str}', icon='TIME')
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
    controls.prop(st, 'auto_save', text='', icon='FILE_TICK')
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


_STATUS_ICONS = {
    'COMPLETED': 'CHECKMARK',
    'FAILED': 'CANCEL',
    'RENDERING': 'RENDER_RESULT',
    'SKIPPED': 'FORWARD',
}


class RQM_UL_Queue(UIList):
    bl_idname = 'RQM_UL_Queue'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            sub = row.row(align=True)
            sub.enabled = item.enabled
            status = getattr(item, 'status', 'PENDING')
            status_icon = _STATUS_ICONS.get(status, 'RENDER_RESULT')
            sub.prop(item, 'name', text='', emboss=False, icon=status_icon)
            cam_part = item.camera_name or '<no cam>'
            sub.label(text=f"{item.scene_name}:{cam_part}")
            render_time = getattr(item, 'last_render_time', 0.0)
            if render_time > 0:
                if render_time >= 3600:
                    time_str = f'{render_time/3600:.1f}h'
                elif render_time >= 60:
                    time_str = f'{render_time/60:.1f}m'
                else:
                    time_str = f'{render_time:.1f}s'
                sub.label(text=time_str, icon='TIME')
        else:
            layout.alignment = 'CENTER'
            layout.label(text='', icon='RENDER_RESULT')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = list(range(len(items)))
        filter_name = self.filter_name
        if filter_name:
            filter_lower = filter_name.lower()
            for i, item in enumerate(items):
                name = (getattr(item, 'name', '') or '').lower()
                scene = (getattr(item, 'scene_name', '') or '').lower()
                cam = (getattr(item, 'camera_name', '') or '').lower()
                notes = (getattr(item, 'notes', '') or '').lower()
                if (filter_lower not in name and filter_lower not in scene
                        and filter_lower not in cam and filter_lower not in notes):
                    flt_flags[i] = 0
        return flt_flags, flt_neworder


class RQM_UL_Outputs(UIList):
    bl_idname = 'RQM_UL_Outputs'

    def _resolve_display_name(self, context, item):
        """Return the node label if available, otherwise the stored node_name."""
        name = item.node_name
        if not name:
            return '(no node)'
        try:
            st = getattr(context.scene, 'rqm_state', None)
            scn = None
            if st and 0 <= st.active_index < len(st.queue):
                job = st.queue[st.active_index]
                scn = bpy.data.scenes.get(job.scene_name) if job.scene_name else None
            if not scn:
                scn = context.scene
            nt = get_compositor_node_tree(scn)
            if nt:
                node = nt.nodes.get(name)
                if node:
                    return node.label or node.name
        except Exception:
            pass
        return name

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'enabled', text='')
            display = self._resolve_display_name(context, item)
            row.label(text=display, icon='NODE_COMPOSITING')
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
        if hasattr(st, 'ui_tab'):
            tab_row.prop(st, 'ui_tab', expand=True)
        if getattr(st, 'ui_tab', 'QUEUE') == 'STATS':
            _draw_stats_tab(layout, st)
            _draw_queue_controls(layout, st)
            return

        header = layout.row(align=True)
        header.operator('rqm.add_from_current', icon='ADD')
        header.operator('rqm.add_cameras_in_scene', icon='OUTLINER_OB_CAMERA')
        header.operator('rqm.clear_queue', icon='TRASH')

        toggle_row = layout.row(align=True)
        toggle_row.operator('rqm.enable_all', icon='CHECKBOX_HLT')
        toggle_row.operator('rqm.disable_all', icon='CHECKBOX_DEHLT')
        toggle_row.operator('rqm.create_folders', icon='NEWFOLDER')

        row_list = layout.row()
        row_list.template_list('RQM_UL_Queue', '', st, 'queue', st, 'active_index', rows=6)
        side = row_list.column(align=True)
        if 0 <= st.active_index < len(st.queue):
            dup = side.operator('rqm.duplicate_job', text='', icon='DUPLICATE')
            dup.index = st.active_index
            rem = side.operator('rqm.remove_job', text='', icon='X')
            rem.index = st.active_index
            side.separator()
            up = side.operator('rqm.move_job', text='', icon='TRIA_UP')
            up.direction = 'UP'
            dn = side.operator('rqm.move_job', text='', icon='TRIA_DOWN')
            dn.direction = 'DOWN'

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

            if hasattr(job, 'notes'):
                box.prop(job, 'notes', text='Notes', icon='TEXT')

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

            if hasattr(job, 'use_samples_override'):
                samp_row = box.row(align=True)
                samp_row.prop(job, 'use_samples_override')
                sub_samp = samp_row.row(align=True)
                sub_samp.enabled = getattr(job, 'use_samples_override', False)
                sub_samp.prop(job, 'samples', text='Samples')

            ind_row = box.row(align=True)
            ind_row.label(text='Indirect Collections:', icon='OUTLINER_COLLECTION')
            ind_row.operator('rqm.toggle_indirect_only', text='Toggle (Layer)')
            ind_row.operator('rqm.toggle_indirect_only_all', text='Toggle (All)')

            col = box.column(align=True)
            col.label(text='Resolution')
            rr = col.row(align=True)
            rr.prop(job, 'res_x')
            rr.prop(job, 'res_y')
            rr.prop(job, 'percent')

            if hasattr(job, 'use_margin') and hasattr(job, 'margin'):
                margin_row = col.row(align=True)
                margin_row.prop(job, 'use_margin')
                sub_margin = margin_row.row(align=True)
                sub_margin.enabled = getattr(job, 'use_margin', False)
                sub_margin.prop(job, 'margin', text='Margin (px)')
                if getattr(job, 'use_margin', False) and job.margin > 0:
                    eff_x = job.res_x + job.margin * 2
                    eff_y = job.res_y + job.margin * 2
                    col.label(text=f'Effective: {eff_x} x {eff_y}', icon='INFO')

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
            col.operator('rqm.open_output_folder', text='Open Output Folder', icon='FILEBROWSER')
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
                tag_row.operator('rqm.sync_stereo_tags', text='', icon='FILE_REFRESH')
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
                    # Node selection: single dropdown picker
                    _btn_label = out.node_name or 'Select Node\u2026'
                    if out.node_name and scn_for_job:
                        _nt = get_compositor_node_tree(scn_for_job)
                        if _nt:
                            _nd = _nt.nodes.get(out.node_name)
                            if _nd:
                                _btn_label = _nd.label or _nd.name
                    sub.operator_menu_enum(
                        'rqm.pick_file_output_node', 'node',
                        text=_btn_label,
                        icon='NODE_COMPOSITING',
                    )
                    sub.prop(out, 'create_if_missing')
                    sub.prop(out, 'override_node_format')
                    if hasattr(out, 'use_custom_encoding'):
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
                    elif out.override_node_format:
                        enc_info = sub.box()
                        enc_info.label(text='Follows job encoding', icon='INFO')
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
