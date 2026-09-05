#!/usr/bin/env python3
"""Repository-wide package inventory: the single enforceable contract.

Every factory task consumes :func:`inventory` instead of rescanning
``packages/``, ``config/upstream-sources.json``, or ``.packit.yaml`` on its
own. The inventory refuses ambiguous state outright: duplicate spec
directories, duplicate source locks, unknown stages, or multiple specs per
package are contract violations, not warnings.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tools.packit_workflow import package_names

# Stages the rebuild matrix (.github/workflows/rebuild-rpms.yml) can resolve;
# packages without an explicit stage build in stage 0.
KNOWN_STAGES = frozenset(range(5))


@dataclass(frozen=True)
class PackageRecord:
    name: str
    spec: Path
    stage: int
    source_locked: bool
    packit_configured: bool


def _spec_per_package(root: Path) -> dict[str, Path]:
    specs = {}
    for directory in sorted((root / "packages").iterdir()):
        if not directory.is_dir():
            continue
        found = sorted(directory.glob("*.spec"))
        if len(found) != 1:
            raise ValueError(f"expected exactly one spec in {directory}")
        if directory.name in specs:
            raise ValueError(f"duplicate spec directory: {directory.name}")
        specs[directory.name] = found[0]
    return specs


def _source_locks(root: Path) -> dict[str, int]:
    data = json.loads((root / "config" / "upstream-sources.json").read_text())
    locks = {}
    for entry in data["packages"]:
        name = entry["name"]
        if name in locks:
            raise ValueError(f"duplicate source lock: {name}")
        stage = entry.get("stage", 0)
        if not isinstance(stage, int) or stage not in KNOWN_STAGES:
            raise ValueError(f"unknown stage for {name}: {stage!r}")
        locks[name] = stage
    return locks


def inventory(root: Path) -> list[PackageRecord]:
    specs = _spec_per_package(root)
    locks = _source_locks(root)
    packit = set(package_names(root / ".packit.yaml"))
    return [
        PackageRecord(
            name=name,
            spec=spec,
            stage=locks.get(name, 0),
            source_locked=name in locks,
            packit_configured=name in packit,
        )
        for name, spec in specs.items()
    ]
