#!/usr/bin/env python3
"""Resolve and snapshot factory buildroots.

``config/buildroot-lock.json`` is the declarative record of which image a
buildroot is: a digest pin, not a tag. Its ``fedora-44`` image is the same
reference ``config/buildroot-image`` pins for prepare to pull;
``tools/buildroot_pin.py set`` moves both and ``tools/validate.py`` fails if
they differ. ``snapshot`` writes what the root actually contained -- every
package NEVRA, the digest the run resolved, and the digest the lock expected --
so a rebuild says which bytes it used rather than which bytes it meant to use.

The package list comes from ``rpm -qa`` here, or from ``--packages-from`` when
that inventory was printed elsewhere; CI uses the second form, because the
build root is a Fedora container with no interpreter this factory may assume.

The lock is never used as the resolved image: with no ``--image``,
``--digest`` or ``BUILDROOT_DIGEST`` the snapshot records ``image: null`` and
warns, so an empty digest cannot quietly re-assert the lock's provenance.
Those three are the only inputs. ``BUILDROOT_IMAGE`` is not read: prepare
sets it from the pin, and ``tools/validate.py`` forces the lock to equal the
pin, so reading it would re-assert that pin through a second door.

A mismatch between the resolved and locked image warns, matching prepare: a
legacy ``quay.io/fedora/fedora:44`` pin pulls a moving tag and only warns when
it moved, because failing on it is the outage
`docs/skills/repeated-mistakes.md` section 7 records. ``--strict`` turns that
warning, and any divergence from a non-empty locked package list, into an
error -- for an operator asking whether a root is exactly what was locked, not
for the scheduled rebuild. It also refuses an inventory that could not be
fully parsed: a capture that under-reports the root cannot answer that
question either way.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterable
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


QUERY_FORMAT = "%{NAME}\t%|EPOCH?{%{EPOCH}:}|%{VERSION}-%{RELEASE}\t%{ARCH}\n"


def parse_packages(
    lines: Iterable[str], *, discarded: list[str] | None = None
) -> list[dict[str, str]]:
    """Turn ``rpm -qa --qf QUERY_FORMAT`` output into sorted NEVRA records.

    Taken as text rather than by calling rpm, because the inventory is printed
    inside the build root and read out here: the root is a Fedora container
    with no interpreter this factory is entitled to assume, and installing one
    to take its own inventory would change the set being recorded.

    A line that is not three tab-separated fields is dropped, but never
    quietly: this is an attestation input, and a truncated or corrupted
    ``rpm -qa`` capture makes the snapshot under-report what the root
    contained. Dropped lines are warned about on stderr and appended to
    ``discarded`` when a caller passes a list, so ``--strict`` can refuse a
    snapshot that is known to be incomplete.
    """
    packages = []
    malformed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            malformed.append(line)
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
    if malformed:
        if discarded is not None:
            discarded.extend(malformed)
        shown = ", ".join(repr(line) for line in malformed[:5])
        print(
            f"warning: dropped {len(malformed)} unparsable line(s) from the buildroot "
            f"inventory; this snapshot under-reports the root's contents: {shown}",
            file=sys.stderr,
        )
    return sorted(packages, key=lambda item: (item["name"], item["evra"], item["arch"]))


def rpm_packages(*, discarded: list[str] | None = None) -> list[dict[str, str]]:
    output = subprocess.check_output(["rpm", "-qa", "--qf", QUERY_FORMAT], text=True)
    return parse_packages(output.splitlines(), discarded=discarded)


def compare(expected: list[dict], actual: list[dict]) -> list[str]:
    """Report how a snapshot's packages diverge from the locked list.

    A lock entry without a usable ``nevra`` is a malformed lock, not a missing
    package. ``load_lock`` only checks that ``packages`` is a list -- the
    per-entry requirement is enforced by ``tools/validate.py`` -- so running
    this module standalone against a hand-edited lock can reach here with
    ``None`` in the expected set. Report that as its own error rather than
    letting it reach ``", ".join(...)`` and die with a TypeError: the gate
    still failed either way, but a traceback tells an operator nothing about
    which entry to fix.
    """
    errors = []
    wanted = set()
    malformed = 0
    for item in expected:
        nevra = item.get("nevra") if isinstance(item, dict) else None
        if isinstance(nevra, str) and nevra:
            wanted.add(nevra)
        else:
            malformed += 1
    if malformed:
        errors.append(
            f"malformed lock: {malformed} locked package entr"
            f"{'y has' if malformed == 1 else 'ies have'} no nevra field"
        )
    got = {item["nevra"] for item in actual}
    missing = sorted(wanted - got)
    extra = sorted(got - wanted)
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
    discarded: list[str] = []
    if args.packages_from:
        if not args.packages_from.is_file():
            print(f"missing buildroot inventory: {args.packages_from}", file=sys.stderr)
            return 1
        packages = parse_packages(
            args.packages_from.read_text().splitlines(), discarded=discarded
        )
    else:
        packages = rpm_packages(discarded=discarded)
    locked_image = spec["image"]
    base_ref = locked_image.split("@")[0]
    digest = getattr(args, "digest", None) or os.environ.get("BUILDROOT_DIGEST")
    # Only what the run resolved counts as the image. The lock is never a
    # fallback: it says which bytes the rebuild meant to use, and writing it
    # here would attest a root the packages may not have been built in. With
    # nothing resolved the snapshot records null and says so.
    # No environment fallback either: prepare sets BUILDROOT_IMAGE from the
    # pin and validate.py forces the lock to equal the pin, so reading it here
    # would re-assert the lock's pin through a second door -- the same
    # attestation this command exists to avoid making.
    actual_image = getattr(args, "image", None) or (
        f"{base_ref}@{digest}" if digest else None
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
    if actual_image is None:
        msg = (
            f"buildroot image unknown: no --image, --digest or BUILDROOT_DIGEST was given, "
            f"so the snapshot records image null rather than the lock's {locked_image}"
        )
        if args.strict:
            errors.append(msg)
        else:
            print(f"warning: {msg}", file=sys.stderr)
    elif actual_image != locked_image:
        msg = f"buildroot image mismatch: lock specifies {locked_image}, actual running image is {actual_image}"
        if args.strict:
            errors.append(msg)
        else:
            print(f"warning: {msg}", file=sys.stderr)
    if discarded and args.strict:
        # --strict answers "is this root exactly what was locked?". An
        # inventory we could not fully parse cannot answer that either way.
        errors.append(
            f"buildroot inventory incomplete: {len(discarded)} unparsable line(s) "
            f"were dropped, so this snapshot cannot be compared against the lock"
        )
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
    snapshot.add_argument(
        "--packages-from",
        type=Path,
        # argparse %-formats help text, so the rpm query's own % signs must
        # be doubled or the parser refuses the string (eagerly on 3.14+).
        help="read rpm -qa --qf %s output instead of running rpm"
        % repr(QUERY_FORMAT).replace("%", "%%"),
    )
    snapshot.add_argument("--image", help="actual image/digest of the running buildroot")
    snapshot.add_argument("--digest", help="actual digest of the running buildroot")
    snapshot.add_argument("--strict", action="store_true")
    snapshot.set_defaults(func=cmd_snapshot)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
