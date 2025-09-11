bl_info = {
    'name': 'Render Queue Manager',
    'author': 'Xnom3d',
    'version': (1, 11, 1),
    'blender': (3, 0, 0),
    'location': 'Properties > Output > Render Queue Manager',
    'description': 'Queue renders with per‑job folders & compositor outputs; modular package version.',
    'category': 'Render',
}

# --- Hot reload support ---
import importlib, sys
_submods = [
    '.rqm.utils', '.rqm.properties', '.rqm.jobs', '.rqm.comp',
    '.rqm.operators_queue', '.rqm.operators_outputs', '.rqm.ui', '.rqm.handlers'
]
_pkg_name = __name__
if any(m.startswith(_pkg_name + '.rqm') for m in list(sys.modules.keys())):
    for rel in _submods:
        full = _pkg_name + rel[1:]
        mod = sys.modules.get(full)
        if mod:
            try:
                importlib.reload(mod)
            except Exception:
                pass

from .rqm.properties import RQM_CompOutput, RQM_Job, RQM_State
from .rqm.operators_queue import (
    RQM_OT_AddFromCurrent, RQM_OT_AddCamerasInScene, RQM_OT_RemoveJob, RQM_OT_ClearQueue,
    RQM_OT_MoveJob, RQM_OT_StartQueue, RQM_OT_StopQueue,
    RQM_OT_DuplicateJob
)
from .rqm.operators_outputs import (
    RQM_OT_Output_Add, RQM_OT_Output_Remove, RQM_OT_Output_Move, RQM_OT_DetectTags
)
from .rqm.ui import RQM_UL_Queue, RQM_UL_Outputs, RQM_UL_Tags, RQM_PT_Panel
from .rqm import comp  # ensure compositor logic packaged
from .rqm import handlers  # ensure handlers module present (for reload)

import bpy
from bpy.props import PointerProperty

classes = (
    RQM_CompOutput, RQM_Job, RQM_State,
    RQM_OT_AddFromCurrent, RQM_OT_AddCamerasInScene, RQM_OT_RemoveJob, RQM_OT_ClearQueue,
    RQM_OT_MoveJob, RQM_OT_StartQueue, RQM_OT_StopQueue,
    RQM_OT_DuplicateJob,
    RQM_OT_Output_Add, RQM_OT_Output_Remove, RQM_OT_Output_Move, RQM_OT_DetectTags,
    RQM_UL_Queue, RQM_UL_Outputs, RQM_UL_Tags, RQM_PT_Panel,
)

def register():
    # Robust (re)registration: if a class is already registered, unregister then register
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except ValueError:
            try:
                bpy.utils.unregister_class(c)
            except Exception:
                pass
            try:
                bpy.utils.register_class(c)
            except Exception:
                pass
    if not hasattr(bpy.types.Scene, 'rqm_state'):
        bpy.types.Scene.rqm_state = PointerProperty(type=RQM_State)
    # (Re)register handlers each time register() runs
    try:
        handlers.register_handlers()
    except Exception:
        pass

def unregister():
    if hasattr(bpy.types.Scene, 'rqm_state'):
        try:
            del bpy.types.Scene.rqm_state
        except Exception:
            pass
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass

if __name__ == '__main__':
    register()
