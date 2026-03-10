#!/usr/bin/env python3
"""Package the Blender extension into a versioned zip.

Usage:
  python scripts/package_extension.py [--version X.Y.Z] [--out dist]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RE_INIT_VERSION = re.compile(r"__version__\s*=\s*['\"]([^'\"]+)['\"]")
RE_MANIFEST_VERSION = re.compile(r"^version\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
RE_MANIFEST_ID = re.compile(r"^id\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def read_version_from_init() -> str:
    init_path = ROOT / "__init__.py"
    match = RE_INIT_VERSION.search(init_path.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("Failed to locate __version__ in __init__.py")
    return match.group(1).strip()


def read_manifest_metadata() -> tuple[str, str]:
    manifest_path = ROOT / "blender_manifest.toml"
    text = manifest_path.read_text(encoding="utf-8")

    match_id = RE_MANIFEST_ID.search(text)
    if not match_id:
        raise SystemExit("Failed to locate id in blender_manifest.toml")
    extension_id = match_id.group(1).strip()

    match_version = RE_MANIFEST_VERSION.search(text)
    if not match_version:
        raise SystemExit("Failed to locate version in blender_manifest.toml")
    manifest_version = match_version.group(1).strip()

    return extension_id, manifest_version


def build(version: str, out_dir: Path) -> Path:
    extension_id, manifest_version = read_manifest_metadata()
    version_from_init = read_version_from_init()

    if version != manifest_version:
        raise SystemExit(
            f"Version mismatch: requested {version} but manifest has {manifest_version}"
        )

    if version != version_from_init:
        raise SystemExit(
            f"Version mismatch: requested {version} but __init__ has {version_from_init}"
        )

    staging_root = out_dir / extension_id
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)

    for fname in ["__init__.py", "README.md", "CHANGELOG.md", "LICENSE", "blender_manifest.toml"]:
        shutil.copy2(ROOT / fname, staging_root / fname)
    shutil.copytree(
        ROOT / "rqm",
        staging_root / "rqm",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    zip_base_name = extension_id.replace("_", "-")
    zip_name = f"{zip_base_name}-v{version}.zip"
    zip_path = ROOT / zip_name
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in staging_root.rglob("*"):
            z.write(path, path.relative_to(out_dir))

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"Created {zip_name} (sha256={sha256})")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Override version (default: __version__ in __init__.py)")
    parser.add_argument("--out", default="dist", help="Output directory for staging (default: dist)")
    args = parser.parse_args()

    requested_version = args.version or read_version_from_init()
    out_dir = ROOT / args.out
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    build(requested_version, out_dir)


if __name__ == "__main__":
    main()
