"""Compositor output related operators."""
from __future__ import annotations
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from typing import Any as _Any
from .state import get_state
import os, re, glob
from .comp import base_render_dir
from .properties import RQM_Job

__all__ = ['RQM_OT_Output_Add','RQM_OT_Output_Remove','RQM_OT_Output_Move','RQM_OT_DetectTags']

class RQM_OT_Output_Add(Operator):
    bl_idname = 'rqm.output_add'
    bl_label = 'Add Compositor Output'
    bl_description = 'Add a compositor File Output configuration to the active job.'
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
    bl_description = 'Remove the selected compositor output from the active job.'
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
    bl_description = 'Reorder the selected compositor output up or down.'
    bl_options = {'REGISTER','UNDO'}
    direction: _Any = EnumProperty(items=[('UP','Up',''),('DOWN','Down','')])
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
    bl_description = 'Scan the base output folder for additional stereo view tags and add them to the job.'
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
        # scan for patterns *_TAG <frame>.ext
        found = []
        tag_rx = re.compile(r'^.+?_([A-Za-z0-9]+)\s+\d+\.[^.]+$')
        for fp in glob.glob(os.path.join(bdir, '*')):
            name = os.path.basename(fp)
            m = tag_rx.match(name)
            if m:
                t = m.group(1).upper()
                if t not in {'L','R'} and t not in found:
                    found.append(t)
        # merge with existing collection
        existing = {t.name.upper() for t in job.stereo_tags}
        for t in found:
            if t not in existing:
                nt = job.stereo_tags.add(); nt.name = t; nt.enabled = True
        if found:
            job.use_tag_collection = True
            self.report({'INFO'}, f"Detected tags: {', '.join(found)}")
        else:
            self.report({'INFO'}, 'No additional tags detected.')
        return {'FINISHED'}
