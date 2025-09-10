"""Handlers for render lifecycle."""
from __future__ import annotations
import bpy
from .state import get_state

__all__ = ['register_handlers']

# We keep lightweight handlers and tag them to avoid duplicates.

def _tagged(hlist):
    return any(getattr(h, '_rqm_tag', False) for h in hlist)

def register_handlers():
    if not _tagged(bpy.app.handlers.render_complete):
        def _on_render_complete(_):
            st = bpy.context.scene.rqm_state
            st.render_in_progress = False
            if st.running and st.current_job_index < len(st.queue):
                st.current_job_index += 1
        _on_render_complete._rqm_tag = True
        bpy.app.handlers.render_complete.append(_on_render_complete)

    if not _tagged(bpy.app.handlers.render_cancel):
        def _on_render_cancel(_):
            st = bpy.context.scene.rqm_state
            st.render_in_progress = False
            if st.running and st.current_job_index < len(st.queue):
                st.current_job_index += 1
        _on_render_cancel._rqm_tag = True
        bpy.app.handlers.render_cancel.append(_on_render_cancel)
