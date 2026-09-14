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

Like theirs, this compares only the stable leading segment of a `Release:` --
the `5` in `5%{?gitdate:.%{gitdate}git%{gitversion}}%{?dist}`, the `1` in
`1%{?pre_tag}%{?dist}`. A release that is only macros has nothing literal to
compare against a baseline -- `%autorelease`, `%{baserelease}`, and the fully
dynamic releases of nodejs, kernel-headers and krb5 -- so the bump is skipped
rather than guessed at. That skip is graceful: the tool reports no suffix
instead of crashing on two strings that do not mean what they appear to.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import source_locks

ROOT = Path(__file__).resolve().parent.parent
RELEASE = re.compile(r"^Release:\s*(\S+)", re.MULTILINE)


class BumpError(Exception):
    """The recorded bump cannot be applied to this spec."""


def spec_release(spec: str) -> str:
    """The comparable leading release, or the empty string when the spec
    cannot be bumped.

    The release is the literal segment before the first unexpanded macro -- the
    `5` in `5%{?gitdate:.%{gitdate}git%{gitversion}}%{?dist}` and the `1` in
    `1%{?pre_tag}%{?dist}`. That literal is stable across rebuilds of the same
    Fedora release, so it is what a recorded baseline can be checked against.
    A release that is only macros -- `%autorelease`, `%{baserelease}` -- has no
    literal segment to compare, so this returns the empty string and the caller
    skips the bump instead of guessing at (or crashing on) two strings that do
    not mean what they appear to.
    """
    match = RELEASE.search(spec)
    if match is None:
        raise BumpError("spec has no Release: line")
    # The dist macro and every optional sub-macro sit after the first `%`, so
    # the literal release is everything before it. A (\S+) capture carries no
    # whitespace, so nothing further needs stripping.
    return match.group(1).split("%", 1)[0]


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
    entry = source_locks(ROOT).get(name)
    if entry is None or entry.get("dist_bump") is None:
        return ""
    specs = sorted((ROOT / "packages" / name).glob("*.spec"))
    if not specs:
        raise BumpError(f"{name} records a dist_bump but has no spec")
    release = spec_release(specs[0].read_text())
    if not release:
        # A purely-macro Release: (%autorelease, %{baserelease}) has no literal
        # segment to compare against the recorded baseline, so the bump is
        # skipped. build-stage.yml captures main()'s stdout, so a silent "" would
        # drop the rebuild with no trace and ship an RPM that does not supersede;
        # log it on stderr to keep the skip observable.
        print(
            f"{name}: dist_bump skipped, Release: has no comparable baseline",
            file=sys.stderr,
        )
        return ""
    return suffix(entry, release)


if __name__ == "__main__":
    try:
        print(main(sys.argv[1]), end="")
    except BumpError as error:
        print(f"{sys.argv[1]}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
