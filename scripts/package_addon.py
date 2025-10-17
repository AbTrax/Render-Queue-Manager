#!/usr/bin/env python3
"""Package the Blender add-on into a versioned zip.

Usage:
  python scripts/package_addon.py [--version X.Y.Z] [--out dist]

If --version is omitted the version tuple in root __init__.py is used.
"""
from __future__ import annotations
import argparse, re, shutil, zipfile, hashlib
from pathlib import Path

RE_VERSION = re.compile(r"version': \(([^)]+)\)")

ROOT = Path(__file__).resolve().parents[1]


def parse_version(text: str) -> str:
    m = RE_VERSION.search(text)
    if not m:
        raise SystemExit("Could not find version tuple in __init__.py")
    parts = [p.strip() for p in m.group(1).split(',') if p.strip().isdigit()]
    if not parts:
        raise SystemExit("Parsed empty version tuple")
    # keep at most 3 segments
    return '.'.join(parts[:3])


def read_version() -> str:
    init_path = ROOT / '__init__.py'
    return parse_version(init_path.read_text(encoding='utf-8'))


def build(version: str, out_dir: Path) -> Path:
    folder_name = 'render_queue_manager_x'
    staging_root = out_dir / folder_name
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)

    # copy files
    for fname in ['__init__.py', 'README.md', 'CHANGELOG.md', 'LICENSE']:
        shutil.copy2(ROOT / fname, staging_root / fname)
    shutil.copytree(ROOT / 'rqm', staging_root / 'rqm')

    zip_name = f'render-queue-manager-x-v{version}.zip'
    zip_path = ROOT / zip_name
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in staging_root.rglob('*'):
            z.write(path, path.relative_to(out_dir))

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f'Created {zip_name} (sha256={sha256})')
    return zip_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', help='Override version (default: from __init__.py)')
    ap.add_argument('--out', default='dist', help='Output directory for staging (default: dist)')
    args = ap.parse_args()

    version = args.version or read_version()
    out_dir = ROOT / args.out
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    build(version, out_dir)

if __name__ == '__main__':
    main()
