"""Top-level add-on entry.

All implementation lives inside the internal package `rqm`.
This file only exposes Blender's required `bl_info` and delegates
register/unregister to the modular submodules for clarity.
"""

bl_info = {
	'name': 'Render Queue Manager',
	'author': 'Xnom3d',
	'version': (1, 10, 6),  # operator tooltips
	'blender': (3, 0, 0),
	'location': 'Properties > Output > Render Queue Manager',
	'description': 'Queue renders with per-job folders, compositor outputs, stereoscopy, and extension hooks.',
	'category': 'Render'
}

# Use relative imports so Blender package loader (zip root) resolves correctly
from . import rqm as _rqm_pkg  # noqa: F401
from .rqm import utils, properties, outputs, queue_ops, ui

MODULES = (utils, properties, outputs, queue_ops, ui)

def register():
	for m in MODULES:
		if hasattr(m, 'register'):
			m.register()

def unregister():
	for m in reversed(MODULES):
		if hasattr(m, 'unregister'):
			m.unregister()

__all__ = ['register', 'unregister', 'bl_info']
