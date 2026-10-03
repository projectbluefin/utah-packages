#!/usr/bin/env python3
"""Propose version bumps for the packages this factory locks to download.gnome.org.

Why this exists
---------------
`renovate.json` already carries a custom manager aimed at
`config/upstream-sources.json`, keyed on `datasource` and `depName`. No entry
carries those fields, so it has never matched anything and nothing here has
ever been bumped automatically -- which is why the inventory still asks for
GNOME 51 betas after 51.0 shipped.

Renovate could not finish the job on its own anyway. A version in this factory
is written in three places that must move together, and Renovate can rewrite
only the first:

  config/upstream-sources.json  version, url, filename, sha512, sha256_url,
                                fallback_urls
  packages/<pkg>/<pkg>.spec     Version:, Release:
  packages/<pkg>/sources        SHA512 (<tarball>) = <digest>

A version bump with a stale checksum is rejected by source_pipeline.py -- a
safe failure, but not a working bump. So the checksum has to be computed from
the bytes at bump time, which is what this does.

Scope
-----
GNOME entries (Source0 on download.gnome.org) poll the module's cache.json;
git-forge entries poll tags or releases. A lock whose own URLs reveal no feed
-- a lookaside primary with no forge mirror -- may carry an explicit `feed`
naming the project's real upstream feed, derived from the spec's Source0 and
verified against the forge; see issue #134. An explicit feed may name a git
forge, a GNOME module (download.gnome.org/sources/<module>/), or a
release-monitoring.org (Anitya) project for upstreams that publish only a
directory listing. detect-rawhide-updates.yml takes Fedora's recipe changes
but never a version or a lookaside source, on the stated policy that "Fedora
is a compatibility build root, not a source-update feed" -- version moves are
this tool's.

GNOME publishes an authoritative release index per module at
sources/<module>/cache.json, so the candidate list needs no scraping.

A lock still on the Fedora lookaside can be relocked with an explicit
--package run: to its GNOME module (the explicit feed's, else one named like
the package), or to the git forge its explicit feed names. The tool proposes
kind "relock" when the feed is newer within the lock's cycle or major, and
--apply moves the primary off the lookaside, keeps the lookaside as a
fallback, and deletes the package from config/fedora-primary-sources.txt.
Full runs never propose relocks, so no scan moves a primary on its own, and
an Anitya feed never relocks at all: it names versions, not a download URL.

Two spellings
-------------
RPM orders a prerelease below its final with a tilde, so the spec says
`Version: 51~beta` while the tarball is `gnome-shell-51.beta.tar.xz`. Fedora's
%{gnome_tarball_version} macro performs that `~` -> `.` conversion, which is
why bumping `Version:` alone also moves Source0 -- 25 specs here rely on it.
The inventory stores the tarball spelling. Both are derived from one release
string rather than restated, so they cannot disagree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.bootstrap_upstream_sources import FEDORA_HOSTS
from tools.bump_gate import HOLDS, dump_holds, load_holds
from tools.package_inventory import (
    FORGE_ARCHIVE,
    FORGE_RELEASE,
    GITLAB_ARCHIVE,
    parse_explicit_feed,
    parse_feed_url,
    source_locks,
)

GNOME_SOURCES = "https://download.gnome.org/sources/"

# The git forges this factory locks sources on. Both expose an ordered tag
# list, which is the only feed a bump needs; releases are preferred over tags
# where a project publishes them, because a tag is not a release.
GITHUB_API = "https://api.github.com"
LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms"
# Anitya's per-project version list. stable_versions is Anitya's own
# prerelease filter, applied before is_prerelease() applies this tool's.
ANITYA_VERSIONS = "https://release-monitoring.org/api/v2/versions/?project_id="

# alpha/beta/rc in any spelling GNOME uses: 51.beta, 51~rc, 1.10.beta.1.
# The trailing context is a lookahead, not part of the match: consuming it made
# rpm_version("1.10.beta.1") return "1.10~beta1", eating the separator before
# the point release. Caught by the round-trip test.
PRERELEASE = re.compile(r"(?:^|[.~-])(alpha|beta|rc)(?=[.~-]|\d|$)", re.IGNORECASE)
# The same marker with its leading separator, for rewriting that separator to
# the tilde RPM needs.
PRERELEASE_SEPARATOR = re.compile(r"[.~-](alpha|beta|rc)(?=[.~-]|\d|$)", re.IGNORECASE)


def is_prerelease(version: str) -> bool:
    """True for a GNOME prerelease such as 51.beta, 51~rc or 1.10.beta.1."""
    return bool(PRERELEASE.search(version))


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for a stable GNOME version.

    Only meaningful for stable versions, which are numeric and dot-separated;
    callers filter prereleases out first. A non-numeric component sorts as -1
    rather than raising, so one malformed entry in cache.json cannot take the
    whole run down.
    """
    return tuple(int(part) if part.isdigit() else -1 for part in version.split("."))


def newest_stable(versions: list[str]) -> str | None:
    """The highest non-prerelease in a cache.json version list, or None.

    "Not alpha/beta/rc" is not the same as "stable" -- see cycle_final.
    """
    stable = [v for v in versions if not is_prerelease(v)]
    return max(stable, key=version_key) if stable else None


def cycle_final(versions: list[str], cycle: str) -> str | None:
    """The highest release within one cycle, ignoring prereleases.

    A bump is only ever proposed for application automatically when it stays
    inside the cycle the lock already names -- 51.beta to 51.0. Crossing a
    cycle cannot be decided from the number alone, because GNOME's numbering
    encodes development series that no arithmetic rule separates from stable
    ones. pango is the proof: its releases run

        1.56.4, 1.57.0, 1.57.1, 1.58.0, 1.58.2, 1.90.0

    where 1.57 is a development series under the traditional odd-minor
    convention and 1.90 is the development series toward 2.0. Both sort above
    the stable 1.58.2, and 90 is even, so neither "highest" nor "even minor"
    picks the right answer. An earlier draft of this tool proposed
    1.58.2 -> 1.90.0 for exactly that reason.

    So cross-cycle candidates are reported for a human and never applied.
    """
    inside = [
        v
        for v in versions
        if not is_prerelease(v) and release_cycle(tarball_version(v)) == cycle
    ]
    return max(inside, key=version_key) if inside else None


def tarball_version(version: str) -> str:
    """The tarball spelling: RPM's prerelease tilde becomes a dot."""
    return version.replace("~", ".")


def rpm_version(version: str) -> str:
    """The Version: spelling: a prerelease sorts below its final with a tilde."""
    if not is_prerelease(version):
        return version
    return PRERELEASE_SEPARATOR.sub(lambda m: "~" + m.group(1), version, count=1)


def major(version: str) -> str:
    """The leading component of a release, used to group forge releases.

    This is NOT the download.gnome.org filing directory -- the library
    scheme files 4.23.4 under 4.23/, which is release_cycle()'s job.
    """
    return version.split(".")[0]


def release_cycle(version: str) -> str:
    """The development cycle a release belongs to.

    GNOME uses two numbering schemes and the cycle sits in a different place in
    each, so this cannot be "the first component":

      gnome-shell 51.beta, 51.0     cycle 51    -- the app scheme (GNOME 40+),
      nautilus 51.0.1               cycle 51       where the leading number is
                                                   the GNOME release and every
                                                   point release belongs to it
      pango 1.58.2, gtk4 4.23.3     cycle 1.58  -- the library scheme, where
                                                   major.minor is the cycle and
                                                   the last component is the
                                                   point release
      libadwaita 1.10.beta.1        cycle 1.10  -- library scheme, prerelease

    Getting this wrong is not cosmetic. With the cycle read as just the leading
    component, pango's cycle was "1", which made the development release 1.90.0
    look like an in-cycle successor to the stable 1.58.2.
    """
    parts = version.split(".")
    numeric = []
    for part in parts:
        if not part.isdigit():
            break
        numeric.append(part)
    if not numeric:
        return version
    if is_prerelease(version):
        # Everything before the marker is the cycle: 1.10.beta.1 -> 1.10.
        return ".".join(numeric)
    if len(numeric) >= 3 and int(numeric[0]) >= 40:
        # The app scheme (GNOME 40+): the leading number is the GNOME release
        # and every point release belongs to it -- 51.0 and 51.0.1 are both
        # cycle 51, filed under 51/.
        return numeric[0]
    # The library scheme: major.minor is the cycle, so 1.58.2 stays 1.58 and
    # the 1.90 development series never reads as its successor.
    if len(numeric) >= 3:
        return ".".join(numeric[:2])
    return numeric[0]


def forge_feed(entry: dict) -> dict | None:
    """The git-forge release feed a locked entry tracks, if it tracks one.

    Returns a descriptor rather than a tuple because the three shapes differ in
    what they need: GitHub releases are read from a different endpoint than
    GitHub tags, and GitLab is a different host entirely.

    The primary URL is read first, then each fallback in order. A lock whose
    primary moved to the Fedora lookaside for stability (forge archives can
    be regenerated upstream, silently changing the bytes) still tracks the
    feed its mirror names, so the daily poll keeps watching it. Whether the
    resulting proposal may be applied is decided in plan(), not here.
    """
    urls = [entry.get("url", ""), *entry.get("fallback_urls", [])]
    for url in urls:
        feed = parse_feed_url(url)
        if feed:
            return feed
    return None


def primary_tracks_forge(entry: dict) -> bool:
    """Whether the lock's primary URL names a git-forge feed.

    When only a fallback does, the new release's bytes are not where the
    primary points -- the lookaside carries only what Fedora uploaded, and a
    bare listing has no version to substitute -- so a proposal from that feed
    is reported for a human and never applied.
    """
    url = entry.get("url", "")
    return bool(
        FORGE_RELEASE.match(url) or FORGE_ARCHIVE.match(url) or GITLAB_ARCHIVE.match(url)
    )


def forge_label(feed: dict) -> str:
    """A short human name for a feed, for reports."""
    if feed["forge"] == "github":
        return f"github.com/{feed['owner']}/{feed['repo']}"
    if feed["forge"] == "anitya":
        return f"release-monitoring.org/project/{feed['id']}"
    return f"{feed['host']}/{feed['path']}"


def _forge_request(url: str) -> urllib.request.Request:
    """A forge API request, authenticated when a token is in the environment.

    Unauthenticated GitHub allows 60 requests an hour, and this factory locks
    36 sources on it, so an anonymous run would rate-limit part way through and
    report the rest as unreachable. The workflow supplies GITHUB_TOKEN.
    """
    headers = {
        "User-Agent": "utah-packages-bump/1",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith(GITHUB_API):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def forge_versions(feed: dict, opener=urllib.request.urlopen) -> list[str]:
    """Every version a forge lists for a project, tag prefixes stripped.

    Draft and prerelease-flagged GitHub releases are dropped here rather than
    left to is_prerelease: a maintainer marking a release prerelease is a
    stronger signal than the version string, and some use neither an alpha nor
    a beta suffix for one.
    """
    if feed["forge"] == "github":
        url = (
            f"{GITHUB_API}/repos/{feed['owner']}/{feed['repo']}"
            f"/{feed['endpoint']}?per_page=100"
        )
    else:
        project = urllib.parse.quote(feed["path"], safe="")
        url = (
            f"https://{feed['host']}/api/v4/projects/{project}"
            f"/repository/tags?per_page=100"
        )
    with opener(_forge_request(url), timeout=60) as response:
        document = json.loads(response.read())
    if not isinstance(document, list):
        raise ValueError("forge returned no list")
    found = []
    for item in document:
        if feed.get("endpoint") == "releases" and feed["forge"] == "github":
            if item.get("draft") or item.get("prerelease"):
                continue
            tag = item.get("tag_name", "")
        else:
            tag = item.get("name", "")
        version = strip_tag_prefix(tag)
        if version:
            found.append(version)
    return found


def anitya_versions(feed: dict, opener=urllib.request.urlopen) -> list[str]:
    """Every stable version release-monitoring.org lists for a project.

    Anitya's stable_versions already drops what its backend marks as a
    prerelease (gstreamer's odd 1.29 series); is_prerelease() still runs over
    the result in the callers, as for every other feed.
    """
    request = urllib.request.Request(
        f"{ANITYA_VERSIONS}{feed['id']}",
        headers={"User-Agent": "utah-packages-bump/1"},
    )
    with opener(request, timeout=60) as response:
        document = json.loads(response.read())
    versions = document.get("stable_versions") if isinstance(document, dict) else None
    if not isinstance(versions, list):
        raise ValueError("release-monitoring.org returned no version list")
    return list(dict.fromkeys(v for v in versions if isinstance(v, str) and v))


def strip_tag_prefix(tag: str) -> str:
    """The version inside a tag name: v2.2.1, release-2.2.1 and 2.2.1 alike.

    A tag carrying no digits at all is not a version and returns empty, which
    drops branch-style tags such as "main" or "stable" from the feed.
    """
    match = re.match(r"^[A-Za-z._-]*?(\d.*)$", tag.strip())
    return match.group(1) if match else ""


def gnome_module(entry: dict) -> str | None:
    """The download.gnome.org module a locked entry tracks, if it tracks one."""
    url = entry.get("url", "")
    if not url.startswith(GNOME_SOURCES):
        return None
    return url[len(GNOME_SOURCES):].split("/", 1)[0] or None


def releases(module: str, opener=urllib.request.urlopen) -> list[str]:
    """Every release GNOME lists for a module, from its cache.json index.

    cache.json is a 4-element array whose third element maps module name to an
    ordered version list.
    """
    request = urllib.request.Request(
        f"{GNOME_SOURCES}{module}/cache.json",
        headers={"User-Agent": "utah-packages-bump/1"},
    )
    with opener(request, timeout=60) as response:
        document = json.loads(response.read())
    return list(document[2].get(module, []))


def sha512_of(url: str, opener=urllib.request.urlopen) -> str:
    """The SHA-512 of the bytes at a URL, streamed rather than buffered."""
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-bump/1"})
    digest = hashlib.sha512()
    with opener(request, timeout=300) as response:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def planned_entry(entry: dict, release: str, digest: str, module: str | None = None) -> dict:
    """The locked entry rewritten for a new release.

    Every URL is rebuilt from the release string rather than patched, so a
    field cannot be left behind pointing at the old tarball -- fallback_urls in
    particular embeds both the filename and the digest. The module defaults to
    the entry's own GNOME primary; a relock passes the new one explicitly.
    """
    module = module or gnome_module(entry)
    if not module:
        raise ValueError(f"no GNOME module for {entry.get('name')}: refusing to guess a URL")
    tarball = tarball_version(release)
    name = f"{module}-{tarball}.tar.xz"
    # The filing directory follows the release cycle, not the leading
    # component: app-scheme 51.0 lives under 51/, library-scheme 4.23.4
    # under 4.23/ and 1.10.0 under 1.10/.
    base = f"{GNOME_SOURCES}{module}/{release_cycle(tarball)}"
    updated = dict(entry)
    updated["version"] = tarball
    updated["url"] = f"{base}/{name}"
    updated["filename"] = name
    updated["sha512"] = digest
    if "sha256_url" in entry:
        updated["sha256_url"] = f"{base}/{module}-{tarball}.sha256sum"
    if entry.get("fallback_urls"):
        # The lookaside is keyed by the Fedora package, not the GNOME module:
        # gtk3's tarball is gtk-3.24.52.tar.xz, filed under rpms/gtk3/.
        package = entry.get("name") or module
        updated["fallback_urls"] = [
            f"{LOOKASIDE}/{package}/{name}/sha512/{digest}/{name}"
        ]
    return updated


def substituted(value, replacements: list[tuple[str, str]]):
    """A string, or list of strings, with every replacement applied in turn."""
    if isinstance(value, list):
        return [substituted(item, replacements) for item in value]
    for old, new in replacements:
        value = value.replace(old, new)
    return value


def forge_planned_entry(entry: dict, release: str, digest: str) -> dict:
    """A forge-hosted entry rewritten for a new release.

    GNOME entries are rebuilt from a known template; a forge URL has no
    template this tool can own, because projects choose their own tag and
    asset names. So every URL-bearing field is rewritten by substituting the
    old version for the new one and the old digest for the new one. That
    reaches the places a field-by-field rebuild forgets -- fallback_urls
    embeds both the filename and the SHA-512, and sha256_url embeds the tag.

    Substituting the bare version also fixes a v-prefixed tag in the same
    pass, since "v2.2.1" contains "2.2.1".

    The old version must appear in the URL or this raises rather than writing
    a half-substituted entry: a project whose URL does not carry its version
    cannot be bumped by substitution, and guessing would corrupt the lock.
    """
    current = entry["version"]
    if current not in entry.get("url", ""):
        raise ValueError(
            f"{entry['name']}: version {current} does not appear in its url, "
            "so it cannot be bumped by substitution"
        )
    swaps = [(current, release)]
    if entry.get("sha512"):
        swaps.append((entry["sha512"], digest))
    updated = dict(entry)
    for field in ("url", "filename", "sha256_url", "fallback_urls"):
        if field in entry:
            updated[field] = substituted(entry[field], swaps)
    updated["version"] = release
    updated["sha512"] = digest
    return updated


RELEASE_LINE = re.compile(r"(?m)^(Release:[ \t]*)(\d+(?:\.\d+)*)(.*)$")


def reset_release(text: str) -> str:
    """Reset the leading literal to 1, preserving macros and trailing text.

    Macro-only releases have no literal to reset, just as dist_bump has no
    comparable baseline for them.
    """
    return RELEASE_LINE.sub(lambda m: f"{m.group(1)}1{m.group(3)}", text, count=1)


VERSION_LINE = re.compile(r"(?m)^(Version:\s*)(\S+)$")
MACRO_DEFINITION = re.compile(r"(?m)^%(?:global|define)\s+(\w+)\s+(.*)$")
MACRO_REFERENCE = re.compile(r"%\{?[?!]*(\w+)")
SOURCE_LINE = re.compile(r"(?m)^Source\d*:\s*(.*)$")


def version_macro_sources(text: str) -> list[str]:
    """Source lines that read a macro the Version: field is computed from.

    pipewire and alsa-utils build Version: from macros but name Source0 by
    %{version}, so overwriting the field with a literal still builds. A
    Source that reads the components instead (alsa-sof-firmware's
    %{sof_ver_pkg}, re2's %{tag}) would stay on the old release.
    """
    match = VERSION_LINE.search(text)
    if match is None or "%" not in match.group(2):
        return []
    definitions = {name: set(MACRO_REFERENCE.findall(body))
                   for name, body in MACRO_DEFINITION.findall(text)}
    bound = set(MACRO_REFERENCE.findall(match.group(2)))
    pending = list(bound)
    while pending:
        for name in definitions.get(pending.pop(), ()):
            if name not in bound:
                bound.add(name)
                pending.append(name)
    grown = True
    while grown:
        grown = False
        for name, references in definitions.items():
            if name not in bound and references & bound:
                bound.add(name)
                grown = True
    return [line for line in SOURCE_LINE.findall(text)
            if set(MACRO_REFERENCE.findall(line)) & bound]


def refuse_macro_sources(spec: Path, text: str) -> None:
    if version_macro_sources(text):
        raise ValueError(
            f"{spec}: Version: is computed from macros that a Source line reads, "
            "so a bump cannot rewrite it"
        )


def rewrite_spec(spec: Path, release: str) -> bool:
    """Update Version: and reset a literal Release:. True when changed."""
    text = spec.read_text()
    wanted = rpm_version(release)
    pattern = VERSION_LINE
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"{spec}: no Version: line to bump")
    refuse_macro_sources(spec, text)
    if match.group(2) == wanted:
        return False
    text = pattern.sub(lambda m: m.group(1) + wanted, text, count=1)
    spec.write_text(reset_release(text))
    return True


MANIFEST_LINE = re.compile(r"SHA512 \((\S+)\) = [0-9a-f]{128}")


def version_bound(filename: str, version: str) -> bool:
    """Whether a file name carries `version` as a whole version string."""
    return re.search(rf"(?<![\w.]){re.escape(version)}(?![\w]|\.\d)", filename) is not None


def bundled_entries(manifest: Path, primary: str) -> list[str]:
    """The manifest lines other than the primary tarball's, in order."""
    if not manifest.is_file():
        return []
    return [
        line for line in manifest.read_text().splitlines()
        if (match := MANIFEST_LINE.fullmatch(line.strip())) and match.group(1) != primary
    ]


def check_bumpable(root: Path, entry: dict) -> None:
    """Refuse, before fetching anything, a recipe a version bump cannot move.

    The `sources` manifest also pins bundled files that come from Fedora's
    lookaside (tools/source_pipeline.py bundled_sources): ppp-watch.tar.xz,
    a signing key, a vendored Go tree. A bump keeps those. One whose name
    carries the old version -- gum-2.0.0-vendor.tar.bz2, fish-4.6.0.tar.xz.asc
    -- has a successor that only a human (or Fedora) can produce, so the
    bump is reported for review rather than written half-done.
    """
    package = root / "packages" / entry["name"]
    spec = package / f"{entry['name']}.spec"
    if spec.is_file():
        refuse_macro_sources(spec, spec.read_text())
    # glycin pins glycin-2.2.beta-vendor.tar.xz for version 2.2~beta.
    spellings = {entry["version"], tarball_version(entry["version"])}
    for line in bundled_entries(package / "sources", entry.get("filename", "")):
        filename = MANIFEST_LINE.fullmatch(line.strip()).group(1)
        if any(version_bound(filename, spelling) for spelling in spellings):
            raise ValueError(
                f"{entry['name']}: bundled source {filename} is bound to {entry['version']}; "
                "its successor has to be produced by hand"
            )


def rewrite_sources(manifest: Path, filename: str, digest: str, previous: str = "") -> None:
    """Move the primary tarball pin in a Fedora sources manifest.

    Every other line -- a bundled file fetched from the lookaside by its own
    digest -- is kept. Writing the new pin alone dropped them, and the build
    of every such package (ppp, adw-gtk3-theme, gum, fish) died in
    `rpmbuild -bs` on a missing source.
    """
    kept = bundled_entries(manifest, previous or filename)
    lines = [f"SHA512 ({filename}) = {digest}", *[line for line in kept
             if MANIFEST_LINE.fullmatch(line.strip()).group(1) != filename]]
    manifest.write_text("\n".join(lines) + "\n")


def held(proposal: dict, holds: dict[str, dict]) -> dict | None:
    """The hold that stops this proposal, if its exact version is held."""
    hold = holds.get(proposal["name"])
    if hold and rpm_version(hold["version"]) == rpm_version(proposal["latest"]):
        return hold
    return None


def candidates(locks: dict[str, dict], only: str | None = None) -> list[tuple[str, dict, dict]]:
    """(name, entry, feed) for every lock this tool can track, sorted by name.

    A feed is either {"forge": "gnome", "module": ...} or a git-forge
    descriptor from forge_feed, which also reads the fallback mirrors and the
    lock's explicit `feed`. A lock with no feed anywhere -- the Fedora
    lookaside with no forge mirror and no explicit feed, a bare directory
    listing -- has nothing to poll and is skipped; see the module docstring.
    """
    found = []
    for name, entry in sorted(locks.items()):
        if only and name != only:
            continue
        module = gnome_module(entry)
        if module:
            found.append((name, entry, {"forge": "gnome", "module": module}))
            continue
        feed = forge_feed(entry)
        if feed:
            found.append((name, entry, feed))
            continue
        # An explicit `feed` names the project's real release feed when the
        # lock's own URLs cannot reveal one (a lookaside primary with no
        # forge mirror). The primary still points at the lookaside, so in a
        # full run every proposal from it stays review-only -- the new bytes
        # are not where the lock points. A human naming the package with
        # --package may relock it instead: a GNOME or forge feed names where
        # the new bytes live. An Anitya feed never does; it lists versions,
        # not downloads, so it stays review-only even then.
        explicit = entry.get("feed")
        if explicit:
            feed = parse_explicit_feed(explicit)
            if feed:
                if only and feed["forge"] != "anitya":
                    feed = {**feed, "relock": True}
                found.append((name, entry, feed))
                continue
        if only:
            # A human named this package explicitly: give it one chance to
            # be a GNOME module still locked on the Fedora lookaside, so its
            # tarball can be pulled from GNOME when GNOME is newer. Full runs
            # never probe here -- 258 lookaside locks are not 258 guesses --
            # and a name that is no GNOME module fails as a visible skip.
            found.append((name, entry, {"forge": "gnome", "module": name, "relock": True}))
    return found


def forge_proposal(name: str, entry: dict, feed: dict, opener=urllib.request.urlopen) -> dict:
    """What a single git-forge lock should move to, if anything.

    The safety rule mirrors the GNOME path's, with the major standing in for
    the release cycle: a newer stable release sharing the current major is an
    "update" and may be applied, while one that crosses a major is "review"
    only. A major bump can move a soname and break every consumer in the
    graph, which is a judgement no comparison of version strings can make.

    Prereleases are never proposed, and a forge whose API cannot be read is
    reported and skipped so one unreachable project does not stop the rest.
    An Anitya feed takes the same rule; only where the versions come from
    differs.
    """
    label = forge_label(feed)
    fetch = anitya_versions if feed["forge"] == "anitya" else forge_versions
    try:
        available = fetch(feed, opener=opener)
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as error:
        return {"name": name, "error": f"{label}: {error}"}

    current = entry["version"]
    newest = newest_stable(available)
    if newest is None or version_key(newest) <= version_key(current):
        return {"name": name, "module": label, "current": current, "latest": None}

    same_major = [
        v for v in available
        if not is_prerelease(v) and major(v) == major(current)
    ]
    within = newest_stable(same_major)
    if within is not None and version_key(within) > version_key(current):
        return {
            "kind": "update",
            "name": name,
            "module": label,
            "current": current,
            "latest": within,
        }
    return {
        "kind": "review",
        "name": name,
        "module": label,
        "current": current,
        "latest": newest,
    }


def plan(
    root: Path,
    only: str | None,
    opener=urllib.request.urlopen,
    cycle: str | None = None,
) -> list[dict]:
    """What would change, without changing anything.

    `cycle` names the release cycle to move within (GNOME 52 work runs with
    --cycle 52 on a next branch). Without it each lock stays in the cycle it
    already names, so a scheduled run never jumps GNOME majors on its own --
    and a cycle whose final has not shipped yet proposes nothing, so even an
    explicit --cycle cannot land on an alpha.

    Each proposal carries a `kind`:

      "final"  -- the lock names a prerelease and the same cycle has since
                  produced a release. Safe to apply: the cycle is already the
                  maintainers' choice, and only the prerelease suffix moves.
      "review" -- a newer release exists in a later cycle. Reported so a human
                  sees it, never applied; see cycle_final for why the number
                  cannot decide this.

    A module whose index cannot be read is reported and skipped rather than
    failing the run: one unreachable module must not stop the other sixteen.
    """
    locks = source_locks(root)
    proposals = []
    for name, entry, feed in candidates(locks, only):
        if feed["forge"] != "gnome":
            proposal = forge_proposal(name, entry, feed, opener=opener)
            if proposal.get("kind") == "update" and not primary_tracks_forge(entry):
                if feed.get("relock"):
                    # --package on an explicit forge feed: apply() moves the
                    # primary to the forge, so the bytes are fetched from
                    # where the lock will point.
                    proposals.append({**proposal, "kind": "relock"})
                    continue
                # The feed came from a mirror or an explicit `feed`, so the
                # primary points at the lookaside or a bare listing: apply()
                # would fetch the digest from an address that does not carry
                # the new release, or substitute a version into a URL that has
                # none. Report it so a human sees the release; main() only
                # applies final/update/relock.
                if "feed" in entry:
                    where = "the lock's explicit feed"
                else:
                    where = "a fallback mirror"
                proposal = {
                    **proposal,
                    "kind": "review",
                    "reason": (
                        f"the release feed is tracked through {where}; "
                        "the new bytes must be ingested through the primary first"
                    ),
                }
            proposals.append(proposal)
            continue
        module = feed["module"]
        try:
            available = releases(module, opener=opener)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as error:
            proposals.append({"name": name, "error": f"{module}: {error}"})
            continue
        current = tarball_version(entry["version"])
        target = cycle or release_cycle(current)

        # A lock whose primary is still the Fedora lookaside moves its bytes
        # to GNOME as well as forward in version: a relock, not just a bump.
        # Without --package (an explicit GNOME feed in a full run) the same
        # in-cycle release is only reported: apply() would have no GNOME
        # primary to rewrite.
        extra = {}
        if gnome_module(entry):
            kind = "final"
        elif feed.get("relock"):
            kind = "relock"
        else:
            kind = "review"
            extra = {
                "reason": "the release feed is tracked through the lock's explicit "
                "feed; relock it with --package to move the primary to GNOME"
            }
        within = cycle_final(available, target)
        if (is_prerelease(entry["version"]) and within is not None) or (
            within is not None and version_key(within) > version_key(current)
        ):
            proposals.append(
                {
                    "kind": kind,
                    "name": name,
                    "module": module,
                    "current": entry["version"],
                    "latest": within,
                    **extra,
                }
            )
            continue

        newest = newest_stable(available)
        if newest is not None and version_key(newest) > version_key(current):
            proposals.append(
                {
                    "kind": "review",
                    "name": name,
                    "module": module,
                    "current": entry["version"],
                    "latest": newest,
                }
            )
    return proposals


def apply(root: Path, proposal: dict, opener=urllib.request.urlopen) -> dict:
    """Move one package to a new release across all three files."""
    name, release = proposal["name"], proposal["latest"]
    config = root / "config" / "upstream-sources.json"
    document = json.loads(config.read_text())
    index = next(i for i, e in enumerate(document["packages"]) if e["name"] == name)
    entry = document["packages"][index]
    check_bumpable(root, entry)

    # A relock proposal carries the GNOME module explicitly because the old
    # primary is the lookaside; every other proposal reads it off the lock.
    # Only a relock: forge proposals carry their feed label (github.com/o/r)
    # under the same key, and reading that as a GNOME module built
    # download.gnome.org/sources/github.com/... URLs that 404ed, which killed
    # every scheduled run that had a forge update to apply.
    relock = proposal.get("kind") == "relock"
    explicit = parse_explicit_feed(entry.get("feed", "")) if relock else None
    module = (proposal.get("module") if relock else None) or gnome_module(entry)
    if explicit and explicit["forge"] not in ("gnome", "anitya"):
        # A forge relock: the explicit feed is the project's own Source0 at
        # the locked version, so it is the template the new primary is
        # substituted into. The old lookaside primary becomes a fallback,
        # rewritten by the same substitution (content-addressed, so it
        # resolves once Fedora uploads the same bytes, and only then).
        base = {
            **entry,
            "url": entry["feed"],
            "fallback_urls": [entry["url"], *entry.get("fallback_urls", [])],
        }
        url = substituted(entry["feed"], [(entry["version"], release)])
        digest = sha512_of(url, opener=opener)
        updated = forge_planned_entry(base, release, digest)
    elif module:
        tarball = tarball_version(release)
        url = f"{GNOME_SOURCES}{module}/{release_cycle(tarball)}/{module}-{tarball}.tar.xz"
        digest = sha512_of(url, opener=opener)
        if relock and entry.get("url", "") and not gnome_module(entry):
            # Keep the lookaside as the fallback a GNOME primary carries.
            entry = {**entry, "fallback_urls": [entry["url"]]}
        updated = planned_entry(entry, release, digest, module=module)
    else:
        # The new URL comes from substituting into the old one, so the digest
        # is fetched from the same address the lock will carry -- not from a
        # template this tool guessed.
        url = substituted(entry["url"], [(entry["version"], release)])
        digest = sha512_of(url, opener=opener)
        updated = forge_planned_entry(entry, release, digest)
    # The counter belongs to the old version even if both releases are 1.
    if rpm_version(entry["version"]) != rpm_version(updated["version"]):
        updated.pop("dist_bump", None)
    if relock:
        # The primary now names the feed itself; a stale explicit copy would
        # only be a second place for the two to disagree.
        updated.pop("feed", None)
    document["packages"][index] = updated

    # The lock is written last. rewrite_spec() raises before writing when the
    # spec has no Version: line, and main() skips that package and carries on;
    # with the lock written first, the skip left the lock on the new release
    # and the spec on the old one.
    package = root / "packages" / name
    spec = package / f"{name}.spec"
    if spec.is_file():
        rewrite_spec(spec, release)
    manifest = package / "sources"
    if manifest.is_file():
        rewrite_sources(manifest, updated["filename"], digest, previous=entry.get("filename", ""))
    config.write_text(json.dumps(document, indent=2) + "\n")
    if relock:
        retire_fedora_primary(root, name, updated["url"])
    return updated


def retire_fedora_primary(root: Path, name: str, url: str) -> None:
    """Drop a relocked package from the Fedora-primary ratchet.

    tools/validate.py fails when a package listed in
    config/fedora-primary-sources.txt no longer has a Fedora primary, so a
    relock that left the list alone produced a lock no workflow could
    validate.
    """
    host = urllib.parse.urlparse(url).hostname or ""
    if host in FEDORA_HOSTS or host.endswith(".fedoraproject.org"):
        return
    baseline = root / "config" / "fedora-primary-sources.txt"
    if not baseline.is_file():
        return
    lines = baseline.read_text().splitlines(keepends=True)
    kept = [line for line in lines if line.split("#", 1)[0].strip() != name]
    if kept != lines:
        baseline.write_text("".join(kept))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--package", help="consider only this package")
    parser.add_argument(
        "--cycle",
        help="move within this release cycle instead of each lock's own "
        "(GNOME 52 work runs with --cycle 52 on a next branch; a cycle "
        "with no final shipped proposes nothing)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite the inventory, spec and sources manifest (default: report only)",
    )
    args = parser.parse_args()
    # Progress goes to stdout and skips to stderr; unbuffered order is what
    # lets a CI log name the package a failure belongs to.
    sys.stdout.reconfigure(line_buffering=True)

    proposals = plan(args.root, args.package, cycle=args.cycle)
    failures = [p for p in proposals if "error" in p]
    # "final" is the GNOME in-cycle move, "update" the forge same-major one,
    # "relock" a GNOME in-cycle move that also shifts the primary off the
    # Fedora lookaside. All three are safe to write; all are reported alike.
    # A relock only ever arises from an explicit --package run, never from a
    # full scan, so no unattended run moves a primary on its own.
    finals = [p for p in proposals if p.get("kind") in ("final", "update", "relock")]
    review = [p for p in proposals if p.get("kind") == "review"]

    # The bump gate held these exact versions after they failed to build; a
    # newer release is proposed as usual, and applying it retires the hold.
    holds = load_holds(args.root)
    for bump in [p for p in finals if held(p, holds)]:
        hold = held(bump, holds)
        print(f"held {bump['name']}: {bump['current']} -> {bump['latest']} "
              f"failed the bump gate ({hold.get('run') or 'no run recorded'})", file=sys.stderr)
        finals.remove(bump)
    retired = False

    for failure in failures:
        print(f"skipped {failure['name']}: {failure['error']}", file=sys.stderr)

    applied = 0
    for bump in finals:
        print(f"{bump['name']}: {bump['current']} -> {bump['latest']}")
        if args.apply:
            # One release whose bytes cannot be fetched is reported and
            # skipped, the same rule plan() applies to an unreachable feed: it
            # must not discard every other bump the run already proved safe.
            try:
                apply(args.root, bump)
            except (urllib.error.URLError, OSError, ValueError) as error:
                print(f"skipped {bump['name']}: {error}", file=sys.stderr)
                continue
            applied += 1
            if holds.pop(bump["name"], None) is not None:
                retired = True

    for item in review:
        # Deliberately not applied, and deliberately not silent: a later cycle
        # may be a development series (pango 1.90 toward 2.0), which no rule
        # here can tell from a stable one.
        detail = item.get("reason", "crosses a release cycle or a major")
        print(
            f"needs review  {item['name']}: {item['current']} -> {item['latest']} "
            f"({detail})",
            file=sys.stderr,
        )

    if retired:
        (args.root / HOLDS).write_text(dump_holds(holds))

    if not finals:
        print("no in-cycle release is newer than what the inventory locks")
    elif args.apply and not applied:
        print("every proposed bump failed to apply", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
