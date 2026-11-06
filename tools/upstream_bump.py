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
  packages/<pkg>/<pkg>.spec     Version:, Release:, manual %changelog
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
directory listing. A same-major release read from such a feed is applied
like any forge update: the version is swapped into the lock's own primary
(mesa-26.2.1.tar.xz on archive.mesa3d.org becomes mesa-26.2.6.tar.xz), the
fallbacks are rebuilt, and the bytes at the derived URL are SHA-512 locked.
Only a primary on Fedora's lookaside, or one that does not carry its
version, is reported instead, each with its own reason (primary_blocker).
detect-rawhide-updates.yml takes Fedora's recipe changes
but never a version or a lookaside source, on the stated policy that "Fedora
is a compatibility build root, not a source-update feed" -- version moves are
this tool's.

GNOME publishes an authoritative release index per module at
sources/<module>/cache.json, so the candidate list needs no scraping.

Following GNOME's stable release
--------------------------------
Utah is a rolling release: a GNOME package tracks GNOME's newest stable
release on its own and never stays on an old or development series. Fedora
supplies the recipe and the build root, never the version decision. cache.json
lists versions but cannot say which series is stable (see cycle_final), so the
series comes from GNOME's own release definition, GNOME/gnome-build-meta: its
highest plain `<major>.<minor>` tag (51.1, never 52.alpha/52.beta/52.rc) is
GNOME's newest stable release, and the element a lock maps to names the
version that release ships. Its release_cycle() is the lock's target series.
A lock behind that series moves to the newest final cache.json lists in it
(kind "stable", applied like "final"); a lock on it keeps the in-cycle rule;
a lock ahead of it gets a note and still takes point releases of its own
series, never a newer series GNOME does not ship. App-scheme modules (major 40
and up, prereleases spelled with markers) that gnome-build-meta does not map
move to their newest final across majors. Library-scheme modules it does not
map, and every forge feed, still only report a cross-cycle or cross-major
release for review. gjs sat on the development release 1.89.2 after 1.90.1
shipped, and gtk4 on 4.23.4 after 4.24.1, because the old rule never crossed
a cycle. --cycle N remains the manual override, and skips gnome-build-meta.

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
from email.utils import formatdate
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from tools.audit_gnome_build_meta import (
    Loader,
    _aliases,
    _gbm_gnome_modules,
    _gbm_module,
    _gbm_version,
    load_pin,
    resolve_element,
)
from tools.bootstrap_upstream_sources import FEDORA_HOSTS
from tools.bump_gate import HOLDS, REVIEW_ONLY, dump_holds, load_holds, load_review_only
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

# alpha/beta/rc in any spelling GNOME uses: 51.beta, 51~rc, 1.10.beta.1, plus
# the -dev tags of release-less GitLab projects (ModemManager 1.25.95-dev).
# The trailing context is a lookahead, not part of the match: consuming it made
# rpm_version("1.10.beta.1") return "1.10~beta1", eating the separator before
# the point release. Caught by the round-trip test.
PRERELEASE = re.compile(r"(?:^|[.~-])(alpha|beta|rc|dev)(?=[.~-]|\d|$)", re.IGNORECASE)
# The same marker with its leading separator, for rewriting that separator to
# the tilde RPM needs.
PRERELEASE_SEPARATOR = re.compile(r"[.~-](alpha|beta|rc|dev)(?=[.~-]|\d|$)", re.IGNORECASE)


def is_prerelease(version: str) -> bool:
    """True for a prerelease such as 51.beta, 51~rc, 1.10.beta.1 or 1.25.95-dev."""
    return bool(PRERELEASE.search(version))


def is_gnome_prerelease(version: str) -> bool:
    """is_prerelease(), plus the library scheme's numeric betas and rcs.

    GNOME libraries spell the beta and rc of the next stable as a micro of 90
    or more on the development minor: at-spi2-core 2.61.90 and gjs 1.89.90 sit
    in cache.json directly before 2.62.0 and 1.90.0, and carry no marker for
    is_prerelease() to see. Only the GNOME feed gets this rule: forge projects
    such as libdrm 2.4.134 or libfprint 1.94.100 ship stables with large
    micros. The app scheme (GNOME 40+) spells its prereleases with a marker.
    """
    if is_prerelease(version):
        return True
    parts = tarball_version(version).split(".")
    return (
        len(parts) == 3
        and all(part.isdigit() for part in parts)
        and int(parts[0]) < 40
        and int(parts[2]) >= 90
    )


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for a stable GNOME version.

    Only meaningful for stable versions, which are numeric and dot-separated;
    callers filter prereleases out first. A non-numeric component sorts as -1
    rather than raising, so one malformed entry in cache.json cannot take the
    whole run down.
    """
    return tuple(int(part) if part.isdigit() else -1 for part in version.split("."))


def newest_stable(versions: list[str], prerelease=is_prerelease) -> str | None:
    """The highest non-prerelease in a cache.json version list, or None.

    "Not alpha/beta/rc" is not the same as "stable" -- see cycle_final.
    """
    stable = [v for v in versions if not prerelease(v)]
    return max(stable, key=version_key) if stable else None


def cycle_final(versions: list[str], cycle: str) -> str | None:
    """The highest release within one cycle, ignoring prereleases.

    Which cycle is the caller's decision, and the number alone cannot make
    it: GNOME's numbering encodes development series that no arithmetic rule
    separates from stable ones. pango is the proof: its releases run

        1.56.4, 1.57.0, 1.57.1, 1.58.0, 1.58.2, 1.90.0

    where 1.57 is a development series under the traditional odd-minor
    convention and 1.90 is the development series toward 2.0. Both sort above
    the stable 1.58.2, and 90 is even, so neither "highest" nor "even minor"
    picks the right answer. An earlier draft of this tool proposed
    1.58.2 -> 1.90.0 for exactly that reason.

    So the cycle comes from GNOME itself: plan() asks gnome-build-meta at
    GNOME's newest stable tag which version that release ships (pango
    1.58.2, gjs 1.90.1) and passes its release_cycle() here. The lock's own
    cycle is used only when gnome-build-meta maps no element to the lock, when
    the lock already sits on GNOME's series, and for --cycle, the manual
    override. Keeping a lock inside its own cycle unconditionally, as this
    tool once did, left gjs on the development release 1.89.2 after 1.90.1
    shipped and gtk4 on 4.23.4 after 4.24.1 (#565).
    """
    inside = [
        v
        for v in versions
        if not is_gnome_prerelease(v) and release_cycle(tarball_version(v)) == cycle
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

    When it does not, the release was read from an explicit feed or a
    fallback mirror, and plan() applies it only if primary_blocker() finds
    nothing in the way of deriving the new primary from the current one.
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


def _forge_list(url: str, opener) -> list:
    """One page of a forge API listing; anything but a JSON list is an error.

    GitHub answers rate limiting and 404 with an object. Treating that as an
    empty listing would silently report every package as up to date.
    """
    with opener(_forge_request(url), timeout=60) as response:
        document = json.loads(response.read())
    if not isinstance(document, list):
        raise ValueError("forge returned no list")
    return document


def _published_releases(document: list) -> list[str]:
    """The stable versions a forge release listing publishes.

    Draft and prerelease-flagged GitHub releases, and GitLab's
    upcoming_release, are dropped here rather than left to is_prerelease: a
    maintainer marking a release prerelease is a stronger signal than the
    version string, and some use neither an alpha nor a beta suffix for one.
    """
    found = []
    for item in document:
        if item.get("draft") or item.get("prerelease") or item.get("upcoming_release"):
            continue
        version = strip_tag_prefix(item.get("tag_name", ""))
        if version:
            found.append(version)
    return found


def forge_versions(feed: dict, opener=urllib.request.urlopen) -> list[str]:
    """Every version a forge publishes for a project, tag prefixes stripped.

    A feed read from an `/archive/` URL names a tag, but a tag is not a
    release: stixfonts tagged `v2.14` on an interim, source-only commit with
    no built fonts while its latest release stayed 2.13b171. So a project that
    publishes releases is read through its releases; only a project that
    publishes none (no stable, non-draft release at all) falls back to its
    tags. That costs one extra request per tag feed, which the authenticated
    GitHub budget absorbs.
    """
    if feed["forge"] == "github":
        base = f"{GITHUB_API}/repos/{feed['owner']}/{feed['repo']}"
        releases_url = f"{base}/releases?per_page=100"
        tags_url = f"{base}/tags?per_page=100"
    else:
        project = urllib.parse.quote(feed["path"], safe="")
        base = f"https://{feed['host']}/api/v4/projects/{project}"
        releases_url = f"{base}/releases?per_page=100"
        tags_url = f"{base}/repository/tags?per_page=100"

    published = _published_releases(_forge_list(releases_url, opener))
    if published or feed.get("endpoint") == "releases":
        return published
    found = []
    for item in _forge_list(tags_url, opener):
        version = strip_tag_prefix(item.get("name", ""))
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


# GNOME's own release definition: gnome-build-meta (BuildStream). A stable
# release is a plain <major>.<minor> tag (51.0, 51.1); development tags carry
# a marker (52.alpha, 52.beta, 52.rc, 49.alpha.1) and branch points a suffix
# (49-branchpoint). download.gnome.org stopped publishing core/<NN>/versions
# after 47, so this is the one place left that says what a release ships.
GBM_PIN = "config/gnome-build-meta.json"
GBM_STABLE_TAG = re.compile(r"\d+\.\d+")


def newest_gbm_tag(tags) -> str | None:
    """GNOME's newest stable release among gnome-build-meta's tag names."""
    stable = [tag for tag in tags if GBM_STABLE_TAG.fullmatch(tag)]
    return max(stable, key=version_key) if stable else None


def _git(*args: str, run=subprocess.run) -> str:
    """stdout of one git command; a failure raises ValueError with git's words."""
    try:
        return run(["git", *args], capture_output=True, text=True, check=True, timeout=600).stdout
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or f"exit {error.returncode}"
        raise ValueError(f"git {args[0]}: {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"git {args[0]}: timed out") from error


def gbm_tags(url: str, run=subprocess.run) -> list[str]:
    """Every tag gnome-build-meta publishes, from one `git ls-remote`."""
    listing = _git("ls-remote", "--tags", "--refs", url, run=run)
    return [line.split("\trefs/tags/", 1)[1] for line in listing.splitlines()
            if "\trefs/tags/" in line]


def checkout_release(tree: Path, run=subprocess.run) -> str:
    """The release an existing gnome-build-meta tree is at.

    A git checkout must sit exactly on a stable tag: one at 52.beta would make
    a development series the target of every GNOME lock. A tree that is not
    a checkout of its own, or not at a tag at all (an exported snapshot, a
    test fixture), is named after its directory and trusted as given.
    """
    if not (tree / ".git").exists():
        return tree.name
    try:
        tag = _git("-C", str(tree), "describe", "--tags", "--exact-match", "HEAD", run=run).strip()
    except (ValueError, OSError):
        return tree.name
    if not GBM_STABLE_TAG.fullmatch(tag):
        raise ValueError(f"{tree} is at {tag}, not a stable GNOME release tag")
    return tag


class GnomeStable:
    """What GNOME's newest stable release ships, read from gnome-build-meta.

    Elements are found the way tools/audit_gnome_build_meta.py finds them:
    config/gnome-build-meta.json's mapping (RPM name -> element, through
    factory_alias), then the element whose own source is on a GNOME host and
    whose stem is the lock's module (_gbm_gnome_modules). Either way the
    element's primary source must belong to that module, and its version is
    read by the audit's _gbm_version.
    """

    def __init__(self, tree: Path, release: str, pin: dict):
        elements = pin["element_path"]["root"]
        if not (tree / elements).is_dir():
            raise ValueError(f"{tree} has no {elements}/: not a gnome-build-meta tree")
        self.release = release
        self.pin = pin
        self.loader = Loader(tree)
        self.aliases = _aliases(self.loader)
        self._stems: dict[str, str] | None = None

    def elements(self, name: str, module: str) -> list[str]:
        """Repository-relative element paths that may describe this lock."""
        root = self.pin["element_path"]["root"]
        alias = self.pin.get("factory_alias") or {}
        found = [f"{root}/{path}" for rpm, path in self.pin["mapping"].items()
                 if alias.get(rpm, rpm) == name]
        if self._stems is None:
            self._stems = _gbm_gnome_modules(self.loader, self.pin, self.aliases)
        if module.lower() in self._stems:
            found.append(self._stems[module.lower()])
        return [path for path in dict.fromkeys(found) if (self.loader.root / path).is_file()]

    def version(self, name: str, module: str) -> str | None:
        """The version of `module` this release ships, or None if it maps none."""
        for path in self.elements(name, module):
            try:
                element = resolve_element(self.loader, self.aliases, path)
            except (OSError, ValueError, AttributeError, TypeError, yaml.YAMLError):
                continue
            primary = element.primary_source
            if not primary or _gbm_module(primary) not in (None, module):
                continue
            version = _gbm_version(primary)
            if version:
                return version
        return None


def load_gnome_stable(root: Path, tree: Path | None, scratch: Path,
                      run=subprocess.run) -> GnomeStable:
    """GNOME's newest stable release, from a given tree or a shallow clone.

    A `tree` that already holds files is used as it is, so tests and a
    workflow that runs the tool twice can supply one. Otherwise the highest
    stable tag is read with one `git ls-remote` and cloned at depth 1 into
    `tree` (kept) or `scratch` (the caller's temporary directory).
    """
    pin = load_pin(root / GBM_PIN)
    if tree is not None and tree.is_dir() and any(tree.iterdir()):
        release = checkout_release(tree, run=run)
    else:
        url = pin["source"]["url"]
        release = newest_gbm_tag(gbm_tags(url, run=run))
        if release is None:
            raise ValueError(f"{url} publishes no stable release tag")
        tree = tree or scratch / "gnome-build-meta"
        _git("-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1",
             "--branch", release, url, str(tree), run=run)
    print(f"GNOME stable release: gnome-build-meta {release} ({tree})")
    return GnomeStable(tree, release, pin)


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


def version_pattern(version: str) -> re.Pattern:
    """A version as a whole number in a URL: not inside a longer one.

    A plain replace("238", "239") also rewrites a hex digest or commit that
    happens to contain 238, and replace("1.0", "1.1") turns 1.0.1 into 1.1.1.
    So the version may not follow a hex digit or a version component, nor run
    on into another component; a letter may follow (firefox-140.13.0esr).
    """
    return re.compile(rf"(?<![0-9A-Fa-f])(?<!\d\.){re.escape(version)}(?!\.?\d)")


def swap_version(value, current: str, release: str):
    """A string, or list of strings, with every whole `current` made `release`."""
    if isinstance(value, list):
        return [swap_version(item, current, release) for item in value]
    return version_pattern(current).sub(lambda _: release, value)


def carries_version(url: str, version: str) -> bool:
    """Whether a URL names `version` where swap_version() can replace it."""
    return version_pattern(version).search(url) is not None


LOOKASIDE_URL = re.compile(
    rf"^{re.escape(LOOKASIDE)}/(?P<package>[^/]+)/(?P<file>[^/]+)/[^/]+/[^/]+/(?P=file)$"
)


def rebuilt_fallback(url: str, current: str, release: str, digest: str) -> str:
    """One fallback URL rewritten for a new release.

    A Fedora lookaside URL is content-addressed: it is rebuilt in the SHA-512
    form planned_entry() writes, from the new file name and the new digest,
    whatever algorithm the old one used (hyphen and libao still carried md5
    ones, whose old hash no substitution can update). It resolves once Fedora
    uploads the same bytes. Any other mirror only has its version swapped.
    """
    match = LOOKASIDE_URL.match(url)
    if match is None:
        return swap_version(url, current, release)
    name = swap_version(match.group("file"), current, release)
    return f"{LOOKASIDE}/{match.group('package')}/{name}/sha512/{digest}/{name}"


def forge_planned_entry(entry: dict, release: str, digest: str) -> dict:
    """An entry with no GNOME template rewritten for a new release.

    GNOME entries are rebuilt from a known template; a forge or project URL
    has no template this tool can own, because projects choose their own tag
    and asset names. So the old version is swapped for the new one in the
    primary url, filename and sha256_url, and every fallback is rebuilt by
    rebuilt_fallback(): a lookaside fallback embeds the filename and the
    digest, which is exactly what a field-by-field rewrite leaves pointing at
    the old tarball.

    Swapping the bare version also fixes a v-prefixed tag in the same pass,
    since "v2.2.1" contains "2.2.1".

    The old version must appear in the URL or this raises rather than writing
    a half-substituted entry: a project whose URL does not carry its version
    cannot be bumped by substitution, and guessing would corrupt the lock.
    """
    current = entry["version"]
    if not carries_version(entry.get("url", ""), current):
        raise ValueError(
            f"{entry['name']}: version {current} does not appear in its url, "
            "so it cannot be bumped by substitution"
        )
    updated = dict(entry)
    for field in ("url", "filename", "sha256_url"):
        if field in entry:
            updated[field] = swap_version(entry[field], current, release)
    if "fallback_urls" in entry:
        updated["fallback_urls"] = [
            rebuilt_fallback(url, current, release, digest) for url in entry["fallback_urls"]
        ]
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


def update_changelog(text: str, version: str) -> str:
    """Prepend a dated entry to an existing manual changelog, keeping history."""
    section = re.search(r"(?m)^%changelog[ \t]*(?:\n|$)", text)
    if section is None or re.search(r"(?m)^[ \t]*%autochangelog\b", text[section.end():]):
        return text
    # Never put live macros in history: a later bump would change old entries.
    # Macro-derived releases cannot be resolved without executing the spec;
    # record the known version alone in that case.
    preamble = text[:section.start()]
    release = re.search(r"(?m)^Release:[ \t]*(\S+)", preamble)
    # rpmlint expects epoch:version-release when the main package sets Epoch:.
    main = re.split(r"(?m)^%(?:package|description)\b", preamble, maxsplit=1)[0]
    epoch = re.search(r"(?m)^Epoch:[ \t]*(\d+)[ \t]*(?:#.*)?$", main)
    evr = f"{epoch.group(1)}:{version}" if epoch else version
    if release:
        literal = release.group(1).replace("%{?dist}", "").replace("%{dist}", "")
        if literal and "%" not in literal:
            evr += f"-{literal}"
    # formatdate is English and UTC regardless of the process locale/timezone.
    weekday, day, month, year, *_ = formatdate().split()
    date = f"{weekday.rstrip(',')} {month} {day} {year}"
    entry = (
        f"* {date} github-actions[bot] "
        f"<41898282+github-actions[bot]@users.noreply.github.com> - {evr}\n"
        f"- Update to {version}\n\n"
    )
    end = section.end()
    separator = "" if text[:end].endswith("\n") else "\n"
    return text[:end] + separator + entry + text[end:]


def rewrite_spec(spec: Path, release: str) -> bool:
    """Update Version:, reset a literal Release:, and record manual history."""
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
    spec.write_text(update_changelog(reset_release(text), wanted))
    return True


# Fedora `sources` manifests use the BSD form (`SHA512 (file) = <hex>`) and,
# in older recipes, the legacy md5sum form (`<32 hex>  file`). Ten carried
# recipes still use the latter.
MANIFEST_LINE = re.compile(
    r"(?:[A-Za-z0-9]+ \((?P<bsd>\S+)\) = [0-9a-fA-F]+|[0-9a-fA-F]{32} [ *](?P<md5>\S+))"
)


def manifest_name(line: str) -> str | None:
    """The file a manifest line pins, or None for a line in neither form."""
    match = MANIFEST_LINE.fullmatch(line.strip())
    return (match.group("bsd") or match.group("md5")) if match else None


def version_bound(filename: str, version: str) -> bool:
    """Whether a file name carries `version` as a whole version string."""
    return re.search(rf"(?<![\w.]){re.escape(version)}(?![\w]|\.\d)", filename) is not None


def bundled_entries(manifest: Path, primary: str) -> list[str]:
    """The manifest lines other than the primary tarball's, in order."""
    if not manifest.is_file():
        return []
    return [
        line for line in manifest.read_text().splitlines()
        if line.strip() and manifest_name(line) != primary
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
        filename = manifest_name(line)
        if filename and any(version_bound(filename, spelling) for spelling in spellings):
            raise ValueError(
                f"{entry['name']}: bundled source {filename} is bound to {entry['version']}; "
                "its successor has to be produced by hand"
            )


def rewrite_sources(manifest: Path, filename: str, digest: str, previous: str = "") -> None:
    """Move the primary tarball pin in a Fedora sources manifest, in place.

    Every other line -- a bundled file fetched from the lookaside by its own
    digest, in either manifest form, or a line this tool cannot parse -- is
    kept verbatim. Writing the new pin alone dropped them, and the build of
    every such package (ppp, adw-gtk3-theme, gum, fish) died in `rpmbuild -bs`
    on a missing source; keeping only BSD-form lines would still have dropped
    the bundled pins of the legacy md5 manifests (#326). MD5 lines themselves
    are no longer accepted on a live tree
    (`tools/validate.py:check_sources_digests`, #385); this keeps them around
    so a hand repin can land in the same commit as a bump, but a tree with
    one still in it fails the validate gate.
    """
    primary = previous or filename
    pin = f"SHA512 ({filename}) = {digest}"
    lines = manifest.read_text().splitlines() if manifest.is_file() else []
    out, placed = [], False
    for line in lines:
        name = manifest_name(line)
        if name in (primary, filename):
            if not placed:
                out.append(pin)
                placed = True
            continue
        out.append(line)
    if not placed:
        out.append(pin)
    manifest.write_text("\n".join(out) + "\n")

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
        # lock's own URLs cannot reveal one: a project download such as
        # archive.mesa3d.org or a SourceForge path, or a lookaside primary
        # with no forge mirror. A same-major release is applied by swapping
        # its version into the primary (primary_blocker); a lookaside primary
        # stays review-only in a full run, because the new bytes are not
        # where the lock points. A human naming the package with --package
        # may relock it instead: a GNOME or forge feed names where the new
        # bytes live. An Anitya feed never does; it lists versions, not
        # downloads, so a lookaside lock with one stays review-only even then.
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


# A suffix that marks a prerelease of the version it follows: 1.0~rc2 and
# 4.25.0rc1 come before 1.0 and 4.25.0.
PRERELEASE_SUFFIX = re.compile(r"^[.~_-]?(alpha|beta|rc|pre|dev)", re.IGNORECASE)
NUMERIC_PREFIX = re.compile(r"^\d+(?:\.\d+)*")


def newer(candidate: str, current: str) -> bool:
    """Whether a feed version is newer than a forge lock's version.

    version_key cannot read a suffixed component and keys 2.13b171 as
    (2, -1), below every 2.x. But stixfonts' 2.13b171 is build 171 after
    its 2.13 release, and usbmuxd's 1.1.1^20251205git... a snapshot after
    1.1.1, so proposing 2.13, 2.12 or 1.1.1 for them would be a downgrade.
    A suffixed lock is therefore compared by its numeric prefix: a
    prerelease suffix (rc, alpha, beta, pre, dev) sits below the prefix, so
    the prefix itself is newer; any other suffix sits above it, so only
    something newer than the prefix is.
    """
    match = NUMERIC_PREFIX.match(current)
    rest = current[match.end():] if match else ""
    if not match or not rest:
        return version_key(candidate) > version_key(current)
    prefix = version_key(match.group())
    if PRERELEASE_SUFFIX.match(rest):
        return version_key(candidate) >= prefix
    return version_key(candidate) > prefix


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
    if newest is None or not newer(newest, current):
        return {"name": name, "module": label, "current": current, "latest": None}

    same_major = [
        v for v in available
        if not is_prerelease(v) and major(v) == major(current)
    ]
    within = newest_stable(same_major)
    if within is not None and newer(within, current):
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


def primary_blocker(name: str, entry: dict, feed: dict, latest: str) -> str | None:
    """Why a release read from a feed other than the primary cannot be applied.

    None when it can: apply() swaps the version in the lock's own primary
    (mesa's archive.mesa3d.org/mesa-26.2.1.tar.xz becomes mesa-26.2.6),
    rebuilds the fallbacks, and pins the SHA-512 of the bytes that URL serves,
    like any other bump. Three primaries cannot be derived from, and each gets
    its own reason so it can be fixed per package:

    - Fedora's lookaside, which carries only what Fedora uploaded. A primary
      is never pointed at Fedora; the lock has to be relocked onto upstream
      first (--package does it for an explicit forge or GNOME feed).
    - A primary that does not carry the locked version as a whole number,
      so there is nothing to swap.
    - A primary filed under a content hash
      (files.pythonhosted.org/packages/38/61/<blake2b>/argcomplete-3.6.3.tar.gz):
      the next release lives under a hash nobody can predict.

    A derived URL the project does not serve is caught when apply() fetches
    it, and main() names that URL when it skips the bump.
    """
    url = entry.get("url", "")
    label = forge_label(feed)
    if is_fedora_url(url):
        if "feed" not in entry:
            return (f"the primary is Fedora's lookaside; point it at the {label} "
                    "mirror by hand before it can move")
        if feed["forge"] == "anitya":
            return ("the primary is Fedora's lookaside and release-monitoring.org "
                    "names no download; give the lock its upstream primary by hand")
        return (f"the primary is Fedora's lookaside; `--package {name}` relocks it "
                f"onto its explicit feed {label}")
    if not carries_version(url, entry["version"]):
        return (f"the primary {url} does not carry the version {entry['version']}, "
                f"so no {latest} download can be derived from it")
    if CONTENT_HASH_SEGMENT.search(urllib.parse.urlparse(url).path):
        return (f"the primary {url} is filed under a content hash, so no {latest} "
                "download can be derived from it; re-pin it by hand")
    return None


# A path segment that is a bare digest (PyPI's /packages/38/61/<blake2b>/).
CONTENT_HASH_SEGMENT = re.compile(r"/[0-9a-f]{32,}/")


def is_app_scheme(version: str) -> bool:
    """Whether a GNOME version uses the app scheme: major 40 and up.

    Its leading number is the GNOME release (nautilus 51.1, ptyxis 50.1) and
    its prereleases carry a marker (52.beta), so every marker-free release is
    a final of some cycle. The library scheme (pango 1.58.2, gjs 1.89.2) keeps
    development series under plain numbers, which is why only gnome-build-meta
    can say which of its series is stable.
    """
    lead = major(tarball_version(version))
    return lead.isdigit() and int(lead) >= 40


def stable_series(stable: GnomeStable, name: str, module: str, current: str) -> str | None:
    """The series GNOME's stable release ships this lock's module in.

    None when gnome-build-meta maps no element to the lock, or the element is
    another API of the module: gbm builds gcr 4.x while the gcr3 lock is 3.41,
    and gtksourceview 5.x while gtksourceview4 is 4.8. A library-scheme
    element on another major is therefore treated as unmapped, which keeps a
    major move (usually a new soname) a human decision.
    """
    shipped = stable.version(name, module)
    if shipped is None:
        return None
    shipped = tarball_version(shipped)
    if is_app_scheme(current):
        if not is_app_scheme(shipped):
            return None
    elif major(shipped) != major(current):
        return None
    return release_cycle(shipped)


def plan(
    root: Path,
    only: str | None,
    opener=urllib.request.urlopen,
    cycle: str | None = None,
    gnome_stable=None,
) -> list[dict]:
    """What would change, without changing anything.

    `gnome_stable` is a callable returning the GnomeStable to follow. It is
    called once, on the first GNOME lock that needs it, so a run that touches
    no GNOME lock never fetches gnome-build-meta. If it raises, the failure is
    reported like an unreachable feed and every GNOME lock falls back to its
    own cycle, where a cross-cycle release is only reported. Without it (or
    with `cycle`), that fallback is the whole rule.

    `cycle` names the release cycle to move within (GNOME 52 work runs with
    --cycle 52 on a next branch); it is the manual override and ignores
    gnome-build-meta. A cycle whose final has not shipped yet proposes
    nothing, so no run can land on an alpha.

    Each proposal carries a `kind`:

      "final"  -- a newer release in the cycle the lock already names, such as
                  51.beta -> 51.0 or 51.0 -> 51.1. Applied.
      "stable" -- the lock's series is older than the one GNOME's newest
                  stable release ships (gjs 1.89.2 while GNOME 51.1 ships
                  1.90.x): the newest final of GNOME's series. Also an
                  app-scheme module gnome-build-meta does not map, moving to
                  its newest final across majors. Applied like "final".
      "review" -- a newer release no rule here may pick: a later cycle of a
                  library-scheme module gnome-build-meta does not map, a new
                  major of one it does, or anything when gnome-build-meta is
                  unavailable. Reported so a human sees it, never applied.
      "note"   -- informational, never applied: the lock is ahead of GNOME's
                  series (it still takes its own point releases as "final"),
                  or a newer series exists that GNOME does not ship
                  (pango 1.90.0, the development line toward 2.0).

    A module whose index cannot be read is reported and skipped rather than
    failing the run: one unreachable module must not stop the other sixteen.
    """
    locks = source_locks(root)
    proposals = []
    loaded: dict = {}

    def stable_release() -> GnomeStable | None:
        if cycle is not None or gnome_stable is None:
            return None
        if "stable" not in loaded:
            loaded["stable"] = None
            try:
                loaded["stable"] = gnome_stable()
            except (OSError, ValueError, KeyError, yaml.YAMLError) as error:
                proposals.append({
                    "name": "gnome-build-meta",
                    "error": f"{error}; GNOME locks keep their own cycle this run",
                })
        return loaded["stable"]

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
                # The release was read from an explicit `feed` (Anitya, a
                # forge) or a fallback mirror, not from the primary. It stays
                # an "update" when the new primary can be derived from the
                # current one; otherwise the reason says what is missing.
                blocker = primary_blocker(name, entry, feed, proposal["latest"])
                if blocker:
                    proposal = {**proposal, "kind": "review", "reason": blocker}
            proposals.append(proposal)
            continue
        module = feed["module"]
        try:
            available = releases(module, opener=opener)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as error:
            proposals.append({"name": name, "error": f"{module}: {error}"})
            continue
        current = tarball_version(entry["version"])
        own = release_cycle(current)
        target = cycle or own

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
        base = {"name": name, "module": module, "current": entry["version"]}
        across = "stable" if kind == "final" else kind

        stable = stable_release()
        series = stable_series(stable, name, module, current) if stable else None
        ahead = series is not None and version_key(series) < version_key(own)
        if ahead:
            # Ahead of GNOME: a human chose this series (--cycle). It still
            # takes its own point releases below, so it is never frozen, but
            # no unattended run moves it to a series GNOME does not ship, or
            # back to GNOME's.
            proposals.append({
                **base, "kind": "note", "latest": None,
                "reason": f"ahead of GNOME {stable.release}, which ships the "
                f"{series} series; only point releases of {own} are taken",
            })
        if series is not None and version_key(series) > version_key(own):
            latest = cycle_final(available, series)
            if latest is not None:
                proposals.append({
                    **base, "kind": across, "latest": latest,
                    "reason": f"GNOME {stable.release} ships the {series} series",
                    **extra,
                })
                continue
        if series is None and stable is not None and is_app_scheme(current):
            # The app scheme marks every prerelease, so its newest marker-free
            # release is a final; without a gnome-build-meta element there is
            # no series to wait for.
            newest = newest_stable(available, prerelease=is_gnome_prerelease)
            if (
                newest is not None
                and version_key(newest) > version_key(current)
                and release_cycle(newest) != own
            ):
                proposals.append({
                    **base, "kind": across, "latest": newest,
                    "reason": "newest final of an app-scheme module "
                    "gnome-build-meta does not map",
                    **extra,
                })
                continue

        within = cycle_final(available, target)
        if (is_prerelease(entry["version"]) and within is not None) or (
            within is not None and version_key(within) > version_key(current)
        ):
            proposals.append({**base, "kind": kind, "latest": within, **extra})
            continue

        newest = newest_stable(available, prerelease=is_gnome_prerelease)
        if not ahead and newest is not None and version_key(newest) > version_key(current):
            if series is not None:
                proposals.append({
                    **base, "kind": "note", "latest": newest,
                    "reason": f"GNOME {stable.release} ships the {series} series",
                })
            else:
                proposals.append({**base, "kind": "review", "latest": newest})
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
        url = swap_version(entry["feed"], entry["version"], release)
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
        # The new URL comes from swapping the version in the old one -- the
        # project's own download, whether its feed is a forge, Anitya or a
        # mirror -- so the digest is fetched from the address the lock will
        # carry, not from a template this tool guessed. A primary on Fedora is
        # never derived: the lookaside carries only what Fedora uploaded.
        if is_fedora_url(entry.get("url", "")):
            raise ValueError(f"{name}: the primary is Fedora's lookaside; relock it first")
        url = swap_version(entry["url"], entry["version"], release)
        try:
            digest = sha512_of(url, opener=opener)
        except (urllib.error.URLError, OSError) as error:
            raise ValueError(f"derived download {url}: {error}") from error
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
    if is_fedora_url(url):
        return
    baseline = root / "config" / "fedora-primary-sources.txt"
    if not baseline.is_file():
        return
    lines = baseline.read_text().splitlines(keepends=True)
    kept = [line for line in lines if line.split("#", 1)[0].strip() != name]
    if kept != lines:
        baseline.write_text("".join(kept))


def is_fedora_url(url: str) -> bool:
    """Whether a URL is served by Fedora (the lookaside, dist-git, Koji)."""
    host = urllib.parse.urlparse(url).hostname or ""
    return host in FEDORA_HOSTS or host.endswith(".fedoraproject.org")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--package", help="consider only this package")
    parser.add_argument(
        "--cycle",
        help="manual override: move within this release cycle instead of the "
        "series GNOME's newest stable release names (GNOME 52 work runs with "
        "--cycle 52 on a next branch; a cycle with no final shipped proposes "
        "nothing). Skips gnome-build-meta.",
    )
    parser.add_argument(
        "--gbm-dir",
        type=Path,
        help="gnome-build-meta tree to read GNOME's stable release from. Used as "
        "is when it holds files; otherwise the newest stable tag is cloned "
        "into it at depth 1 and kept (default: a temporary clone)",
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

    with tempfile.TemporaryDirectory(prefix="gnome-build-meta-") as scratch:
        proposals = plan(
            args.root, args.package, cycle=args.cycle,
            gnome_stable=lambda: load_gnome_stable(args.root, args.gbm_dir, Path(scratch)),
        )
    failures = [p for p in proposals if "error" in p]
    # "final" is the GNOME in-cycle move, "stable" the GNOME move onto the
    # series GNOME's newest stable release ships, "update" the forge
    # same-major one, "relock" a GNOME move that also shifts the primary off
    # the Fedora lookaside. All are safe to write; all are reported alike.
    # A relock only ever arises from an explicit --package run, never from a
    # full scan, so no unattended run moves a primary on its own.
    finals = [p for p in proposals if p.get("kind") in ("final", "stable", "update", "relock")]
    review = [p for p in proposals if p.get("kind") == "review"]
    notes = [p for p in proposals if p.get("kind") == "note"]

    # A bump pins whatever bytes the forge serves, and the gate merges it with
    # no one looking. Packages the review-only list names -- root daemons, the
    # boot chain, firmware -- are reported like a cross-cycle candidate and
    # bumped by hand instead; the gate refuses them too, should one get in.
    # A relock is exempt: it comes only from an explicit --package run and
    # lands on its own branch, which the gate never merges.
    review_only = load_review_only(args.root)
    for bump in [p for p in finals if p["name"] in review_only and p["kind"] != "relock"]:
        finals.remove(bump)
        review.append({**bump, "kind": "review",
                       "reason": f"listed in {REVIEW_ONLY}; bump it in a reviewed pull request"})

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
        why = f" ({bump['reason']})" if bump["kind"] == "stable" and bump.get("reason") else ""
        print(f"{bump['name']}: {bump['current']} -> {bump['latest']}{why}")
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
        # of a module gnome-build-meta does not map may be a development
        # series, which no rule here can tell from a stable one.
        detail = item.get("reason", "crosses a release cycle or a major")
        print(
            f"needs review  {item['name']}: {item['current']} -> {item['latest']} "
            f"({detail})",
            file=sys.stderr,
        )

    for item in notes:
        newer = f" -> {item['latest']}" if item.get("latest") else ""
        print(f"note  {item['name']}: {item['current']}{newer} ({item['reason']})",
              file=sys.stderr)

    if retired:
        (args.root / HOLDS).write_text(dump_holds(holds))

    if not finals:
        print("no lock is behind the newest release it may move to")
    elif args.apply and not applied:
        print("every proposed bump failed to apply", file=sys.stderr)
        return 1
    # A relock moves the primary URL: a `workflow_dispatch --package` that
    # proposes one must write to a branch the next daily create-pull-request
    # run cannot overwrite, otherwise the relock commit silently disappears
    # when the scheduled run force-updates it from a plan based on the old
    # lookaside lock. The workflow reads this flag and routes the PR to
    # bump/upstream-sources-relock-<pkg> when it is true.
    relock = any(p.get("kind") == "relock" for p in finals)
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
            handle.write(f"relock={'true' if relock else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
