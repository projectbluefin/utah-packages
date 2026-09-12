#!/usr/bin/env python3
"""Validate package-factory configuration."""
import json
import re
import sys
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def validate_buildroots(path: Path) -> None:
    data = json.loads(path.read_text())
    if data.get("schema") != 1 or not isinstance(data.get("buildroots"), dict):
        raise SystemExit(f"invalid buildroot lock: {path}")
    for name, buildroot in data["buildroots"].items():
        image = buildroot.get("image") if isinstance(buildroot, dict) else None
        if not isinstance(image, str) or "@sha256:" not in image:
            raise SystemExit(f"buildroot {name} image must be digest-pinned")
        packages = buildroot.get("packages", [])
        if not isinstance(packages, list):
            raise SystemExit(f"buildroot {name} packages must be a list")
        for package in packages:
            if not isinstance(package, dict) or not package.get("nevra"):
                raise SystemExit(f"buildroot {name} package locks must carry NEVRA entries")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory

for path in Path("packages").glob("*/.hummingbird-upstream.json"):
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
        if not data["remote"]:
            raise SystemExit(f"upstream import must name its upstream remote: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        if not FULL_SHA.fullmatch(data["commit"]):
            raise SystemExit(f"rawhide import must carry a full commit SHA: {path}")
        if not FULL_SHA.fullmatch(data["tree"]):
            raise SystemExit(f"rawhide import must carry a full tree SHA: {path}")
records = inventory(Path("."))
missing_locks = sorted(record.name for record in records if not record.source_locked)
missing_packit = sorted(record.name for record in records if not record.packit_configured)
missing_provenance = sorted(record.name for record in records if record.provenance is None)
if missing_locks or missing_packit or missing_provenance:
    if missing_locks:
        print(f"packages missing source locks: {', '.join(missing_locks)}")
    if missing_packit:
        print(f"packages missing Packit config: {', '.join(missing_packit)}")
    if missing_provenance:
        print(f"packages missing recipe provenance: {', '.join(missing_provenance)}")
    raise SystemExit(1)
validate_buildroots(Path("config/buildroot-lock.json"))
print(f"validated {len(records)} source RPMs")
