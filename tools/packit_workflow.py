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

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--package", required=True)
    result_parser.add_argument("--status", choices=("success", "failure"), required=True)
    result_parser.add_argument("--nevra", default="")

    args = parser.parse_args()
    if args.command == "packages":
        print(json.dumps(package_names(args.config)))
    else:
        print(result(args.package, args.status, args.nevra))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
