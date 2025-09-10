import bpy
from bpy.types import PropertyGroup
from bpy.props import (StringProperty, BoolProperty, IntProperty, EnumProperty, CollectionProperty)
from .utils import sanitize_component

FILE_FORMAT_ITEMS = [
    ('PNG','PNG',''),('JPEG','JPEG',''),('OPEN_EXR','OpenEXR',''),('BMP','BMP',''),('TIFF','TIFF','')
]

def scene_items(self, context):
    return [(s.name, s.name, '') for s in bpy.data.scenes]

def camera_items(self, context):
    scn = bpy.data.scenes.get(self.scene_name) if getattr(self, 'scene_name', None) else None
    cams = []
    if scn:
        for ob in scn.objects:
            if ob.type == 'CAMERA':
                cams.append((ob.name, ob.name, ''))
    return cams or [('', '<no cameras>', '')]

def engine_items(self, context):
    seen, items = set(), []
    try:
        enum = bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
        for e in enum:
            items.append((e.identifier, e.name, e.description or ''))
            seen.add(e.identifier)
    except Exception:
        pass
    if 'CYCLES' not in seen:
        items.append(('CYCLES','Cycles','Cycles Render Engine'))
    return items or [('BLENDER_EEVEE','Eevee','Eevee Render Engine')]

class RQM_CompOutput(PropertyGroup):
    enabled: BoolProperty(name='Enabled', default=True)
    node_name: StringProperty(name='File Output Node', default='')
    create_if_missing: BoolProperty(name='Create if missing', default=False)
    base_source: EnumProperty(name='Base folder', items=[
        ('JOB_OUTPUT','Job output folder','Job base comp folder'),
        ('SCENE_OUTPUT','Scene output folder','Scene output directory'),
        ('FROM_FILE','Folder of chosen file','Use folder of a picked file'),
    ], default='JOB_OUTPUT')
    base_file: StringProperty(name='Pick file', subtype='FILE_PATH', default='')
    use_node_named_subfolder: BoolProperty(name='Node-named subfolder', default=True)
    extra_subfolder: StringProperty(name='Extra subfolder', default='')
    ensure_dirs: BoolProperty(name='Create folders', default=True)
    override_node_format: BoolProperty(name='Node format = Render format', default=True)

class RQM_Job(PropertyGroup):
    # Basic
    name: StringProperty(name='Job Name', default='')
    scene_name: EnumProperty(name='Scene', items=scene_items)
    camera_name: EnumProperty(name='Camera', items=camera_items)
    engine: EnumProperty(name='Engine', items=engine_items)
    # Resolution
    res_x: IntProperty(name='Width', default=1920, min=4)
    res_y: IntProperty(name='Height', default=1080, min=4)
    percent: IntProperty(name='Scale %', default=100, min=1, max=100)
    # Frames
    use_animation: BoolProperty(name='Render animation', default=False)
    frame_start: IntProperty(name='Start frame', default=1, min=0)
    frame_end: IntProperty(name='End frame', default=1, min=0)
    link_marker: BoolProperty(name='Use start marker', default=False)
    marker_name: StringProperty(name='Start marker name', default='')
    marker_offset: IntProperty(name='Start offset', default=0)
    link_end_marker: BoolProperty(name='Use end marker', default=False)
    end_marker_name: StringProperty(name='End marker name', default='')
    end_marker_offset: IntProperty(name='End offset', default=-1)
    zero_index_numbering: BoolProperty(name='(deprecated) 0-based numbering', default=True, options={'HIDDEN'})
    # Output
    file_format: EnumProperty(name='Render format', items=FILE_FORMAT_ITEMS, default='PNG')
    output_path: StringProperty(name='Render folder', subtype='DIR_PATH', default='//renders/')
    file_basename: StringProperty(name='Render filename', default='render')
    # Compositor
    use_comp_outputs: BoolProperty(name='Use Compositor outputs', default=False)
    comp_outputs_non_blocking: BoolProperty(name='Non-blocking comp errors', default=True)
    comp_outputs: CollectionProperty(type=RQM_CompOutput)
    comp_outputs_index: IntProperty(default=0)
    # Stereo
    use_stereoscopy: BoolProperty(name='Stereoscopic (Multi-View)', default=False)
    stereo_views_format: EnumProperty(name='Stereo Format', items=[
        ('STEREO_3D','Stereo 3D','Combined left/right'),
        ('MULTIVIEW','Multi-View Images','Separate images per view')
    ], default='STEREO_3D')

class RQM_State(PropertyGroup):
    queue: CollectionProperty(type=RQM_Job)
    active_index: IntProperty(default=0)
    running: BoolProperty(default=False)
    current_job_index: IntProperty(default=-1)
    render_in_progress: BoolProperty(default=False)
    # Internal: increments each time a new queue run starts so any stray timers from
    # a previous run can detect mismatch and abort safely.
    run_id: IntProperty(default=0, options={'HIDDEN'})

CLASSES = (RQM_CompOutput, RQM_Job, RQM_State)

def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.rqm_state = bpy.props.PointerProperty(type=RQM_State)

def unregister():
    if hasattr(bpy.types.Scene, 'rqm_state'):
        del bpy.types.Scene.rqm_state
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
