bl_info = {
    'name': 'Render Queue Manager',
    'author': 'Xnom3d (modularized)',
    'version': (1, 10, 11),
    'blender': (3, 0, 0),
    'location': 'Properties > Output > Render Queue Manager',
    'description': 'Queue renders with per‑job folders & compositor outputs; modular package version.',
    'category': 'Render',
}

from .rqm.properties import RQM_CompOutput, RQM_Job, RQM_State
from .rqm.operators_queue import (
    RQM_OT_AddFromCurrent, RQM_OT_AddCamerasInScene, RQM_OT_RemoveJob, RQM_OT_ClearQueue,
    RQM_OT_MoveJob, RQM_OT_StartQueue, RQM_OT_StopQueue
)
from .rqm.operators_outputs import (
    RQM_OT_Output_Add, RQM_OT_Output_Remove, RQM_OT_Output_Move
)
from .rqm.ui import RQM_UL_Queue, RQM_UL_Outputs, RQM_PT_Panel
from .rqm import comp  # ensure compositor logic packaged

import bpy
from bpy.props import PointerProperty

classes = (
    RQM_CompOutput, RQM_Job, RQM_State,
    RQM_OT_AddFromCurrent, RQM_OT_AddCamerasInScene, RQM_OT_RemoveJob, RQM_OT_ClearQueue,
    RQM_OT_MoveJob, RQM_OT_StartQueue, RQM_OT_StopQueue,
    RQM_OT_Output_Add, RQM_OT_Output_Remove, RQM_OT_Output_Move,
    RQM_UL_Queue, RQM_UL_Outputs, RQM_PT_Panel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.rqm_state = PointerProperty(type=RQM_State)

def unregister():
    if hasattr(bpy.types.Scene, 'rqm_state'):
        del bpy.types.Scene.rqm_state
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == '__main__':
    register()
