"""Compositor output related operators."""
from __future__ import annotations
import bpy  # type: ignore
from bpy.types import Operator  # type: ignore
from bpy.props import EnumProperty  # type: ignore
from .state import get_state

__all__ = ['RQM_OT_Output_Add','RQM_OT_Output_Remove','RQM_OT_Output_Move']

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
        out.use_custom_encoding = False
        job_enc = getattr(job, 'encoding', None)
        out_enc = getattr(out, 'encoding', None)
        if out_enc and job_enc:
            try:
                out_enc.color_mode = job_enc.color_mode
                out_enc.color_depth = job_enc.color_depth
                out_enc.compression = job_enc.compression
                out_enc.quality = job_enc.quality
                out_enc.exr_codec = job_enc.exr_codec
            except Exception:
                pass
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

