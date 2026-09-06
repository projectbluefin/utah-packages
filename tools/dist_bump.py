#!/usr/bin/env python3
"""Print the .N suffix for a package's disttag, or nothing.

Our disttag follows AlmaLinux: Fedora's release and dist, then .bfin, then a
counter when we rebuild the same Fedora build more than once -- their dnf is
4.14.0-34.el9_8.alma.1 against Red Hat's 34.el9_8, and both .alma and .alma.N
appear in their repositories.

The counter is per package, so it lives beside the package's source entry:

    "dist_bump": {"count": 1, "baseline": "3"}

`baseline` is the spec's own `Release:` that the count was taken against, and
it is what stops the counter outliving its reason. The counter exists only for
the case where the Fedora release we derive from has *not* moved but our build
of it has to. The moment that release moves, the counter is spent: the new
leading segment already outranks everything published against the old one, and
carrying `.1` forward would claim a rebuild that never happened.

Ported from Hummingbird's `bump_release()`, which draws the same distinction
between "Fedora shipped 3.1" and "we already rebuilt Fedora's 3":

    current 3,   baseline 3    -> 3.1
    current 3.1, baseline 3.1  -> 3.1.1
    current 3.1, baseline 3    -> 3.2

We express the counter in the disttag rather than in `Release:`, so the
translation is that a moved baseline retires the counter instead of re-seating
it.

Like theirs, this refuses to guess at a `Release:` built from macros --
nodejs, kernel-headers and krb5 are the packages that shape is used for -- and
asks for the bump to be handled by hand rather than comparing two strings that
do not mean what they appear to.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = re.compile(r"^Release:\s*(\S+)", re.MULTILINE)


class BumpError(Exception):
    """The recorded bump cannot be applied to this spec."""


def spec_release(spec: str) -> str:
    """The `Release:` value, with a trailing dist macro removed."""
    match = RELEASE.search(spec)
    if match is None:
        raise BumpError("spec has no Release: line")
    release = match.group(1)
    for dist in ("%{?dist}", "%{dist}"):
        if release.endswith(dist):
            release = release[: -len(dist)]
            break
    if "%" in release:
        raise BumpError(
            f"Release: {match.group(1)} is built from macros; bump it by hand "
            "rather than against a baseline that cannot be compared"
        )
    return release


def suffix(entry: dict, release: str) -> str:
    """The disttag suffix for one package, given its current spec release."""
    bump = entry.get("dist_bump")
    if bump is None:
        return ""
    if not isinstance(bump, dict) or {"count", "baseline"} - set(bump):
        raise BumpError(
            'dist_bump must be {"count": N, "baseline": "<the Release: it applies to>"}'
        )
    if str(bump["baseline"]) != release:
        # Fedora moved. The counter answered "same release, built again",
        # which is no longer the question.
        return ""
    return f".{bump['count']}"


def main(name: str) -> str:
    config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
    entry = next((e for e in config["packages"] if e.get("name") == name), None)
    if entry is None or entry.get("dist_bump") is None:
        return ""
    specs = sorted((ROOT / "packages" / name).glob("*.spec"))
    if not specs:
        raise BumpError(f"{name} records a dist_bump but has no spec")
    return suffix(entry, spec_release(specs[0].read_text()))


if __name__ == "__main__":
    try:
        print(main(sys.argv[1]), end="")
    except BumpError as error:
        print(f"{sys.argv[1]}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
