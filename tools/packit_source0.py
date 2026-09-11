#!/usr/bin/env python3
"""Tell Packit to use the factory's already-verified Source0 archive."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import source_locks


def verified_source0(root: Path, working_directory: Path | None = None) -> str:
    spec_path = os.environ.get("PACKIT_SPECFILE_PATH")
    if not spec_path:
        raise ValueError("PACKIT_SPECFILE_PATH is not set")

    configured = Path(spec_path)
    candidates = []
    package_env = os.environ.get("PACKAGE")
    if package_env and (root / "packages" / package_env / configured.name).is_file():
        candidates.append(root / "packages" / package_env / configured.name)
    elif configured.is_absolute() and configured.is_file():
        candidates.append(configured)
    elif (root / configured).is_file():
        candidates.append(root / configured)
    else:
        candidates.extend(root.glob(f"packages/*/{configured.name}"))
    if len(candidates) != 1:
        raise ValueError(f"cannot uniquely locate Packit spec file: {spec_path}")

    package_name = candidates[0].parent.name
    lock = source_locks(root).get(package_name)
    if lock is None:
        raise ValueError(f"no source lock for {package_name}")

    archive = candidates[0].parent / lock["filename"]
    if not archive.is_file():
        raise ValueError(f"verified Source0 is not staged: {archive}")
    working_directory = (working_directory or Path.cwd()).resolve()
    try:
        return str(archive.resolve().relative_to(working_directory))
    except ValueError:
        return str(archive.relative_to(root))


def main() -> int:
    root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )
    print(verified_source0(root, Path.cwd()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
