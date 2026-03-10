"""Compositor output related operators."""
from __future__ import annotations
import bpy  # type: ignore
from bpy.types import Operator  # type: ignore
from bpy.props import EnumProperty  # type: ignore
from .comp import get_compositor_node_tree
from .state import get_state

__all__ = [
    'RQM_OT_Output_Add', 'RQM_OT_Output_Remove', 'RQM_OT_Output_Move',
    'RQM_OT_PickFileOutputNode',
]


def _pick_node_items(self, context):
    """Dynamic enum items: list File Output nodes from the active job's scene."""
    items = []
    try:
        st = getattr(context.scene, 'rqm_state', None)
        if st and 0 <= st.active_index < len(st.queue):
            job = st.queue[st.active_index]
            scn = bpy.data.scenes.get(job.scene_name) if job.scene_name else None
            nt = get_compositor_node_tree(scn) if scn else None
            if nt:
                for node in nt.nodes:
                    if node.bl_idname == 'CompositorNodeOutputFile':
                        display = node.label or node.name
                        items.append((node.name, display, node.name))
    except Exception:
        pass
    if not items:
        try:
            scn = context.scene
            nt = get_compositor_node_tree(scn) if scn else None
            if nt:
                for node in nt.nodes:
                    if node.bl_idname == 'CompositorNodeOutputFile':
                        display = node.label or node.name
                        items.append((node.name, display, node.name))
        except Exception:
            pass
    if not items:
        items.append(('NONE', 'No File Output Nodes Found', 'Enable Use Nodes in the compositor and add a File Output node'))
    return items


# Cache to prevent garbage collection of dynamic enum items
_pick_node_items_cache: list = []

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


class RQM_OT_PickFileOutputNode(Operator):
    bl_idname = 'rqm.pick_file_output_node'
    bl_label = 'Select File Output Node'
    bl_description = 'Pick a Compositor File Output node from the scene'
    bl_options = {'REGISTER', 'UNDO'}

    node: EnumProperty(name='Node', items=_pick_node_items)

    def execute(self, context):
        if self.node == 'NONE':
            self.report({'WARNING'}, 'No File Output nodes available')
            return {'CANCELLED'}
        st = get_state(context)
        if not (st and 0 <= st.active_index < len(st.queue)):
            return {'CANCELLED'}
        job = st.queue[st.active_index]
        idx = job.comp_outputs_index
        if 0 <= idx < len(job.comp_outputs):
            job.comp_outputs[idx].node_name = self.node
        return {'FINISHED'}

