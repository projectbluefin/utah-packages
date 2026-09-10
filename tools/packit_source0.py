#!/usr/bin/env python3
"""Tell Packit to use the factory's already-verified Source0 archive."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


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
    config = json.loads((root / "config" / "upstream-sources.json").read_text())
    matches = [
        package
        for package in config["packages"]
        if package["name"] == package_name
    ]
    if len(matches) != 1:
        raise ValueError(f"cannot uniquely locate source lock for {package_name}")

    if matches[0].get("no_upstream_source"):
        return _placeholder_archive(candidates[0].parent, package_name, matches[0]["version"])

    archive = candidates[0].parent / matches[0]["filename"]
    if not archive.is_file():
        raise ValueError(f"verified Source0 is not staged: {archive}")
    working_directory = (working_directory or Path.cwd()).resolve()
    try:
        return str(archive.resolve().relative_to(working_directory))
    except ValueError:
        return str(archive.relative_to(root))


def _placeholder_archive(spec_dir: Path, package: str, version: str) -> str:
    """Satisfy Packit's create-archive contract for a recipe with no archive.

    color-filesystem has no upstream source at all -- four directories and an
    rpm macro file, no Source line, no dist-git sources -- so its lock declares
    `no_upstream_source` rather than inventing a URL. Packit does not offer a
    way to opt out: `prepare()` calls create_archive unconditionally, and the
    action must print the path of a file that exists or Packit raises "No output
    from create-archive action."

    Nothing consumes the bytes. The workflow passes --preserve-spec, so Packit
    never rewrites Source0 to point at this, and a spec with no Source line puts
    nothing but itself in the SRPM. It is written into the spec directory so
    Packit has no archive outside the spec dir to symlink, and it is emitted
    empty with a zeroed gzip header so two runs produce identical bytes.
    """
    archive = spec_dir / f"{package}-{version}.tar.gz"
    if not archive.is_file():
        with archive.open("wb") as sink:
            with gzip.GzipFile(filename="", mode="wb", fileobj=sink, mtime=0) as raw:
                with tarfile.open(fileobj=raw, mode="w"):
                    pass
    return archive.name


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
