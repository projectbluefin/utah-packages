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
    provenance: Path | None
    provenance_branch: str | None


def _recipe_provenance(root: Path) -> dict[str, tuple[Path, str]]:
    provenance = {}
    for path in sorted((root / "packages").glob("*/.hummingbird-upstream.json")):
        name = path.parent.name
        data = json.loads(path.read_text())
        branch = data.get("branch")
        if not isinstance(branch, str):
            raise ValueError(f"invalid provenance branch: {path}")
        provenance[name] = (path, branch)
    return provenance


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
    provenance = _recipe_provenance(root)
    return [
        PackageRecord(
            name=name,
            spec=spec,
            stage=locks.get(name, 0),
            source_locked=name in locks,
            packit_configured=name in packit,
            provenance=provenance.get(name, (None, None))[0],
            provenance_branch=provenance.get(name, (None, None))[1],
        )
        for name, spec in specs.items()
    ]
