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

__all__ = ['register_handlers', 'unregister_handlers']

# We keep lightweight handlers and tag them to avoid duplicates.

def _tagged(hlist):
    return any(getattr(h, '_rqm_tag', False) for h in hlist)


_marker_cache = {}
_current_render_state = None
_STATS_PERCENT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*%')


def _active_state(scene=None):
    """Return the add-on state from the given scene or best-known context."""
    global _current_render_state
    if scene and hasattr(scene, 'rqm_state'):
        st = getattr(scene, 'rqm_state', None)
        if st:
            _current_render_state = st
            return st
    try:
        context_scene = bpy.context.scene
    except Exception:
        context_scene = None
    if context_scene and hasattr(context_scene, 'rqm_state'):
        st = getattr(context_scene, 'rqm_state', None)
        if st:
            _current_render_state = st
            return st
    return _current_render_state


def _reset_stats(st, status='Idle'):
    if not st:
        return
    try:
        st.stats_status = status
    except Exception:
        pass
    try:
        st.stats_progress = 0.0
    except Exception:
        pass
    try:
        st.stats_raw = ''
    except Exception:
        pass
    try:
        st.stats_lines.clear()
    except Exception:
        pass


def _apply_stats(st, stats):
    if not st:
        return
    text = str(stats or '').replace('\r\n', '\n').strip()
    previous = getattr(st, 'stats_progress', 0.0)
    found_progress = False
    try:
        st.stats_raw = text
    except Exception:
        pass
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    try:
        st.stats_lines.clear()
    except Exception:
        pass
    if not lines:
        return
    try:
        st.stats_status = lines[0]
    except Exception:
        pass
    for line in lines:
        if ':' in line:
            label, value = line.split(':', 1)
            label = label.strip()
            value = value.strip()
        else:
            label = line
            value = ''
        try:
            entry = st.stats_lines.add()
            entry.label = label
            entry.value = value
        except Exception:
            pass
        search_texts = (value, label)
        for chunk in search_texts:
            match = _STATS_PERCENT_RE.search(chunk)
            if match:
                try:
                    pct = float(match.group(1)) / 100.0
                    pct = max(0.0, min(pct, 1.0))
                    st.stats_progress = pct
                    found_progress = True
                    break
                except Exception:
                    pass
    if not found_progress:
        try:
            st.stats_progress = previous
        except Exception:
            pass


def _mark_status(st, status, progress=None):
    if not st:
        return
    try:
        st.stats_status = status
    except Exception:
        pass
    if progress is not None:
        try:
            st.stats_progress = progress
        except Exception:
            pass

def register_handlers():
    _marker_cache.clear()
    if not _tagged(bpy.app.handlers.render_complete):
        def _on_render_complete(scene):
            st = _active_state(scene)
            if not st:
                return
            was_render = st.render_in_progress
            st.render_in_progress = False
            # Attempt stereo rename for just-finished job (current_job_index points to finished job)
            try:
                idx = st.current_job_index
                if 0 <= idx < len(st.queue):
                    job = st.queue[idx]
                    if getattr(job, 'use_stereoscopy', False):
                        _stereo_rename(job)
                    # Rebase numbering if requested
                    try:
                        if getattr(job, 'use_animation', False) and getattr(job, 'rebase_numbering', True):
                            _rebase_numbering(job)
                    except Exception:
                        pass
            except Exception:
                pass
            if st.running and was_render and not getattr(st, '_skip_increment_once', False) and st.current_job_index < len(st.queue):
                st.current_job_index += 1
            st._skip_increment_once = False
            _mark_status(st, 'Render finished', progress=1.0)
        _on_render_complete._rqm_tag = True
        bpy.app.handlers.render_complete.append(_on_render_complete)

    if not _tagged(bpy.app.handlers.render_cancel):
        def _on_render_cancel(scene):
            st = _active_state(scene)
            if not st:
                return
            was_render = st.render_in_progress
            st.render_in_progress = False
            if st.running and was_render and not getattr(st, '_skip_increment_once', False) and st.current_job_index < len(st.queue):
                st.current_job_index += 1
            st._skip_increment_once = False
            _mark_status(st, 'Render cancelled')
        _on_render_cancel._rqm_tag = True
        bpy.app.handlers.render_cancel.append(_on_render_cancel)

    if not _tagged(bpy.app.handlers.depsgraph_update_post):
        def _on_depsgraph_update(scene, depsgraph):
            try:
                _sync_marker_links()
            except Exception:
                pass
        _on_depsgraph_update._rqm_tag = True
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)

    if not _tagged(bpy.app.handlers.render_init):
        def _on_render_init(scene):
            st = _active_state(scene)
            if not st:
                return
            status = 'Initializing render'
            try:
                if st.running and 0 <= st.current_job_index < len(st.queue):
                    job = st.queue[st.current_job_index]
                    job_name = getattr(job, 'name', '')
                    if job_name:
                        status = f'Initializing render: {job_name}'
            except Exception:
                pass
            _reset_stats(st, status=status)
        _on_render_init._rqm_tag = True
        bpy.app.handlers.render_init.append(_on_render_init)

    if not _tagged(bpy.app.handlers.render_stats):
        def _on_render_stats(stats):
            st = _active_state()
            if not st:
                return
            _apply_stats(st, stats)
        _on_render_stats._rqm_tag = True
        bpy.app.handlers.render_stats.append(_on_render_stats)

def _remove_tagged(hlist):
    try:
        to_del = [h for h in hlist if getattr(h, '_rqm_tag', False)]
        for h in to_del:
            try:
                hlist.remove(h)
            except Exception:
                pass
    except Exception:
        pass

def unregister_handlers():
    """Remove our tagged handlers to avoid duplicates across reloads."""
    try:
        _remove_tagged(bpy.app.handlers.render_complete)
        _remove_tagged(bpy.app.handlers.render_cancel)
        _remove_tagged(bpy.app.handlers.depsgraph_update_post)
        _remove_tagged(bpy.app.handlers.render_init)
        _remove_tagged(bpy.app.handlers.render_stats)
    except Exception:
        pass
    global _current_render_state
    _current_render_state = None

# ---- Internal helpers ----

_EXT_MAP = {
    'PNG': '.png','JPEG': '.jpg','BMP': '.bmp','TIFF': '.tif','OPEN_EXR': '.exr'
}
_view_pat_variants = [
    # base + view word/tag + frame (SceneCamLeft0001.png / SceneCamALT20001.png)
    re.compile(r'^(?P<base>.+?)(?P<view>Left|Right|[A-Za-z0-9]{2,})?(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + _ + view tag (SceneCam0001_L.png / SceneCam0001_ALT2.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)[_-](?P<view>[A-Za-z0-9]+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + frame + single letter view appended (SceneCam0001L.png)
    re.compile(r'^(?P<base>.+?)(?P<frame>\d+)(?P<view>[A-Za-z])(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + _ + view + frame (SceneCam_L0001.png / SceneCam_ALT20001.png)
    re.compile(r'^(?P<base>.+?)[_-](?P<view>[A-Za-z0-9]+)(?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
    # base + view + _ + frame (SceneCamLeft_0001.png / SceneCamALT2_0001.png)
    re.compile(r'^(?P<base>.+?)(?P<view>[A-Za-z0-9]+)[_-](?P<frame>\d+)(?P<ext>\.[^.]+)$', re.IGNORECASE),
]
_plain_frame_pat = re.compile(r'^(?P<base>.+?)(?P<frame>\d{3,})(?P<ext>\.[^.]+)$')
_dup_token_sep = re.compile(r'[_\.]+')
_num_before_suffix_pat = re.compile(r'^(?P<base>.+?)(?P<frame>\d{3,})(?P<tag>_[A-Za-z0-9]+)(?P<ext>\.[^.]+)$')
_any_frame_pat = re.compile(r'^(?P<prefix>.+?)(?P<tag>_[A-Za-z0-9]+)?\s+(?P<frame>\d{3,})(?P<ext>\.[^.]+)$')

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


def _sync_one_marker(job, scn, is_start: bool):
    key = (job.as_pointer(), 'start' if is_start else 'end')
    link_both = getattr(job, 'link_timeline_markers', False)
    if is_start:
        enabled = link_both or getattr(job, 'link_marker', False)
        marker_name = getattr(job, 'marker_name', '')
        offset_val = getattr(job, 'marker_offset', 0)
        target_attr = 'frame_start'
    else:
        enabled = link_both or getattr(job, 'link_end_marker', False)
        marker_name = getattr(job, 'end_marker_name', '')
        offset_val = getattr(job, 'end_marker_offset', 0)
        target_attr = 'frame_end'
    if not enabled or not marker_name:
        _marker_cache.pop(key, None)
        return
    marker = scn.timeline_markers.get(marker_name)
    if not marker:
        return
    try:
        base_frame = int(marker.frame)
    except Exception:
        return
    try:
        offset = int(offset_val)
    except Exception:
        offset = 0
    desired = base_frame + offset
    prev = _marker_cache.get(key)
    if prev == (base_frame, offset) and getattr(job, target_attr, None) == desired:
        return
    _marker_cache[key] = (base_frame, offset)
    try:
        if getattr(job, target_attr) != desired:
            setattr(job, target_attr, desired)
    except Exception:
        pass


def _sync_marker_links():
    try:
        scenes = list(bpy.data.scenes)
    except Exception:
        scenes = []
    for scn in scenes:
        state = getattr(scn, 'rqm_state', None)
        if not state:
            continue
        for job in state.queue:
            target_scene = bpy.data.scenes.get(job.scene_name) if getattr(job, 'scene_name', '') else scn
            if not target_scene:
                continue
            _sync_one_marker(job, target_scene, True)
            _sync_one_marker(job, target_scene, False)


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
                        try:
                            # If target exists, remove it so rename proceeds (ensures latest file kept)
                            if os.path.exists(new_path):
                                try:
                                    os.remove(new_path)
                                except Exception:
                                    pass
                            os.replace(path, new_path)
                        except Exception:
                            pass
                    processed.add(path)
        # Pass 2: ensure space before frame for plain (non-view) files e.g. main.0010000 -> main.001 0000
        for path in plain_candidates:
            if path in processed or not os.path.isfile(path):
                continue
            name = os.path.basename(path)
            # Handle pattern with numbers before suffix e.g. main.0010001_ALT.png -> main.001_ALT 0001.png
            mnum = _num_before_suffix_pat.match(name)
            if mnum:
                b = mnum.group('base')
                frame = mnum.group('frame')
                tag = mnum.group('tag')  # includes leading underscore
                ext_full = mnum.group('ext')
                new_name_nb = f"{b}{tag} {frame}{ext_full}"
                if new_name_nb != name:
                    new_path_nb = os.path.join(os.path.dirname(path), new_name_nb)
                    try:
                        if os.path.exists(new_path_nb):
                            os.remove(new_path_nb)
                        os.replace(path, new_path_nb)
                        name = new_name_nb  # update for further plain processing if needed
                    except Exception:
                        pass
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
                try:
                    if os.path.exists(new_path):
                        os.remove(new_path)
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

def _compute_src_range(job):
    scn = bpy.data.scenes.get(job.scene_name)
    # Fallback to job fields if scene/markers not available
    try:
        if getattr(job, 'link_timeline_markers', False) and scn:
            ms = scn.timeline_markers.get(job.marker_name) if job.marker_name else None
            me = scn.timeline_markers.get(job.end_marker_name) if job.end_marker_name else None
            src_start = int(ms.frame) + int(job.marker_offset) if ms else int(job.frame_start)
            src_end = int(me.frame) + int(job.end_marker_offset) if me else int(job.frame_end)
        else:
            if getattr(job, 'link_marker', False) and scn:
                ms = scn.timeline_markers.get(job.marker_name) if job.marker_name else None
                src_start = int(ms.frame) + int(job.marker_offset) if ms else int(job.frame_start)
            else:
                src_start = int(job.frame_start)
            if getattr(job, 'link_end_marker', False) and scn:
                me = scn.timeline_markers.get(job.end_marker_name) if job.end_marker_name else None
                src_end = int(me.frame) + int(job.end_marker_offset) if me else int(job.frame_end)
            else:
                src_end = int(job.frame_end)
        if src_end < src_start:
            src_end = src_start
        return src_start, src_end
    except Exception:
        return int(job.frame_start), int(job.frame_end)

def _rebase_numbering(job):
    try:
        src_start, src_end = _compute_src_range(job)
        bdir = base_render_dir(job)
        if not os.path.isdir(bdir):
            return
        job_root = os.path.dirname(bdir.rstrip('/\\'))
        search_roots = [bdir]
        if os.path.isdir(job_root):
            search_roots.append(job_root)
            try:
                for entry in os.listdir(job_root):
                    p = os.path.join(job_root, entry)
                    if os.path.isdir(p):
                        search_roots.append(p)
            except Exception:
                pass
        # Go through files that end with ' <frame>.ext' (with optional _TAG)
        for root in search_roots:
            try:
                for fname in os.listdir(root):
                    m = _any_frame_pat.match(fname)
                    if not m:
                        continue
                    frame_no = int(m.group('frame'))
                    if frame_no < src_start or frame_no > src_end:
                        continue
                    new_index = frame_no - src_start
                    width = len(m.group('frame'))
                    new_frame_str = str(new_index).zfill(width)
                    prefix = m.group('prefix')
                    tag = m.group('tag') or ''
                    ext = m.group('ext')
                    new_name = f"{prefix}{tag} {new_frame_str}{ext}"
                    if new_name == fname:
                        continue
                    src_path = os.path.join(root, fname)
                    dst_path = os.path.join(root, new_name)
                    try:
                        if os.path.exists(dst_path):
                            os.remove(dst_path)
                        os.replace(src_path, dst_path)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass
