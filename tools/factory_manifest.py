#!/usr/bin/env python3
"""Write the package/source/buildroot manifest published beside the RPM repo."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def read_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def rpm_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.rpm"))


def reports(root: Path) -> list[object]:
    reports_dir = root / "reports"
    targets = [reports_dir] if reports_dir.is_dir() else [root]
    values = []
    seen = set()
    for directory in targets:
        for path in sorted(directory.glob("*.json")):
            if path.name == "manifest.json":
                continue
            if path in seen:
                continue
            seen.add(path)
            data = read_json(path)
            if isinstance(data, dict):
                data.setdefault("report", str(path.relative_to(root)))
                values.append(data)
    return values


def buildroot_provenance(
    snapshots: list[dict], run_digest: str
) -> tuple[list[dict], list[dict]]:
    """Split buildroot snapshots into the ones this run measured and the rest.

    ``buildroots`` is an attestation: it says which root the packages beside it
    were built in. The publish job seeds ``repository/`` from the previously
    published factory image, and that image was built with ``COPY repository
    /repository`` after this file's own output had landed there -- so the
    previous run's ``reports/buildroot-*.json`` comes back with the seed. A
    fresh preflight snapshot normally overwrites it, but preflight is skipped
    outright on a cleanup-only run and its artifact download is
    ``continue-on-error``, so the stale snapshot can reach here and be folded
    in as a root this run never measured.

    A snapshot belongs to this run only if the image it resolved carries the
    digest the run resolved. Anything else is named under
    ``buildroots_discarded`` rather than dropped in silence: "no root was
    measured" and "a root was measured and withheld" are different claims, and
    an operator reading the manifest after a bad package ships needs to tell
    them apart. With no run digest to compare against -- standalone use, or a
    run whose own resolution failed -- nothing can be judged, so nothing is
    discarded; the workflow closes that door by pruning the seeded reports.
    """
    if not run_digest:
        return list(snapshots), []
    measured: list[dict] = []
    discarded: list[dict] = []
    for snapshot in snapshots:
        image = snapshot.get("image")
        if isinstance(image, str) and image.rsplit("@", 1)[-1] == run_digest:
            measured.append(snapshot)
            continue
        discarded.append(
            {
                "name": snapshot.get("name"),
                "report": snapshot.get("report"),
                "image": image,
                "run_digest": run_digest,
                "reason": (
                    "snapshot records no resolved image"
                    if not isinstance(image, str) or not image
                    else "snapshot image is not the buildroot this run resolved"
                ),
            }
        )
    return measured, discarded


def source_verification(package_reports: list[dict]) -> dict:
    """Summarise how each accepted source was verified.

    The manifest is meant to be read, not grepped: a signature that upstream
    supplies and a checksum that stands in for one are not the same claim, so
    the packages carrying only a checksum are named rather than counted.
    """
    counts: dict[str, int] = {}
    checksum_only = set()
    for report in package_reports:
        if report.get("result") != "accepted":
            continue
        kind = report.get("verification", "unknown")
        counts[kind] = counts.get(kind, 0) + 1
        if report.get("checksum_only", kind != "signature"):
            name = report.get("package")
            if name:
                checksum_only.add(name)
    return {
        "counts": dict(sorted(counts.items())),
        "checksum_only": sorted(checksum_only),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument(
        "--build-list", default="[]", help="JSON array emitted by the prepare job"
    )
    parser.add_argument(
        "--buildroot-lock", type=Path, default=Path("config/buildroot-lock.json")
    )
    parser.add_argument(
        "--buildroot-digest",
        default="",
        help="digest of the buildroot this run resolved; a snapshot recording "
        "any other image is discarded rather than attested",
    )
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

    all_reports = reports(args.repository)
    buildroot_reports = []
    package_reports = []
    for item in all_reports:
        if (
            isinstance(item, dict)
            and item.get("schema") == 1
            and "packages" in item
            and "name" in item
        ):
            buildroot_reports.append(item)
        elif isinstance(item, dict) and "package" in item:
            package_reports.append(item)

    buildroot_reports, discarded_buildroots = buildroot_provenance(
        buildroot_reports, args.buildroot_digest
    )
    for item in discarded_buildroots:
        print(
            f"warning: not attesting buildroot snapshot {item['report']}: "
            f"{item['reason']} ({item['image']} is not {args.buildroot_digest})",
            file=sys.stderr,
        )

    payload = {
        "schema": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "requested_packages": requested,
        "packages": rpm_files(args.repository),
        "sources": package_reports,
        "source_verification": source_verification(package_reports),
        "buildroot_lock": read_json(args.buildroot_lock),
        "buildroots": buildroot_reports,
        "buildroots_discarded": discarded_buildroots,
        "oci": {"ref": args.oci_ref, "digest": args.oci_digest},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote factory manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
