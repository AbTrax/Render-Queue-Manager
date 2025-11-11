"""Property groups and shared data structures."""

from __future__ import annotations

import bpy  # type: ignore  # Blender runtime provided
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup  # type: ignore

from .utils import (
    FILE_FORMAT_ITEMS,
    camera_items,
    engine_items,
    scene_items,
    view_layer_identifier_map,
    view_layer_items,
)

__all__ = [
    'RQM_Tag',
    'RQM_EncodingSettings',
    'RQM_CompOutput',
    'RQM_RenderStat',
    'RQM_Job',
    'RQM_State',
    'get_job_view_layer_names',
    'set_job_view_layer_names',
    'sync_job_view_layers',
]


def _selected_view_layer_ids(job):
    raw_sel = getattr(job, 'view_layers', set())
    if isinstance(raw_sel, str):
        return [raw_sel] if raw_sel else []
    try:
        return [item for item in raw_sel if item]
    except TypeError:
        try:
            return list(raw_sel)
        except Exception:
            return []


def _split_view_layer_names(raw: str):
    return [name for name in (raw or '').split('|') if name]


def _store_view_layer_names(job, names):
    unique = []
    for name in names:
        if name and name not in unique:
            unique.append(name)
    job.view_layer_selection = '|'.join(unique)


def _names_from_identifiers(identifiers, mapping):
    names = []
    for ident in identifiers:
        layer = mapping.get(ident)
        if layer:
            names.append(layer.name)
    return names


def _identifiers_from_names(names, mapping):
    name_to_ident = {layer.name: ident for ident, layer in mapping.items()}
    identifiers = []
    for name in names:
        ident = name_to_ident.get(name)
        if ident and ident not in identifiers:
            identifiers.append(ident)
    return identifiers


def _fallback_view_layer_names(mapping):
    names = []
    for layer in mapping.values():
        try:
            if getattr(layer, 'use', True):
                names.append(layer.name)
        except Exception:
            names.append(layer.name)
    if names:
        return names
    for layer in mapping.values():
        return [layer.name]
    return []


def _assign_view_layers(job, identifiers):
    identifiers = [ident for ident in identifiers if ident]
    if not identifiers:
        try:
            job.view_layers = set()
        except Exception:
            pass
        return
    current = set()
    for ident in identifiers:
        current.add(ident)
        try:
            job.view_layers = set(current)
        except Exception:
            pass


def set_job_view_layer_names(job, scn, names, mapping=None):
    mapping = mapping or view_layer_identifier_map(scn)
    if not mapping:
        _store_view_layer_names(job, [])
        _assign_view_layers(job, [])
        return []
    cleaned = []
    name_to_ident = {layer.name: ident for ident, layer in mapping.items()}
    for name in names:
        if name and name in name_to_ident and name not in cleaned:
            cleaned.append(name)
    _store_view_layer_names(job, cleaned)
    _assign_view_layers(job, _identifiers_from_names(cleaned, mapping))
    return cleaned


def sync_job_view_layers(job, scn, mapping=None):
    mapping = mapping or view_layer_identifier_map(scn)
    if not mapping:
        _store_view_layer_names(job, [])
        _assign_view_layers(job, [])
        return []
    name_lookup = {layer.name: ident for ident, layer in mapping.items()}
    stored_names = [
        name for name in _split_view_layer_names(getattr(job, 'view_layer_selection', ''))
        if name in name_lookup
    ]
    identifiers = _selected_view_layer_ids(job)
    had_selection = bool(stored_names or identifiers)
    if not stored_names and identifiers:
        stored_names = _names_from_identifiers(identifiers, mapping)
    if not stored_names and had_selection:
        stored_names = _fallback_view_layer_names(mapping)
    _store_view_layer_names(job, stored_names)
    _assign_view_layers(job, [name_lookup[name] for name in stored_names])
    return stored_names


def get_job_view_layer_names(job):
    return _split_view_layer_names(getattr(job, 'view_layer_selection', ''))


class RQM_Tag(PropertyGroup):
    name: StringProperty(name='Tag')
    enabled: BoolProperty(name='Use', default=True)


class RQM_EncodingSettings(PropertyGroup):
    color_mode: EnumProperty(
        name='Color Mode',
        items=[
            ('BW', 'BW', 'Monochrome output'),
            ('RGB', 'RGB', 'RGB color channels'),
            ('RGBA', 'RGBA', 'RGB with alpha'),
        ],
        default='RGB',
    )
    color_depth: EnumProperty(
        name='Color Depth',
        items=[
            ('8', '8 bit', '8-bit per channel'),
            ('16', '16 bit', '16-bit per channel'),
            ('32', '32 bit', '32-bit per channel (floating point)'),
        ],
        default='8',
    )
    compression: IntProperty(
        name='Compression',
        default=15,
        min=0,
        max=100,
        description='Compression level for PNG/TIFF/EXR formats (0 = none, 100 = maximum)',
    )
    quality: IntProperty(
        name='Quality',
        default=90,
        min=0,
        max=100,
        description='Quality for JPEG outputs (100 = best)',
    )
    exr_codec: EnumProperty(
        name='EXR Codec',
        items=[
            ('ZIP', 'ZIP', 'ZIP compression'),
            ('ZIPS', 'ZIPS', 'ZIP per scanline'),
            ('PIZ', 'PIZ', 'PIZ wavelet compression'),
            ('PXR24', 'PXR24', 'Pixar 24-bit compression'),
            ('DWAA', 'DWAA', 'DreamWorks fast lossy compression'),
            ('DWAB', 'DWAB', 'DreamWorks high-quality compression'),
            ('NONE', 'None', 'No compression'),
        ],
        default='ZIP',
    )


class RQM_CompOutput(PropertyGroup):
    enabled: BoolProperty(
        name='Enabled',
        default=True,
        description='Include this File Output node when rendering this job',
    )
    node_name: StringProperty(
        name='File Output Node',
        default='',
        description="Pick a Compositor File Output node to drive. We'll set its base folder only.",
    )
    create_if_missing: BoolProperty(
        name='Create if missing (once)',
        default=False,
        description="If the node isn't found, create and remember one",
    )
    base_source: EnumProperty(
        name='Base folder',
        items=[
            ('JOB_OUTPUT', 'Job output folder', 'Use the job\'s Render folder'),
            ('SCENE_OUTPUT', 'Scene output folder', 'Use Output Properties \u2192 Output directory'),
            ('FROM_FILE', 'Folder of a chosen file', 'Pick any file; we use its folder'),
        ],
        default='JOB_OUTPUT',
    )
    base_file: StringProperty(name='Pick file (we use its folder)', subtype='FILE_PATH', default='')
    use_node_named_subfolder: BoolProperty(name='Put in subfolder named after node', default=True)
    extra_subfolder: StringProperty(
        name='Extra subfolder (optional)',
        default='',
        description='Tokens OK: {scene} {camera} {job} {node}',
    )
    ensure_dirs: BoolProperty(name='Create folders if missing', default=True)
    override_node_format: BoolProperty(name='Use job render format', default=True)
    use_custom_encoding: BoolProperty(
        name='Override encoding',
        default=False,
        description='Apply custom encoding settings to this File Output node',
    )
    encoding: PointerProperty(type=RQM_EncodingSettings)
    file_basename: StringProperty(
        name='Filename prefix',
        default='',
        description=(
            'Optional filename prefix for files from this File Output node. '
            'Tokens OK: {scene} {camera} {job} {node}. Leave blank to follow the job settings.'
        ),
    )


class RQM_RenderStat(PropertyGroup):
    label: StringProperty(name='Label', default='')
    value: StringProperty(name='Value', default='')


def _on_job_scene_change(self, context):
    scene_name = getattr(self, 'scene_name', '')
    scn = bpy.data.scenes.get(scene_name) if scene_name else None
    if scn:
        cam_name = getattr(self, 'camera_name', '') or ''
        cam_obj = bpy.data.objects.get(cam_name) if cam_name else None
        if not cam_obj or cam_obj.type != 'CAMERA' or cam_obj.name not in scn.objects:
            default_cam = scn.camera
            self.camera_name = default_cam.name if default_cam else ''
        mapping = view_layer_identifier_map(scn)
        if mapping:
            sync_job_view_layers(self, scn, mapping)
        else:
            _store_view_layer_names(self, [])
            _assign_view_layers(self, [])
    else:
        self.camera_name = ''
        _store_view_layer_names(self, [])
        _assign_view_layers(self, [])


def _on_view_layers_change(self, context):
    scene_name = getattr(self, 'scene_name', '')
    scn = bpy.data.scenes.get(scene_name) if scene_name else None
    mapping = view_layer_identifier_map(scn) if scn else {}
    if not mapping:
        _store_view_layer_names(self, [])
        return
    identifiers = _selected_view_layer_ids(self)
    names = _names_from_identifiers(identifiers, mapping)
    _store_view_layer_names(self, names)


class RQM_Job(PropertyGroup):
    enabled: BoolProperty(
        name='Enabled', default=True, description='Include this job when rendering the queue'
    )
    name: StringProperty(name='Job Name', default='')
    scene_name: EnumProperty(name='Scene', items=scene_items, update=_on_job_scene_change)
    camera_name: EnumProperty(name='Camera', items=camera_items)
    view_layers: EnumProperty(
        name='View Layers',
        items=view_layer_items,
        options={'ENUM_FLAG'},
        description='View layers to enable for this job (empty = scene defaults)',
        update=_on_view_layers_change,
    )
    view_layer_selection: StringProperty(
        name='View Layer Selection (names)',
        default='',
        options={'HIDDEN'},
    )
    engine: EnumProperty(name='Engine', items=engine_items)

    res_x: IntProperty(name='Width', default=1920, min=4)
    res_y: IntProperty(name='Height', default=1080, min=4)
    percent: IntProperty(name='Scale %', default=100, min=1, max=100)

    use_persistent_data: BoolProperty(
        name='Persistent Data',
        default=False,
        description='Keep render data between frames (Cycles only). Saves reload time but uses more VRAM.',
    )

    use_animation: BoolProperty(name='Render animation', default=False)
    frame_start: IntProperty(name='Start frame', default=1, min=0)
    frame_end: IntProperty(name='End frame', default=1, min=0)
    preserve_frame_numbers: BoolProperty(
        name='Preserve frame numbers',
        default=True,
        description=(
            'If enabled, renders use the original frame numbers (e.g. 20-30). '
            'If disabled, frames are remapped to start at 0 for this job.'
        ),
    )

    # Single toggle to control using timeline markers for both start and end
    link_timeline_markers: BoolProperty(
        name='Link timeline markers',
        default=False,
        description=(
            'When enabled, use Start/End timeline markers (with offsets) '
            'and disable manual Start/End frame inputs'
        ),
    )

    link_marker: BoolProperty(name='Use start marker', default=False)
    marker_name: StringProperty(name='Start marker name', default='')
    marker_offset: IntProperty(name='Start offset', default=0)
    link_end_marker: BoolProperty(name='Use end marker', default=False)
    end_marker_name: StringProperty(name='End marker name', default='')
    end_marker_offset: IntProperty(name='End offset', default=-1)

    zero_index_numbering: BoolProperty(
        name='(deprecated) 0-based numbering', default=True, options={'HIDDEN'}
    )

    file_format: EnumProperty(name='Render format', items=FILE_FORMAT_ITEMS, default='PNG')
    output_path: StringProperty(name='Render folder', subtype='DIR_PATH', default='//renders/')
    file_basename: StringProperty(
        name='Render filename',
        default='render',
        description=(
            "Prefix for main render files (sanitised). Example: 'beauty' -> beauty0001.png. "
            'Leave blank to derive from folders.'
        ),
    )
    prefix_files_with_job_name: BoolProperty(
        name='Prefix filenames with job name',
        default=True,
        description='When enabled, final filenames are prefixed with the job name (Job_render 0001.png)',
    )
    suffix_output_folders_with_job: BoolProperty(
        name='Prefix folders with job name',
        default=False,
        description='Name generated folders like Job_base or Job_comp instead of appending the job name',
    )
    rebase_numbering: BoolProperty(
        name='Number files from 0',
        default=True,
        description=(
            'For animations, rename output files so numbering starts at 0000 '
            'for this job, regardless of timeline frame indices'
        ),
    )
    encoding: PointerProperty(type=RQM_EncodingSettings)

    use_comp_outputs: BoolProperty(name='Use Compositor outputs', default=False)
    comp_outputs_non_blocking: BoolProperty(
        name='Don’t block render on compositor errors', default=True
    )
    comp_outputs: CollectionProperty(type=RQM_CompOutput)
    comp_outputs_index: IntProperty(default=0)

    # Stereoscopy / Multiview
    use_stereoscopy: BoolProperty(
        name='Use Stereoscopy',
        default=False,
        description='Enable multiview (stereoscopic) rendering for this job',
    )
    stereo_views_format: EnumProperty(
        name='Stereo Format',
        items=[
            ('STEREO_3D', 'Stereo 3D', 'Left and Right views'),
            ('MULTIVIEW', 'Multi-View', 'Use scene multi-view configuration'),
        ],
        default='STEREO_3D',
        description='How to configure view rendering for this job',
    )
    stereo_extra_tags: StringProperty(
        name='Extra view tags',
        default='',
        description=(
            'Optional extra view identifiers (comma or space separated). '
            'Example: "ALT QA" -> produces _ALT and _QA tags'
        ),
    )
    stereo_keep_plain: BoolProperty(
        name='Keep plain fallback',
        default=True,
        description=(
            'If off, plain (untagged) files are deleted once all '
            'view-tagged files for that frame exist'
        ),
    )
    stereo_tags: CollectionProperty(type=RQM_Tag)
    stereo_tags_index: IntProperty(default=0)
    use_tag_collection: BoolProperty(
        name='Use tag list',
        default=False,
        description=(
            'If enabled, only the tags in the list (checked) are used '
            'instead of the free-text field'
        ),
    )


class RQM_State(PropertyGroup):
    queue: CollectionProperty(type=RQM_Job)
    active_index: IntProperty(default=0)
    running: BoolProperty(default=False)
    current_job_index: IntProperty(default=-1)
    render_in_progress: BoolProperty(default=False)
    stall_polls: IntProperty(default=0, options={'HIDDEN'})
    job_filter: StringProperty(name='Filter Jobs', default='')
    ui_prev_tab: StringProperty(default='QUEUE', options={'HIDDEN'})
    ui_tab: EnumProperty(
        name='Active Tab',
        items=[
            ('QUEUE', 'Queue', 'Manage render queue jobs'),
            ('STATS', 'Render Stats', 'View live render statistics'),
        ],
        default='QUEUE',
    )
    stats_status: StringProperty(name='Render Status', default='Idle')
    stats_progress: FloatProperty(
        name='Progress',
        default=0.0,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
    )
    stats_raw: StringProperty(name='Raw Stats', default='', options={'HIDDEN'})
    stats_lines: CollectionProperty(type=RQM_RenderStat)
