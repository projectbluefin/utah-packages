#!/usr/bin/env python3
"""Tell Packit to use the factory's already-verified Source0 archive."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def verified_source0(root: Path) -> str:
    spec_path = os.environ.get("PACKIT_SPECFILE_PATH")
    if not spec_path:
        raise ValueError("PACKIT_SPECFILE_PATH is not set")

    configured = Path(spec_path)
    candidates = []
    if configured.is_absolute() and configured.is_file():
        candidates.append(configured)
    elif (root / configured).is_file():
        candidates.append(root / configured)
    else:
        candidates.extend(root.glob(f"packages/*/{configured.name}"))
    if len(candidates) != 1:
        raise ValueError(f"cannot uniquely locate Packit spec file: {spec_path}")

    package_name = candidates[0].parent.name
    config = json.loads((root / "config" / "upstream-sources.json").read_text())
    matches = [
        package
        for package in config["packages"]
        if package["name"] == package_name
        or package.get("dist_git_name") == package_name
    ]
    if len(matches) != 1:
        raise ValueError(f"cannot uniquely locate source lock for {package_name}")

    archive = candidates[0].parent / matches[0]["filename"]
    if not archive.is_file():
        raise ValueError(f"verified Source0 is not staged: {archive}")
    return str(archive.relative_to(root))


def main() -> int:
    root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )
    print(verified_source0(root))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
