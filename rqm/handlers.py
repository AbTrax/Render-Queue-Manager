"""Handlers for render lifecycle.

Adds a light post-render step to adjust stereoscopic filenames when the
user prefers view name before the frame number with a space, e.g.:
    renderLeft0001.png -> renderLeft 0001.png
This only runs if a job had stereoscopy enabled and files exist. Failures are silent.
"""
from __future__ import annotations
import bpy  # type: ignore
import os, re, glob
from .comp import base_render_dir
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
            # Attempt stereo rename for just-finished job (current_job_index points to finished job)
            try:
                idx = st.current_job_index
                if 0 <= idx < len(st.queue):
                    job = st.queue[idx]
                    if getattr(job, 'use_stereoscopy', False):
                        _stereo_rename(job)
            except Exception:
                pass
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

# ---- Internal helpers ----

_EXT_MAP = {
    'PNG': '.png','JPEG': '.jpg','BMP': '.bmp','TIFF': '.tif','OPEN_EXR': '.exr'
}
_view_pat = re.compile(r'^(?P<base>.+?)(Left|Right)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE)

def _stereo_rename(job):
    try:
        base_dir = base_render_dir(job)
        if not os.path.isdir(base_dir):
            return
        ext = _EXT_MAP.get(job.file_format or 'PNG', '')
        # Glob any Left/Right files regardless of extension to be safe
        for path in glob.glob(os.path.join(base_dir, '*Left*'+ext)) + glob.glob(os.path.join(base_dir, '*Right*'+ext)):
            name = os.path.basename(path)
            m = _view_pat.match(name)
            if not m:
                continue
            new_name = f"{m.group('base')}{'Left' if 'Left' in name else 'Right'} {m.group('frame')}{m.group('ext')}"
            if new_name != name:
                new_path = os.path.join(base_dir, new_name)
                if not os.path.exists(new_path):
                    try:
                        os.replace(path, new_path)
                    except Exception:
                        pass
    except Exception:
        pass
