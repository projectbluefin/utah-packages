#!/usr/bin/env python3
"""Validate package-factory configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory

packages = [
    raw.strip()
    for raw in Path("config/bootstrap-packages.txt").read_text().splitlines()
    if raw.strip() and not raw.lstrip().startswith("#")
]
for path in Path("packages").glob("*/.hummingbird-upstream.json"):
    import json
    data = json.loads(path.read_text())
    required = {"package", "branch", "remote", "commit", "tree", "imported_at"}
    if set(data) != required:
        raise SystemExit(f"invalid upstream provenance: {path}")
    if data["branch"] not in ("rawhide", "upstream"):
        raise SystemExit(f"only rawhide or upstream imports are supported: {path}")
    if data["branch"] == "upstream":
        # Direct-upstream recipes (e.g. liblc3plus, libfreeaptx,
        # pipewire-libs-extra) are imported from the project's own release
        # repository rather than Fedora dist-git. They carry a remote and
        # imported_at but no dist-git commit/tree; the verified source lock
        # lives in config/upstream-sources.json instead.
        for key in ("commit", "tree"):
            if data[key]:
                raise SystemExit(f"upstream import must not carry {key}: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        for key in ("commit", "tree"):
            if not data[key]:
                raise SystemExit(f"rawhide import must carry {key}: {path}")
if not packages:
    raise SystemExit("bootstrap package set is empty")
if len(packages) != len(set(packages)):
    raise SystemExit("bootstrap package set contains duplicates")
if any(" " in package or "/" in package for package in packages):
    raise SystemExit("package names must be source RPM names, one per line")
records = inventory(Path("."))
missing_locks = sorted(record.name for record in records if not record.source_locked)
missing_packit = sorted(record.name for record in records if not record.packit_configured)
if missing_locks or missing_packit:
    if missing_locks:
        print(f"packages missing source locks: {', '.join(missing_locks)}")
    if missing_packit:
        print(f"packages missing Packit config: {', '.join(missing_packit)}")
    raise SystemExit(1)
print(f"validated {len(packages)} source RPMs")
