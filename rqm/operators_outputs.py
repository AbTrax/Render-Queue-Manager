"""Compositor output related operators."""
from __future__ import annotations
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from .state import get_state
import os, re, glob
from .comp import base_render_dir
from .properties import RQM_Job

__all__ = ['RQM_OT_Output_Add','RQM_OT_Output_Remove','RQM_OT_Output_Move','RQM_OT_DetectTags']

class RQM_OT_Output_Add(Operator):
    bl_idname = 'rqm.output_add'
    bl_label = 'Add Compositor Output'
    bl_description = 'Add a new Compositor File Output mapping to this job'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)):
            return {'CANCELLED'}
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

class RQM_OT_Output_Remove(Operator):
    bl_idname = 'rqm.output_remove'
    bl_label = 'Remove Compositor Output'
    bl_description = 'Remove the selected Compositor File Output mapping'
    bl_options = {'REGISTER','UNDO'}
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)):
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        idx = job.comp_outputs_index
        if 0 <= idx < len(job.comp_outputs):
            job.comp_outputs.remove(idx)
            job.comp_outputs_index = min(idx, len(job.comp_outputs)-1)
        return {'FINISHED'}

class RQM_OT_Output_Move(Operator):
    bl_idname = 'rqm.output_move'
    bl_label = 'Move Compositor Output'
    bl_description = 'Move the selected Compositor File Output mapping up or down'
    bl_options = {'REGISTER','UNDO'}
    direction: EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)):
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        idx = job.comp_outputs_index
        if self.direction == 'UP' and idx > 0:
            job.comp_outputs.move(idx, idx-1)
            job.comp_outputs_index -= 1
            return {'FINISHED'}
        if self.direction == 'DOWN' and idx < len(job.comp_outputs)-1:
            job.comp_outputs.move(idx, idx+1)
            job.comp_outputs_index += 1
            return {'FINISHED'}
        return {'CANCELLED'}

class RQM_OT_DetectTags(Operator):
    bl_idname = 'rqm.detect_tags'
    bl_label = 'Detect View Tags'
    bl_description = 'Scan the output folder for alternate view tags and add them to the list'
    bl_options = {'REGISTER'}
    def execute(self, context):
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)):
            return {'CANCELLED'}
        job: RQM_Job = st.queue[st.active_index]
        bdir = base_render_dir(job)
        if not os.path.isdir(bdir):
            self.report({'WARNING'}, 'No base output directory yet.')
            return {'CANCELLED'}
        # Scan base folder, job root, and first-level subfolders for common view tag patterns
        found = []
        job_root = os.path.dirname(bdir.rstrip('/\\'))
        search_roots = [bdir]
        if os.path.isdir(job_root):
            search_roots.append(job_root)
            try:
                for entry in os.listdir(job_root):
                    p = os.path.join(job_root, entry)
                    if os.path.isdir(p):
                        search_roots.append(p)
            except Exception:
                pass
        # Patterns similar to handlers: capture optional view token and frame
        view_patterns = [
            re.compile(r'^(?P<base>.+?)(?P<view>Left|Right|[A-Za-z0-9]{2,})?(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
            re.compile(r'^(?P<base>.+?)(?P<frame>\d+)[_-](?P<view>[A-Za-z0-9]+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
            re.compile(r'^(?P<base>.+?)(?P<frame>\d+)(?P<view>[A-Za-z])(?P<ext>\.[^.]+)$', re.IGNORECASE),
            re.compile(r'^(?P<base>.+?)[_-](?P<view>[A-Za-z0-9]+)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
            re.compile(r'^(?P<base>.+?)(?P<view>[A-Za-z0-9]+)[_-](?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
        ]
        for root in search_roots:
            try:
                for fname in os.listdir(root):
                    path = os.path.join(root, fname)
                    if not os.path.isfile(path):
                        continue
                    m = None
                    for rx in view_patterns:
                        m = rx.match(fname)
                        if m:
                            break
                    if not m:
                        continue
                    view_raw = (m.group('view') or '').upper()
                    if not view_raw:
                        continue
                    if view_raw in {'LEFT','L'}:
                        token = 'L'
                    elif view_raw in {'RIGHT','R'}:
                        token = 'R'
                    else:
                        token = re.sub(r'[^A-Z0-9]', '', view_raw)
                    if token and token not in {'L','R'} and token not in found:
                        found.append(token)
            except Exception:
                pass
        if hasattr(job, 'stereo_tags'):
            # merge with existing collection
            existing = {t.name.upper() for t in job.stereo_tags}
            for t in found:
                if t not in existing:
                    nt = job.stereo_tags.add(); nt.name = t; nt.enabled = True
            if found:
                if hasattr(job, 'use_tag_collection'):
                    job.use_tag_collection = True
                self.report({'INFO'}, f"Detected tags: {', '.join(found)}")
            else:
                self.report({'INFO'}, 'No additional tags detected.')
        else:
            # Fallback: update the free-text field
            current = getattr(job, 'stereo_extra_tags', '') or ''
            current_tokens = {tok.strip().upper() for tok in re.split(r'[\s,]+', current) if tok.strip()}
            new_tokens = [t for t in found if t not in current_tokens]
            if new_tokens:
                sep = ('' if current == '' else ' ')
                job.stereo_extra_tags = (current + sep + ' '.join(new_tokens)).strip()
                self.report({'INFO'}, f"Detected tags (free-text): {', '.join(new_tokens)}")
            else:
                self.report({'INFO'}, 'No additional tags detected.')
        return {'FINISHED'}
