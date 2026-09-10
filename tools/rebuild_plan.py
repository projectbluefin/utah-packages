#!/usr/bin/env python3
"""Decide which recipes a rebuild has to build, and in which wave.

This was an inline heredoc in .github/workflows/rebuild-rpms.yml, which meant
the one decision that can silently ship an incomplete repository had no tests.
It lives here so it does.

Two rules govern the skip, both taken from how Packit decides whether its own
work is already done:

**A skip needs two witnesses that agree.** Packit's
`should_archives_be_uploaded_to_lookaside` (packit/api.py) uploads unless the
archive is in the remote lookaside cache *and* recorded in the local `sources`
file -- `if not in_cache or not in_sources_file: return True`. One witness is
not enough, and disagreement means do the work. This factory learned the same
thing the hard way: `prepare` skipped what the published repository carried,
while the build root only saw the repositories it was actually given, and
pipewire-libs-extra failed on `pkgconfig(libfreeaptx)` with libfreeaptx-devel
sitting published and skipped. So the published listing only counts as a
witness when the build root will really have that repository enabled, which is
what `factory_repo` says here.

**Compare the whole NEVR, not the name and version.** Packit checks presence by
filename *and* content hash (`is_archive_uploaded`, packit/utils/lookaside.py,
"the same approach fedpkg itself uses") and decides whether an update is needed
by comparing NVRs in a Koji tag, not versions. Comparing only name and version
here missed a recipe whose `Release:` moved while its `Version:` stood still --
a spec fix or an added patch -- which the git diff catches on a push but not on
the nightly schedule, where there is no diff range to read at all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tools.dist_bump import BumpError, spec_release, suffix

# Matches the disttag the build derives in build-stage.yml: the Hummingbird
# release tag of the buildroot, then .bfin, then an optional dist_bump counter.
# The tag is read from the buildroot rather than hardcoded, so this accepts any
# humN and pins only the shape.
PUBLISHED_RELEASE = re.compile(r"^(?P<base>.+)\.hum\d+\.bfin(?P<bump>(?:\.\d+)?)$")

# GitHub caps a matrix at 256 jobs, and it does not fail when a matrix would
# exceed it -- it expands to NOTHING. A stage holding more than 256 packages
# therefore produces zero build jobs, silently, and every later stage builds
# against an empty buildroot. Hand each stage over in chunks instead.
CHUNK = 250

# The job chain in rebuild-rpms.yml is eleven deep and GitHub needs it static.
STAGES = 11


def published_from_primary(primary: bytes) -> dict[str, tuple[str, str]]:
    """Map source package name -> (version, release) from repodata primary.xml.

    Keyed by the *source* name out of `rpm:sourcerpm`, not by the binary
    `<name>`. A source package need not produce a binary that shares its name:
    `wayland` ships libwayland-server and wayland-devel and nothing called
    wayland, so a lookup by binary name can never match it -- the trap the
    build-failure-triage skill warns about under "Binary versus source names".
    That direction is safe (it rebuilds what it could have skipped) but it means
    the comparison was never really about the thing being built.
    """
    published: dict[str, tuple[str, str]] = {}
    for match in re.finditer(
        rb"<rpm:sourcerpm>([^<]+)\.src\.rpm</rpm:sourcerpm>", primary
    ):
        nevr = match.group(1).decode()
        name, _, remainder = nevr.rpartition("-")
        name, _, version = name.rpartition("-")
        if not name:
            continue
        published[name] = (version, remainder)
    return published


def normalize_version(version: str) -> str:
    """Fedora's spec Version rewrites the tarball's '.' to '~'.

    gnome-shell 51.beta becomes 51~beta, so both sides are normalized before
    they are compared.
    """
    return version.replace("~", ".")


def expected_release(root: Path, entry: dict) -> str | None:
    """The `Release:` this recipe would build as, ignoring the disttag.

    None when it cannot be known: a Release built from macros (nodejs,
    kernel-headers, krb5), or a recipe with no spec. The caller must treat that
    as "cannot prove it is published" and rebuild.
    """
    specs = sorted((root / "packages" / entry["name"]).glob("*.spec"))
    if not specs:
        return None
    try:
        release = spec_release(specs[0].read_text())
        return release + suffix(entry, release)
    except (BumpError, OSError):
        return None


def is_published(root: Path, entry: dict, published: dict[str, tuple[str, str]]) -> bool:
    """Whether the published repository already carries exactly this recipe."""
    name = entry["name"]
    if name not in published:
        return False
    published_version, published_release = published[name]
    if normalize_version(published_version) != normalize_version(entry.get("version", "")):
        return False

    expected = expected_release(root, entry)
    if expected is None:
        # `Release:` is %autorelease (about half the inventory) or built from
        # other macros, so rpmautospec decides it at build time and it cannot be
        # predicted here. Fall back to matching the version alone, which is what
        # this comparison did for every package before: no worse than it was,
        # and strictly better wherever the release *can* be read. The residual
        # gap is narrow -- a recipe edit reaches `changed` on any push or pull
        # request, so only the nightly schedule, which has no diff range, could
        # skip an %autorelease recipe whose version did not move.
        return True
    match = PUBLISHED_RELEASE.match(published_release)
    if match is None:
        # Something not built by this factory, or a disttag shape that changed.
        # Either way it is not proof that this recipe is published.
        return False
    return match.group("base") + match.group("bump") == expected


def plan(
    config: dict,
    root: Path,
    *,
    published: dict[str, tuple[str, str]],
    changed: set[str],
    full: bool,
    factory_repo: str,
) -> list[dict]:
    """The recipes to build, in inventory order."""
    # Without a factory repository the build root cannot see anything the
    # published listing claims, so the listing is not a witness and nothing may
    # be skipped.
    trust_published = bool(factory_repo) and bool(published)
    build = []
    for entry in config["packages"]:
        name = entry["name"]
        if full or name in changed or not trust_published:
            build.append(entry)
        elif is_published(root, entry, published):
            continue
        else:
            build.append(entry)
    return build


def stage_outputs(build: list[dict]) -> dict[str, str]:
    """Per-stage package lists and their <=250-package chunks."""
    outputs: dict[str, str] = {
        "build_list": json.dumps([entry["name"] for entry in build]),
    }
    for stage in range(STAGES):
        names = [
            entry["name"] for entry in build if (entry.get("stage") or 0) == stage
        ]
        outputs[f"stage{stage}"] = json.dumps(names)
        chunks = [names[i : i + CHUNK] for i in range(0, len(names), CHUNK)]
        outputs[f"stage{stage}_chunks"] = json.dumps(
            [json.dumps(chunk) for chunk in chunks]
        )
    return outputs


def overflow(build: list[dict]) -> list[str]:
    """Recipes asking for a wave that has no job.

    These used to fall out of every stage list while staying in build_list, so
    the run published a repository that was quietly missing them.
    """
    return sorted(
        entry["name"] for entry in build if (entry.get("stage") or 0) >= STAGES
    )
