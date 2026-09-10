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

from tools.rebuild_plan import overflow, plan, published_from_primary, stage_outputs

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_REPO_TIMEOUT = 120


def changed_recipes(base_sha: str) -> set[str]:
    """Recipes touched since the base commit.

    Empty when there is no range to read -- a scheduled run has no `before` and
    no pull request base -- which is why the published comparison must stand on
    its own rather than leaning on this.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha or "") or set(base_sha) == {"0"}:
        return set()
    paths = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_sha}..HEAD"], text=True
    ).splitlines()
    return {
        match.group(1)
        for path in paths
        if (match := re.match(r"^packages/([^/]+)/", path))
    }


def fetch_published(base_url: str) -> dict[str, tuple[str, str]]:
    """What the published repository already carries, by source package.

    A failure here is not fatal: an empty result means nothing can be proven
    published, so everything rebuilds. Slower, never wrong.
    """
    if not base_url:
        return {}
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
    return published_from_primary(primary)


def main() -> int:
    config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
    full = os.environ.get("FULL") == "1"
    factory_repo = os.environ.get("FACTORY_REPO", "")

    changed = changed_recipes(os.environ.get("BASE_SHA", ""))
    print(f"changed package recipes: {', '.join(sorted(changed)) or 'none'}")

    published: dict[str, tuple[str, str]] = {}
    if not full:
        try:
            published = fetch_published(factory_repo)
            print(f"published repo has {len(published)} source packages")
        except Exception as error:  # noqa: BLE001 - availability, not correctness
            print(
                f"WARNING: could not read published repo, rebuilding all: {error}",
                file=sys.stderr,
            )
    if not factory_repo:
        print(
            "WARNING: no factory repository for the build root; "
            "nothing may be skipped as already published",
            file=sys.stderr,
        )

    build = plan(
        config,
        ROOT,
        published=published,
        changed=changed,
        full=full,
        factory_repo=factory_repo,
    )
    building = {entry["name"] for entry in build}
    for entry in config["packages"]:
        if entry["name"] not in building:
            print(f"skip {entry['name']}: already published")

    if late := overflow(build):
        raise SystemExit(
            "no job exists for stage 11 or later; "
            f"reduce the stage of: {', '.join(late)}"
        )

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
