#!/usr/bin/env python3
"""Create a deterministic Rawhide availability report.

This is observability only. Rawhide metadata must not trigger a package update:
Fedora dist-git snapshots are accepted by dist_git.py only after their NVR has
passed the Koji gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.rawhide_sources import import_binaries, source_name


def query(package: str) -> dict[str, str] | None:
    command = [
        "dnf", "repoquery", "--latest-limit=1",
        "--qf", "%{name}\\t%{evr}\\t%{arch}\\t%{sourcerpm}", package,
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    lines = [line for line in result.stdout.splitlines() if line and "(none)" not in line]
    if not lines:
        return None
    name, evr, arch, sourcerpm = lines[0].split("\\t", 3)
    return {"name": name, "evr": evr, "arch": arch, "sourcerpm": sourcerpm}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("config/bluefin-packages.toml"))
    parser.add_argument("--state", type=Path, default=Path("config/rawhide-state.json"))
    parser.add_argument("--changed", type=Path, default=Path("reports/rawhide-changed-sources.txt"))
    args = parser.parse_args()

    manifest = tomllib.loads(args.manifest.read_text())
    binaries = import_binaries(manifest)
    state = {package: query(package) for package in binaries}
    state = {package: value for package, value in state.items() if value}
    previous = json.loads(args.state.read_text()) if args.state.exists() else {}
    changed = sorted({
        source_name(value["sourcerpm"])
        for package, value in state.items()
        if previous.get(package) != value
    })

    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.changed.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    args.changed.write_text("\n".join(changed) + ("\n" if changed else ""))
    print(f"observed {len(state)} Rawhide packages; queued {len(changed)} source rebuilds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
