#!/usr/bin/env python3
"""The decisions and assertions behind .github/workflows/canary.yml.

The canary runs rebuild-rpms.yml itself over a fixed handful of packages. The
workflow is plumbing; what it concludes lives here, where it is under test:

    canary.py touches-pipeline < changed-paths   exit 0 when the canary must run
    canary.py salt                               the cache namespace for pass1
    canary.py verify-image REF@DIGEST --utah-reader PATH --expect JSON
    canary.py verify-cache JOBS.json --set JSON --perturbed NAME
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# A change under any of these can break a factory run without touching a
# recipe, so a pull request carrying one must pass the canary. Recipes
# themselves are not here: they are proven by building them.
PIPELINE_PATHS = (
    ".github/workflows/",
    ".github/actions/",
    "tools/",
    "config/",
    "Containerfile",
)

# What decides how a package is compiled. pass1 compiles for real whenever
# one of these changed since the last canary, and reuses its builds otherwise.
BUILD_PATH = (
    ".github/workflows/build-stage.yml",
    ".github/actions/load-buildroot/action.yml",
    ".github/actions/load-factory-repo/action.yml",
    "config/hummingbird.repo",
    "tools/source_pipeline.py",
    "tools/dist_bump.py",
    "tools/package_cache_key.py",
    "tools/build_container.sh",
    "tools/hermetic_build.sh",
    "tools/mock_config.py",
)

BUILD_STEP = "Build the verified source with its RPM recipe"
HERMETIC_BUILD_STEP = "Build offline from the lock (hermetic)"
RESTORE_STEP = "Restore package RPM cache"
BUILD_JOB = re.compile(r"^(?P<pass>pass\d+) / rebuild\d+ .*/ build \((?P<package>[^)]+)\)$")


def touches_pipeline(paths: list[str]) -> bool:
    return any(path.startswith(PIPELINE_PATHS) for path in paths if path)


def salt(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for relative in BUILD_PATH:
        digest.update(relative.encode() + b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return "canary-" + digest.hexdigest()[:16]


# ---------------------------------------------------------------------------
# The published image


def registry_json(image: str, kind: str, reference: str) -> dict:
    registry, rest = image.split("/", 1)
    repository = rest.split("@", 1)[0].split(":", 1)[0]
    query = urllib.parse.urlencode({"service": registry, "scope": f"repository:{repository}:pull"})
    with urllib.request.urlopen(f"https://{registry}/token?{query}", timeout=120) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(
        f"https://{registry}/v2/{repository}/{kind}/{reference}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.oci.image.manifest.v1+json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def check_layers(manifest: dict) -> list[str]:
    """The two-layer, repodata-first layout Utah depends on (#254)."""
    problems = []
    layers = manifest.get("layers", [])
    if len(layers) != 2:
        problems.append(f"expected 2 layers (repodata, then repository), found {len(layers)}")
    elif layers[0]["size"] >= layers[1]["size"]:
        problems.append("the leading layer is not the small metadata one")
    return problems


def primary_sources(repodata: Path) -> set[str]:
    """Source package names in a repodata directory's primary.xml."""
    from tools.rebuild_plan import published_from_primary

    candidates = sorted(repodata.glob("*primary.xml*"))
    if not candidates:
        raise ValueError(f"no primary.xml in {repodata}")
    path = candidates[0]
    raw = path.read_bytes()
    if path.name.endswith(".gz"):
        raw = gzip.decompress(raw)
    elif path.name.endswith(".zst"):
        raw = subprocess.run(["zstd", "-dc", str(path)], check=True, capture_output=True).stdout
    return set(published_from_primary(raw))


def load_utah_reader(path: Path):
    spec = importlib.util.spec_from_file_location("utah_check_repo_availability", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_state(config: dict, expected: set[str]) -> list[str]:
    """The state label tools/factory_state.py writes records every package."""
    labels = (config.get("config") or {}).get("Labels") or {}
    raw = labels.get("org.projectbluefin.factory.state")
    if not raw:
        return ["the image carries no org.projectbluefin.factory.state label"]
    recorded = set(json.loads(raw).get("inputs", {}))
    if recorded != expected:
        return [f"the state label records {sorted(recorded)}, expected {sorted(expected)}"]
    return []


def verify_image(
    image: str, utah_reader: Path, expected: set[str], expect_state: bool = False
) -> list[str]:
    manifest = registry_json(image, "manifests", image.split("@", 1)[1])
    problems = check_layers(manifest)
    if expect_state:
        config = registry_json(image, "blobs", manifest["config"]["digest"])
        problems += check_state(config, expected)
    reader = load_utah_reader(utah_reader)
    with tempfile.TemporaryDirectory(prefix="canary-repodata-") as tmp:
        try:
            # Utah's own function: reads manifest.layers[0] only, refuses one
            # over 64 MiB or holding anything outside repository/repodata.
            reader.repository_metadata(image, Path(tmp))
        except Exception as error:  # noqa: BLE001 - reported, not swallowed
            problems.append(f"Utah's metadata reader refused the image: {error}")
            return problems
        found = primary_sources(Path(tmp) / "repodata")
    if found != expected:
        problems.append(
            f"repository carries {sorted(found)}, expected exactly {sorted(expected)}"
        )
    return problems


# ---------------------------------------------------------------------------
# The cache


def build_outcomes(jobs: list[dict]) -> dict[str, dict[str, str]]:
    """pass -> package -> 'compiled' | 'cache hit' | 'failed' | other."""
    outcomes: dict[str, dict[str, str]] = {}
    for job in jobs:
        match = BUILD_JOB.match(job.get("name", ""))
        if not match:
            continue
        steps = {step["name"]: step.get("conclusion") for step in job.get("steps", [])}
        build = steps.get(BUILD_STEP)
        if build in (None, "skipped") and steps.get(HERMETIC_BUILD_STEP) not in (None, "skipped"):
            build = steps[HERMETIC_BUILD_STEP]
        restore = steps.get(RESTORE_STEP)
        if job.get("conclusion") != "success":
            outcome = "failed"
        elif build == "success":
            outcome = "compiled"
        elif build == "skipped" and restore == "success":
            outcome = "cache hit"
        else:
            outcome = f"unclear (build {build}, restore {restore})"
        outcomes.setdefault(match["pass"], {})[match["package"]] = outcome
    return outcomes


def cache_problems(
    outcomes: dict[str, dict[str, str]], canary_set: set[str], perturbed: str
) -> list[str]:
    problems = []
    for name, expected in (("pass2", canary_set), ("pass3", canary_set | {perturbed})):
        seen = outcomes.get(name, {})
        if set(seen) != expected:
            problems.append(f"{name} built {sorted(seen)}, expected {sorted(expected)}")
    for package in sorted(canary_set):
        for name in ("pass2", "pass3"):
            outcome = outcomes.get(name, {}).get(package)
            if outcome is not None and outcome != "cache hit":
                problems.append(f"{name}: {package} was {outcome}, not a cache hit")
    perturbed_outcome = outcomes.get("pass3", {}).get(perturbed)
    if perturbed_outcome is not None and perturbed_outcome != "compiled":
        problems.append(
            f"pass3: {perturbed} was {perturbed_outcome}; its recipe changed, so it must compile"
        )
    return problems


def flaky_problems(jobs: list[dict], pass_name: str, package: str,
                   annotations: list[dict]) -> list[str]:
    """The package compiled, failed %check once, was retried, and succeeded."""
    outcome = build_outcomes(jobs).get(pass_name, {}).get(package)
    problems = []
    if outcome != "compiled":
        problems.append(f"{pass_name}: {package} was {outcome}; it must compile to retry %check")
    messages = [str(a.get("title", "")) + " " + str(a.get("message", "")) for a in annotations]
    if not any("flaky %check retry" in m and package in m for m in messages):
        problems.append(f"{pass_name}: no 'flaky %check retry' annotation for {package}")
    if not any(m.startswith("flaky %check ") and "passed on retry" in m for m in messages):
        problems.append(f"{pass_name}: no 'passed on retry' annotation for {package}")
    return problems


def incremental_problems(
    jobs: list[dict], build_list: list[str] | None, expected: dict[str, int], name: str
) -> list[str]:
    """The incremental pass selected exactly `expected`, each in its wave."""
    problems = []
    if sorted(build_list or []) != sorted(expected):
        problems.append(f"{name} selected {build_list}, expected {sorted(expected)}")
    waves: dict[str, int] = {}
    for job in jobs:
        match = re.match(rf"^{name} / rebuild(\d+) .*/ build \((?P<package>[^)]+)\)$",
                         job.get("name", ""))
        if match:
            waves[match["package"]] = int(match.group(1))
    if waves != expected:
        problems.append(f"{name} built in waves {waves}, expected {expected}")
    return problems


def built_problems(outcomes: dict[str, str], expected: set[str], name: str = "pass6") -> list[str]:
    """Every expected package built or restored, and nothing else."""
    problems = []
    if set(outcomes) != expected:
        problems.append(f"{name} built {sorted(outcomes)}, expected {sorted(expected)}")
    for package in sorted(expected):
        if outcomes.get(package) not in ("compiled", "cache hit"):
            problems.append(f"{name}: {package} was {outcomes.get(package)}")
    return problems


LOCK_ARTIFACT = re.compile(r"lock-s\d+-(?P<package>.+)$")


def read_locks(directory: Path) -> dict[str, dict]:
    """package -> lock, from downloaded <prefix>lock-s<N>-<package> artifacts."""
    locks = {}
    for path in sorted(directory.rglob("buildroot_lock.json")):
        artifact = path.relative_to(directory).parts[0]
        match = LOCK_ARTIFACT.search(artifact)
        if match:
            locks[match["package"]] = json.loads(path.read_text())
    return locks


def hermetic_problems(
    outcomes: dict[str, str], locks: dict[str, dict], canary_set: set[str],
    stage_dependencies: dict[str, str], name: str = "pass6",
) -> list[str]:
    """Every package locked, built offline or restored, stages via the lock."""
    problems = [p.replace("pass6", name) for p in built_problems(outcomes, canary_set)]
    for package in sorted(canary_set):
        lock = locks.get(package)
        if lock is None:
            problems.append(f"{name}: no buildroot_lock.json for {package}")
            continue
        rpms = lock.get("buildroot", {}).get("rpms", [])
        if not rpms:
            problems.append(f"{name}: {package}'s lock records no packages")
        if not (lock.get("bootstrap") or {}).get("pull_digest"):
            problems.append(f"{name}: {package}'s lock does not pin the bootstrap image")
    for consumer, provider in stage_dependencies.items():
        rpms = (locks.get(consumer) or {}).get("buildroot", {}).get("rpms", [])
        staged = [r for r in rpms if r.get("name", "").startswith(provider)
                  and str(r.get("url", "")).startswith("file:///work/prior/")]
        if not staged:
            problems.append(
                f"{name}: {consumer}'s lock does not take {provider} from the earlier stage"
            )
    return problems


def early_publish_problems(jobs: list[dict], pass_name: str, wave: int) -> list[str]:
    """The pass published wave `wave` on its own, before its final publication."""
    by_name = {job.get("name", ""): job for job in jobs}
    early = by_name.get(f"{pass_name} / publish{wave} / publish")
    final = by_name.get(f"{pass_name} / publish / publish")
    if early is None:
        return [f"{pass_name}: no early publication after wave {wave}"]
    steps = {s["name"]: s.get("conclusion") for s in early.get("steps", [])}
    problems = []
    if steps.get("Publish the repository as an OCI image") != "success":
        problems.append(f"{pass_name}: the wave-{wave} publication pushed no image")
    if final is not None and early.get("completed_at", "") > final.get("started_at", "~"):
        problems.append(f"{pass_name}: the wave-{wave} publication did not finish before the final one")
    return problems


def summary(outcomes: dict[str, dict[str, str]], problems: list[str]) -> str:
    lines = ["### Canary cache", "", "| pass | package | outcome |", "| --- | --- | --- |"]
    for name in sorted(outcomes):
        for package, outcome in sorted(outcomes[name].items()):
            lines.append(f"| {name} | `{package}` | {outcome} |")
    lines.append("")
    if problems:
        lines += ["**Failed:**", ""] + [f"- {problem}" for problem in problems]
    else:
        lines.append("pass2 compiled nothing; pass3 compiled only the perturbed package.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("touches-pipeline")
    commands.add_parser("salt")
    image = commands.add_parser("verify-image")
    image.add_argument("image")
    image.add_argument("--utah-reader", type=Path, required=True)
    image.add_argument("--expect", required=True)
    flaky = commands.add_parser("verify-flaky")
    flaky.add_argument("jobs", type=Path)
    flaky.add_argument("--pass", dest="pass_name", required=True)
    flaky.add_argument("--package", required=True)
    image.add_argument("--expect-state", action="store_true")
    incremental = commands.add_parser("verify-incremental")
    incremental.add_argument("jobs", type=Path)
    incremental.add_argument("--build-list", required=True)
    incremental.add_argument("--expect", required=True, help="JSON package -> wave")
    hermetic = commands.add_parser("verify-hermetic")
    hermetic.add_argument("jobs", type=Path)
    hermetic.add_argument("--pass", dest="pass_name", default="pass6")
    hermetic.add_argument("--locks", type=Path, required=True)
    hermetic.add_argument("--set", required=True)
    hermetic.add_argument("--stage-dependency", action="append", default=[],
                          help="consumer=provider the consumer's lock must take from a stage")
    built = commands.add_parser("verify-built")
    built.add_argument("jobs", type=Path)
    built.add_argument("--pass", dest="pass_name", required=True)
    built.add_argument("--set", required=True)
    early = commands.add_parser("verify-early")
    early.add_argument("jobs", type=Path)
    early.add_argument("--pass", dest="pass_name", required=True)
    early.add_argument("--wave", type=int, required=True)
    cache = commands.add_parser("verify-cache")
    cache.add_argument("jobs", type=Path)
    cache.add_argument("--set", required=True)
    cache.add_argument("--perturbed", required=True)
    args = parser.parse_args(argv)

    if args.command == "touches-pipeline":
        return 0 if touches_pipeline(sys.stdin.read().splitlines()) else 1
    if args.command == "salt":
        print(salt())
        return 0
    if args.command == "verify-image":
        problems = verify_image(args.image, args.utah_reader, set(json.loads(args.expect)),
                                args.expect_state)
        for problem in problems:
            print(f"::error title=canary image::{problem}", file=sys.stderr)
        if not problems:
            print(f"{args.image}: two layers, repodata first, Utah's reader accepts it, "
                  "and it carries exactly the canary set")
        return 1 if problems else 0
    if args.command == "verify-flaky":
        jobs = json.loads(args.jobs.read_text())
        job = next((j for j in jobs if BUILD_JOB.match(j.get("name", ""))
                    and BUILD_JOB.match(j["name"])["pass"] == args.pass_name
                    and BUILD_JOB.match(j["name"])["package"] == args.package), None)
        annotations = []
        if job is not None:
            annotations = json.loads(subprocess.run(
                ["gh", "api", f"repos/{os.environ['REPOSITORY']}/check-runs/{job['id']}/annotations"],
                check=True, capture_output=True, text=True,
            ).stdout)
        problems = flaky_problems(jobs, args.pass_name, args.package, annotations)
        for problem in problems:
            print(f"::error title=canary flaky check::{problem}", file=sys.stderr)
        if not problems:
            print(f"{args.pass_name}: {args.package} failed %check once, was retried, and built")
        return 1 if problems else 0
    if args.command == "verify-incremental":
        problems = incremental_problems(
            json.loads(args.jobs.read_text()), json.loads(args.build_list or "null"),
            json.loads(args.expect), "pass5",
        )
        print("### Canary incremental selection\n")
        print("\n".join(f"- {p}" for p in problems) or "Selected exactly the change and "
              "its reverse dependency, in solved waves.")
        for problem in problems:
            print(f"::error title=canary incremental::{problem}", file=sys.stderr)
        return 1 if problems else 0
    if args.command == "verify-hermetic":
        outcomes = build_outcomes(json.loads(args.jobs.read_text())).get(args.pass_name, {})
        locks = read_locks(args.locks)
        dependencies = dict(item.split("=", 1) for item in args.stage_dependency)
        problems = hermetic_problems(outcomes, locks, set(json.loads(args.set)), dependencies,
                                     args.pass_name)
        print("### Canary hermetic lane\n")
        for package in sorted(locks):
            rpms = locks[package]["buildroot"]["rpms"]
            print(f"- `{package}`: {outcomes.get(package)}, {len(rpms)} locked packages")
        for problem in problems:
            print(f"::error title=canary hermetic::{problem}", file=sys.stderr)
        return 1 if problems else 0
    if args.command == "verify-built":
        outcomes = build_outcomes(json.loads(args.jobs.read_text())).get(args.pass_name, {})
        problems = built_problems(outcomes, set(json.loads(args.set)), args.pass_name)
        print(f"### Canary {args.pass_name}\n")
        for package, outcome in sorted(outcomes.items()):
            print(f"- `{package}`: {outcome}")
        for problem in problems:
            print(f"::error title=canary {args.pass_name}::{problem}", file=sys.stderr)
        return 1 if problems else 0
    if args.command == "verify-early":
        jobs = json.loads(args.jobs.read_text())
        problems = early_publish_problems(jobs, args.pass_name, args.wave)
        for problem in problems:
            print(f"::error title=canary early publish::{problem}", file=sys.stderr)
        if not problems:
            print(f"{args.pass_name}: wave {args.wave} published on its own, before the final publication")
        return 1 if problems else 0
    if args.command == "verify-cache":
        outcomes = build_outcomes(json.loads(args.jobs.read_text()))
        problems = cache_problems(outcomes, set(json.loads(args.set)), args.perturbed)
        print(summary(outcomes, problems))
        for problem in problems:
            print(f"::error title=canary cache::{problem}", file=sys.stderr)
        return 1 if problems else 0
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
