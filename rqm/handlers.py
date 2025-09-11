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
            was_render = st.render_in_progress
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
            if st.running and was_render and not getattr(st, '_skip_increment_once', False) and st.current_job_index < len(st.queue):
                st.current_job_index += 1
            st._skip_increment_once = False
        _on_render_complete._rqm_tag = True
        bpy.app.handlers.render_complete.append(_on_render_complete)

    if not _tagged(bpy.app.handlers.render_cancel):
        def _on_render_cancel(_):
            st = bpy.context.scene.rqm_state
            was_render = st.render_in_progress
            st.render_in_progress = False
            if st.running and was_render and not getattr(st, '_skip_increment_once', False) and st.current_job_index < len(st.queue):
                st.current_job_index += 1
            st._skip_increment_once = False
        _on_render_cancel._rqm_tag = True
        bpy.app.handlers.render_cancel.append(_on_render_cancel)

# ---- Internal helpers ----

_EXT_MAP = {
    'PNG': '.png','JPEG': '.jpg','BMP': '.bmp','TIFF': '.tif','OPEN_EXR': '.exr'
}
_view_pat_variants = [
    # base + view word + frame (SceneCamLeft0001.png)
    re.compile(r'^(?P<base>.+?)(?P<view>Left|Right)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + _ + letter view (SceneCam0001_L.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)[_-](?P<view>[LR])(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + letter view appended (SceneCam0001L.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)(?P<view>[LR])(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + _ + letter view + frame (SceneCam_L0001.png)
    re.compile(r'^(?P<base>.+?)[_-](?P<view>[LR])(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + _ + word view + frame (SceneCam_Left0001.png)
    re.compile(r'^(?P<base>.+?)[_-](?P<view>Left|Right)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + word view + _ + frame (SceneCamLeft_0001.png)
    re.compile(r'^(?P<base>.+?)(?P<view>Left|Right)[_-](?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
]
_dup_token_sep = re.compile(r'[_\.]+')

def _stereo_rename(job):
    try:
        bdir = base_render_dir(job)
        if not os.path.isdir(bdir):
            return
        job_root = os.path.dirname(bdir.rstrip('/\\'))
        search_roots = [bdir]
        if os.path.isdir(job_root):
            search_roots.append(job_root)
            # add first-level subfolders of job root (e.g. compositor node subfolders)
            try:
                for entry in os.listdir(job_root):
                    p = os.path.join(job_root, entry)
                    if os.path.isdir(p):
                        search_roots.append(p)
            except Exception:
                pass
        ext = _EXT_MAP.get(job.file_format or 'PNG', '')
        patterns = ['*Left*'+ext,'*Right*'+ext,'*_L'+ext,'*_R'+ext,'*-L'+ext,'*-R'+ext,'*L'+ext,'*R'+ext]
        processed = set()
        for root in search_roots:
            for pat in patterns:
                for path in glob.glob(os.path.join(root, pat)):
                    if path in processed or not os.path.isfile(path):
                        continue
                    name = os.path.basename(path)
                    match = None
                    for rx in _view_pat_variants:
                        match = rx.match(name)
                        if match:
                            break
                    if not match:
                        continue
                    base = match.group('base')
                    view_raw = match.group('view')
                    frame = match.group('frame')
                    ext_full = match.group('ext')
                    letter = 'L' if view_raw.lower() in {'l','left'} else 'R'
                    # Deduplicate
                    parts = [p for p in _dup_token_sep.split(base.strip('_ .')) if p]
                    dedup = []
                    for p in parts:
                        if not dedup or dedup[-1].lower() != p.lower():
                            dedup.append(p)
                    clean_base = '_'.join(dedup)
                    new_name = f"{clean_base}_{letter} {frame}{ext_full}"
                    if new_name != name:
                        new_path = os.path.join(root, new_name)
                        if not os.path.exists(new_path):
                            try:
                                os.replace(path, new_path)
                            except Exception:
                                pass
                    processed.add(path)
    except Exception:
        pass
