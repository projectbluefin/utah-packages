#!/usr/bin/env python3
"""Transfer recipe data across the import workflow's read/write job boundary."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from tools.bootstrap_upstream_sources import merge_candidates
from tools.import_rawhide import validate_package


def restore(root: Path, incoming: Path, package: str) -> None:
    validate_package(package)
    allowed = {"packages", "candidate.json", "report.json"}
    if {p.name for p in incoming.iterdir()} != allowed:
        raise ValueError("unexpected import artifact entries")
    for path in incoming.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"import artifact contains a link or special file: {path}")
    recipe_root = incoming / "packages"
    if {p.name for p in recipe_root.iterdir()} != {package}:
        raise ValueError("artifact must contain exactly the requested recipe")
    recipe = recipe_root / package
    if len(list(recipe.glob("*.spec"))) != 1:
        raise ValueError("recipe must contain exactly one spec")
    provenance = json.loads((recipe / ".hummingbird-upstream.json").read_text())
    if provenance.get("package") != package:
        raise ValueError("recipe provenance names another package")
    candidate = json.loads((incoming / "candidate.json").read_text())
    entries = candidate.get("packages", [])
    if len(entries) != 1 or entries[0].get("name") != package:
        raise ValueError("source candidate must name exactly the requested package")
    report = json.loads((incoming / "report.json").read_text())
    if report.get("accepted") != 1 or report.get("rejected"):
        raise ValueError("source bootstrap did not accept the requested package")
    lock = root / "config/upstream-sources.json"
    merged = merge_candidates(json.loads(lock.read_text()), entries)
    destination = root / "packages" / package
    if destination.exists():
        raise ValueError("an import cannot replace a carried recipe")
    shutil.copytree(recipe, destination)
    lock.write_text(json.dumps(merged, indent=2) + "\n")
    report_path = root / "reports/import-source-bootstrap.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("incoming", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    restore(args.root, args.incoming, args.package)


if __name__ == "__main__":
    main()
