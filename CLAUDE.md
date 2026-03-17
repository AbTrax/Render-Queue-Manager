# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Render Queue Manager X** is a Blender extension (add-on) for batch rendering with per-job output organization, compositor output support, and advanced rendering controls. It targets Blender 4.2+ and 5.x.

- **Version source of truth:** `__version__` in `__init__.py` and `version` in `blender_manifest.toml` — keep these in sync.
- **Extension ID:** `render_queue_manager_x`

## Commands

### Package the Extension

```bash
python scripts/package_extension.py [--version X.Y.Z] [--out dist]
```

Produces a versioned `.zip` (e.g., `render-queue-manager-x-v2.1.0.zip`) ready for Blender Extensions installation.

### Lint & Format

```bash
ruff check .          # lint
black .               # format (line length 100, no string normalization)
```

Config is in `pyproject.toml`. Ruff ignores F401/F403/F405 in addon files (required by Blender's dynamic import system).

**No automated test suite** — testing is done manually inside Blender.

### Release

Push a tag matching `v*` to trigger the GitHub Actions release workflow (`.github/workflows/release.yml`), which packages and publishes a GitHub Release automatically.

## Architecture

### Module Structure (`rqm/`)

| Module | Role |
|--------|------|
| `properties.py` | All `PropertyGroup` classes — data model |
| `operators_queue.py` | Queue operations (add, remove, move, start/stop render) |
| `operators_outputs.py` | Compositor File Output node operations |
| `jobs.py` | `apply_job()` — applies a queued job's settings to the scene before rendering |
| `comp.py` | Compositor path resolution & File Output node sync; handles Blender 4.x/5.x API differences |
| `handlers.py` | Render lifecycle event handlers (render_pre/post/cancel, statistics, frame rebasing) |
| `ui.py` | Panels and UIList classes (Queue, Encoding, Compositor, Stereo, Stats tabs) |
| `utils.py` | Enums, path sanitization, view layer helpers |
| `state.py` | `get_state(context)` shorthand |

### Property Group Hierarchy

```
Scene.rqm_state  (RQM_State)
  └─ queue[]     (RQM_Job)
       ├─ comp_outputs[]  (RQM_CompOutput)
       │    └─ encoding   (RQM_EncodingSettings)
       ├─ tags[]          (RQM_Tag)
       └─ stats[]         (RQM_RenderStat)
```

### Blender 4.x / 5.x Compatibility

The `comp.py` module contains wrapper functions (`_node_set_base_path`, `_node_get_slots`, `_slot_get_path`, `_slot_set_path`) that branch on attribute presence to handle File Output node API changes:
- **4.x:** `node.base_path`, `node.file_slots`, `slot.path`
- **5.x:** `node.directory`, `node.file_output_items`, `item.name`

When touching render engine names, account for `BLENDER_EEVEE_NEXT` / `BLENDER_WORKBENCH_NEXT` renames. Handler signatures use `*args` to absorb API variations.

### Render Queue Lifecycle

1. `RQM_OT_StartQueue` iterates the job list and calls `apply_job()` for each enabled job.
2. `apply_job()` (in `jobs.py`) sets scene, camera, engine, samples, view layers, resolution, frame range, and encoding on the active scene.
3. `handlers.py` event handlers (`render_pre`, `render_post`, `render_cancel`) manage compositor sync, statistics capture, frame rebasing, and advancing to the next job.
4. Handlers are tagged to prevent duplicate registration on hot-reload.

### Extension Registration (`__init__.py`)

- Handles hot-reload by detecting previously loaded submodules.
- Registers 17 classes with fallback unregister on collision.
- Attaches `rqm_state` to `bpy.types.Scene` on enable; removes it on disable.

## Development Setup

1. Clone the repo.
2. Symlink or copy to the Blender extensions folder:
   - **Windows:** `%APPDATA%\Blender\<version>\scripts\extensions\`
   - **macOS:** `~/Library/Application Support/Blender/<version>/scripts/extensions/`
   - **Linux:** `~/.config/blender/<version>/scripts/extensions/`
3. Enable via **Preferences > Extensions**.
4. After code changes, disable and re-enable the extension in Blender to reload.

## Key Conventions

- UI is located in **Properties > Output** tab under the **Render Queue Manager X** panel.
- `JOB_PREPROCESSORS` is a callback list in `operators_queue.py` that external code can hook into before a job is applied — document any use of this in PRs.
- When updating the version, change both `__init__.py` and `blender_manifest.toml`, and add an entry to `CHANGELOG.md`.
