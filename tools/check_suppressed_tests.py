#!/usr/bin/env python3
"""Fail when a recipe introduces a known ``%check`` failure suppression.

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

Direct test commands followed by ``|| :`` or ``|| true`` are another narrow
tripwire. The check recognizes test macros, make check/test, ctest/pytest,
and executables or Python scripts under test directories. Only literal
fallbacks at the end of a command in ``%check`` are matched; probes such as
``test -f``, ``grep`` and diagnostic log reads are not test commands.
Existing imported fallbacks have the same exact-count ratchet as macro
definitions. Removing an exception requires shrinking its recorded count;
an inherited recipe is never exempt from adding a different suppression.

This is not a shell or RPM parser. Backslash continuations are joined, but
compound shell commands, RPM conditionals, shell wrappers and embedded
scripts are not interpreted. In particular, uchardet's fallback is
split across ``%ifarch`` directives and is outside this tripwire. Deleting
an exit guard or defining a macro in an included source also remains outside
it. A reviewer still has to read the ``%check`` diff: passing this gate is not
proof that every failing test propagates.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ``%global tests_nonfatal 1`` / ``%define tests_nonfatal 1``. Only a
# definition matters: ``%{!?tests_nonfatal:exit $TESTS_ERROR}`` is the guard
# itself and appears in every recipe that carries this %check shape.
DEFINITION = re.compile(r"^\s*%(?:global|define)\s+tests_nonfatal\b")

# Deliberately limited to direct, recognizable test invocations. Do not flag
# every fallback in %check: grep probes and failure-log collection are valid.
SECTION = re.compile(
    r"^%(?:prep|generate_buildrequires|build|install|check|clean|files|"
    r"changelog|package|description|pre|preun|pretrans|post|postun|posttrans|"
    r"trigger\w*|filetrigger\w*|transfiletrigger\w*|verifyscript)\b"
)
SUCCESS_FALLBACK = re.compile(r"\s*\|\|\s*(?::|true)\s*;?\s*(?:#.*)?$")
TEST_COMMAND = re.compile(
    r"^(?:[A-Za-z_]\w*=\S+\s+)*(?:"
    r"%(?:\{(?:meson_test|ctest|pytest|make_check)\}|"
    r"(?:meson_test|ctest|pytest|make_check)\b)|"
    r"(?:make|%make_build|%\{make_build\})(?:\s+\S+)*\s+(?:check|test)(?=\s|$)|"
    r"(?:ctest|pytest|pytest-[\d.]+)(?=\s|$)|"
    r"(?:\./)?(?:[^\s/]+/)*(?:test|tests|jit-test)/\S+|"
    r"(?:python[23]?(?:\.\d+)?|%\{_{0,2}python3?\})\s+"
    r"(?:\./)?(?:test|tests|jit-test)/\S+"
    r")"
)

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

# Literal fallbacks already carried by main before the codec-tail import.
# Counts include inactive RPM branches; these are recorded debt, not approval
# of advisory tests and not permission for an import to add another fallback.
INHERITED_FALLBACKS = {
    "appstream": (1, "inherited Fedora meson_test fallback"),
    "glycin": (1, "inherited Fedora fallback for published-tarball tests"),
    "mozjs140": (2, "inherited Fedora require_tests-disabled branches"),
    "python-pillow": (2, "inherited Fedora pytest fallbacks in both arch branches"),
    "vid.stab": (1, "inherited Fedora tests/tests fallback"),
    "xhost": (1, "inherited Fedora make check fallback"),
}


def definitions(spec: Path) -> list[tuple[int, str]]:
    """Return (line number, line) for every ``tests_nonfatal`` definition."""
    return [
        (number, line.strip())
        for number, line in enumerate(spec.read_text().splitlines(), start=1)
        if DEFINITION.match(line)
    ]


def masked_tests(spec: Path) -> list[tuple[int, str]]:
    """Find direct test commands with a literal unconditional-success tail."""
    found = []
    in_check = False
    pending = ""
    start = 0
    for number, line in enumerate(spec.read_text().splitlines(), start=1):
        stripped = line.strip()
        if SECTION.match(stripped):
            in_check = bool(re.match(r"^%check\b", stripped))
            pending = ""
            continue
        if not in_check or stripped.startswith("#"):
            continue
        if not pending:
            start = number
        pending += stripped
        if pending.endswith("\\"):
            pending = pending[:-1] + " "
            continue
        fallback = SUCCESS_FALLBACK.search(pending)
        if fallback:
            command = pending[:fallback.start()].rstrip()
            if (
                TEST_COMMAND.match(command)
                and not any(part in command for part in ("#", ";", "|", "&&"))
                and not re.search(r"\s(?:--help|--version)\s*$", command)
            ):
                found.append((start, pending))
        pending = ""
    return found


def offenders(root: Path) -> list[tuple[str, int, str]]:
    """Return (package, line number, line) for new known suppressions.

    Each inherited suppression kind is counted separately by :func:`drifted`;
    an exception for one kind never exempts the other kind.
    """
    found = []
    for spec in sorted((root / "packages").glob("*/*.spec")):
        package = spec.parent.name
        for inherited, scan in (
            (INHERITED, definitions),
            (INHERITED_FALLBACKS, masked_tests),
        ):
            if package not in inherited:
                found.extend(
                    (package, number, line) for number, line in scan(spec)
                )
    return found


def drifted(root: Path) -> list[str]:
    """Return present recipes whose inherited suppression counts have drifted.

    Both increases and decreases fail. Absent recipes are ignored so this
    guard also works on synthetic or partial trees.
    """
    reports = []
    for inherited, scan, description, noun in (
        (INHERITED, definitions, "defines tests_nonfatal", "definition"),
        (INHERITED_FALLBACKS, masked_tests, "masks test failures", "fallback"),
    ):
        for package, (expected, _reason) in sorted(inherited.items()):
            specs = sorted((root / "packages" / package).glob("*.spec"))
            if not specs:
                continue
            found = [
                (spec, number)
                for spec in specs
                for number, _line in scan(spec)
            ]
            if len(found) == expected:
                continue
            if not found:
                reports.append(
                    f"{package}: no longer {description}; drop the entry"
                )
            elif len(found) < expected:
                reports.append(
                    f"{package}: {description} {len(found)} time(s), "
                    f"allowlist records {expected}; lower the count to match the "
                    f"import"
                )
            else:
                sites = ", ".join(
                    f"{spec.relative_to(root)}:{number}" for spec, number in found
                )
                reports.append(
                    f"{package}: {description} {len(found)} time(s), "
                    f"allowlist records {expected}; a {noun} was added after "
                    f"the import ({sites})"
                )
    return reports


def main(root: Path | None = None) -> int:
    root = root or Path(__file__).resolve().parent.parent
    problems = offenders(root)
    rotted = drifted(root)

    if problems:
        print(
            "A recipe may not introduce tests_nonfatal or mask a test command "
            "with || : / || true. It turns a failing %check into a green build:",
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
            "\ntools/check_suppressed_tests.py inherited counts no longer match "
            "the tree. An entry exempts a recorded number of inherited "
            "suppressions, not the whole recipe:",
            file=sys.stderr,
        )
        for entry in rotted:
            print(f"  {entry}", file=sys.stderr)

    if problems or rotted:
        return 1

    count = len(list((root / "packages").glob("*/*.spec")))
    inherited = ", ".join(
        f"{package} ({expected} {kind})"
        for kind, entries in (
            ("definitions", INHERITED), ("fallbacks", INHERITED_FALLBACKS)
        )
        for package, (expected, _reason) in sorted(entries.items())
    )
    print(
        f"checked {count} recipes: no new known test suppressions "
        f"(inherited: {inherited})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
