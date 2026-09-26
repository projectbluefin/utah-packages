#!/usr/bin/env python3
"""Fail when a recipe silences its own ``%check`` with ``tests_nonfatal``.

Fedora's audio specs share a ``%check`` shaped like this::

    %meson_test || TESTS_ERROR=$?
    if [ "${TESTS_ERROR}" != "" ]; then
    echo "test failed"
    %{!?tests_nonfatal:exit $TESTS_ERROR}
    fi

so defining ``tests_nonfatal`` anywhere above it turns a failing suite into a
successful build in one line, and the build log still prints ``test failed``.
Nothing else in the factory notices.

That line was the obvious way to close issue #132: ``pipewire``'s
``pw-test-endpoint`` hangs and is killed by its own ``alarm(5)``, it is the
only failure in the whole recipe set, and the recipe cannot simply be dropped
because ``pipewire-libs-extra`` -- which Utah does install -- carries
``Requires: pipewire >= %{version}``. One ``%global`` would have published a
silently broken audio stack.

``AGENTS.md`` and the ``build-failure-triage`` skill both already say never to
skip a test to get a build green. This makes that mechanical, because a prose
rule did not stop the question being asked.

``pulseaudio`` is the one recipe that already defines it, inherited verbatim
from Fedora dist-git rather than added here. It is recorded below so the gate
passes on the tree as imported while still refusing anything new; the entry is
a description of what we inherited, not permission to add more.

An allowlist entry therefore covers an exact *number* of definitions, not the
recipe. Exempting the whole recipe would let the next Fedora import bump add an
unconditional ``%global tests_nonfatal 1`` to ``pulseaudio`` and sail past the
gate -- the prose above would still say "not permission to add more" while the
code said otherwise. Pinning the count makes both directions fail: a definition
appearing beyond the recorded number, and the recorded number outliving the
import that earned it.

What this gate does **not** catch
---------------------------------

It matches one evasion: a ``%global``/``%define tests_nonfatal`` line in a
``packages/<name>/<name>.spec``. That is the one that was about to be written
for #132, and it is the one a rushed author reaches for -- it is not the only
way to land a green build on a failing suite. A recipe can still:

* delete the ``%{!?tests_nonfatal:exit $TESTS_ERROR}`` guard, leaving a
  ``%check`` that prints ``test failed`` and exits 0 -- no macro required;
* append ``|| :`` (or ``|| true``) to ``%meson_test`` / ``%ctest`` / the test
  command, which never reaches ``TESTS_ERROR`` at all;
* define the macro somewhere the ``packages/*/*.spec`` glob does not read.
  Not hypothetical: ``packages/grub2/grub2.spec:1136`` already does
  ``%include %{SOURCE11}``, so a definition can live in a source file.

Closing those mechanically means parsing ``%check`` bodies rather than grepping
for one line, which is a different and much larger tool. Until that exists,
treat this as a tripwire on the most likely route, not as proof that no recipe
silences its tests -- the standing rule is the prose one in ``AGENTS.md`` and
``.agents/skills/build-failure-triage/SKILL.md``: never skip or defang a test
to make a build green. A reviewer still has to read the ``%check`` diff.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ``%global tests_nonfatal 1`` / ``%define tests_nonfatal 1``. Only a
# definition matters: ``%{!?tests_nonfatal:exit $TESTS_ERROR}`` is the guard
# itself and appears in every recipe that carries this %check shape.
DEFINITION = re.compile(r"^\s*%(?:global|define)\s+tests_nonfatal\b")

# package -> (how many definitions were inherited, why they are there).
# Inherited from Fedora, never ours. The count is the exemption: anything
# beyond it is a new suppression and fails the gate like any other recipe's.
INHERITED = {
    # packages/pulseaudio/pulseaudio.spec %check, Fedora's own FIXMEs: one
    # arch-gated (i686 cpu-remap-test, s390x core-util-test) and one
    # release-gated (`%if 0%{?fedora} > 27`) which is therefore always on for
    # the Fedora 44 build root. PulseAudio's suite is effectively advisory
    # here. Raise it with a human before relying on it as a gate.
    "pulseaudio": (2, "inherited from Fedora dist-git, arch and release gated"),
}


def definitions(spec: Path) -> list[tuple[int, str]]:
    """Return (line number, line) for every ``tests_nonfatal`` definition."""
    return [
        (number, line.strip())
        for number, line in enumerate(spec.read_text().splitlines(), start=1)
        if DEFINITION.match(line)
    ]


def offenders(root: Path) -> list[tuple[str, int, str]]:
    """Return (package, line number, line) for every new ``tests_nonfatal``.

    Allowlisted recipes are counted by :func:`drifted` instead, which is what
    makes the exemption a number rather than a blanket pass for the package.
    """
    found = []
    for spec in sorted((root / "packages").glob("*/*.spec")):
        package = spec.parent.name
        if package in INHERITED:
            continue
        found.extend(
            (package, number, line) for number, line in definitions(spec)
        )
    return found


def drifted(root: Path) -> list[str]:
    """Return allowlisted recipes whose definition count no longer matches.

    Both directions are failures. Too few -- down to none -- and the entry is
    claiming a recipe is compromised long after the import that made it so is
    gone; an exception nobody can see is worse than no exception. Too many and
    a definition has been added since the import, which is exactly the thing
    the gate exists to refuse, so it must not hide behind the entry that
    documents Fedora's two.

    A package that is absent entirely is **not** drift. ``tools/validate.py``
    runs against synthetic trees in its own tests and against whatever root it
    is handed; complaining that a recipe the caller never had is missing would
    make the gate depend on the tree it is pointed at. A dropped recipe is
    caught by ``tests/test_check_suppressed_tests.py`` instead, which asserts
    the entries still exist in this repository.
    """
    reports = []
    for package, (expected, _reason) in sorted(INHERITED.items()):
        specs = sorted((root / "packages" / package).glob("*.spec"))
        if not specs:
            continue
        found = [
            (spec, number)
            for spec in specs
            for number, _line in definitions(spec)
        ]
        if len(found) == expected:
            continue
        if not found:
            reports.append(
                f"{package}: no longer defines tests_nonfatal; drop the entry"
            )
        elif len(found) < expected:
            reports.append(
                f"{package}: defines tests_nonfatal {len(found)} time(s), "
                f"allowlist records {expected}; lower the count to match the "
                f"import"
            )
        else:
            sites = ", ".join(
                f"{spec.relative_to(root)}:{number}" for spec, number in found
            )
            reports.append(
                f"{package}: defines tests_nonfatal {len(found)} time(s), "
                f"allowlist records {expected}; a definition was added after "
                f"the import ({sites})"
            )
    return reports


def main(root: Path | None = None) -> int:
    root = root or Path(__file__).resolve().parent.parent
    problems = offenders(root)
    rotted = drifted(root)

    if problems:
        print(
            "A recipe may not define tests_nonfatal. It turns a failing %check "
            "into a green build and ships the failure:",
            file=sys.stderr,
        )
        for package, number, line in problems:
            print(f"  packages/{package}: line {number}: {line}", file=sys.stderr)
        print(
            "\nFix the test or the build root instead. See "
            ".agents/skills/build-failure-triage/SKILL.md.",
            file=sys.stderr,
        )
    if rotted:
        print(
            "\ntools/check_suppressed_tests.py INHERITED no longer matches the "
            "tree. An entry exempts a recorded number of inherited "
            "definitions, not the whole recipe:",
            file=sys.stderr,
        )
        for entry in rotted:
            print(f"  {entry}", file=sys.stderr)

    if problems or rotted:
        return 1

    count = len(list((root / "packages").glob("*/*.spec")))
    inherited = ", ".join(
        f"{package} ({expected})"
        for package, (expected, _reason) in sorted(INHERITED.items())
    )
    print(
        f"checked {count} recipes: no new tests_nonfatal "
        f"(inherited: {inherited})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
