<div align="center">
<h1>Render Queue Manager</h1>
<p><strong>Blender add-on for structured multi-job rendering with clean foldering, compositor integration, and stereoscopy.</strong></p>
<p>
<sup>Per‑job folders · Smart File Output management · Stereo/multi‑view · Windows‑safe paths</sup>
</p>
</div>

---

## ✨ Features

- Per‑job overrides: scene, camera, engine, resolution, animation range (uses scene frame numbers for animations; stills render at frame 0 → 0000).
- Deterministic directory layout:
  - Base renders: `<root>/<job_name>/base/<basename> <frame>.ext` (note the space before the frame number)
  - Compositor outputs: `<root>/<job_name>/<NodeName>/...` when “Use node‑named subfolder” is enabled; otherwise directly under `<root>/<job_name>/`
- Multiple Compositor File Output nodes per job (manages base path, optional format override, and sensible default slot naming).
- Smart slot naming: empty/default slot paths become `<job>_<basename>` (a trailing space is added so Blender writes `0000`, `0001`, …).
- Optional stereoscopic (multi‑view) rendering with selectable views format.
- Non‑blocking compositor mode (warn instead of abort) per job.
- Windows‑safe name sanitizing (reserved device names avoided).

## 📦 Structure

```text
__init__.py              # Add-on entry (bl_info + registers submodules)
rqm/
  __init__.py            # Internal namespace
  utils.py               # Sanitizing, tokens, path helpers
  properties.py          # PropertyGroups (jobs, outputs, state)
  comp.py                # Compositor File Output handling & path resolve
  jobs.py                # Apply a job to the scene (render settings)
  operators_queue.py     # Queue operators (add/move/start/stop/etc.)
  operators_outputs.py   # Compositor output operators
  handlers.py            # Render/scene handlers and timers
  state.py               # Global add-on state
  ui.py                  # Panels & UILists
```

## 🔧 Installation

1. Create a zip of the add-on root so the archive contains directly:
   - `__init__.py`
   - `rqm/` directory
2. Blender → Edit → Preferences → Add-ons → Install… select the zip.
3. Enable: Render Queue Manager.
4. Open the panel in Properties → Output tab.

## 🚀 Quick Start

1. Open your target scene & camera.
2. Add a job: Add Job (Current Scene/Camera).
3. Adjust output folder (defaults to `//renders/`).
4. (Optional) Enable animation & set start/end OR link timeline markers.
5. (Optional) Enable Stereoscopic or Compositor Outputs.
6. Press Start Queue.

## 📁 Folder & Naming Model

For a job named `Shot01_MainCam` with basename `render`:
```text
<output_root>/Shot01_MainCam/
  base/render 0000.png …
  <FileOutputNodeName>/<job>_<basename> 0000.png    # if node-named subfolder enabled
  <job>_<basename> 0000.png                         # if subfolder disabled (files in job root)
```
Animation ranges use the scene’s actual frame numbers (e.g. 101–148). Single still renders are written as frame `0000`.

## 🎞️ Stereoscopy

Enable per job. Choose:

- Stereo 3D (combined)
- Multi-View Images (separate left/right)
If disabled, we restore standard single‑view output.

## 🧩 Compositor Outputs

When enabled:

1. Add one or more outputs.
2. Choose (or auto-create) File Output nodes.
3. Optionally pick base source: Job output folder, Scene output folder, or a folder inferred from a chosen file.
4. Optional node-named and custom token subfolders (`{scene} {camera} {job} {node}`).
5. Slots with default/empty paths are renamed to `<job>_<basename>`.

Operator tooltips are available in Blender via hover (we include detailed popover help in the add-on UI).

## 🐛 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Add-on fails: `No module named 'rqm'` | Zip contained an extra parent folder | Re-zip so `__init__.py` is at archive root |
| Compositor outputs not written | Node missing or disabled | Enable node or use “Create if missing” |
| Frame numbers differ from expected | Expectation of zero-based numbering | Animations use scene frame numbers; stills render at 0000 |
| Overwriting from multiple jobs | Same job name/basename | Ensure unique job names or change basename |

## ❓ FAQ

**Why always start at 0000?**  Consistent naming prevents gaps and cross-project confusion when merging outputs.

**Can I keep original frame numbers?** Yes—animations use the scene’s frame numbers.

**Does this change render settings permanently?** Only for the duration of the job; subsequent jobs override again.

## 🗺️ Roadmap (Potential)

- Queue import/export (JSON)
- Per-job color management & sampling overrides
- Dependency ordering (render B after A)
- Optional original frame numbering toggle

## 🤝 Contributing

See `CONTRIBUTING.md`. Pull Requests welcome—keep changes modular.

## 📄 License

MIT. See `LICENSE`.

## 🔢 Versioning

Semantic-like tuple in `bl_info['version']`: (MAJOR, MINOR, PATCH). Patch = fixes / packaging, Minor = new features, Major = breaking changes.

## 🛠️ Building / Packaging

You can build the distributable zip in three ways:

PowerShell (auto-detect version):
```powershell
pwsh scripts/build.ps1
```

Specify version override:
```powershell
pwsh scripts/build.ps1 -Version 1.10.6
```

Cross-platform Python script:
```bash
python scripts/package_addon.py
```

Override version:
```bash
python scripts/package_addon.py --version 1.10.6
```

Output: `render-queue-manager-vX.Y.Z.zip` at repo root and staging under `dist/`.

GitHub Actions: Push a tag (e.g., `v1.10.6`). The workflow builds, attaches the zip, and creates release notes with a commit diff since the previous tag.

---

Made for production batch rendering and extension. Enjoy.
