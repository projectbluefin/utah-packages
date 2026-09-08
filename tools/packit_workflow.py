#!/usr/bin/env python3
"""Small machine-readable helpers shared by Packit CI orchestrators."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


# Underscores are part of a package name: lm_sensors and volume_key are both
# real recipes. Without one here they parse as no package at all, and a name
# this misses is a name the rebuild matrix silently never builds.
PACKAGE_KEY = re.compile(r"^  ([a-zA-Z0-9][a-zA-Z0-9+._-]*):$")


def package_names(config: Path) -> list[str]:
    packages = config.read_text().split("packages:\n", 1)[1]
    return [
        match.group(1)
        for line in packages.splitlines()
        if (match := PACKAGE_KEY.fullmatch(line))
    ]


# GitHub caps a matrix at 256 jobs, and a larger one does not fail -- it
# expands to nothing. The pilot enumerates every package in the monorepo, so
# once that passed 256 its srpm matrix produced zero jobs and the run failed
# beneath a green discover step. Hand the matrix chunks instead.
MATRIX_CHUNK = 250


def package_chunks(names: list[str], size: int = MATRIX_CHUNK) -> list[str]:
    """Split names into JSON-encoded chunks, none exceeding the matrix cap."""
    if size < 1:
        raise ValueError("chunk size must be positive")
    return [
        json.dumps(names[start : start + size])
        for start in range(0, len(names), size)
    ]


def result(package: str, status: str, nevra: str) -> str:
    return json.dumps(
        {"package": package, "status": status, "nevra": nevra},
        sort_keys=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    packages_parser = subparsers.add_parser("packages")
    packages_parser.add_argument("--config", type=Path, default=Path(".packit.yaml"))

    chunks_parser = subparsers.add_parser("chunks")
    chunks_parser.add_argument("--config", type=Path, default=Path(".packit.yaml"))
    chunks_parser.add_argument("--size", type=int, default=MATRIX_CHUNK)

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--package", required=True)
    result_parser.add_argument("--status", choices=("success", "failure"), required=True)
    result_parser.add_argument("--nevra", default="")

    args = parser.parse_args()
    if args.command == "packages":
        print(json.dumps(package_names(args.config)))
    elif args.command == "chunks":
        print(json.dumps(package_chunks(package_names(args.config), args.size)))
    else:
        print(result(args.package, args.status, args.nevra))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
