#!/usr/bin/env python3
"""Write the package/source/buildroot manifest published beside the RPM repo."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def rpm_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.rpm"))


def reports(root: Path, prefix: str | None = None) -> list[object]:
    report_dir = root / "reports"
    if not report_dir.is_dir():
        return []
    values = []
    for path in sorted(report_dir.glob("*.json")):
        if prefix and not path.name.startswith(prefix):
            continue
        data = read_json(path)
        if isinstance(data, dict):
            data.setdefault("report", str(path.relative_to(root)))
            values.append(data)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--build-list", default="[]", help="JSON array emitted by the prepare job")
    parser.add_argument("--buildroot-lock", type=Path, default=Path("config/buildroot-lock.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oci-ref", default="")
    parser.add_argument("--oci-digest", default="")
    args = parser.parse_args(argv)

    try:
        requested = json.loads(args.build_list)
    except json.JSONDecodeError:
        requested = []
    if not isinstance(requested, list):
        requested = []

    source_reports = reports(args.repository)
    buildroot_reports = [item for item in source_reports if isinstance(item, dict) and str(item.get("name", "")).startswith("fedora-")]
    package_reports = [item for item in source_reports if item not in buildroot_reports]
    payload = {
        "schema": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "requested_packages": requested,
        "packages": rpm_files(args.repository),
        "sources": package_reports,
        "buildroot_lock": read_json(args.buildroot_lock),
        "buildroots": buildroot_reports,
        "oci": {"ref": args.oci_ref, "digest": args.oci_digest},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote factory manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
