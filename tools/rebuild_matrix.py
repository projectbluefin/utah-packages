#!/usr/bin/env python3
"""Emit the rebuild matrix for .github/workflows/rebuild-rpms.yml.

The thin, untestable half of the decision: read the environment the workflow
provides, fetch the published repository, and write GITHUB_OUTPUT. Every rule
about what to build lives in tools/rebuild_plan.py, where it is under test.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.rebuild_plan import (
    changed_entries,
    dependents_from_primary,
    format_build_plan,
    is_global_change,
    is_published,
    merge_dependents,
    overflow,
    plan,
    provides_from_primary,
    published_from_primary,
    spec_dependents,
    stage_outputs,
    stale_from_primary,
)

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_REPO_TIMEOUT = 120
INVENTORY = "config/upstream-sources.json"


def git_diff_paths(base_sha: str) -> list[str]:
    """Changed file paths between base_sha and HEAD."""
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha or "") or set(base_sha) == {"0"}:
        return []
    try:
        return subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_sha}..HEAD"], text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        return []


def changed_recipes(base_sha: str, paths: list[str] | None = None) -> set[str]:
    """Recipes touched since the base commit.

    Empty when there is no range to read -- a scheduled run has no `before` and
    no pull request base -- which is why the published comparison must stand on
    its own rather than leaning on this.
    """
    if paths is None:
        paths = git_diff_paths(base_sha)
    changed = {
        match.group(1)
        for path in paths
        if (match := re.match(r"^packages/([^/]+)/", path))
    }
    return changed | changed_inventory(base_sha, paths)


def changed_inventory(base_sha: str, paths: list[str]) -> set[str]:
    """Names whose entry in the source inventory changed since the base.

    Reads the old config out of git rather than trusting the diff text, so a
    reformat or a moved entry does not read as a change to every package.
    """
    if INVENTORY not in paths:
        return set()
    try:
        before = json.loads(
            subprocess.check_output(["git", "show", f"{base_sha}:{INVENTORY}"], text=True)
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        # The inventory did not exist or does not parse at the base commit.
        # Nothing can be proven unchanged, so prove nothing and let the
        # published comparison decide on its own.
        return set()
    after = json.loads((ROOT / INVENTORY).read_text())
    return changed_entries(before, after)


def fetch_primary(base_url: str) -> bytes:
    """The decompressed primary.xml of the repository at base_url.

    A failure here is not fatal: an empty result means nothing can be proven
    published, so everything rebuilds. Slower, never wrong.
    """
    if not base_url:
        return b""
    if not base_url.endswith("/"):
        base_url += "/"
    repomd = (
        urllib.request.urlopen(base_url + "repodata/repomd.xml", timeout=60)
        .read()
        .decode()
    )
    href = re.search(r'<location href="([^"]*primary[^"]*)"', repomd).group(1)
    raw = urllib.request.urlopen(base_url + href, timeout=PUBLISHED_REPO_TIMEOUT).read()
    if href.endswith(".zst"):
        import zstandard

        primary = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)).read()
    else:
        primary = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    return primary


def hummingbird_baseurl(repo_file: Path) -> str:
    """The baseurl of config/hummingbird.repo, with a trailing slash."""
    match = re.search(r"^baseurl=(\S+)", repo_file.read_text(), re.MULTILINE)
    if match is None:
        raise ValueError(f"{repo_file} has no baseurl")
    return match.group(1).rstrip("/") + "/"


def fetch_published(base_url: str) -> dict[str, tuple[str, str]]:
    """What the published repository already carries, by source package.

    A failure here is not fatal: an empty result means nothing can be proven
    published, so everything rebuilds. Slower, never wrong.
    """
    return published_from_primary(fetch_primary(base_url))


def main() -> int:
    config = json.loads((ROOT / INVENTORY).read_text())
    base_sha = os.environ.get("BASE_SHA", "")
    full = os.environ.get("FULL") == "1"
    factory_repo = os.environ.get("FACTORY_REPO", "")

    paths = git_diff_paths(base_sha)
    is_global, global_triggers = is_global_change(paths)
    if is_global:
        full = True
        print(f"global rebuild triggered by: {', '.join(global_triggers)}")

    changed = changed_recipes(base_sha, paths)
    print(f"changed package recipes: {', '.join(sorted(changed)) or 'none'}")

    factory_pkgs = {entry["name"] for entry in config["packages"]}
    spec_deps = spec_dependents(ROOT, factory_pkgs)

    published: dict[str, tuple[str, str]] = {}
    primary_deps: dict[str, set[str]] = {}
    stale: dict[str, set[str]] = {}

    if not full:
        primary = b""
        try:
            primary = fetch_primary(factory_repo)
            published = published_from_primary(primary)
            primary_deps = dependents_from_primary(primary) if primary else {}
            print(f"published repo has {len(published)} source packages")
        except Exception as error:  # noqa: BLE001 - availability, not correctness
            print(
                f"WARNING: could not read published repo, rebuilding all: {error}",
                file=sys.stderr,
            )
        if primary:
            try:
                hb_repo = ROOT / "config" / "hummingbird.repo"
                if hb_repo.exists():
                    external = provides_from_primary(
                        fetch_primary(hummingbird_baseurl(hb_repo))
                    )
                    stale = stale_from_primary(primary, external)
            except Exception as error:  # noqa: BLE001 - availability, not correctness
                print(
                    "WARNING: could not read the Hummingbird repository, "
                    f"so stale published builds cannot be detected: {error}",
                    file=sys.stderr,
                )

    if not factory_repo:
        print(
            "WARNING: no factory repository for the build root; "
            "nothing may be skipped as already published",
            file=sys.stderr,
        )

    dependents = merge_dependents(spec_deps, primary_deps)

    reasons: dict[str, list[str]] = {}
    build = plan(
        config,
        ROOT,
        published=published,
        changed=changed,
        full=full,
        factory_repo=factory_repo,
        dependents=dependents,
        stale=set(stale),
        reasons=reasons,
        global_triggers=global_triggers,
    )
    building = {entry["name"] for entry in build}

    direct_changes = {
        entry["name"]
        for entry in build
        if entry["name"] in changed
        or (not full and not is_published(ROOT, entry, published))
    }
    reverse_deps = {
        entry["name"]
        for entry in build
        if entry["name"] not in direct_changes and not full
    }

    for entry in config["packages"]:
        name = entry["name"]
        if name not in building:
            print(f"skip {name}: already published")
        elif name in stale:
            missing = ", ".join(sorted(stale[name])[:3])
            print(f"rebuild {name}: published build requires {missing}, which nothing provides")
        elif name in reverse_deps:
            r = "; ".join(reasons.get(name, []))
            print(f"rebuild {name}: {r}")

    if late := overflow(build):
        raise SystemExit(
            "no job exists for stage 11 or later; "
            f"reduce the stage of: {', '.join(late)}"
        )

    summary_md, plan_json = format_build_plan(
        build,
        reasons,
        full=full,
        global_triggers=global_triggers,
        direct_changes=direct_changes,
        reverse_deps=reverse_deps,
        total_inventory=len(config["packages"]),
    )

    if "GITHUB_STEP_SUMMARY" in os.environ:
        try:
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as handle:
                handle.write(summary_md + "\n")
        except OSError as error:
            print(f"WARNING: could not write GITHUB_STEP_SUMMARY: {error}", file=sys.stderr)

    reports_dir = ROOT / "work" / "reports"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "build-plan.md").write_text(summary_md)
        (reports_dir / "build-plan.json").write_text(json.dumps(plan_json, indent=2))
    except OSError as error:
        print(f"WARNING: could not write build plan reports: {error}", file=sys.stderr)

    outputs = stage_outputs(build)
    for stage in range(11):
        chunks = json.loads(outputs[f"stage{stage}_chunks"])
        if len(chunks) > 1:
            names = json.loads(outputs[f"stage{stage}"])
            print(f"stage {stage}: {len(names)} packages in {len(chunks)} chunks")

    with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")
    print(f"will build {len(build)} of {len(config['packages'])} packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
