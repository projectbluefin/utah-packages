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

from tools import build_graph, factory_state
from tools.package_inventory import source_locks
from tools.rebuild_plan import (
    cacheable,
    stale_from_primary,
    provides_by_source,
    provides_from_primary,
    changed_entries,
    dependents_from_primary,
    STAGES,
    overflow,
    plan,
    prunable_sources,
    published_from_primary,
    restrict,
    stage_outputs,
)

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_REPO_TIMEOUT = 120
INVENTORY = "config/upstream-sources.json"
HUMMINGBIRD_OWNED = "config/hummingbird-provided-sources.json"


def changed_recipes(base_sha: str) -> set[str]:
    """Recipes touched since the base commit.

    Empty when there is no range to read -- a scheduled run has no `before` and
    no pull request base -- which is why the published comparison must stand on
    its own rather than leaning on this.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha or "") or set(base_sha) == {"0"}:
        return set()
    try:
        paths = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_sha}..HEAD"], text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        # The base is not in this clone: a force push dropped it, or the
        # range was never fetched. No range means no diff-derived changes,
        # which is what a scheduled run already works with.
        print(f"WARNING: cannot diff from {base_sha}; treating the range as unknown",
              file=sys.stderr)
        return set()
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
    after = {"packages": list(source_locks(ROOT).values())}
    return changed_entries(before, after)


def fetch_primary(base_url: str) -> bytes:
    """The decompressed primary.xml of the repository at base_url.

    base_url is normally the file:// path of the repository `prepare`
    extracted from the published factory image, so the listing read here is
    byte-for-byte the one every build root will have enabled. A failure here
    is not fatal to the caller: an empty result means nothing can be proven
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
    """What the published repository already carries, by source package."""
    return published_from_primary(fetch_primary(base_url))


def load_graph(rows_dir: str, primary: bytes) -> dict[str, set[str]] | None:
    """BuildRequires edges from the rpmspec extraction prepare ran, or None."""
    if not rows_dir or not Path(rows_dir).is_dir():
        return None
    published = provides_by_source(primary) if primary else None
    recipes, edges = build_graph.load(Path(rows_dir), published)
    unparsed = sorted(name for name, recipe in recipes.items() if not recipe.parsed)
    for name in unparsed:
        print(f"::warning title=spec not parsed::{name}: {recipes[name].error or 'rpmspec failed'}; "
              "its BuildRequires are missing from the graph", file=sys.stderr)
    print(f"build graph: {len(recipes)} recipes, "
          f"{sum(len(v) for v in edges.values())} factory BuildRequires edges")
    return edges


def load_state(labels_file: str) -> dict | None:
    if not labels_file or not Path(labels_file).is_file():
        return None
    text = Path(labels_file).read_text().strip()
    return factory_state.parse_labels(json.loads(text or "null"))


def main() -> int:
    locks = source_locks(ROOT)
    config = {"packages": list(locks.values())}
    # The canary names its fixed package set; every other run leaves it empty.
    only = json.loads(os.environ.get("ONLY_PACKAGES") or "[]")
    if only:
        config = restrict(config, only)
        print(f"restricted to {len(config['packages'])} named packages: {', '.join(only)}")
    names = [entry["name"] for entry in config["packages"]]
    hummingbird_owned = set(
        json.loads((ROOT / HUMMINGBIRD_OWNED).read_text())["sources"]
    )
    full = os.environ.get("FULL") == "1"
    factory_repo = os.environ.get("FACTORY_REPO", "")
    # A push rebuilds what changed. The schedule and a dispatch also retry
    # packages whose last attempt at their current inputs failed.
    retry_failed = os.environ.get("EVENT", "") != "push"

    published: dict[str, tuple[str, str]] = {}
    stale: dict[str, set[str]] = {}
    primary = b""
    if factory_repo:
        try:
            primary = fetch_primary(factory_repo)
            published = published_from_primary(primary)
            print(f"published repo has {len(published)} source packages")
        except Exception as error:  # noqa: BLE001 - availability, not correctness
            print(
                f"WARNING: could not read published repo, rebuilding all: {error}",
                file=sys.stderr,
            )

    # What changed since the published build. The state label on the image
    # records the inputs of every published build, so the comparison covers
    # every merge since the last publication, including runs that were
    # replaced in the queue. An image without it (the first run after this
    # landed) falls back to the diff and the NEVR comparison.
    digests = {name: digest for name, digest in factory_state.current(ROOT, locks).items()
               if name in set(names)}
    state = load_state(os.environ.get("FACTORY_LABELS", "")) if factory_repo else None
    held: set[str] = set()
    if state is not None:
        changed, held = factory_state.changed(state, digests, retry_failed=retry_failed)
        mode = "state"
    else:
        changed = changed_recipes(os.environ.get("BASE_SHA", ""))
        mode = "diff"
    print(f"change detection: {mode}; changed: {', '.join(sorted(changed)) or 'none'}")
    for name in sorted(held):
        print(f"hold {name}: its last build at these exact inputs failed; "
              "the scheduled run retries it")

    edges = load_graph(os.environ.get("GRAPH_ROWS", ""), primary)
    dependents: dict[str, set[str]] = {}
    if not full:
        # Reverse dependencies come from real BuildRequires: rpmspec in the
        # build root, mapped to factory packages through the spec and the
        # published provides. Without the graph, the published runtime
        # Requires are the fallback, as before.
        if edges is not None:
            dependents = build_graph.dependents(edges)
        elif primary:
            dependents = dependents_from_primary(primary)
        # A published package whose binaries require something that neither
        # the published repository nor Hummingbird provides is stale: it was
        # built against a build root that has since moved. Without the
        # Hummingbird listing that judgement cannot be made, so it is not
        # made -- the run then trusts the recipe match alone, as before.
        if primary:
            try:
                external = provides_from_primary(
                    fetch_primary(hummingbird_baseurl(ROOT / "config" / "hummingbird.repo"))
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

    common = dict(
        published=published, changed=changed, full=full,
        factory_repo=factory_repo, stale=set(stale), trust_state=state is not None,
    )
    # From the BuildRequires graph, only the direct dependents: a package
    # that BuildRequires what changed is relinked against it. Following the
    # edges further drags in everything downstream of tools such as git
    # (47 recipes BuildRequire it for %autosetup -S git) and through a
    # 55-package BuildRequires cycle, so a one-line libical fix selected 167
    # packages. A consumer two hops away that really is broken shows up as a
    # stale published build (an unsatisfied Requires) and is rebuilt then.
    # The runtime fallback keeps its old transitive closure.
    build = plan(config, ROOT, dependents=dependents,
                 closure_depth=1 if edges is not None else None, **common)
    building = {entry["name"] for entry in build}
    direct = {entry["name"] for entry in plan(config, ROOT, **common)}
    reasons: dict[str, str] = {}
    for entry in config["packages"]:
        name = entry["name"]
        if name not in building:
            continue
        if full:
            reasons[name] = "full rebuild"
        elif name in stale:
            missing = ", ".join(sorted(stale[name])[:3])
            reasons[name] = f"published build requires {missing}, which nothing provides"
        elif name in changed:
            reasons[name] = "changed since the published build"
        elif name not in direct:
            providers = sorted((edges or {}).get(name, set()) & building) if edges else []
            reasons[name] = ("BuildRequires " + ", ".join(providers)) if providers \
                else "depends on something being rebuilt"
        else:
            reasons[name] = "not published at this version"
        print(f"rebuild {name}: {reasons[name]}")

    stages = {entry["name"]: entry.get("stage") or 0 for entry in config["packages"]}
    solved = None
    if edges is not None:
        unordered: list[set[str]] = []
        solved = build_graph.waves(building, edges, stages, unordered)
        for members in unordered:
            print(f"::warning title=unbroken BuildRequires cycle::{', '.join(sorted(members))} "
                  "build side by side; give them distinct stages in config to order them",
                  file=sys.stderr)

    if late := overflow(build, solved):
        raise SystemExit(
            f"no job exists for wave {STAGES} or later; the BuildRequires chain through "
            f"{', '.join(late)} is deeper than rebuild-rpms.yml's {STAGES} waves"
        )

    outputs = stage_outputs(build, solved)
    outputs["cacheable"] = json.dumps(cacheable(build, changed, set(stale)))
    outputs["prune_sources"] = json.dumps(
        prunable_sources(published, hummingbird_owned)
    )
    # What publish records on the image for packages this run did not touch:
    # everything prepare judged up to date at its current inputs.
    outputs["trusted"] = json.dumps(sorted(set(names) - building - held))
    for stage in range(STAGES):
        chunks = json.loads(outputs[f"stage{stage}_chunks"])
        if len(chunks) > 1:
            wave_names = json.loads(outputs[f"stage{stage}"])
            print(f"wave {stage}: {len(wave_names)} packages in {len(chunks)} chunks")

    with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as handle:
            handle.write(plan_summary(mode, build, reasons, solved, held, len(names)))
    print(f"will build {len(build)} of {len(config['packages'])} packages")
    return 0


def plan_summary(
    mode: str,
    build: list[dict],
    reasons: dict[str, str],
    solved: dict[str, int] | None,
    held: set[str],
    total: int,
) -> str:
    lines = ["### Build plan", "",
             f"{len(build)} of {total} packages; change detection: **{mode}**; "
             f"waves: **{'solved from BuildRequires' if solved is not None else 'config stage'}**.",
             ""]
    if build:
        lines += ["| wave | package | why |", "| ---: | --- | --- |"]
        for entry in sorted(build, key=lambda e: ((solved or {}).get(e["name"], e.get("stage") or 0), e["name"])):
            wave = (solved or {}).get(entry["name"], entry.get("stage") or 0)
            lines.append(f"| {wave} | `{entry['name']}` | {reasons.get(entry['name'], '')} |")
    if held:
        lines += ["", "Held (failed at these exact inputs; retried by the scheduled run): "
                  + ", ".join(f"`{n}`" for n in sorted(held))]
    return "\n".join(lines) + "\n\n"


if __name__ == "__main__":
    raise SystemExit(main())
