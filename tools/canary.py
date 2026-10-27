#!/usr/bin/env python3
"""The decisions and assertions behind .github/workflows/canary.yml.

The canary runs rebuild-rpms.yml itself over a fixed handful of packages. The
workflow is plumbing; what it concludes lives here, where it is under test:

    canary.py touches-pipeline < changed-paths   exit 0 when the canary must run
    canary.py pr-relevant --repository R --pr N --set JSON
                                                 the same, judged on a pull request's
                                                 files and the lock entries they change
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
from collections.abc import Sequence
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


# Recipe inventory, not pipeline. The canary reads only the canary set's own
# entries in these files, so a pull request that adds recipes and new entries
# changes nothing it can prove anything about. They stay under config/ for the
# tools that read them; PIPELINE_PATHS only counts a change to them when it
# could reach the canary set (pipeline_relevant).
SOURCES_LOCK = "config/upstream-sources.json"
DATA_FILES = frozenset({
    SOURCES_LOCK,
    "config/factory-build-backlog.toml",
    "config/fedora-primary-sources.txt",
})
# pass3 perturbs this recipe and reads its lock entry; it is not in CANARY_SET.
PERTURBED = ("python-typing-inspection",)


def sources_touch_existing(base: object, head: object) -> bool:
    """Whether head changes anything base already had in the lock.

    Adding entries is the import case and cannot affect packages that were
    already locked. Any modified or removed entry, any change outside the
    package list, or anything unparseable counts as touching.
    """
    try:
        base_rows, head_rows = base["packages"], head["packages"]  # type: ignore[index]
        before = {row["name"]: row for row in base_rows}
        after = {row["name"]: row for row in head_rows}
        other_before = {key: value for key, value in base.items() if key != "packages"}  # type: ignore[union-attr]
        other_after = {key: value for key, value in head.items() if key != "packages"}  # type: ignore[union-attr]
    except (KeyError, TypeError, AttributeError):
        return True
    if len(before) != len(base_rows) or len(after) != len(head_rows):
        return True
    if other_before != other_after:
        return True
    return any(name not in after or after[name] != row for name, row in before.items())


def patch_mentions(patch: str, names: Sequence[str]) -> bool:
    """Whether a changed line of a unified diff names one of these packages."""
    changed = [
        line[1:] for line in patch.splitlines()
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    return any(
        re.search(rf"(?<![\w.+-]){re.escape(name)}(?![\w.+-])", line)
        for line in changed for name in names
    )


def pipeline_relevant(
    files: Sequence[dict],
    canary_set: Sequence[str],
    base_sources: object = None,
    head_sources: object = None,
) -> bool:
    """Whether a pull request's files can change what the canary proves.

    Everything under PIPELINE_PATHS counts, except the inventory files above:
    those count only when the change reaches an entry that already existed or
    names a canary package. A file whose diff GitHub did not return (binary,
    too large) is judged relevant.
    """
    for entry in files:
        for path in {entry.get("filename"), entry.get("previous_filename")} - {None, ""}:
            if not path.startswith(PIPELINE_PATHS):
                continue
            if path not in DATA_FILES:
                return True
            if path == SOURCES_LOCK:
                if base_sources is None or head_sources is None:
                    return True
                if sources_touch_existing(base_sources, head_sources):
                    return True
            elif entry.get("patch") is None or patch_mentions(entry["patch"], canary_set):
                return True
    return False


def _gh(args: Sequence[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def _json_stream(text: str) -> list[dict]:
    """Every JSON value in text (gh --paginate prints one array per page)."""
    decoder, index, items = json.JSONDecoder(), 0, []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, index = decoder.raw_decode(text, index)
        items.extend(value if isinstance(value, list) else [value])
    return items


def pr_relevant(repository: str, pr: int, canary_set: Sequence[str], gh=_gh) -> bool:
    """pipeline_relevant for a pull request, fetching what the rule needs."""
    files = _json_stream(gh(["api", "--paginate", f"repos/{repository}/pulls/{pr}/files"]))
    touches_lock = any(
        SOURCES_LOCK in (entry.get("filename"), entry.get("previous_filename")) for entry in files
    )
    base_sources = head_sources = None
    if touches_lock:
        meta = json.loads(gh(["api", f"repos/{repository}/pulls/{pr}"]))
        head = meta["head"]["sha"]
        compare = json.loads(gh(["api", f"repos/{repository}/compare/{meta['base']['sha']}...{head}"]))
        merge_base = compare["merge_base_commit"]["sha"]
        raw = ["-H", "Accept: application/vnd.github.raw"]
        try:
            base_sources = json.loads(gh(["api", *raw, f"repos/{repository}/contents/{SOURCES_LOCK}?ref={merge_base}"]))
            head_sources = json.loads(gh(["api", *raw, f"repos/{repository}/contents/{SOURCES_LOCK}?ref={head}"]))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            base_sources = head_sources = None
    return pipeline_relevant(files, [*canary_set, *PERTURBED], base_sources, head_sources)


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


def lock_nevras(lock: dict) -> list[str]:
    """Sorted NEVRAs recorded in a buildroot_lock.json."""
    rpms = lock.get("buildroot", {}).get("rpms", [])
    nevras = []
    for r in rpms:
        epoch = f"{r['epoch']}:" if r.get("epoch") else ""
        nevras.append(f"{r['name']}-{epoch}{r['version']}-{r['release']}.{r['arch']}")
    return sorted(nevras)


def cache_problems(
    outcomes: dict[str, dict[str, str]], canary_set: set[str], perturbed: str,
    locks: dict[str, dict[str, dict]] | None = None,
    tolerated: list[str] | None = None,
) -> list[str]:
    """Cache-verdict problems. A pass2/pass3 compile whose buildroot NEVRAs
    moved since pass1 is a legitimate invalidation, not a problem: it is
    appended to ``tolerated`` (or printed to stderr when none is given)."""
    problems = []
    for name, expected in (("pass2", canary_set), ("pass3", canary_set | {perturbed})):
        seen = outcomes.get(name, {})
        if set(seen) != expected:
            problems.append(f"{name} built {sorted(seen)}, expected {sorted(expected)}")
    for package in sorted(canary_set):
        for name in ("pass2", "pass3"):
            outcome = outcomes.get(name, {}).get(package)
            if outcome is not None and outcome != "cache hit":
                if (
                    locks
                    and outcome == "compiled"
                    and name in locks
                    and "pass1" in locks
                    and package in locks[name]
                    and package in locks["pass1"]
                ):
                    p1_nevras = lock_nevras(locks["pass1"][package])
                    pn_nevras = lock_nevras(locks[name][package])
                    if p1_nevras != pn_nevras:
                        added = [f"+{n}" for n in pn_nevras if n not in p1_nevras]
                        removed = [f"-{n}" for n in p1_nevras if n not in pn_nevras]
                        diff_str = ", ".join((added + removed)[:5])
                        note = f"{name}: {package} recompiled due to buildroot NEVRA changes ({diff_str})"
                        if tolerated is None:
                            print(f"info: {note}", file=sys.stderr)
                        else:
                            tolerated.append(note)
                        continue
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
PASS_LOCK_ARTIFACT = re.compile(r"^(?:(?P<pass>p\d+)-)?lock-s\d+-(?P<package>.+)$")


def read_locks(directory: Path) -> dict[str, dict]:
    """package -> lock, from downloaded <prefix>lock-s<N>-<package> artifacts."""
    locks = {}
    for path in sorted(directory.rglob("buildroot_lock.json")):
        artifact = path.relative_to(directory).parts[0]
        match = LOCK_ARTIFACT.search(artifact)
        if match:
            locks[match["package"]] = json.loads(path.read_text())
    return locks


def read_pass_locks(directory: Path) -> dict[str, dict[str, dict]]:
    """pass -> package -> lock, from downloaded p<N>-lock-s<stage>-<package> artifacts."""
    pass_locks: dict[str, dict[str, dict]] = {}
    for path in sorted(directory.rglob("buildroot_lock.json")):
        artifact = path.relative_to(directory).parts[0]
        match = PASS_LOCK_ARTIFACT.search(artifact)
        if match:
            prefix = match["pass"] or "p1"
            pass_name = f"pass{prefix[1:]}"
            pass_locks.setdefault(pass_name, {})[match["package"]] = json.loads(path.read_text())
    return pass_locks


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


def summary(
    outcomes: dict[str, dict[str, str]], problems: list[str], tolerated: Sequence[str] = (),
) -> str:
    lines = ["### Canary cache", "", "| pass | package | outcome |", "| --- | --- | --- |"]
    for name in sorted(outcomes):
        for package, outcome in sorted(outcomes[name].items()):
            lines.append(f"| {name} | `{package}` | {outcome} |")
    lines.append("")
    if problems:
        lines += ["**Failed:**", ""] + [f"- {problem}" for problem in problems]
        if tolerated:
            lines += [
                "",
                "**Tolerated compiles** (buildroot NEVRAs moved since pass1, so the cache key legitimately changed):",
                "",
            ] + [f"- {note}" for note in tolerated]
    elif tolerated:
        lines += [
            "**Tolerated compiles** (buildroot NEVRAs moved since pass1, so the cache key legitimately changed):",
            "",
        ] + [f"- {note}" for note in tolerated] + [
            "",
            "Every other pass2/pass3 build was a cache hit; pass3 compiled the perturbed package.",
        ]
    else:
        lines.append("pass2 compiled nothing; pass3 compiled only the perturbed package.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("touches-pipeline")
    commands.add_parser("salt")
    relevant = commands.add_parser("pr-relevant")
    relevant.add_argument("--repository", required=True)
    relevant.add_argument("--pr", required=True, type=int)
    relevant.add_argument("--set", required=True, help="JSON array of canary package names")
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
    cache.add_argument("--locks", type=Path, help="Directory containing downloaded pass lock artifacts")
    args = parser.parse_args(argv)

    if args.command == "touches-pipeline":
        return 0 if touches_pipeline(sys.stdin.read().splitlines()) else 1
    if args.command == "pr-relevant":
        return 0 if pr_relevant(args.repository, args.pr, json.loads(args.set)) else 1
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
        locks = read_pass_locks(args.locks) if args.locks else None
        tolerated: list[str] = []
        problems = cache_problems(
            outcomes, set(json.loads(args.set)), args.perturbed, locks=locks, tolerated=tolerated
        )
        print(summary(outcomes, problems, tolerated))
        for note in tolerated:
            print(f"::notice title=canary cache::{note}", file=sys.stderr)
        for problem in problems:
            print(f"::error title=canary cache::{problem}", file=sys.stderr)
        return 1 if problems else 0
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
