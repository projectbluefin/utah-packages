#!/usr/bin/env python3
"""Capture the resolved buildroot package state as a lock file.

Runs inside the buildroot container after ``dnf builddep`` has resolved the
recipe dependencies.  Every installed RPM NEVRA is recorded as a snapshot so
that a later run can detect silent buildroot drift: a mutable Fedora or
Hummingbird repository tag that moved between runs would change the NEVRA set,
and the lock surfaces that change rather than hiding it.

Usage (inside the container)::

    python3 /work/tools/capture_buildroot.py \\
        --buildroot work/reports/buildroot-<package>.json \\
        --image-ref quay.io/fedora/fedora:44@sha256:abc123

The output is a JSON document keyed by package name with NEVRA, architecture,
and source RPM, plus the pinned image digest and a UTC timestamp.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def query_rpms() -> list[dict[str, str]]:
    """Return every installed RPM in the buildroot as structured records."""
    query = r"%{NAME}\t%{EPOCH}\t%{VERSION}\t%{RELEASE}\t%{ARCH}\t%{SOURCERPM}\t%{REPOID}"
    result = subprocess.run(
        ["rpm", "-qa", "--qf", query + "\n"],
        capture_output=True, text=True, check=True,
    )
    records: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 7:
            continue
        name, epoch, version, release, arch, sourcerpm, repoid = parts
        records.append({
            "name": name,
            "epoch": epoch if epoch and epoch != "(none)" else "0",
            "version": version,
            "release": release,
            "arch": arch,
            "source_rpm": sourcerpm if sourcerpm and sourcerpm != "(none)" else "",
            "repository": repoid if repoid and repoid != "(none)" else "",
        })
    return sorted(records, key=lambda r: r["name"])


def nevra(record: dict[str, str]) -> str:
    """Render a single record as a NEVRA string."""
    epoch = record["epoch"]
    if epoch and epoch != "0":
        return f"{epoch}:{record['name']}-{record['version']}-{record['release']}.{record['arch']}"
    return f"{record['name']}-{record['version']}-{record['release']}.{record['arch']}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buildroot", type=Path, required=True,
                        help="path to write the buildroot lock JSON")
    parser.add_argument("--image-ref", default="",
                        help="the digest-pinned image reference this buildroot was created from")
    parser.add_argument("--check", type=Path,
                        help="compare current buildroot against this previous lock; fail on drift")
    args = parser.parse_args()

    records = query_rpms()
    lock = {
        "captured_at": datetime.now(UTC).isoformat(),
        "image_ref": args.image_ref,
        "package_count": len(records),
        "packages": {r["name"]: r for r in records},
        "nevras": [nevra(r) for r in records],
    }

    if args.check:
        previous = json.loads(args.check.read_text())
        current_names = {r["name"] for r in records}
        previous_names = set(previous.get("packages", {}))
        added = sorted(current_names - previous_names)
        removed = sorted(previous_names - current_names)
        changed = sorted(
            name for name in (current_names & previous_names)
            if nevra(lock["packages"][name]) != nevra(previous["packages"][name])
        )
        if added or removed or changed:
            print("BUILDROOT DRIFT detected:", file=sys.stderr)
            if added:
                print(f"  added: {', '.join(added)}", file=sys.stderr)
            if removed:
                print(f"  removed: {', '.join(removed)}", file=sys.stderr)
            if changed:
                for name in changed:
                    old = nevra(previous["packages"][name])
                    new = nevra(lock["packages"][name])
                    print(f"  changed: {name}: {old} -> {new}", file=sys.stderr)
            return 1
        print(f"buildroot unchanged: {len(records)} packages match the lock")
        return 0

    args.buildroot.parent.mkdir(parents=True, exist_ok=True)
    args.buildroot.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(f"captured {len(records)} buildroot packages -> {args.buildroot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
