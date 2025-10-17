# Render Queue Manager X — Reliable Multi-Job Rendering for Blender

**Version:** 1.14.2 - **Blender Compatibility:** 4.2+ (Extensions build; use the legacy add-on zip for Blender 3.x)

Render Queue Manager X is a modular toolkit for orchestrating Blender renders authored by **Xnom3d**. Queue per-scene jobs, keep compositor outputs tidy, and ship consistent folders for every shot without babysitting renders. Install once and drive the workflow from the **Properties ▸ Output** tab under **Render Queue Manager X**.

> 💡 Render Queue Manager X keeps evolving. Share ideas, pain points, or integrations you need and they can help steer upcoming releases.

---

## Features at a Glance

- **Queue-Based Workflow**
  - Capture scene, camera, frame range, engine, and resolution per job.
  - Duplicate, reorder, or clear jobs without touching the base scene.
- **Deterministic Output Layout**
  - Every job renders to `<root>/<job>/base/<basename><frame>.<ext>`.
  - Compositor outputs nest under `<root>/<job>/<NodeName>/…` with job-prefixed filenames.
- **Compositor File Outputs**
  - Manage multiple File Output nodes per job with optional auto-create.
  - Override file format and encoding per output or inherit from the job.
- **Timeline Marker Integration**
  - Link start/end markers so frame ranges update automatically when you slide markers.
  - Optional offsets keep handles attached while still exporting zero-based filenames.
- **Stereoscopic & Multiview Support**
  - Toggle stereoscopy per job with combined or split view exports.
  - Add extra view tags and control output folder suffixing.
- **Extensible Hooks**
  - Register preprocessors that run before each job for custom validation or automation.
  - Windows-safe path sanitizing keeps generated folders usable everywhere.

---

## Installation

### Blender 4.2+ (Extensions)

1. Download the latest `.zip` built with the extension packaging script (see Automated Releases).
2. In Blender, open **Edit > Preferences > Get Extensions**.
3. Click **Install from Disk**, choose the zip, then enable **Render Queue Manager X**.
4. Blender keeps the extension listed under the Extensions panel for future updates.

### Manual Source Checkout

1. Clone or copy this repository into your Blender extensions folder:
   - Windows: `%APPDATA%/Blender Foundation/Blender/<version>/scripts/extensions`
   - macOS: `~/Library/Application Support/Blender/<version>/scripts/extensions`
   - Linux: `~/.config/blender/<version>/scripts/extensions`
2. Ensure the folder name is `render_queue_manager_x`.
3. Restart Blender and enable the extension from **Preferences > Extensions**.

> Supporting Blender 4.1 or earlier? Use the final add-on zip from previous releases; the extension packaging requires Blender 4.2 or newer.

---

## Getting Started

1. After enabling, head to **Properties ▸ Output** and locate the **Render Queue Manager X** panel.
2. Press `Add Job (Current Scene/Camera)` to capture your starting setup.
3. Point the job to an output folder (defaults to `//renders/`) and set a basename.
4. Choose animation frames directly or link start/end markers for automatic updates.
5. Enable Stereoscopy or Compositor Outputs if needed, then press **Start Queue**.

Each panel section is collapsible so you can focus on the controls you need. Hover any field to see Blender tooltips for details.

---

## Tool Guide

### Job Queue

- Toggle job enable state, reorder entries, and duplicate setups for variants.
- Override scene, camera, view layers, render engine, resolution, and sampling.
- Rebase animation numbering so exported filenames always start at frame `0000`.

### Compositor Outputs

- Add multiple File Output bindings per job with optional creation if missing.
- Pick base paths from the job folder, the scene output, or a manual file reference.
- Apply node-named subfolders, custom tokens (`{scene}`, `{camera}`, `{job}`, `{node}`), and per-output encoding overrides.

### Marker-Linked Ranges

- Link start/end markers to keep queue entries synced to timeline edits.
- Offsets let you include handles while still exporting remapped frame numbers.

### Encoding Controls

- Configure color mode, depth, compression, EXR codec, or JPEG quality per job.
- Optionally delegate encoding to compositor nodes or override for each output.

### Stereoscopic Output

- Switch between combined stereo or multi-view image sequences.
- Add supplemental view tags for pipeline integration and keep plain renders if desired.

---

## Release Notes

### 1.14.2

- Renamed the project to **Render Queue Manager X**.
- Adopted the GPL license and refreshed documentation to match the new branding.

Refer to `CHANGELOG.md` for a complete history of prior releases.

---

## Roadmap & Feedback

Render Queue Manager X focuses on:

- Additional queue utilities (JSON import/export, dependency chaining).
- Quality-of-life tweaks surfaced from production usage.
- Documentation, tutorial content, and automation helpers.

Have a suggestion? Open an issue or start a discussion—community feedback guides upcoming work.

---

## Contributing

1. Fork the repository and branch off from main.
2. Follow Blender’s Python style (PEP 8) and keep modules focused.
3. Run the add-on locally to verify your changes.
4. Submit a pull request outlining motivation and testing (see `CONTRIBUTING.md`).

Bug reports, UX ideas, and documentation fixes are all welcome.

---

## Automated Releases

### Local Packaging

- `python scripts/package_extension.py` builds `render-queue-manager-x-v<version>.zip` using metadata from `blender_manifest.toml`.
- Use `--version` to override the detected version (for example `python scripts/package_extension.py --version 1.14.2`).
- Pass `--out <folder>` to change the staging directory (defaults to `dist/`).

### GitHub Actions

- Push a tag beginning with `v` (e.g. `v1.14.2`) to trigger the Release workflow.
- The workflow builds the zip, publishes a GitHub Release, and attaches the packaged artifact.
- You can also run the action manually, providing a tag and optionally marking it draft or prerelease.
- Every workflow upload is available as an artifact even if the release is not published.

---

## Support & Issues

- File bugs, feature requests, and questions through the issue tracker.
- For quick chats, join the project’s Discord or preferred community channel when available.

---

## License

Render Queue Manager X is distributed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See `LICENSE` for full terms.

---

## Credits

- **Author:** Xnom3d
- **Contributors:** Add your name via pull request!
