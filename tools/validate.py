#!/usr/bin/env python3
"""Validate package-factory configuration."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory


def validate_buildroots(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"missing buildroot lock: {path}")
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"invalid buildroot lock: {path}")
    if data.get("schema") != 1 or not isinstance(data.get("buildroots"), dict):
        raise SystemExit(f"invalid buildroot lock: {path}")
    if not data["buildroots"]:
        raise SystemExit(f"invalid buildroot lock: no buildroots defined in {path}")
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

    workflow_path = path.resolve().parent.parent / ".github" / "workflows" / "rebuild-rpms.yml"
    if workflow_path.is_file():
        match = re.search(r"^\s*BUILDROOT_IMAGE:\s*(\S+)", workflow_path.read_text(), re.MULTILINE)
        if match:
            wf_image = match.group(1).strip()
            fedora_44 = data["buildroots"].get("fedora-44", {})
            lock_image = fedora_44.get("image", "") if isinstance(fedora_44, dict) else ""
            if lock_image and wf_image != lock_image:
                raise SystemExit(
                    f"buildroot drift: config/buildroot-lock.json fedora-44 image ({lock_image}) "
                    f"does not match rebuild-rpms.yml BUILDROOT_IMAGE ({wf_image})"
                )


def check_provenance(path: Path, data: dict) -> None:
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
        if not data.get("remote"):
            raise SystemExit(f"upstream import must name its upstream remote: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        for key in ("commit", "tree"):
            if not data.get(key):
                raise SystemExit(f"rawhide import must carry {key}: {path}")
            if not FULL_SHA.fullmatch(data[key]):
                raise SystemExit(f"rawhide import must carry a full {key} SHA: {path}")


def main(root: Path = Path(".")) -> int:
    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        return 0
    for directory in sorted(packages_dir.iterdir()):
        if not directory.is_dir():
            continue
        path = directory / ".hummingbird-upstream.json"
        if not path.is_file():
            raise SystemExit(f"missing upstream provenance: {path}")
        data = json.loads(path.read_text())
        check_provenance(path, data)
    records = inventory(root)
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
        return 1
    validate_buildroots(root / "config" / "buildroot-lock.json")
    print(f"validated {len(records)} source RPMs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
