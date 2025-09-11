<div align="center">
<h1>Render Queue Manager</h1>
<p><strong>Blender add-on for structured multi-job rendering with clean foldering, compositor integration, and stereoscopy.</strong></p>
<p>
<sup>Per-job folders · Zero-based numbering · File Output node management · Extension hooks · Windows‑safe paths</sup>
</p>
</div>

---

## ✨ Features
- Per-job overrides: scene, camera, engine, resolution, animation range (remapped to start at frame 0 for consistent filenames).
- Deterministic directory layout:
  - Base renders: `<root>/<job_name>/base/<basename><frame>.ext`
  - Compositor outputs: `<root>/<job_name>/comp/<NodeName>/...`
- Multiple Compositor File Output nodes per job (we only manage base path + optional format + default slot naming).
- Smart slot naming: empty/default slot paths become `<job>_<basename>`.
- Optional stereoscopic (multi‑view) rendering with selectable output format.
- Non‑blocking compositor mode (warn instead of abort) per job.
- Pluggable preprocessors: inject logic before each job via `JOB_PREPROCESSORS`.
- Windows‑safe name sanitizing (reserved device names avoided).

## 📦 Structure
```
__init__.py        # Add-on entry (bl_info + registers submodules)
rqm/
  __init__.py      # Internal namespace
  utils.py         # Sanitizing, tokens, path helpers
  properties.py    # PropertyGroups (jobs, outputs, state)
  outputs.py       # Compositor File Output handling
  queue_ops.py     # Operators, handlers, job application
  ui.py            # Panels & UILists
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
```
<output_root>/Shot01_MainCam/
  base/render0000.png …
  <FileOutputNodeName>/<job>_<basename>0000.png
```
Animation frame range (e.g. 101–148) is internally remapped so exported files still begin at `0000`.

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

Note: The previous “Detect View Tags” utility was removed. Use the free‑text Extra View Tags field to specify additional tags if needed.

## 🔌 Extension Hooks
Register a preprocessor to tweak the scene before each job render:
```python
import rqm

def force_cycles(job, scene):
    scene.render.engine = 'CYCLES'
    return True, ''

rqm.queue_ops.JOB_PREPROCESSORS.append(force_cycles)
```
Return `(False, 'reason')` to skip the job (logged as a warning or failure depending on context).

## 🐛 Troubleshooting
| Issue | Cause | Fix |
|-------|-------|-----|
| Add-on fails: `No module named 'rqm'` | Zip contained an extra parent folder | Re-zip so `__init__.py` is at archive root |
| Compositor outputs not written | Node missing or disabled | Enable node or use “Create if missing” |
| Wrong frame numbers | Expectation of original frame numbers | Tool intentionally remaps to 0-based for consistent batches |
| Overwriting from multiple jobs | Same job name/basename | Ensure unique job names or change basename |

## ❓ FAQ
**Why always start at 0000?**  Consistent naming prevents gaps and cross-project confusion when merging outputs.

**Can I keep original frame numbers?** Not currently; a future option may allow an offset.

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
```
pwsh scripts/build.ps1
```

Specify version override:
```
pwsh scripts/build.ps1 -Version 1.10.6
```

Cross-platform Python script:
```
python scripts/package_addon.py
```

Override version:
```
python scripts/package_addon.py --version 1.10.6
```

Output: `render-queue-manager-vX.Y.Z.zip` at repo root and staging under `dist/`.

GitHub Actions: Push a tag (`git tag -a v1.10.6 -m "Release" && git push origin v1.10.6`). Workflow builds, attaches zip, and creates release notes with commit diff since previous tag.

---

Made for production batch rendering and extension. Enjoy.
