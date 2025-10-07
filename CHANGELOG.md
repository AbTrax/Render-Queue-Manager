# Changelog

All notable changes to this project will be documented in this file.

## [1.14.0] - 2025-10-03

### Added

- Per-job and per-output encoding controls (color depth, compression, EXR codec, JPEG quality) with UI configuration.

### Changed

- Main render output now prefixes filenames with the job name so files in subfolders and multiview variants are job-scoped by default.

### Fixed

- View layer selections stay in sync per job when scenes change or layers are renamed.

## [1.13.5] - 2025-09-26

### Improved (Reload & Registration)

- Hot-reload stability during development: safely reloads submodules without crashing on errors.
- More robust class registration/unregistration to avoid duplicates when reloading the add-on.
- Handler lifecycle tightened to prevent lingering handlers across enable/disable cycles.

### Fixed (Unregister)

- Safer pointer cleanup on unregister to avoid rare AttributeError cases.

## [1.13.0] - 2025-09-12

### Added

- Per-job view layer selection with UI picker and render-time enforcement.
- Optional job-name suffix for generated render/compositor folders.
- Automatic sync to keep marker-linked frame ranges aligned when timeline markers move.

### Improved

- Camera batch creation now records the active view layer for each generated job.

## [1.11.2] - 2025-09-11

### Removed (Stereoscopy UI)


### Changed (Registration)


### Fixed (Compatibility)


 
## [1.11.3] - 2025-09-11

- Cleanup: type-ignores for Blender imports, removed unused imports
- Robust handler (un)registration to avoid duplicates on reload
- Register missing RQM_Tag property group
- Add pyproject.toml with Ruff/Black config

## [1.11.1] - 2025-09-11

### Fixed (UI)


## [1.10.10] - 2025-09-11

### Fixed (Timer / Modal Queue)

- Eliminated AttributeError on updated sessions: migrated legacy `WindowManager._rqm_active_timer` storage to module globals.
- Added safe cleanup and unregister timer removal to prevent orphaned timers after finishing or disabling the add-on.

## [1.10.8] - 2025-09-11

### Added (Markers UI)

- Marker picker enums (start/end) with fallback string fields; Apply Now operator.
- Fallback logic maps picker to stored names before applying.

### Fixed (Markers)

- Marker controls not appearing reliably; added enum + fallback approach.

## [1.10.5] - 2025-09-10

### Added

- Operator hover tooltips (bl_description) for all queue and output operators.

### Restored

- Timeline marker range controls (start/end markers with offsets) re-exposed in UI.

## [1.10.4] - 2025-09-10

### Fixed

- Blender install error (No module named 'rqm'): switched to relative imports in root `__init__.py`.

## [1.10.3] - 2025-09-10

### Removed

- Legacy `render_queue_manager.py` wrapper file (duplicate code) – root `__init__.py` is now the sole entry.

### Changed (Packaging)

- Updated README to reflect single entry point packaging.

## [1.10.2] - 2025-09-10

### Changed

- Consolidated packaging: single bl_info at root `__init__.py`.
- Removed duplicate registration logic from `rqm/__init__.py`.

## [1.10.1] - 2025-09-10

### Added (Project Setup)

- GitHub project scaffolding: LICENSE (MIT), .gitignore, CHANGELOG, CONTRIBUTING guide.

### Changed (Legacy Removal)

- Removed legacy monolithic `render_queue_manager.py` implementation; package `rqm` is sole source.
- Version bump to 1.10.1.

## [1.10.0] - 2025-09-10

### Added (Stereo)

- Stereoscopy (multi-view) per job.

## [1.9.0] - 2025-09-10

### Changed (Folders & Numbering)

- Per-job folder structure (`<job>/base` and `<job>/comp`).
- Compositor slot naming `<job>_<basename>`.
- Always zero-based frame numbering.

## [1.8.x] - 2025-09-10

- Original features and queue management.
