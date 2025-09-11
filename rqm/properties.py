"""Property groups and shared data structures."""

from __future__ import annotations

import os

import bpy  # type: ignore  # Blender runtime provided
from bpy.props import (  # type: ignore
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup  # type: ignore

from .utils import FILE_FORMAT_ITEMS, _sanitize_component, camera_items, engine_items, scene_items

__all__ = ['RQM_CompOutput', 'RQM_Job', 'RQM_State', 'RQM_Tag']


class RQM_Tag(PropertyGroup):
    name: StringProperty(name='Tag')
    enabled: BoolProperty(name='Use', default=True)


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
            ('SCENE_OUTPUT', 'Scene output folder', 'Use Output Properties → Output directory'),
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
    override_node_format: BoolProperty(name='Node format = Render format', default=True)


class RQM_Job(PropertyGroup):
    enabled: BoolProperty(
        name='Enabled', default=True, description='Include this job when rendering the queue'
    )
    name: StringProperty(name='Job Name', default='')
    scene_name: EnumProperty(name='Scene', items=scene_items)
    camera_name: EnumProperty(name='Camera', items=camera_items)
    engine: EnumProperty(name='Engine', items=engine_items)

    res_x: IntProperty(name='Width', default=1920, min=4)
    res_y: IntProperty(name='Height', default=1080, min=4)
    percent: IntProperty(name='Scale %', default=100, min=1, max=100)

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
        description="Prefix for main render files (sanitised). Example: 'beauty' -> beauty0001.png",
    )
    rebase_numbering: BoolProperty(
        name='Number files from 0',
        default=True,
        description=(
            'For animations, rename output files so numbering starts at 0000 '
            'for this job, regardless of timeline frame indices'
        ),
    )

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
    job_filter: StringProperty(name='Filter Jobs', default='')
