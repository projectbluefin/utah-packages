#!/usr/bin/env python3
"""Resolve a factory package to the recipe directory and rpm defines it builds with.

A package entry normally builds packages/<name>. Two entries may share one
recipe and differ only in the macros passed to rpmbuild: that is how a long
recipe is split into shards that build on separate runners. webkitgtk compiles
its source twice, once per GTK port, and the two compiles have nothing in
common but the tarball -- five hours on one runner, two and a half on two.

    "name": "webkit2gtk4.1", "recipe": "webkitgtk", "rpm_defines": ["_without_gtk4 1"]

Every consumer of the recipe directory goes through here so an alias cannot
be honoured in one place and missed in another: the source pipeline stages
bundled sources from it, the build identity hashes it, and the lane workflow
mounts it.

    recipe.py NAME dir       packages/<recipe> relative to the repository root
    recipe.py NAME defines   one "MACRO VALUE" per line, for rpmbuild -D
    recipe.py NAME cache     "true" when the entry keeps a compiler cache
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "upstream-sources.json"


def entry(name: str, config: dict | None = None) -> dict:
    if config is None:
        config = json.loads(CONFIG.read_text())
    matches = [item for item in config.get("packages", []) if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"package is not uniquely configured: {name}")
    return matches[0]


def recipe_name(item: dict) -> str:
    """The packages/ directory an entry builds from."""
    return item.get("recipe") or item["name"]


def lookaside_name(item: dict) -> str:
    """The Fedora dist-git name the recipe was imported from, for its lookaside."""
    return item.get("dist_git_name") or recipe_name(item)


def rpm_defines(item: dict) -> list[str]:
    defines = item.get("rpm_defines", [])
    if not isinstance(defines, list) or not all(
        isinstance(define, str) and len(define.split(None, 1)) == 2 for define in defines
    ):
        raise ValueError(f"rpm_defines for {item.get('name')} must be a list of 'MACRO VALUE' strings")
    return list(defines)


def compiler_cache(item: dict) -> bool:
    """Whether this entry publishes and restores an sccache directory.

    Only worth it where the compile dominates: restoring and publishing a
    multi-gigabyte cache costs minutes, which a three-minute package would pay
    for nothing. Opt in per entry with "compiler_cache": true.
    """
    value = item.get("compiler_cache", False)
    if not isinstance(value, bool):
        raise ValueError(f"compiler_cache for {item.get('name')} must be true or false")
    return value


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in ("dir", "defines", "cache"):
        print(__doc__, file=sys.stderr)
        return 2
    item = entry(sys.argv[1])
    if sys.argv[2] == "dir":
        print(f"packages/{recipe_name(item)}")
    elif sys.argv[2] == "cache":
        print("true" if compiler_cache(item) else "false")
    else:
        for define in rpm_defines(item):
            print(define)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
