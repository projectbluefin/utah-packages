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


def source_name(sourcerpm: str) -> str | None:
    """`name` out of `name-version-release.src.rpm`, or None if it is not one."""
    if not sourcerpm.endswith(".src.rpm"):
        return None
    nevr = sourcerpm[: -len(".src.rpm")]
    name, _, _ = nevr.rpartition("-")
    name, _, _ = name.rpartition("-")
    return name or None


def dependents_from_primary(primary: bytes) -> dict[str, set[str]]:
    """Map source package name -> the source packages that depend on it.

    Runtime dependencies, read from the published binaries: gnome-shell
    Requires libmutter-17.so.0, which mutter-libs Provides, so mutter maps to
    {gnome-shell}. That is exactly the edge a soname break travels along, and
    the one a skip must never cut: with the published listing as a witness, a
    fix to mutter would build mutter alone and leave a gnome-shell in the
    repository that was linked against the mutter it just replaced.

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


def provides_from_primary(primary: bytes) -> set[str]:
    """Every capability a repository provides: rpm Provides plus shipped files."""
    provided: set[str] = set()
    root = ElementTree.fromstring(primary)
    for package in root.iter(f"{{{COMMON_NS}}}package"):
        fmt = package.find(f"{{{COMMON_NS}}}format")
        if fmt is None:
            continue
        for entry in fmt.iterfind(f"{{{RPM_NS}}}provides/{{{RPM_NS}}}entry"):
            provided.add(entry.get("name", ""))
        for file in package.iterfind(f"{{{COMMON_NS}}}file"):
            provided.add(file.text or "")
    return provided


def capability_stem(capability: str) -> str:
    """Extract canonical stem for sonames, pkgconfig, or package names."""
    if ".so" in capability:
        m = re.match(r"^([a-zA-Z0-9_\-+.]+\.so)", capability)
        if m:
            return m.group(1)
    if capability.startswith("pkgconfig(") and capability.endswith(")"):
        return capability
    return capability.split()[0]


def stale_from_primary(primary: bytes, external: set[str]) -> dict[str, set[str]]:
    """Source name -> the Requires of its published binaries that nothing provides.

    A published package can be exactly the recipe on disk and still be wrong:
    it was linked against whatever the build root had at the time, and the
    build root moves. libheif built when the factory carried ffmpeg 8 asks for
    libavcodec.so.62; once ffmpeg 9 is published and provides .so.63, nothing
    satisfies the old binary and the consumer transaction fails on it.

    Neither the recipe nor the inventory changed, so `changed` never sees it,
    and the dependents map does not either: it follows edges from a provider
    that exists, and here the provider is what went missing. `external` is what
    the consumer's other repository (Hummingbird) provides.

    Restricts staleness to capabilities the factory repository itself provides.
    Capabilities provided solely by the base buildroot (Fedora paired with Hummingbird)
    are not factory-managed and do not flag stale published builds.
    """
    provided = provides_from_primary(primary) | external
    factory_provided = provides_from_primary(primary)
    factory_stems = {capability_stem(c) for c in factory_provided}

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
            if capability_stem(capability) in factory_stems:
                stale.setdefault(source, set()).add(capability)
    return stale


def expand_spec_macros(text: str, macros: dict[str, str]) -> str:
    """Expand macros like %{name} or %name without clobbering longer tokens."""
    for k in sorted(macros.keys(), key=len, reverse=True):
        v = macros[k]
        text = re.sub(r"%\{\??\b" + re.escape(k) + r"\b\}", lambda _: v, text)
        text = re.sub(r"%\b" + re.escape(k) + r"\b", lambda _: v, text)
    return text


def strip_spec_comment(line: str) -> str:
    """Strip comments from spec line without cutting URLs with fragments."""
    if line.strip().startswith("#"):
        return ""
    return re.sub(r"\s+#.*$", "", line)


def spec_dependents(root: Path, factory_pkgs: set[str]) -> dict[str, set[str]]:
    """Map provider package name -> set of factory packages that BuildRequire it.

    Parses package spec files under packages/ to identify declared symbols
    (package names, declared subpackages, Provides) and maps each dependency
    to downstream factory packages whose BuildRequires ask for it.
    """
    packages_dir = root / "packages"
    if not packages_dir.exists():
        return {p: set() for p in factory_pkgs}

    symbol_to_pkg: dict[str, str] = {}
    for p in factory_pkgs:
        symbol_to_pkg[p] = p

    pkg_specs: dict[str, str] = {}
    for p in sorted(factory_pkgs):
        spec_files = sorted((packages_dir / p).glob("*.spec"))
        if not spec_files:
            continue
        try:
            content = spec_files[0].read_text(errors="ignore")
        except OSError:
            continue
        pkg_specs[p] = content

        clean_lines = []
        for line in content.splitlines():
            if re.match(r"^%changelog\b", line):
                break
            clean_lines.append(strip_spec_comment(line))
        clean_content = "\n".join(clean_lines)

        macros = {"name": p}
        for m in re.finditer(r"%(?:global|define)\s+([a-zA-Z0-9_]+)\s+([^\n]+)", clean_content):
            macros[m.group(1)] = m.group(2).strip()

        for line in clean_lines:
            m = re.match(r"^%package\s+(.*)", line)
            if m:
                sub = m.group(1).strip()
                sub = expand_spec_macros(sub, macros)
                if sub.startswith("-n"):
                    subname = re.sub(r"^-n\s*", "", sub).strip().split()[0]
                else:
                    subname = f"{p}-{sub.split()[0]}"
                symbol_to_pkg[subname] = p

            m = re.match(r"^Provides:\s+(.*)", line, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                val = expand_spec_macros(val, macros)
                for token in re.findall(r"[^\s,()]+(?:\([^)]*\))?", val):
                    if token in (">=", "<=", "=", ">", "<") or token[0].isdigit() or "%" in token:
                        continue
                    symbol_to_pkg[token] = p

            for pcm in re.finditer(r"([a-zA-Z0-9_\-+*%{}]+)\.pc", line):
                pcname = pcm.group(1)
                pcname = expand_spec_macros(pcname, macros)
                if "%" not in pcname:
                    if "*" in pcname:
                        expanded_pc = pcname.replace("*", p)
                        symbol_to_pkg[f"pkgconfig({expanded_pc})"] = p
                    else:
                        symbol_to_pkg[f"pkgconfig({pcname})"] = p

    forward_deps: dict[str, set[str]] = {p: set() for p in factory_pkgs}
    for p, content in pkg_specs.items():
        for line in content.splitlines():
            if re.match(r"^%changelog\b", line):
                break
            line = strip_spec_comment(line)
            m = re.match(r"^BuildRequires:\s*(.*)", line, re.IGNORECASE)
            if not m:
                continue
            val = m.group(1).strip()
            for token in re.findall(r"[^\s,()]+(?:\([^)]*\))?", val):
                token = token.strip()
                if not token or token in (">=", "<=", "=", ">", "<") or token[0].isdigit() or "%" in token:
                    continue
                if token in symbol_to_pkg:
                    target = symbol_to_pkg[token]
                    if target != p:
                        forward_deps[p].add(target)
                elif token.startswith("pkgconfig("):
                    if token in symbol_to_pkg:
                        target = symbol_to_pkg[token]
                        if target != p:
                            forward_deps[p].add(target)

    rev_deps: dict[str, set[str]] = {p: set() for p in factory_pkgs}
    for p, deps in forward_deps.items():
        for d in deps:
            rev_deps.setdefault(d, set()).add(p)
    return rev_deps


def merge_dependents(*maps: dict[str, set[str]]) -> dict[str, set[str]]:
    """Merge multiple reverse-dependency mappings into one."""
    merged: dict[str, set[str]] = {}
    for m in maps:
        if not m:
            continue
        for provider, dependents in m.items():
            merged.setdefault(provider, set()).update(dependents)
    return merged


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


# Global paths that trigger a full rebuild or policy-defined rebuild
GLOBAL_REBUILD_PATTERNS = (
    r"^\.github/workflows/rebuild-rpms\.yml$",
    r"^\.github/workflows/build-stage\.yml$",
    r"^\.github/actions/.*",
    r"^config/(?!upstream-sources\.json$).*",
    r"^tools/mock_config\.py$",
)

GLOBAL_IGNORE_PATTERNS = (
    r"^\.agents/.*",
    r"^\.claude/.*",
    r"^docs/.*",
    r"^\.gitignore$",
    r"^\.gitattributes$",
    r"^\.pre-commit-config\.yaml$",
    r"^AGENTS\.md$",
    r"^Justfile$",
    r"^README\.md$",
    r"^renovate\.json$",
    r"^reports/.*",
    r"^tests/.*",
    r"^tools/(?!mock_config\.py$).*",
)


def is_global_change(paths: list[str]) -> tuple[bool, list[str]]:
    """Determine if changed paths touch global tooling, workflows, or buildroot policy."""
    triggers: list[str] = []
    for path in paths:
        path = path.strip()
        if not path:
            continue
        if any(re.match(pat, path) for pat in GLOBAL_IGNORE_PATTERNS):
            continue
        if any(re.match(pat, path) for pat in GLOBAL_REBUILD_PATTERNS):
            triggers.append(path)
    return bool(triggers), sorted(triggers)


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
    except (BumpError, OSError):
        return None
    if release is None:
        return None
    return release + suffix(entry, release)


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
    reasons: dict[str, list[str]] | None = None,
    global_triggers: list[str] | None = None,
) -> list[dict]:
    """The recipes to build, in inventory order.

    `dependents` is the reverse dependency map (runtime Provides/Requires from
    the published repository and build-time BuildRequires from specs).
    Whatever is rebuilt drags its dependents with it, so a skip can never
    leave a consumer linked against or built against a replaced package.
    `stale` names published packages whose binaries require capabilities
    that nothing provides anymore.
    """
    # Without a factory repository the build root cannot see anything the
    # published listing claims, so the listing is not a witness and nothing may
    # be skipped.
    trust_published = bool(factory_repo) and bool(published)
    build = []
    global_triggers = global_triggers or []

    for entry in config["packages"]:
        name = entry["name"]
        if full:
            build.append(entry)
            if reasons is not None:
                if global_triggers:
                    reasons[name] = [f"global trigger ({', '.join(global_triggers[:3])})"]
                else:
                    reasons[name] = ["full rebuild requested"]
        elif name in changed:
            build.append(entry)
            if reasons is not None:
                reasons[name] = ["recipe edit or inventory change"]
        elif name in stale:
            build.append(entry)
            if reasons is not None:
                reasons[name] = ["stale published build"]
        elif not trust_published:
            build.append(entry)
            if reasons is not None:
                reasons[name] = ["no trusted factory repo to verify published state"]
        elif not is_published(root, entry, published):
            build.append(entry)
            if reasons is not None:
                if name not in published:
                    reasons[name] = ["new or unpublished package"]
                else:
                    reasons[name] = ["version/release mismatch with published repo"]
        else:
            # Package is published and unchanged
            continue

    if dependents and not full:
        building = {entry["name"] for entry in build}
        dragged = reverse_closure(building, dependents)
        if reasons is not None:
            for d in dragged:
                if d not in reasons:
                    causes = [src for src in building if d in reverse_closure({src}, dependents)]
                    reasons[d] = [f"reverse dependency of {', '.join(sorted(causes))}"]
        build = [
            entry
            for entry in config["packages"]
            if entry["name"] in building or entry["name"] in dragged
        ]

    return build


def format_build_plan(
    build: list[dict],
    reasons: dict[str, list[str]],
    *,
    full: bool,
    global_triggers: list[str] | None = None,
    direct_changes: set[str] | None = None,
    reverse_deps: set[str] | None = None,
    total_inventory: int = 0,
) -> tuple[str, dict]:
    """Format the build plan as Markdown step summary and structured JSON."""
    global_triggers = global_triggers or []
    direct_changes = direct_changes or set()
    reverse_deps = reverse_deps or set()

    lines = ["# Factory Build Plan", ""]
    if full:
        lines.append("**Build Mode:** Full Rebuild")
        if global_triggers:
            lines.append(f"- **Triggered by global changes ({len(global_triggers)}):** {', '.join(sorted(global_triggers))}")
    else:
        lines.append("**Build Mode:** Incremental")
        lines.append(f"- **Direct changes ({len(direct_changes)}):** {', '.join(sorted(direct_changes)) or 'none'}")
        lines.append(f"- **Reverse dependency closures ({len(reverse_deps)}):** {', '.join(sorted(reverse_deps)) or 'none'}")

    inv_str = f" of {total_inventory}" if total_inventory else ""
    lines.append(f"- **Total packages selected:** {len(build)}{inv_str}")
    lines.append("")

    if not build:
        lines.append("No packages require building in this run.")
        summary_md = "\n".join(lines)
        plan_json = {
            "mode": "full" if full else "incremental",
            "total_selected": 0,
            "total_inventory": total_inventory,
            "global_triggers": sorted(global_triggers),
            "direct_changes": sorted(direct_changes),
            "reverse_deps": sorted(reverse_deps),
            "packages": [],
            "stages": {f"stage{s}": [] for s in range(STAGES)},
            "reasons": {},
        }
        return summary_md, plan_json

    lines.append("## Build Waves")
    lines.append("")
    stages_dict: dict[str, list[str]] = {}
    for stage in range(STAGES):
        stage_key = f"stage{stage}"
        pkgs = [e["name"] for e in build if (e.get("stage") or 0) == stage]
        stages_dict[stage_key] = pkgs
        if pkgs:
            lines.append(f"### Stage {stage} ({len(pkgs)} packages)")
            for name in pkgs:
                pkg_reasons = "; ".join(reasons.get(name, ["selected"]))
                lines.append(f"- **{name}**: {pkg_reasons}")
            lines.append("")

    lines.append("## Package Selection Summary")
    lines.append("")
    lines.append("| Package | Stage | Selection Reason |")
    lines.append("| --- | --- | --- |")
    for entry in build:
        name = entry["name"]
        st = entry.get("stage") or 0
        r_str = "; ".join(reasons.get(name, ["selected"]))
        lines.append(f"| `{name}` | {st} | {r_str} |")
    lines.append("")

    summary_md = "\n".join(lines)
    plan_json = {
        "mode": "full" if full else "incremental",
        "total_selected": len(build),
        "total_inventory": total_inventory,
        "global_triggers": sorted(global_triggers),
        "direct_changes": sorted(direct_changes),
        "reverse_deps": sorted(reverse_deps),
        "packages": [e["name"] for e in build],
        "stages": stages_dict,
        "reasons": {name: reasons.get(name, ["selected"]) for name in [e["name"] for e in build]},
    }
    return summary_md, plan_json


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
