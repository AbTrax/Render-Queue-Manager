# Changelog

All notable changes to this project will be documented in this file.

## [1.11.2] - 2025-09-11

### Removed (Stereoscopy UI)

- Detect View Tags operator and UI button. Simplifies stereoscopy workflow; free-text extra tags remain.

### Changed (Registration)

- Robust class re-registration to ensure updated PropertyGroups are applied after updates.

### Fixed (Compatibility)

- UI and operators now guard against missing stereoscopic properties on legacy sessions.

## [1.11.1] - 2025-09-11

### Fixed (UI)

- Prevented AttributeErrors in UI when `use_tag_collection` is missing on older-registered jobs.
- Detect Tags operator made resilient and provided free‑text fallback (subsequently removed in 1.11.2).

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
