# Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses semantic-style versioning.

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [1.10.10] - 2025-09-11

- Fixed: Timer/Modal Queue – Prevented AttributeError on updated sessions by migrating legacy `WindowManager._rqm_active_timer` storage to module-level globals.
- Fixed: Timer lifecycle – Added safe cleanup and removal on unregister to avoid orphaned timers after finishing or disabling the add-on.

## [1.10.8] - 2025-09-11

- Added: Markers UI – Start/End marker picker enums with fallback string fields and an “Apply Now” operator.
- Added: Marker fallback – Picker value is mapped to stored names before applying.
- Fixed: Markers – Controls not appearing reliably; introduced enum + fallback approach for robust display.

## [1.10.5] - 2025-09-10

- Added: Operator hover tooltips (`bl_description`) for all queue and output operators.
- Restored: Timeline marker range controls (start/end markers with offsets) re-exposed in the UI.

## [1.10.4] - 2025-09-10

- Fixed: Packaging/Install – `No module named 'rqm'` error resolved by switching to relative imports in root `__init__.py`.

## [1.10.3] - 2025-09-10

- Removed: Legacy `render_queue_manager.py` wrapper file; root `__init__.py` is now the single entry point.
- Changed: Packaging docs updated in README to reflect the single entry point.

## [1.10.2] - 2025-09-10

- Changed: Consolidated packaging with a single `bl_info` at root `__init__.py`.
- Changed: Removed duplicate registration logic from `rqm/__init__.py`.

## [1.10.1] - 2025-09-10

- Added: Project scaffolding – LICENSE (MIT), .gitignore, CHANGELOG, CONTRIBUTING guide.
- Changed: Legacy removal – dropped monolithic `render_queue_manager.py`; the `rqm` package is the single source.
- Changed: Version bump to 1.10.1.

## [1.10.0] - 2025-09-10

- Added: Stereoscopy (multi-view) support per job.

## [1.9.0] - 2025-09-10

- Changed: Per-job folder structure (`<job>/base` and `<job>/comp`).
- Changed: Compositor slot naming standardized to `<job>_<basename>`.
- Changed: Always zero-based frame numbering for consistent output.

## 1.8.x - 2025-09-10

- Initial features and queue management.

[Unreleased]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.10...HEAD
[1.10.10]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.8...v1.10.10
[1.10.8]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.5...v1.10.8
[1.10.5]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.4...v1.10.5
[1.10.4]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.3...v1.10.4
[1.10.3]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.2...v1.10.3
[1.10.2]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.1...v1.10.2
[1.10.1]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.10.0...v1.10.1
[1.10.0]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/AbTrax/Render-Queue-Manager/compare/v1.8.0...v1.9.0
