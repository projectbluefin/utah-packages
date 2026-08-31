#!/usr/bin/env python3
"""Emit a complete build manifest for the factory publication.

Assembles the provenance, source, buildroot, and package information produced
by a rebuild run into a single manifest.  The manifest is published alongside
the OCI digest so that any consumer or auditor can reproduce exactly what went
into an image: which buildroot image digest was used, every RPM in it, the
verified upstream source lock for each package, and the resulting binary RPMs.

Usage (in the publish job, after artifacts are downloaded)::

    python3 tools/emit_manifest.py \\
        --buildroot-lock config/buildroot-lock.json \\
        --package-dir repository \\
        --report-dir work/downloaded-reports \\
        --output repository/manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def collect_rpms(package_dir: Path) -> list[dict[str, str]]:
    """Query every RPM in *package_dir* for its NEVRA and SHA-256 digest."""
    rpms: list[dict[str, str]] = []
    rpm_files = sorted(package_dir.rglob("*.rpm"))
    for path in rpm_files:
        if path.name.endswith(".src.rpm"):
            continue
        try:
            nevra = subprocess.check_output(
                ["rpm", "-qp", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}", str(path)],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            continue
        rpms.append({
            "nevra": nevra,
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
        })
    return rpms


def collect_buildroot_locks(report_dir: Path) -> dict[str, dict]:
    """Collect all buildroot-neVRA lock files emitted by rebuild stages."""
    locks: dict[str, dict] = {}
    for path in sorted(report_dir.rglob("buildroot-*.json")):
        if path.name == "buildroot-lock-preflight.json":
            locks["preflight"] = json.loads(path.read_text())
            continue
        name = re.sub(r"^buildroot-|\.json$", "", path.name)
        locks[name] = json.loads(path.read_text())
    return locks


def collect_source_reports(report_dir: Path) -> list[dict]:
    """Collect per-package source verification reports."""
    reports: list[dict] = []
    for path in sorted(report_dir.rglob("*.json")):
        if path.name.startswith("buildroot-") or path.name == "signature-report.json" or path.name == "manifest.json":
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if "package" in data and "sha512" in data:
            reports.append(data)
    return reports


def collect_signature_report(report_dir: Path) -> dict | None:
    path = report_dir / "signature-report.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--buildroot-lock", type=Path, default=Path("config/buildroot-lock.json"),
                        help="the committed buildroot image lock file")
    parser.add_argument("--package-dir", type=Path, required=True,
                        help="repository directory containing built RPMs")
    parser.add_argument("--report-dir", type=Path, required=True,
                        help="directory containing buildroot NEVRA locks and source reports")
    parser.add_argument("--output", type=Path, required=True,
                        help="path to write the manifest JSON")
    parser.add_argument("--oci-digest", default="",
                        help="the published OCI image digest")
    args = parser.parse_args()

    buildroot_lock = json.loads(args.buildroot_lock.read_text()) if args.buildroot_lock.exists() else {}
    source_reports = collect_source_reports(args.report_dir)
    signature_report = collect_signature_report(args.report_dir)
    buildroot_locks = collect_buildroot_locks(args.report_dir)
    rpms = collect_rpms(args.package_dir)

    manifest = {
        "schema": 1,
        "published_at": datetime.now(UTC).isoformat(),
        "oci": {
            "digest": args.oci_digest,
        },
        "buildroot": {
            "image": buildroot_lock.get("image", {}),
            "release": buildroot_lock.get("release"),
            "neura_snapshots": {
                name: {
                    "image_ref": snap.get("image_ref", ""),
                    "package_count": snap.get("package_count", 0),
                    "nevras": snap.get("nevras", []),
                }
                for name, snap in buildroot_locks.items()
            },
        },
        "sources": {
            report["package"]: {
                "sha512": report.get("sha512", ""),
                "signature_verified": report.get("signature_verified"),
                "sha256_manifest_checked": "sha256_url" in report,
                "resolved_url": report.get("resolved_url", ""),
            }
            for report in source_reports
        },
        "signature_provenance": signature_report,
        "packages": {
            "total": len(rpms),
            "by_nevra": {rpm["nevra"]: {"sha256": rpm["sha256"], "size": rpm["size"]} for rpm in rpms},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"manifest written: {args.output} ({len(rpms)} packages, "
          f"{len(source_reports)} sources, {len(buildroot_locks)} buildroot snapshots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
