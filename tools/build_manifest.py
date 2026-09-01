#!/usr/bin/env python3
"""Merge per-package build identity records into a candidate manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def update(root: Path) -> Path:
    manifest_path = root / "factory-build-manifest.json"
    manifest: dict[str, object] = {"schema": 1, "packages": {}}
    if manifest_path.is_file():
        try:
            prior = json.loads(manifest_path.read_text())
            if isinstance(prior, dict) and isinstance(prior.get("packages"), dict):
                manifest["packages"].update(prior["packages"])
        except (OSError, ValueError, TypeError):
            pass

    packages = manifest["packages"]
    assert isinstance(packages, dict)
    for path in sorted(root.rglob("*.build-key.json")):
        try:
            item = json.loads(path.read_text())
            package = item["package"]
            build_key = item["build_key"]
            outputs = item["outputs"]
            if not isinstance(package, str) or not isinstance(build_key, str):
                continue
            if not isinstance(outputs, list) or not outputs:
                continue
        except (OSError, ValueError, TypeError, KeyError):
            continue
        packages[package] = {"build_key": build_key, "outputs": outputs}

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    update(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
