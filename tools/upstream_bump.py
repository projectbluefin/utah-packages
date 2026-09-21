#!/usr/bin/env python3
"""Propose version bumps for the packages this factory locks to upstream releases.

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
                                fallback_urls, feed
  packages/<pkg>/<pkg>.spec     Version:
  packages/<pkg>/sources        SHA512 (<tarball>) = <digest>

A version bump with a stale checksum is rejected by source_pipeline.py -- a
safe failure, but not a working bump. So the checksum has to be computed from
the bytes at bump time, which is what this does.

Scope and Feed Resolution
-------------------------
The factory tracks upstream releases across:
  - download.gnome.org (GNOME modules via cache.json index)
  - GitHub repositories (tags and releases endpoints)
  - GitLab instances (repository tags API)
  - Anitya / release-monitoring.org (project versions API)
  - Explicitly pinned packages (documented subset without release feed)

For packages whose primary URL cannot reveal a release feed (such as Fedora
lookaside URLs or bare tarball directory listings), an explicit `feed` field in
`config/upstream-sources.json` identifies the upstream feed or marks the package
as part of the documented pinned subset.

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

from tools.package_inventory import source_locks

GNOME_SOURCES = "https://download.gnome.org/sources/"

# The git forges this factory locks sources on. Both expose an ordered tag
# list, which is the only feed a bump needs; releases are preferred over tags
# where a project publishes them, because a tag is not a release.
GITHUB_API = "https://api.github.com"
ANITYA_API = "https://release-monitoring.org/api/v2"

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
LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms"

# alpha/beta/rc in any spelling GNOME uses: 51.beta, 51~rc, 1.10.beta.1.
# The trailing context is a lookahead, not part of the match: consuming it made
# rpm_version("1.10.beta.1") return "1.10~beta1", eating the separator before
# the point release. Caught by the round-trip test.
PRERELEASE = re.compile(r"(?:^|[.~-])(alpha|beta|rc)(?=[.~-]|\d|$)", re.IGNORECASE)
# The same marker with its leading separator, for rewriting that separator to
# the tilde RPM needs.
PRERELEASE_SEPARATOR = re.compile(r"[.~-](alpha|beta|rc)(?=[.~-]|\d|$)", re.IGNORECASE)


def is_prerelease(version: str) -> bool:
    """True for a prerelease such as 51.beta, 51~rc, 1.10.beta.1, or 2.3.0-rc1."""
    return bool(PRERELEASE.search(version))


def version_key(version: str) -> tuple[int, ...]:
    """Sort key for a stable version.

    Only meaningful for stable versions, which are numeric and dot-separated;
    callers filter prereleases out first. A non-numeric component sorts as -1
    rather than raising, so one malformed entry cannot take the whole run down.
    """
    return tuple(int(part) if part.isdigit() else -1 for part in version.split("."))


def newest_stable(versions: list[str]) -> str | None:
    """The highest non-prerelease in a version list, or None."""
    stable = [v for v in versions if not is_prerelease(v)]
    return max(stable, key=version_key) if stable else None


def cycle_final(versions: list[str], cycle: str) -> str | None:
    """The highest release within one cycle, ignoring prereleases.

    A bump is only ever proposed for application automatically when it stays
    inside the cycle the lock already names -- 51.beta to 51.0. Crossing a
    cycle cannot be decided from the number alone, because GNOME's numbering
    encodes development series that no arithmetic rule separates from stable
    ones.
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
    """The directory GNOME files a release under: the leading component."""
    return version.split(".")[0]


def release_cycle(version: str) -> str:
    """The development cycle a release belongs to."""
    parts = version.split(".")
    numeric = []
    for part in parts:
        if not part.isdigit():
            break
        numeric.append(part)
    if not numeric:
        return version
    if is_prerelease(version):
        return ".".join(numeric)
    return ".".join(numeric[:-1]) if len(numeric) >= 3 else numeric[0]


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


def forge_feed(entry: dict) -> dict | None:
    """The git-forge release feed a locked entry tracks, if it tracks one."""
    url = entry.get("url", "")
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


def is_url_pollable(url: str) -> bool:
    """True if the given URL matches a known direct release feed."""
    if url.startswith(GNOME_SOURCES):
        return True
    if FORGE_ARCHIVE.match(url) or FORGE_RELEASE.match(url) or GITLAB_ARCHIVE.match(url):
        return True
    return False


def parse_feed(feed: str | dict | None) -> dict | None:
    """Normalize a feed declaration into a feed descriptor.

    Supports:
      - GitHub URL ("https://github.com/owner/repo" or "/releases")
      - GitLab URL ("https://gitlab.freedesktop.org/group/repo")
      - GNOME URL or prefix ("https://download.gnome.org/sources/module" or "gnome:module")
      - Anitya prefix or URL ("anitya:14498" or "https://release-monitoring.org/project/14498")
      - Pinned marker ("pinned", "none", or "pinned: reason")
      - Dict descriptors: {"forge": "github", ...}, {"type": "anitya", ...}, etc.
    """
    if not feed:
        return None

    if isinstance(feed, dict):
        if feed.get("pinned") or feed.get("type") in ("pinned", "none"):
            return {"type": "pinned", "reason": feed.get("reason", "pinned")}
        if feed.get("type") == "anitya" or "project_id" in feed:
            pid = int(feed.get("project_id", feed.get("anitya", 0)))
            return {"type": "anitya", "project_id": pid}
        if feed.get("type") == "gnome" or "module" in feed:
            return {"type": "gnome", "forge": "gnome", "module": feed["module"]}
        if feed.get("forge") or feed.get("type") in ("github", "gitlab"):
            forge = feed.get("forge") or feed.get("type")
            return {
                "type": "forge",
                "forge": forge,
                "endpoint": feed.get("endpoint", "tags"),
                **{k: v for k, v in feed.items() if k not in ("type", "forge", "endpoint")},
            }
        return feed

    if isinstance(feed, str):
        val = feed.strip()
        if val in ("pinned", "none") or val.startswith("pinned:") or val.startswith("none:"):
            reason = val.split(":", 1)[1].strip() if ":" in val else "pinned"
            return {"type": "pinned", "reason": reason}
        if val.startswith("anitya:"):
            return {"type": "anitya", "project_id": int(val.split(":", 1)[1])}
        if "release-monitoring.org/project/" in val:
            match = re.search(r"project/(\d+)", val)
            if match:
                return {"type": "anitya", "project_id": int(match.group(1))}
        if val.startswith("gnome:"):
            return {"type": "gnome", "forge": "gnome", "module": val.split(":", 1)[1].strip()}
        if "download.gnome.org/sources/" in val:
            module = val.split("download.gnome.org/sources/")[1].strip("/").split("/")[0]
            return {"type": "gnome", "forge": "gnome", "module": module}
        if "github.com" in val:
            match = re.search(r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)", val)
            if match:
                owner = match.group("owner")
                repo = match.group("repo").rstrip("/").removesuffix(".git")
                endpoint = "releases" if "/releases" in val else "tags"
                return {
                    "type": "forge",
                    "forge": "github",
                    "owner": owner,
                    "repo": repo,
                    "endpoint": endpoint,
                }
        if "gitlab" in val or "salsa.debian.org" in val:
            match = re.search(r"https?://(?P<host>[^/]+)/(?P<path>.+)", val)
            if match:
                host = match.group("host")
                path = match.group("path").rstrip("/").removesuffix(".git").split("/-/")[0]
                return {
                    "type": "forge",
                    "forge": "gitlab",
                    "host": host,
                    "path": path,
                    "endpoint": "tags",
                }

    return None


def resolve_feed(entry: dict) -> dict | None:
    """The release feed descriptor a locked entry tracks, if it tracks one.

    Explicit `feed` entries in config/upstream-sources.json take precedence over
    URL-derived feeds.
    """
    if "feed" in entry:
        parsed = parse_feed(entry["feed"])
        if parsed:
            return parsed

    module = gnome_module(entry)
    if module:
        return {"type": "gnome", "forge": "gnome", "module": module}

    forge = forge_feed(entry)
    if forge:
        return {"type": "forge", **forge}

    return None


def forge_label(feed: dict) -> str:
    """A short human name for a feed, for reports."""
    feed_type = feed.get("type")
    if feed_type == "gnome" or feed.get("forge") == "gnome":
        return f"gnome:{feed.get('module')}"
    if feed_type == "anitya":
        return f"anitya:{feed.get('project_id')}"
    if feed_type == "pinned":
        return f"pinned ({feed.get('reason', 'manual')})"
    if feed.get("forge") == "github":
        return f"github.com/{feed['owner']}/{feed['repo']}"
    if feed.get("forge") == "gitlab":
        return f"{feed['host']}/{feed['path']}"
    return "unknown"


def _forge_request(url: str) -> urllib.request.Request:
    """A forge API request, authenticated when a token is in the environment."""
    headers = {
        "User-Agent": "utah-packages-bump/1",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith(GITHUB_API):
        headers["Authorization"] = f"token {token}"
    return urllib.request.Request(url, headers=headers)


def forge_versions(feed: dict, opener=urllib.request.urlopen, max_pages: int = 5) -> list[str]:
    """Every version a forge lists for a project, tag prefixes stripped."""
    found = []
    page = 1
    while page <= max_pages:
        page_param = f"&page={page}" if page > 1 else ""
        if feed["forge"] == "github":
            url = (
                f"{GITHUB_API}/repos/{feed['owner']}/{feed['repo']}"
                f"/{feed['endpoint']}?per_page=100{page_param}"
            )
        else:
            project = urllib.parse.quote(feed["path"], safe="")
            url = (
                f"https://{feed['host']}/api/v4/projects/{project}"
                f"/repository/tags?per_page=100{page_param}"
            )
        try:
            with opener(_forge_request(url), timeout=60) as response:
                document = json.loads(response.read())
        except Exception:
            if page == 1:
                raise
            break
        if not isinstance(document, list):
            if page == 1:
                raise ValueError("forge returned no list")
            break
        if not document:
            break
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
        if len(document) < 100:
            break
        page += 1
    return found


def anitya_versions(feed: dict, opener=urllib.request.urlopen) -> list[str]:
    """Every version listed for an Anitya (release-monitoring.org) project."""
    project_id = feed["project_id"]
    url = f"{ANITYA_API}/versions/?project_id={project_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "utah-packages-bump/1"})
    with opener(req, timeout=60) as response:
        document = json.loads(response.read())
    if not isinstance(document, dict) or "versions" not in document:
        raise ValueError("Anitya returned no versions list")
    found = []
    for item in document.get("versions", []):
        ver = strip_tag_prefix(str(item))
        if ver:
            found.append(ver)
    return found


def releases(module: str, opener=urllib.request.urlopen) -> list[str]:
    """Every release GNOME lists for a module, from its cache.json index."""
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


def substituted(value, replacements: list[tuple[str, str]]):
    """A string, or list of strings, with every replacement applied in turn."""
    if isinstance(value, list):
        return [substituted(item, replacements) for item in value]
    for old, new in replacements:
        value = value.replace(old, new)
    return value


def planned_entry(entry: dict, release: str, digest: str) -> dict:
    """The GNOME-locked entry rewritten for a new release."""
    module = gnome_module(entry) or entry.get("name")
    tarball = tarball_version(release)
    name = f"{module}-{tarball}.tar.xz"
    base = f"{GNOME_SOURCES}{module}/{major(tarball)}"
    updated = dict(entry)
    updated["version"] = tarball
    updated["url"] = f"{base}/{name}"
    updated["filename"] = name
    updated["sha512"] = digest
    if "sha256_url" in entry:
        updated["sha256_url"] = f"{base}/{module}-{tarball}.sha256sum"
    if entry.get("fallback_urls"):
        updated["fallback_urls"] = [
            f"{LOOKASIDE}/{module}/{name}/sha512/{digest}/{name}"
        ]
    return updated


def forge_planned_entry(entry: dict, release: str, digest: str) -> dict:
    """A forge-hosted entry rewritten for a new release."""
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


def rewrite_spec(spec: Path, release: str) -> bool:
    """Point a spec's Version: at a new release. True when it changed."""
    text = spec.read_text()
    wanted = rpm_version(release)
    pattern = re.compile(r"(?m)^(Version:\s*)(\S+)$")
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"{spec}: no Version: line to bump")
    if match.group(2) == wanted:
        return False
    spec.write_text(pattern.sub(lambda m: m.group(1) + wanted, text, count=1))
    return True


def rewrite_sources(manifest: Path, filename: str, digest: str) -> None:
    """Replace a package's Fedora sources manifest with the new tarball pin."""
    manifest.write_text(f"SHA512 ({filename}) = {digest}\n")


def candidates(locks: dict[str, dict], only: str | None = None) -> list[tuple[str, dict, dict]]:
    """(name, entry, feed) for every pollable lock, sorted by name.

    Locks without an identifiable release feed or marked as pinned are skipped.
    """
    found = []
    for name, entry in sorted(locks.items()):
        if only and name != only:
            continue
        feed = resolve_feed(entry)
        if not feed or feed.get("type") == "pinned":
            continue
        found.append((name, entry, feed))
    return found


def forge_proposal(name: str, entry: dict, feed: dict, opener=urllib.request.urlopen) -> dict:
    """What a single git-forge lock should move to, if anything."""
    label = forge_label(feed)
    try:
        available = forge_versions(feed, opener=opener)
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


def anitya_proposal(name: str, entry: dict, feed: dict, opener=urllib.request.urlopen) -> dict:
    """What a single Anitya-tracked lock should move to, if anything."""
    label = forge_label(feed)
    try:
        available = anitya_versions(feed, opener=opener)
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


def plan(root: Path, only: str | None, opener=urllib.request.urlopen) -> list[dict]:
    """What would change, without changing anything."""
    locks = source_locks(root)
    proposals = []
    for name, entry, feed in candidates(locks, only):
        if feed.get("type") == "anitya":
            proposals.append(anitya_proposal(name, entry, feed, opener=opener))
            continue
        if feed.get("type") == "forge":
            proposals.append(forge_proposal(name, entry, feed, opener=opener))
            continue

        module = feed["module"]
        try:
            available = releases(module, opener=opener)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as error:
            proposals.append({"name": name, "error": f"{module}: {error}"})
            continue
        current = tarball_version(entry["version"])
        cycle = release_cycle(current)

        within = cycle_final(available, cycle)
        if is_prerelease(entry["version"]) and within is not None:
            proposals.append(
                {
                    "kind": "final",
                    "name": name,
                    "module": module,
                    "current": entry["version"],
                    "latest": within,
                }
            )
            continue
        if within is not None and version_key(within) > version_key(current):
            proposals.append(
                {
                    "kind": "final",
                    "name": name,
                    "module": module,
                    "current": entry["version"],
                    "latest": within,
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
    feed = resolve_feed(entry)

    module = gnome_module(entry) or (feed.get("module") if feed and feed.get("type") == "gnome" else None)
    if module and (entry.get("url", "").startswith(GNOME_SOURCES) or (feed and feed.get("type") == "gnome")):
        tarball = tarball_version(release)
        url = f"{GNOME_SOURCES}{module}/{major(tarball)}/{module}-{tarball}.tar.xz"
        digest = sha512_of(url, opener=opener)
        updated = planned_entry(entry, release, digest)
    else:
        if LOOKASIDE in entry.get("url", ""):
            raise ValueError(
                f"{entry['name']}: locked to Fedora lookaside; cannot apply bump "
                "automatically until re-pinned to upstream URL"
            )
        url = substituted(entry["url"], [(entry["version"], release)])
        digest = sha512_of(url, opener=opener)
        updated = forge_planned_entry(entry, release, digest)

    document["packages"][index] = updated
    config.write_text(json.dumps(document, indent=2) + "\n")

    package = root / "packages" / name
    spec = package / f"{name}.spec"
    if spec.is_file():
        rewrite_spec(spec, release)
    manifest = package / "sources"
    if manifest.is_file():
        rewrite_sources(manifest, updated["filename"], digest)
    return updated


def audit_inventory(locks: dict[str, dict]) -> dict:
    """Categorize every lock in the inventory by release feed pollability."""
    url_count = 0
    feed_count = 0
    pinned_count = 0
    gap_count = 0

    feed_breakdown: dict[str, int] = {}
    pinned_breakdown: dict[str, int] = {}

    for name, entry in sorted(locks.items()):
        feed = resolve_feed(entry)
        if "feed" in entry:
            if feed and feed.get("type") == "pinned":
                pinned_count += 1
                reason = feed.get("reason", "pinned")
                pinned_breakdown[reason] = pinned_breakdown.get(reason, 0) + 1
            elif feed:
                feed_count += 1
                ftype = feed.get("forge") or feed.get("type", "other")
                feed_breakdown[ftype] = feed_breakdown.get(ftype, 0) + 1
            else:
                gap_count += 1
        elif feed:
            if feed.get("type") == "pinned":
                pinned_count += 1
            else:
                url_count += 1
        else:
            gap_count += 1

    return {
        "total": len(locks),
        "pollable_url": url_count,
        "pollable_feed": feed_count,
        "pinned": pinned_count,
        "gap": gap_count,
        "feed_breakdown": feed_breakdown,
        "pinned_breakdown": pinned_breakdown,
    }


def print_audit(audit_data: dict) -> None:
    """Print a structured audit table of inventory release feeds."""
    total = audit_data["total"]
    pollable = audit_data["pollable_url"] + audit_data["pollable_feed"]
    print(f"Inventory source lock feed audit ({total} total locks):")
    print(
        f"  Pollable directly by URL:        {audit_data['pollable_url']:3d} "
        f"({audit_data['pollable_url'] * 100 / total:5.1f}%)"
    )
    print(
        f"  Pollable by explicit feed:       {audit_data['pollable_feed']:3d} "
        f"({audit_data['pollable_feed'] * 100 / total:5.1f}%)"
    )
    for ftype, count in sorted(audit_data["feed_breakdown"].items()):
        print(f"    - {ftype:29s}: {count:3d}")
    print(
        f"  Total pollable inventory:        {pollable:3d} "
        f"({pollable * 100 / total:5.1f}%)"
    )
    print(
        f"  Documented pinned subset:        {audit_data['pinned']:3d} "
        f"({audit_data['pinned'] * 100 / total:5.1f}%)"
    )
    for reason, count in sorted(audit_data["pinned_breakdown"].items()):
        print(f"    - {reason:29s}: {count:3d}")
    print(
        f"  Unclassified lookaside gap:      {audit_data['gap']:3d} "
        f"({audit_data['gap'] * 100 / total:5.1f}%)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--package", help="consider only this package")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite the inventory, spec and sources manifest (default: report only)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="print feed classification audit across the entire inventory",
    )
    args = parser.parse_args()

    if args.audit:
        locks = source_locks(args.root)
        report = audit_inventory(locks)
        print_audit(report)
        return 0

    proposals = plan(args.root, args.package)
    failures = [p for p in proposals if "error" in p]
    finals = [p for p in proposals if p.get("kind") in ("final", "update")]
    review = [p for p in proposals if p.get("kind") == "review"]

    for failure in failures:
        print(f"skipped {failure['name']}: {failure['error']}", file=sys.stderr)

    for bump in finals:
        print(f"{bump['name']}: {bump['current']} -> {bump['latest']}")
        if args.apply:
            try:
                apply(args.root, bump)
            except ValueError as err:
                print(f"skipped apply for {bump['name']}: {err}", file=sys.stderr)

    for item in review:
        print(
            f"needs review  {item['name']}: {item['current']} -> {item['latest']} "
            f"(crosses a release cycle or a major)",
            file=sys.stderr,
        )

    if not finals:
        print("no in-cycle or same-major release is newer than what the inventory locks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
