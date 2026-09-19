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
  packages/<pkg>/<pkg>.spec     Version:
  packages/<pkg>/sources        SHA512 (<tarball>) = <digest>

A version bump with a stale checksum is rejected by source_pipeline.py -- a
safe failure, but not a working bump. So the checksum has to be computed from
the bytes at bump time, which is what this does.

Scope
-----
Only entries whose Source0 is download.gnome.org. That is 17 of 341; the other
254 resolve through Fedora's lookaside, whose natural feed is dist-git, and
detect-rawhide-updates.yml deliberately only observes there on the stated
policy that "Fedora is a compatibility build root, not a source-update feed."
Widening this tool to those is a separate decision, not an omission.

GNOME publishes an authoritative release index per module at
sources/<module>/cache.json, so the candidate list needs no scraping.

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
    """The directory GNOME files a release under: the leading component."""
    return version.split(".")[0]


def release_cycle(version: str) -> str:
    """The development cycle a release belongs to.

    GNOME uses two numbering schemes and the cycle sits in a different place in
    each, so this cannot be "the first component":

      gnome-shell 51.beta, 51.0     cycle 51    -- the app scheme, where the
                                                   leading number is the GNOME
                                                   release
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
    # A three-component release keeps major.minor; a two-component one is the
    # app scheme, where the trailing number is the point release within a cycle.
    return ".".join(numeric[:-1]) if len(numeric) >= 3 else numeric[0]


def forge_feed(entry: dict) -> dict | None:
    """The git-forge release feed a locked entry tracks, if it tracks one.

    Returns a descriptor rather than a tuple because the three shapes differ in
    what they need: GitHub releases are read from a different endpoint than
    GitHub tags, and GitLab is a different host entirely.
    """
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


def forge_label(feed: dict) -> str:
    """A short human name for a feed, for reports."""
    if feed["forge"] == "github":
        return f"github.com/{feed['owner']}/{feed['repo']}"
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


def planned_entry(entry: dict, release: str, digest: str) -> dict:
    """The locked entry rewritten for a new release.

    Every URL is rebuilt from the release string rather than patched, so a
    field cannot be left behind pointing at the old tarball -- fallback_urls in
    particular embeds both the filename and the digest.
    """
    module = gnome_module(entry)
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
    """(name, entry, feed) for every lock this tool can track, sorted by name.

    A feed is either {"forge": "gnome", "module": ...} or a git-forge
    descriptor from forge_feed. A lock on neither -- the Fedora lookaside, a
    bare directory listing -- has no release feed to poll and is skipped; see
    the module docstring.
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
    """
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


def plan(root: Path, only: str | None, opener=urllib.request.urlopen) -> list[dict]:
    """What would change, without changing anything.

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

    module = gnome_module(entry)
    if module:
        tarball = tarball_version(release)
        url = f"{GNOME_SOURCES}{module}/{major(tarball)}/{module}-{tarball}.tar.xz"
        digest = sha512_of(url, opener=opener)
        updated = planned_entry(entry, release, digest)
    else:
        # The new URL comes from substituting into the old one, so the digest
        # is fetched from the same address the lock will carry -- not from a
        # template this tool guessed.
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--package", help="consider only this package")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite the inventory, spec and sources manifest (default: report only)",
    )
    args = parser.parse_args()

    proposals = plan(args.root, args.package)
    failures = [p for p in proposals if "error" in p]
    # "final" is the GNOME in-cycle move, "update" the forge same-major one.
    # Both are safe to write; both are reported the same way.
    finals = [p for p in proposals if p.get("kind") in ("final", "update")]
    review = [p for p in proposals if p.get("kind") == "review"]

    for failure in failures:
        print(f"skipped {failure['name']}: {failure['error']}", file=sys.stderr)

    for bump in finals:
        print(f"{bump['name']}: {bump['current']} -> {bump['latest']}")
        if args.apply:
            apply(args.root, bump)

    for item in review:
        # Deliberately not applied, and deliberately not silent: a later cycle
        # may be a development series (pango 1.90 toward 2.0), which no rule
        # here can tell from a stable one.
        print(
            f"needs review  {item['name']}: {item['current']} -> {item['latest']} "
            f"(crosses a release cycle or a major)",
            file=sys.stderr,
        )

    if not finals:
        print("no in-cycle release is newer than what the inventory locks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
