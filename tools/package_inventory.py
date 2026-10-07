#!/usr/bin/env python3
"""Repository-wide package inventory: the single enforceable contract.

Every factory task consumes :func:`inventory` instead of rescanning
``packages/``, ``config/upstream-sources.json``, or ``.packit.yaml`` on its
own. Consumers that need lock-entry fields (``sha512``, ``filename``,
``dist_bump``, ``dist_git_name``, ...) take them from :func:`source_locks`,
which shares the same validation -- the lock file is parsed exactly once,
here. The inventory refuses ambiguous state outright: duplicate spec
directories, duplicate source locks, unknown stages, or multiple specs per
package are contract violations, not warnings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tools.packit_workflow import package_names

# Stages the rebuild matrix (.github/workflows/rebuild-rpms.yml) can resolve;
# packages without an explicit stage build in stage 0.
# Eleven waves, not five. The rebuild is a chain of dependency waves and a
# package can only see what an earlier wave built, so every soname this factory
# moves needs its consumers in a later wave than the library. Five was not
# enough to express that: openjph, libheif, glycin, gdk-pixbuf2 and then
# everything reaching gdk-pixbuf2 is already five, before webkitgtk, gjs,
# evolution-data-server, flatpak or gnome-shell have anywhere to go. The lane
# boundaries are the ones config/build-lanes.toml works out on
# fix/repeatable-local-builds, flattened into consecutive numbers.
KNOWN_STAGES = frozenset(range(11))

# Per-package overrides of the run's build lane (build-stage.yml backend).
BUILD_LANES = frozenset({"container"})

# The git forges a lock's explicit `feed` may name. Both expose an ordered tag
# list, which is the only feed a bump needs; releases are preferred over tags
# where a project publishes them, because a tag is not a release.
FORGE_ARCHIVE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/archive/"
)
FORGE_RELEASE = re.compile(
    r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/releases/download/"
)
# http:// appears in one lock (evtest) and a scheme is not worth missing a
# feed over. Both GitLab shapes resolve to the same tag list: /-/archive/<tag>
# and /-/releases/<tag>/downloads/<asset> name the tag in the same position.
GITLAB_ARCHIVE = re.compile(
    r"^https?://(?P<host>[^/]*gitlab[^/]*)/(?P<path>.+?)/-/(?:archive|releases)/"
)


# An explicit `feed` may also name a feed that no locked URL could: a GNOME
# module's release index (a lookaside lock whose Source0 is download.gnome.org,
# including modules whose name differs from the package -- gtk3 is "gtk"), or
# a release-monitoring.org (Anitya) project, for the projects that publish only
# a directory listing (x.org, freedesktop.org, kernel.org, SourceForge). The
# Anitya project is the one Fedora's own package mapping names, so it is the
# same release feed Fedora's update tracking already trusts.
GNOME_FEED = re.compile(r"^https://download\.gnome\.org/sources/(?P<module>[^/]+)/")
ANITYA_FEED = re.compile(r"^https://release-monitoring\.org/project/(?P<id>\d+)/?$")


def parse_explicit_feed(url: str) -> dict | None:
    """The feed descriptor an explicit lock `feed` names, if it names one.

    Wider than parse_feed_url on purpose: that one also reads a lock's own
    primary and fallback URLs, where a GNOME or Anitya address must never be
    mistaken for a forge mirror.
    """
    feed = parse_feed_url(url)
    if feed:
        return feed
    match = GNOME_FEED.match(url)
    if match:
        return {"forge": "gnome", **match.groupdict()}
    match = ANITYA_FEED.match(url)
    if match:
        return {"forge": "anitya", **match.groupdict()}
    return None


def parse_feed_url(url: str) -> dict | None:
    """The git-forge feed descriptor a URL names, if it names one."""
    match = FORGE_RELEASE.match(url)
    if match:
        return {"forge": "github", "endpoint": "releases", **match.groupdict()}
    match = FORGE_ARCHIVE.match(url)
    if match:
        return {"forge": "github", "endpoint": "tags", **match.groupdict()}
    match = GITLAB_ARCHIVE.match(url)
    if match:
        return {"forge": "gitlab", "endpoint": "tags", **match.groupdict()}
    return None


@dataclass(frozen=True)
class PackageRecord:
    name: str
    spec: Path
    stage: int
    source_locked: bool
    packit_configured: bool
    provenance: Path | None = None
    provenance_branch: str | None = None


def _recipe_provenance(root: Path) -> dict[str, tuple[Path, str]]:
    """Map each recipe to its provenance file and the form that file claims.

    A recipe with no readable `.hummingbird-upstream.json`, or one naming no
    branch, is absent here rather than present-and-empty: the caller reports
    it as missing provenance, which is what it is.
    """
    provenance = {}
    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        return provenance
    for directory in sorted(packages_dir.iterdir()):
        if not directory.is_dir():
            continue
        path = directory / ".hummingbird-upstream.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
            branch = data.get("branch")
            if isinstance(branch, str):
                provenance[directory.name] = (path, branch)
        except (OSError, json.JSONDecodeError):
            continue
    return provenance


def _spec_per_package(root: Path) -> dict[str, Path]:
    specs = {}
    for directory in sorted((root / "packages").iterdir()):
        if not directory.is_dir():
            continue
        found = sorted(directory.glob("*.spec"))
        if len(found) != 1:
            raise ValueError(f"expected exactly one spec in {directory}")
        if directory.name in specs:
            raise ValueError(f"duplicate spec directory: {directory.name}")
        specs[directory.name] = found[0]
    return specs


def load_source_locks(config: Path) -> dict[str, dict]:
    """Validated source-lock entries keyed by package name.

    The only parse of ``upstream-sources.json`` in the factory: a duplicated
    package name or an unknown stage is a contract violation for every reader,
    not only for :func:`inventory`.
    """
    data = json.loads(config.read_text())
    locks = {}
    for entry in data["packages"]:
        name = entry["name"]
        if name in locks:
            raise ValueError(f"duplicate source lock: {name}")
        stage = entry.get("stage", 0)
        if not isinstance(stage, int) or stage not in KNOWN_STAGES:
            raise ValueError(f"unknown stage for {name}: {stage!r}")
        # The hermetic mock lane is the default. A package may stay on the
        # hand-built container root only with a stated reason, so each
        # exception names the gap that keeps it there.
        lane = entry.get("build_lane")
        if lane is not None:
            if lane not in BUILD_LANES:
                raise ValueError(f"unknown build_lane for {name}: {lane!r}")
            reason = entry.get("build_lane_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"{name}: build_lane needs a build_lane_reason")
        # An explicit release feed must name a feed this factory can poll;
        # anything else is a silent hole in the bump coverage, not a feed.
        feed = entry.get("feed")
        if feed is not None and parse_explicit_feed(feed) is None:
            raise ValueError(f"unparseable feed for {name}: {feed!r}")
        locks[name] = entry
    return locks


def source_locks(root: Path) -> dict[str, dict]:
    """The validated source locks for the repository at ``root``."""
    return load_source_locks(root / "config" / "upstream-sources.json")


def inventory(root: Path) -> list[PackageRecord]:
    specs = _spec_per_package(root)
    locks = source_locks(root)
    packit = set(package_names(root / ".packit.yaml"))
    provenance = _recipe_provenance(root)
    records = []
    for name, spec in specs.items():
        path, branch = provenance.get(name, (None, None))
        records.append(
            PackageRecord(
                name=name,
                spec=spec,
                stage=locks[name].get("stage", 0) if name in locks else 0,
                source_locked=name in locks,
                packit_configured=name in packit,
                provenance=path,
                provenance_branch=branch,
            )
        )
    return records
