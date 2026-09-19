#!/usr/bin/env python3
"""Resolve and snapshot factory buildroots.

The workflow reads image references from ``config/buildroot-lock.json`` instead
of embedding mutable tags. Package NEVRAs are captured from the live buildroot
with ``snapshot``; if a lock later carries a non-empty package list, ``--strict``
turns the same command into an exact input verifier.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_CONFIG = Path("config/buildroot-lock.json")


def load_lock(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema") != 1 or not isinstance(data.get("buildroots"), dict):
        raise ValueError(f"invalid buildroot lock: {path}")
    for name, br in data["buildroots"].items():
        image = br.get("image") if isinstance(br, dict) else None
        if not isinstance(image, str) or "@sha256:" not in image:
            raise ValueError(f"buildroot {name} image must be digest-pinned")
        if not isinstance(br.get("packages", []), list):
            raise ValueError(f"buildroot {name} packages must be a list")
    return data


def buildroot(data: dict, name: str) -> dict:
    value = data["buildroots"].get(name)
    if not isinstance(value, dict):
        raise ValueError(f"unknown buildroot: {name}")
    image = value.get("image")
    if not isinstance(image, str) or "@sha256:" not in image:
        raise ValueError(f"buildroot {name} image must be digest-pinned")
    packages = value.get("packages", [])
    if not isinstance(packages, list):
        raise ValueError(f"buildroot {name} packages must be a list")
    return value


def rpm_packages() -> list[dict[str, str]]:
    fmt = "%{NAME}\t%|EPOCH?{%{EPOCH}:}|%{VERSION}-%{RELEASE}\t%{ARCH}\n"
    output = subprocess.check_output(["rpm", "-qa", "--qf", fmt], text=True)
    packages = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        name, evra, arch = parts
        packages.append(
            {
                "name": name,
                "evra": evra,
                "arch": arch,
                "nevra": f"{name}-{evra}.{arch}",
            }
        )
    return sorted(packages, key=lambda item: (item["name"], item["evra"], item["arch"]))


def compare(expected: list[dict], actual: list[dict]) -> list[str]:
    wanted = {item.get("nevra") for item in expected if isinstance(item, dict)}
    got = {item["nevra"] for item in actual}
    missing = sorted(wanted - got)
    extra = sorted(got - wanted)
    errors = []
    if missing:
        errors.append("missing locked buildroot packages: " + ", ".join(missing[:20]))
    if extra:
        errors.append("unexpected buildroot packages: " + ", ".join(extra[:20]))
    return errors


def cmd_image(args: argparse.Namespace) -> int:
    lock = load_lock(args.config)
    print(buildroot(lock, args.name)["image"])
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    lock = load_lock(args.config)
    spec = buildroot(lock, args.name)
    packages = rpm_packages()
    locked_image = spec["image"]
    base_ref = locked_image.split("@")[0]
    digest = getattr(args, "digest", None) or os.environ.get("BUILDROOT_DIGEST")
    actual_image = (
        getattr(args, "image", None)
        or (f"{base_ref}@{digest}" if digest else None)
        or os.environ.get("ACTUAL_BUILDROOT_IMAGE")
        or os.environ.get("BUILDROOT_IMAGE")
        or locked_image
    )
    payload = {
        "schema": 1,
        "name": args.name,
        "image": actual_image,
        "locked_image": locked_image,
        "captured_at": datetime.now(UTC).isoformat(),
        "packages": packages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    expected = spec.get("packages", [])
    errors = []
    if actual_image != locked_image:
        msg = f"buildroot image mismatch: lock specifies {locked_image}, actual running image is {actual_image}"
        if args.strict:
            errors.append(msg)
        else:
            print(f"warning: {msg}", file=sys.stderr)
    if args.strict and expected:
        errors.extend(compare(expected, packages))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"captured {len(packages)} buildroot packages for {args.name}: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)

    image = sub.add_parser("image")
    image.add_argument("name")
    image.set_defaults(func=cmd_image)

    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("name")
    snapshot.add_argument("--output", type=Path, required=True)
    snapshot.add_argument("--image", help="actual image/digest of the running buildroot")
    snapshot.add_argument("--digest", help="actual digest of the running buildroot")
    snapshot.add_argument("--strict", action="store_true")
    snapshot.set_defaults(func=cmd_snapshot)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
