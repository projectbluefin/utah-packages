#!/usr/bin/env python3
"""Fail if a build-toolchain container image is referenced by a mutable tag.

Issue #43: AGENTS.md requires builds to run inside a *digest-pinned* container
and forbids swapping the digest for a mutable tag. The real builds once did the
opposite -- quay.io/fedora/fedora:44 and ...:latest -- so commit 3a6e77a pinned
every quay.io build image to the digest its tag resolves to. This guard stops
anyone swapping a digest back for a tag, which is the exact regression #43
reports: a silent, non-reproducible build.

It checks the registries workflows run containers from by tag: quay.io, which
AGENTS.md names, and registry.access.redhat.com, which serves the Red Hat
Hardened Images (/hi/). Bare `fedora:rawhide` refs and the ghcr `:latest`
publication tag are a separate concern (same commit) and are deliberately out
of scope here -- pinning them is a build-root decision, not a tag-pinning one.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

# A registry image reference: quay.io/<path> or registry.access.redhat.com/<path>
# optionally followed by @sha256:<d> or :<tag>. Stops at whitespace, quotes, or
# a comment marker so it captures the image token, not the shell that follows.
IMAGE_REF = re.compile(r"(?:quay\.io|registry\.access\.redhat\.com)/[^\s\"'`#]+")

# The one place a moving tag is the point. refresh-buildroot.yml copies the
# current fedora:44 into the factory's own never-pruned mirror so builds can pin
# a digest that cannot rot (repeated-mistakes section 7); it builds nothing
# itself. Exempt by exact (workflow, ref), so any other use still fails.
EXEMPT = {("refresh-buildroot.yml", "quay.io/fedora/fedora:44")}


def unpinned_refs(workflows: Iterable[Path]) -> list[tuple[str, int, str]]:
    """Return (workflow, line, ref) for registry images not pinned by digest."""
    offenders: list[tuple[str, int, str]] = []
    for workflow in workflows:
        for number, line in enumerate(workflow.read_text().splitlines(), start=1):
            # Mentioning an image in a comment is not using it as a container;
            # packit-srpm-pilot.yml documents the pre-pin tag this way.
            if line.strip().startswith("#"):
                continue
            for ref in IMAGE_REF.findall(line):
                if "@sha256:" not in ref and (workflow.name, ref) not in EXEMPT:
                    offenders.append((workflow.name, number, ref))
    return offenders


def main(workflows_dir: Path | None = None) -> int:
    if workflows_dir is None:
        workflows_dir = Path(__file__).resolve().parent.parent / ".github" / "workflows"
    workflows = sorted(workflows_dir.glob("*.yml"))
    offenders = unpinned_refs(workflows)
    if offenders:
        print(
            "A quay.io or registry.access.redhat.com image is referenced by a mutable tag. "
            "AGENTS.md requires a digest pin; swap the tag for @sha256:...:",
            file=sys.stderr,
        )
        for name, number, ref in offenders:
            print(f"  {name}:{number}: {ref}", file=sys.stderr)
        print(
            "\nPin to the digest the tag resolves to (e.g. "
            "crane digest quay.io/<image>) and re-pin when the image changes.",
            file=sys.stderr,
        )
        return 1

    print(
        f"checked {len(workflows)} workflows: every quay.io and "
        "registry.access.redhat.com image is digest-pinned"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
