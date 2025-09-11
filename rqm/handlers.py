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
    re.compile(r'^(?P<base>.+?)(?P<view>Left|Right|[A-Za-z]{2,})?(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + _ + letter/multi view (SceneCam0001_L.png / SceneCam0001_ALT.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)[_-](?P<view>[A-Za-z]+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + letter view appended (SceneCam0001L.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)(?P<view>[A-Za-z])(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + _ + view + frame (SceneCam_L0001.png / SceneCam_ALT0001.png)
    re.compile(r'^(?P<base>.+?)[_-](?P<view>[A-Za-z]+)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + word view + _ + frame (SceneCamLeft_0001.png / SceneCamALT_0001.png)
    re.compile(r'^(?P<base>.+?)(?P<view>[A-Za-z]+)[_-](?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
]
_plain_frame_pat = re.compile(r'^(?P<base>.+?)(?P<frame>\d{3,})(?P<ext>\.[^.]+)$')
_dup_token_sep = re.compile(r'[_\.]+')

def _parse_extra_tags(raw: str):
    tags = []
    if not raw:
        return tags
    for piece in re.split(r'[\s,;]+', raw):
        piece = piece.strip().upper()
        if not piece:
            continue
        # ensure only alnum letters
        piece = re.sub(r'[^A-Z0-9]', '', piece)
        if not piece:
            continue
        if piece not in tags and piece not in {'L','R','LEFT','RIGHT'}:
            tags.append(piece)
    return tags

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
        extra_tags = _parse_extra_tags(getattr(job, 'stereo_extra_tags', ''))
        # Build glob patterns for base tags L/R plus extras
        patterns = ['*Left*'+ext,'*Right*'+ext,'*_L'+ext,'*_R'+ext,'*-L'+ext,'*-R'+ext,'*L'+ext,'*R'+ext]
        for tag in extra_tags:
            patterns.extend([
                f'*_{tag}{ext}', f'*-{tag}{ext}', f'*{tag}*{ext}', f'*{tag}{ext}'
            ])
        processed = set()
        # Collect unsuffixed for potential spacing and later cleanup
        plain_candidates = []
        for root in list(search_roots):
            for path in glob.glob(os.path.join(root, '*'+ext)):
                plain_candidates.append(path)
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
                    view_norm = (view_raw or '').upper()
                    if view_norm in {'LEFT','L'}:
                        view_token = 'L'
                    elif view_norm in {'RIGHT','R'}:
                        view_token = 'R'
                    else:
                        # Use entire view_norm (multi-letter) for extra tags
                        view_token = view_norm
                        if view_token not in extra_tags:
                            # Skip unknown tag patterns to avoid accidental renames
                            continue
                    # Deduplicate
                    parts = [p for p in _dup_token_sep.split(base.strip('_ .')) if p]
                    dedup = []
                    for p in parts:
                        if not dedup or dedup[-1].lower() != p.lower():
                            dedup.append(p)
                    clean_base = '_'.join(dedup)
                    new_name = f"{clean_base}_{view_token} {frame}{ext_full}"
                    if new_name != name:
                        new_path = os.path.join(root, new_name)
                        if not os.path.exists(new_path):
                            try:
                                os.replace(path, new_path)
                            except Exception:
                                pass
                    processed.add(path)
        # Pass 2: ensure space before frame for plain (non-view) files e.g. main.0010000 -> main.001 0000
        for path in plain_candidates:
            if path in processed or not os.path.isfile(path):
                continue
            name = os.path.basename(path)
            m = _plain_frame_pat.match(name)
            if not m:
                continue
            base = m.group('base')
            frame = m.group('frame')
            ext_full = m.group('ext')
            # Skip if base already ends with space or underscore + view letter pattern
            if base.endswith(' '):
                continue
            # Avoid touching if already has '_L ' or '_R '
            if base.endswith('_L') or base.endswith('_R'):
                continue
            new_name = f"{base} {frame}{ext_full}"
            if new_name != name:
                new_path = os.path.join(os.path.dirname(path), new_name)
                if not os.path.exists(new_path):
                    try:
                        os.replace(path, new_path)
                    except Exception:
                        pass
        # Pass 3: remove plain duplicates if all expected view variants exist and user disabled plain
        try:
            keep_plain = getattr(job, 'stereo_keep_plain', True)
            frame_index = {}
            for root in search_roots:
                for f in os.listdir(root):
                    if not f.lower().endswith(ext):
                        continue
                    plain = False
                    view = None
                    parts_split = f.rsplit(' ', 1)
                    if len(parts_split) == 2 and parts_split[1].split('.')[0].isdigit():
                        tag_part = parts_split[0]
                        frame_no = parts_split[1].split('.')[0]
                        key = (root, frame_no)
                        # Determine tag: suffix after last underscore
                        tag_candidate = None
                        if '_' in tag_part:
                            tag_candidate = tag_part.split('_')[-1]
                        if tag_candidate in {'L','R'} or tag_candidate in extra_tags:
                            entry = frame_index.setdefault(key, {'views': set(), 'plain': []})
                            entry['views'].add(tag_candidate)
                        else:
                            pm = _plain_frame_pat.match(f)
                            if pm:
                                entry = frame_index.setdefault(key, {'views': set(), 'plain': []})
                                entry['plain'].append(f)
                    else:
                        pm = _plain_frame_pat.match(f)
                        if pm:
                            frame_no = pm.group('frame')
                            key = (root, frame_no)
                            entry = frame_index.setdefault(key, {'views': set(), 'plain': []})
                            entry['plain'].append(f)
            expected = {'L','R'} | set(extra_tags)
            if not keep_plain:
                for (root, frame_no), info in frame_index.items():
                    if expected.issubset(info['views']) and info['plain']:
                        for fname in info['plain']:
                            try:
                                os.remove(os.path.join(root, fname))
                            except Exception:
                                pass
        except Exception:
            pass
    except Exception:
        pass
