# Changelog

All notable changes to this project will be documented in this file.

## [2.2.0] - 2026-03-16

### Added

- **Stereo tag sync** — stereo tags auto-populate from scene render views when stereoscopy is enabled. Manual "Sync from Scene" button available.
- **Indirect-only collection toggle** — operators to exclude/include indirect-only collections from view layers, useful for Eevee where indirect-only is unsupported.
- **Create Folders** — pre-create output directories for all enabled jobs before rendering.
- **Margin (overscan)** — add extra pixels around the camera view with FOV-corrected framing.

### Changed

- Margin now adjusts camera FOV angle instead of sensor dimensions for more accurate overscan framing.

### Removed

- Per-job indirect light clamping override (replaced by indirect-only collection toggle).

## [2.1.0] - 2026-03-10

### Added

- **File Output node picker** — compositor output settings now show a filtered dropdown listing only `CompositorNodeOutputFile` nodes in the scene, replacing the previous unfiltered node search.
- **Open Output Folder** operator — opens the selected job's render directory in the OS file explorer (Windows, macOS, Linux).
- **Auto-save before render** — toggle (on by default) to save the `.blend` file before the queue starts.
- **Job status tracking** — each job tracks its status (`Pending`, `Rendering`, `Completed`, `Failed`, `Skipped`) and shows a corresponding icon in the queue list.
- **Estimated time remaining** — the Stats tab shows queue progress and estimated remaining time based on average completed job durations.

### Changed

- `StartQueue` now resets all job statuses to `Pending`/`Skipped` before rendering begins.
- Queue controls row now includes the auto-save toggle icon.

## [2.0.0] - 2025-07-23

### Added

- **Blender 5 compatibility** — all handler signatures accept `*args`; dynamic PropertyGroup attributes replaced with proper `BoolProperty`/`FloatProperty` declarations; render engine fallbacks handle renamed identifiers (`BLENDER_EEVEE_NEXT`, `BLENDER_WORKBENCH_NEXT`).
- **Enable All / Disable All** operators to toggle every job in the queue at once.
- **Per-job render time tracking** — each job records how long its last render took; displayed in the queue list.
- **Queue filtering** — search/filter jobs by name, scene, camera, or notes in the queue list.
- **Per-job sample override** — optionally set a custom sample count (Cycles / Eevee) per job.
- **Per-job notes field** — free-text notes for annotating or describing jobs.
- **Move buttons** in the queue sidebar for reordering jobs.
- **Render Stats tab** — live progress bar, status text, and parsed statistics during rendering.

### Changed

- Converted to Blender Extensions packaging (`blender_manifest.toml`), replacing legacy `bl_info`.
- `percent` (resolution scale) max raised from 100 to 10000 for super-sampling workflows.
- Compositor debug `print()` statements removed; output is now silent.
- Code cleaned up across all modules: consistent docstrings, formatting, and import structure.
- Deprecated `zero_index_numbering` property hidden from UI.

### Fixed

- Smart quote (`\u2019`) in `comp_outputs_non_blocking` description replaced with ASCII apostrophe.
- Compositor File Output slot names now update even when the node already used custom paths.
- Inline import of `comp_root_dir` in `jobs.py` moved to top-level imports.
- `render_stats` handler registered defensively with `hasattr` check for builds that lack it.

## [1.14.1] - 2025-10-11

### Changed

- Generated render and compositor outputs now use the `[job]_[subfolder]` convention for both folders and filenames (frame numbers remain suffixes).
- Compositor outputs nested in subfolders now prefix filenames with the job and full subfolder path to keep names unique.
- The folder option now prefixes job names (e.g. `Job_base`) instead of suffixing them.

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
