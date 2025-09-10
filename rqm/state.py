"""State helpers bridging properties and logic."""
from __future__ import annotations
import bpy

def get_state(context):
    scn = context.scene
    return getattr(scn, 'rqm_state', None)
