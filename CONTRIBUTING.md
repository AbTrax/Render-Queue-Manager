# Contributing

Thanks for your interest in improving Render Queue Manager X!

## Development Setup
1. Clone the repository.
2. Zip the root (containing `blender_manifest.toml` and `rqm/`) or create a symlink inside your Blender `scripts/extensions` folder.
3. Enable Render Queue Manager X from Blender's Extensions preferences.

## Code Style
- Keep modules focused (`properties`, `outputs`, `queue_ops`, `ui`, `utils`).
- Avoid heavy side effects in module import scope.
- Prefer small functions; log warnings instead of raising unless fatal.

## Versioning
Keep the version string in `__version__` and `blender_manifest.toml` aligned. Bump patch for fixes, minor for features.

## Pull Requests
1. Describe feature or fix clearly.
2. Note any user-facing changes.
3. Update `CHANGELOG.md`.

## Extension Hooks
Register a preprocessor via:
```python
import rqm
rqm.queue_ops.JOB_PREPROCESSORS.append(lambda job, scene: (True, ''))
```
Return `(False, 'reason')` to skip a job.

## License
By contributing you agree your code is licensed under the GPL-3.0-or-later.
