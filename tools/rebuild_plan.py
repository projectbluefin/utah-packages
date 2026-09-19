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
import xml.etree.ElementTree as ElementTree
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


# repodata primary.xml puts every rpm: element in this namespace.
RPM_NS = "http://linux.duke.edu/metadata/rpm"
COMMON_NS = "http://linux.duke.edu/metadata/common"


def dependents_from_primary(primary: bytes) -> dict[str, set[str]]:
    """Map source package name -> the source packages that depend on it.

    Runtime dependencies, read from the published binaries: gnome-shell
    Requires libmutter-17.so.0, which mutter-libs Provides, so mutter maps to
    {gnome-shell}. That is exactly the edge a soname break travels along, and
    the one a skip must never cut: with the published listing as a witness, a
    fix to mutter would build mutter alone and leave a gnome-shell in the
    repository that was linked against the mutter it just replaced. The
    published repository carries no source RPMs, so BuildRequires are not
    readable here; a devel package that is only built against, never linked,
    is the residual gap.

    Self-edges are dropped: a package requiring its own subpackages is not a
    reason to rebuild anything else.
    """
    provided_by: dict[str, set[str]] = {}
    requires: list[tuple[str, set[str]]] = []
    root = ElementTree.fromstring(primary)
    for package in root.iter(f"{{{COMMON_NS}}}package"):
        fmt = package.find(f"{{{COMMON_NS}}}format")
        if fmt is None:
            continue
        sourcerpm = fmt.findtext(f"{{{RPM_NS}}}sourcerpm") or ""
        source = source_name(sourcerpm)
        if source is None:
            continue
        for entry in fmt.iterfind(f"{{{RPM_NS}}}provides/{{{RPM_NS}}}entry"):
            provided_by.setdefault(entry.get("name", ""), set()).add(source)
        # Files a package ships are Provides in every sense dnf cares about:
        # a Requires: /usr/bin/foo resolves through them.
        for file in package.iterfind(f"{{{COMMON_NS}}}file"):
            provided_by.setdefault(file.text or "", set()).add(source)
        needed = {
            entry.get("name", "")
            for entry in fmt.iterfind(f"{{{RPM_NS}}}requires/{{{RPM_NS}}}entry")
        }
        requires.append((source, needed))
    dependents: dict[str, set[str]] = {}
    for source, needed in requires:
        for capability in needed:
            for provider in provided_by.get(capability, ()):
                if provider != source:
                    dependents.setdefault(provider, set()).add(source)
    return dependents


# Builds the consumer transaction refuses, as (name, version prefix). Their
# capabilities must not count as provided here either, or this model disagrees
# with the transaction it exists to predict.
#
# Hummingbird ships libicu 77.1 beside 78.3 under one package name; it has
# migrated to 78 (every current build links libicuuc.so.78, only superseded ones
# link .so.77), and the publish gate excludes 77 so consumers cannot split
# across both. Counting 77 as provided here meant a published package linked
# against it looked satisfiable, was skipped as fresh, and then failed the very
# transaction this check exists to predict -- which is how run 35413902261 lost
# publication after 331 green builds.
EXCLUDED_EXTERNAL: tuple[tuple[str, str], ...] = (("libicu", "77."),)


def provides_from_primary(
    primary: bytes, excluded: tuple[tuple[str, str], ...] = EXCLUDED_EXTERNAL
) -> set[str]:
    """Every capability a repository provides: rpm Provides plus shipped files.

    Builds named in `excluded` contribute nothing, because the consumer
    transaction will not install them.
    """
    provided: set[str] = set()
    root = ElementTree.fromstring(primary)
    for package in root.iter(f"{{{COMMON_NS}}}package"):
        fmt = package.find(f"{{{COMMON_NS}}}format")
        if fmt is None:
            continue
        name = package.findtext(f"{{{COMMON_NS}}}name") or ""
        version = package.find(f"{{{COMMON_NS}}}version")
        ver = version.get("ver", "") if version is not None else ""
        if any(name == excluded_name and ver.startswith(prefix)
               for excluded_name, prefix in excluded):
            continue
        for entry in fmt.iterfind(f"{{{RPM_NS}}}provides/{{{RPM_NS}}}entry"):
            provided.add(entry.get("name", ""))
        for file in package.iterfind(f"{{{COMMON_NS}}}file"):
            provided.add(file.text or "")
    return provided


def stale_from_primary(primary: bytes, external: set[str]) -> dict[str, set[str]]:
    """Source name -> the Requires of its published binaries that nothing provides.

    A published package can be exactly the recipe on disk and still be wrong:
    it was linked against whatever the build root had at the time, and the
    build root moves. libheif built when the factory carried ffmpeg 8 asks for
    libavcodec.so.62; once ffmpeg 9 is published and provides .so.63, nothing
    satisfies the old binary and the consumer transaction fails on it. The
    same happens when Hummingbird bumps a soname underneath the factory.

    Neither the recipe nor the inventory changed, so `changed` never sees it,
    and the dependents map does not either: it follows edges from a provider
    that exists, and here the provider is what went missing. This is the
    third rule, and the only one that reads what the published binaries
    actually ask for. `external` is what the consumer's other repository
    (Hummingbird) provides; a Requires satisfied by neither side marks the
    package stale, and stale packages rebuild -- against the current build
    root, which is the only cure.

    Skipped, to avoid calling healthy packages stale on a partial view:
    rpmlib() capabilities, which are the package manager's; rich
    dependencies in parentheses, which need dnf to evaluate; and file paths,
    because primary.xml lists only a subset of files and the full list lives
    in filelists.xml, which is not read here.
    """
    provided = provides_from_primary(primary) | external
    stale: dict[str, set[str]] = {}
    root = ElementTree.fromstring(primary)
    for package in root.iter(f"{{{COMMON_NS}}}package"):
        fmt = package.find(f"{{{COMMON_NS}}}format")
        if fmt is None:
            continue
        source = source_name(fmt.findtext(f"{{{RPM_NS}}}sourcerpm") or "")
        if source is None:
            continue
        for entry in fmt.iterfind(f"{{{RPM_NS}}}requires/{{{RPM_NS}}}entry"):
            capability = entry.get("name", "")
            if (
                not capability
                or capability.startswith(("rpmlib(", "(", "/"))
                or capability in provided
            ):
                continue
            stale.setdefault(source, set()).add(capability)
    return stale


def source_name(sourcerpm: str) -> str | None:
    """`name` out of `name-version-release.src.rpm`, or None if it is not one."""
    if not sourcerpm.endswith(".src.rpm"):
        return None
    nevr = sourcerpm[: -len(".src.rpm")]
    name, _, _ = nevr.rpartition("-")
    name, _, _ = name.rpartition("-")
    return name or None


def reverse_closure(names: set[str], dependents: dict[str, set[str]]) -> set[str]:
    """Every published package that transitively depends on one of `names`."""
    closure: set[str] = set()
    frontier = list(names)
    while frontier:
        current = frontier.pop()
        for dependent in dependents.get(current, ()):
            if dependent not in closure and dependent not in names:
                closure.add(dependent)
                frontier.append(dependent)
    return closure


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


def changed_entries(before: dict, after: dict) -> set[str]:
    """Names whose inventory entry is not identical in both configs.

    A recipe edit reaches `changed` through the git diff of packages/<name>/,
    but an inventory edit reached nothing, and that gap published a broken
    repository. Moving mozc from stage 0 to stage 1 and gnome-shell from 9 to
    10 was exactly the fix their soname breaks needed -- and it did nothing,
    because a stage move leaves Version and Release untouched, so both matched
    the published listing, were skipped, and came back from the seeded image
    as the very builds the move existed to replace. The stage is part of how a
    package is built, so a change to it has to invalidate the match the same
    way a changed spec does.

    Compares whole entries rather than the stage alone: a new source URL, a
    new checksum or a new dist_bump all change what gets built, and none of
    them is visible in the published NEVR either.
    """
    old = {entry["name"]: entry for entry in before.get("packages", [])}
    return {
        entry["name"]
        for entry in after.get("packages", [])
        if old.get(entry["name"]) != entry
    }


def plan(
    config: dict,
    root: Path,
    *,
    published: dict[str, tuple[str, str]],
    changed: set[str],
    full: bool,
    factory_repo: str,
    dependents: dict[str, set[str]] | None = None,
    stale: set[str] = frozenset(),
) -> list[dict]:
    """The recipes to build, in inventory order.

    `dependents` is the reverse dependency map of the published repository
    (see dependents_from_primary). Whatever is rebuilt drags its published
    dependents with it, so a skip can never leave a consumer linked against
    a library the same run is replacing. `stale` names published packages
    whose binaries require something nothing provides any more (see
    stale_from_primary); they build regardless of matching the recipe.
    """
    # Without a factory repository the build root cannot see anything the
    # published listing claims, so the listing is not a witness and nothing may
    # be skipped.
    trust_published = bool(factory_repo) and bool(published)
    build = []
    for entry in config["packages"]:
        name = entry["name"]
        if full or name in changed or name in stale or not trust_published:
            build.append(entry)
        elif is_published(root, entry, published):
            continue
        else:
            build.append(entry)
    if dependents:
        building = {entry["name"] for entry in build}
        dragged = reverse_closure(building, dependents)
        build = [
            entry
            for entry in config["packages"]
            if entry["name"] in building or entry["name"] in dragged
        ]
    return build


def cacheable(build: list[dict], changed: set[str], stale: set[str]) -> list[str]:
    """Which selected packages may consult the per-package build cache.

    The cache answers "have we already built this exact thing" (see
    tools/package_cache_key.py and issue #177). It deliberately does not answer
    "should this be rebuilt", which is what `plan` above decides -- so it narrows
    nothing and widens nothing. Every package `plan` selected is still selected;
    this only says which of them a build job may satisfy from the cache instead
    of by compiling.

    Two exclusions, both about intent rather than correctness:

    `changed` is excluded because a recipe the author just edited is the one case
    where they are owed a real build. The key would in fact miss -- editing the
    recipe changes the recipe digest -- so this is belt and braces, and it keeps
    the promise legible rather than resting on the key being right.

    `stale` is excluded because a stale published package is one whose binaries
    require something nothing provides any more. Its recipe may not have moved,
    so its key can hit, and hitting would hand back the very build that is
    broken. That is the one case where the cache would actively defeat the
    repair, so it is named here rather than left to chance.
    """
    excluded = set(changed) | set(stale)
    return [entry["name"] for entry in build if entry["name"] not in excluded]


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
