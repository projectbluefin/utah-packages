#!/usr/bin/env python3
"""The incremental-publish gate for the Utah factory.

ghcr.io/.../utah-packages:latest is the only digest consumers read. It used to
move only when the *whole* selected package set built: one flaky %check (fish)
held back every other package, and over four weeks 3 of 117 full runs
published. The rule is now the one Fedora and Hummingbird follow -- each good
build goes into the repository:

* The candidate repository is seeded from the previously published image,
  after verifying that this workflow signed it.
* Each source package this run built successfully *replaces* that source's
  RPMs in the seed. Nothing else in the seed changes.
* A package that failed to build -- or built but does not outrank what Fedora
  or Hummingbird already offer (precedence) -- keeps its previously published
  build, or stays absent if it never had one. Every such package is named in
  the job summary and in a tracking issue; a failure is never silent.
* The Hummingbird-only consumer transaction still gates the whole candidate.
  It is what protects Utah: if the new set does not resolve, the tag does not
  move, however many packages built.

This module encodes that in three forms that must agree:

* ``publish_allowed`` is the pure decision over the job outcomes.
* ``assemble`` is the pure decision over the files: which seed RPMs a run
  removes, which built RPMs it adds, and which packages failed.
* ``assert_gate_enforced`` reads ``.github/workflows/rebuild-rpms.yml`` and
  checks the publish job's ``needs``, ``if:`` and step order encode the same
  rule, so the workflow and the decision cannot drift apart.

The command line is what the workflow runs:

    publish_gate.py assemble --seed repository --built built \\
        --build-list JSON --losers JSON --report work/publish-report.json
    publish_gate.py failures --build-list JSON --artifacts NAMES.json \\
        --prefix P --losers JSON
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REBUILD_WORKFLOW = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "rebuild-rpms.yml"
)

# Every build wave the publish job waits on, in wave order. This restates what
# rebuild-rpms.yml declares, so that the decision functions can be exercised
# without reading the workflow; ``assert_gate_enforced`` proves the two agree.
STAGES = tuple(f"rebuild{stage}" for stage in range(14))

STAGE_JOB = re.compile(r"^rebuild(\d+)$")

# The artifact build-stage.yml uploads for one successful package build,
# optionally behind the canary's per-pass prefix.
RPM_ARTIFACT = re.compile(r"^rpm-s(?P<stage>\d+)-(?P<package>.+)$")


def rebuild_stages(workflow: dict) -> tuple[str, ...]:
    """The rebuild waves ``rebuild-rpms.yml`` actually declares, in wave order."""
    jobs = workflow.get("jobs") or {}
    matched = [(int(m.group(1)), name) for name in jobs if (m := STAGE_JOB.match(name))]
    return tuple(name for _, name in sorted(matched))


def publish_allowed(
    *,
    stages: list[str],
    precedence: str,
    transaction_resolved: bool,
    is_fork_pull_request: bool,
    replaced: int = 1,
    pruned: int = 0,
) -> bool:
    """Whether the consumer OCI tag may move for this run.

    ``stages`` is the sequence of rebuild-wave results. They are deliberately
    *not* a condition: a failed wave means some packages failed, and those
    keep their previous build (see ``assemble``). They are an argument so the
    tests can prove exactly that. ``precedence`` must have *run* to success:
    it is what names the packages that must not replace their predecessor,
    so without it no replacement can be judged. ``transaction_resolved`` is
    the Hummingbird-only consumer transaction over the whole candidate, and
    it is the gate that protects Utah. ``replaced`` and ``pruned`` count what
    the run would change; a run that changes nothing republishes nothing.
    """
    del stages  # a failed build is reported and kept out, never a veto
    if is_fork_pull_request:
        return False
    if precedence != "success":
        return False
    if not transaction_resolved:
        return False
    return replaced + pruned > 0


# ---------------------------------------------------------------------------
# Which files the run changes


@dataclass
class Assembly:
    """What one run does to the seeded repository."""

    replaced: list[str] = field(default_factory=list)
    """Sources whose seed RPMs are removed and whose new RPMs are added."""
    failed: list[str] = field(default_factory=list)
    """Selected sources with no accepted build this run."""
    kept_previous: list[str] = field(default_factory=list)
    """Failed sources that stay published at their previous build."""
    absent: list[str] = field(default_factory=list)
    """Failed sources that were never published and still are not."""
    losers: list[str] = field(default_factory=list)
    """Built, but did not outrank Fedora or Hummingbird: not published."""
    remove: list[str] = field(default_factory=list)
    """Seed files to delete."""
    add: list[str] = field(default_factory=list)
    """Built files to copy in."""

    def report(self) -> dict:
        return {
            "replaced": self.replaced,
            "failed": self.failed,
            "kept_previous": self.kept_previous,
            "absent": self.absent,
            "precedence_losers": self.losers,
        }


def assemble(
    *,
    seed: dict[str, str],
    built: dict[str, str],
    build_list: list[str],
    losers: set[str],
) -> Assembly:
    """Decide the candidate repository from file -> source-name maps.

    ``seed`` maps each RPM in the seeded repository to its source package
    name; ``built`` does the same for every RPM this run's successful builds
    uploaded. A source in ``build_list`` with no built RPM failed. A source
    in ``losers`` built but lost precedence, so it is treated as failed.

    Replacement is by *source* name, not file name: a build that renamed or
    dropped a subpackage must take the old subpackage with it, which adding
    files on top of the seed never did.
    """
    accepted = set(built.values()) - losers
    seeded_sources = set(seed.values())
    failed = sorted(set(build_list) - accepted)
    return Assembly(
        replaced=sorted(accepted),
        failed=failed,
        kept_previous=[name for name in failed if name in seeded_sources],
        absent=[name for name in failed if name not in seeded_sources],
        losers=sorted(losers & set(build_list)),
        remove=sorted(path for path, source in seed.items() if source in accepted),
        add=sorted(path for path, source in built.items() if source in accepted),
    )


# Recipes built only to feed a later wave, never to ship. malcontent-bootstrap
# builds the SRPM "malcontent" at Release 0.bootstrap; publish deletes those
# RPMs. Counted as a build of source "malcontent", it made publish remove the
# real malcontent from the seed and then delete the bootstrap copies, leaving
# no malcontent at all -- run 36206943088 failed its transaction on
# "nothing provides libmalcontent-0.so.0 needed by gnome-control-center".
BOOTSTRAP_RPM = re.compile(r"-0\.bootstrap\.")


def publishable(built: dict[str, str]) -> dict[str, str]:
    """The built RPMs that may enter the repository: no bootstrap builds."""
    return {path: source for path, source in built.items()
            if not BOOTSTRAP_RPM.search(Path(path).name)}


def failures_from_artifacts(
    build_list: list[str], artifact_names: list[str], prefix: str, losers: set[str]
) -> list[str]:
    """Selected packages with no uploaded RPM artifact, plus precedence losers.

    build-stage.yml uploads ``rpm-s<stage>-<package>`` only after a build (or
    a cache restore) produced RPMs, so the artifact list alone says which
    packages built. This is how the report job names failures even when the
    publish job never ran.
    """
    built = set()
    for name in artifact_names:
        if not name.startswith(prefix):
            continue
        match = RPM_ARTIFACT.match(name[len(prefix):])
        if match:
            built.add(match["package"])
    return sorted((set(build_list) - built) | (losers & set(build_list)))


def source_names(paths: list[Path]) -> dict[str, str]:
    """RPM path -> source package name, read from the RPM headers.

    From %{SOURCERPM} rather than the file name: a source need not produce a
    binary that shares its name (wayland ships libwayland-*).
    """
    from tools.rebuild_plan import source_name

    result: dict[str, str] = {}
    rpms = [path for path in paths if path.name.endswith(".rpm")
            and not path.name.endswith(".src.rpm")]
    for start in range(0, len(rpms), 200):
        chunk = rpms[start:start + 200]
        output = subprocess.run(
            ["rpm", "-qp", "--nosignature", "--qf", "%{SOURCERPM}\n", *map(str, chunk)],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        if len(output) != len(chunk):
            raise RuntimeError(f"rpm reported {len(output)} headers for {len(chunk)} files")
        for path, sourcerpm in zip(chunk, output):
            name = source_name(sourcerpm.strip())
            if name is None:
                raise RuntimeError(f"{path}: no source RPM in its header ({sourcerpm!r})")
            result[str(path)] = name
    return result


def apply(assembly: Assembly, seed_root: Path, built_root: Path) -> None:
    """Delete the replaced seed RPMs, then copy in the accepted builds."""
    for path in assembly.remove:
        Path(path).unlink()
    for path in assembly.add:
        source = Path(path)
        target = seed_root / source.relative_to(built_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def summary(assembly: Assembly) -> str:
    lines = ["### Incremental publish", ""]
    names = ", ".join(f"`{n}`" for n in assembly.replaced)
    lines.append(
        f"Replaced {len(assembly.replaced)} source package(s)"
        + (f": {names}" if assembly.replaced and len(assembly.replaced) <= 40 else ".")
    )
    if assembly.failed:
        lines += ["", f"**{len(assembly.failed)} package(s) failed and were not replaced:**", ""]
        lines += ["| package | what consumers get |", "| --- | --- |"]
        for name in assembly.failed:
            if name in assembly.losers:
                state = "previous build (this build lost precedence)"
            elif name in assembly.kept_previous:
                state = "previous build"
            else:
                state = "nothing: never published"
            lines.append(f"| `{name}` | {state} |")
    return "\n".join(lines) + "\n"


def render_report(
    *,
    failed: list[str],
    publish_result: str,
    publish_report: dict | None,
    digest: str,
    run_url: str,
) -> str:
    """The job summary and tracking-issue body for one run.

    Names every package that did not publish and says what consumers get
    for each, and says plainly whether the tag moved at all -- a blocked
    transaction is the one failure that holds back everything.
    """
    kept = set((publish_report or {}).get("kept_previous", []))
    absent = set((publish_report or {}).get("absent", []))
    losers = set((publish_report or {}).get("precedence_losers", []))
    lines = ["### Factory run report", "", f"Run: {run_url}", ""]
    if digest:
        replaced = len((publish_report or {}).get("replaced", []))
        lines.append(f"Published `{digest}`, replacing {replaced} source package(s).")
    elif publish_result == "success":
        lines.append("Nothing new to publish; the published image is unchanged.")
    elif publish_result == "failure":
        lines.append(
            "**Not published.** The candidate failed a publish gate -- most likely "
            "the Hummingbird-only consumer transaction -- so the published image "
            "is unchanged and every package below, and every package that did "
            "build, waits for the next run."
        )
    else:
        lines.append(f"**Not published** (publish job: {publish_result or 'did not run'}).")
    lines.append("")
    if failed:
        lines += [f"**{len(failed)} package(s) failed this run:**", "",
                  "| package | what consumers get |", "| --- | --- |"]
        for name in failed:
            if name in losers:
                state = "previous build (this build lost precedence)"
            elif name in kept:
                state = "previous build"
            elif name in absent:
                state = "nothing: never published"
            else:
                state = "previous build, if one was published"
            lines.append(f"| `{name}` | {state} |")
    else:
        lines.append("Every selected package built.")
    lines += ["", f"<!-- failed: {json.dumps(failed)} -->"]
    return "\n".join(lines) + "\n"


def failed_marker(body: str) -> list[str] | None:
    """The failed list a previous report recorded, or None."""
    match = re.search(r"<!-- failed: (\[.*?\]) -->", body or "")
    return json.loads(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# The workflow must say the same thing


def _normalized(gate: str) -> str:
    return re.sub(r"\s+", " ", gate).strip()


PUBLISH_WORKFLOW = REBUILD_WORKFLOW.with_name("publish-repository.yml")
PUBLISH_USES = "./.github/workflows/publish-repository.yml"
EARLY_JOB = re.compile(r"^publish(\d+)$")


def assert_gate_enforced(workflow: dict, publish_workflow: dict | None = None) -> None:
    """The publish jobs must encode exactly the rule ``publish_allowed`` models.

    ``workflow`` is rebuild-rpms.yml, which decides *when* a publication
    runs; ``publish_workflow`` is publish-repository.yml, which decides what
    one does.
    """
    if publish_workflow is None:
        publish_workflow = load_workflow(PUBLISH_WORKFLOW)
    try:
        publish = workflow["jobs"]["publish"]
    except (KeyError, TypeError) as error:
        raise AssertionError("rebuild-rpms.yml has no publish job") from error
    if publish.get("uses") != PUBLISH_USES:
        raise AssertionError(f"rebuild-rpms.yml's publish job must call {PUBLISH_USES}")
    if publish.get("with", {}).get("final") is not True:
        raise AssertionError("rebuild-rpms.yml's publish job must be the final publication")

    gate = _normalized(str(publish.get("if", "")))

    stages = rebuild_stages(workflow)
    if not stages:
        raise AssertionError("rebuild-rpms.yml declares no rebuild waves")
    if stages != STAGES:
        raise AssertionError(
            "rebuild-rpms.yml declares waves "
            f"{list(stages)}, but publish_gate.STAGES says {list(STAGES)}; "
            "update STAGES and the publish job together"
        )

    # The final publication still waits for every wave to *finish*: a wave
    # still running would otherwise be published around, and its packages
    # reported failed.
    needs = publish.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    missing = [stage for stage in stages if stage not in needs]
    if missing:
        raise AssertionError(
            f"publish job must depend on every rebuild wave; missing {missing}"
        )

    # ...but no wave's result may veto it. That was the atomic rule, and the
    # reason one flaky test held back every package.
    for name, job in workflow["jobs"].items():
        if job.get("uses") != PUBLISH_USES:
            continue
        condition = _normalized(str(job.get("if", "")))
        for stage in stages:
            if f"needs.{stage}.result" in condition:
                raise AssertionError(
                    f"{name} must not depend on {stage}'s result; a failed "
                    "package keeps its previous build instead"
                )
        if "!cancelled()" not in condition:
            raise AssertionError(f"{name} must run after a failed wave, so its if: needs !cancelled()")
        if "needs.prepare.result == 'success'" not in condition:
            raise AssertionError(f"{name} must require prepare to succeed")

    # An early publication covers waves 0..k and must not wait for a later
    # wave -- that is its whole point -- nor cover one.
    for name, job in workflow["jobs"].items():
        match = EARLY_JOB.match(name)
        if not match:
            continue
        wave = int(match.group(1))
        early_needs = job.get("needs", [])
        later = [need for need in early_needs
                 if (m := STAGE_JOB.match(need)) and int(m.group(1)) > wave]
        if later:
            raise AssertionError(f"{name} must not wait for later waves {later}")
        with_ = job.get("with", {})
        if with_.get("final") is not False or str(with_.get("wave")) != str(wave):
            raise AssertionError(f"{name} must be an early publication of wave {wave}")
        if f"needs.prepare.outputs.through{wave}" not in str(with_.get("build_list")):
            raise AssertionError(f"{name} must cover exactly waves 0..{wave}")

    triggers = workflow.get("on", workflow.get(True, {}))
    if "pull_request" in triggers and "pull_request.head.repo.full_name" not in gate:
        raise AssertionError("publish gate must exclude fork pull requests")

    _assert_publication(publish_workflow)


def _assert_publication(publish_workflow: dict) -> None:
    """What one publication does, in publish-repository.yml."""
    try:
        publish = publish_workflow["jobs"]["publish"]
    except (KeyError, TypeError) as error:
        raise AssertionError("publish-repository.yml has no publish job") from error
    needs = publish.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    if "precedence" not in needs:
        raise AssertionError("publish job must depend on precedence")
    gate = _normalized(str(publish.get("if", "")))
    # Precedence names the builds that must not replace their predecessor,
    # so it has to have run.
    if "needs.precedence.result == 'success'" not in gate:
        raise AssertionError("publish gate must require precedence to succeed")
    if "!cancelled()" not in gate:
        raise AssertionError("publish must run after a failed wave, so its if: needs !cancelled()")
    _assert_step_order(publish)


def _step_index(names: list[str], fragment: str, what: str) -> int:
    try:
        return next(i for i, name in enumerate(names) if fragment in name)
    except StopIteration:
        raise AssertionError(f"publish job must {what}") from None


def _assert_step_order(publish: dict) -> None:
    steps = publish.get("steps", [])
    names = [str(step.get("name", "")) for step in steps]
    seed = _step_index(names, "Verify and seed repository", "seed from the verified previous image")
    assemble_step = _step_index(
        names, "Replace the packages this run built", "replace only what this run built"
    )
    validate = _step_index(
        names, "Hummingbird-only consumer transaction",
        "validate the Hummingbird-only consumer transaction",
    )
    publish_step = _step_index(
        names, "Publish the repository as an OCI image", "publish the repository as an OCI image"
    )
    if not seed < assemble_step < validate < publish_step:
        raise AssertionError(
            "publish must seed, then replace what this run built, then validate "
            "the Hummingbird-only transaction, then publish -- in that order"
        )
    run = str(steps[assemble_step].get("run", ""))
    if "tools/publish_gate.py assemble" not in run:
        raise AssertionError("the replacement must be decided by publish_gate.py assemble")
    # The validation runs whenever the publish job runs; it must not be
    # skippable, and the image step must require it to have passed. Only an
    # early publication may carry on past a failure -- publishing nothing.
    if "if" in steps[validate]:
        raise AssertionError("the transaction validation must not be skippable")
    if "steps.validate.outcome == 'success'" not in str(steps[publish_step].get("if", "")):
        raise AssertionError("the image may publish only when the transaction validated")
    if str(steps[validate].get("continue-on-error", "false")) not in ("false", "${{ !inputs.final }}"):
        raise AssertionError("only an early publication may continue past a failed transaction")


def load_workflow(path: Path = REBUILD_WORKFLOW) -> dict:
    with path.open() as handle:
        return yaml.safe_load(handle)


def _cli_assemble(args: argparse.Namespace) -> int:
    seed_root, built_root = args.seed, args.built
    seed = source_names(sorted(seed_root.rglob("*.rpm")))
    everything = source_names(sorted(built_root.rglob("*.rpm")))
    built = publishable(everything)
    build_list = json.loads(args.build_list)
    # A bootstrap recipe that built is done: its output is for later waves.
    bootstrapped = sorted(
        name for name in build_list
        if name.endswith("-bootstrap") and any(
            BOOTSTRAP_RPM.search(Path(path).name) for path in everything)
    )
    assembly = assemble(
        seed=seed,
        built=built,
        build_list=[name for name in build_list if name not in bootstrapped],
        losers=set(json.loads(args.losers or "[]")),
    )
    apply(assembly, seed_root, built_root)
    report = assembly.report()
    report["bootstrapped"] = bootstrapped
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(summary(assembly))
    print(f"removed {len(assembly.remove)} seed RPMs, added {len(assembly.add)} built RPMs",
          file=sys.stderr)
    return 0


def _cli_failures(args: argparse.Namespace) -> int:
    names = json.loads(args.artifacts.read_text())
    print(json.dumps(failures_from_artifacts(
        json.loads(args.build_list), names, args.prefix, set(json.loads(args.losers or "[]")),
    )))
    return 0


def _cli_report(args: argparse.Namespace) -> int:
    names = json.loads(args.artifacts.read_text())
    losers = set(json.loads(args.losers or "[]"))
    failed = failures_from_artifacts(json.loads(args.build_list), names, args.prefix, losers)
    publish_report = json.loads(args.publish_report) if args.publish_report else None
    body = render_report(
        failed=failed,
        publish_result=args.publish_result,
        publish_report=publish_report,
        digest=args.digest,
        run_url=args.run_url,
    )
    args.output.write_text(body)
    args.failed_output.write_text(json.dumps(failed) + "\n")
    print(body)
    return 0


def artifact_pattern(wave: str, prefix: str) -> str:
    """download-artifact pattern for the RPMs of waves 0..wave (all if empty).

    Brace alternation needs two members to expand, so wave 0 is spelled out.
    """
    if wave == "":
        return f"{prefix}rpm-*"
    last = int(wave)
    if last == 0:
        return f"{prefix}rpm-s0-*"
    return f"{prefix}rpm-s{{{','.join(str(n) for n in range(last + 1))}}}-*"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    assemble_cmd = commands.add_parser("assemble")
    assemble_cmd.add_argument("--seed", type=Path, required=True)
    assemble_cmd.add_argument("--built", type=Path, required=True)
    assemble_cmd.add_argument("--build-list", required=True)
    assemble_cmd.add_argument("--losers", default="[]")
    assemble_cmd.add_argument("--report", type=Path, required=True)
    failures_cmd = commands.add_parser("failures")
    failures_cmd.add_argument("--build-list", required=True)
    failures_cmd.add_argument("--artifacts", type=Path, required=True)
    failures_cmd.add_argument("--prefix", default="")
    failures_cmd.add_argument("--losers", default="[]")
    report_cmd = commands.add_parser("report")
    report_cmd.add_argument("--build-list", required=True)
    report_cmd.add_argument("--artifacts", type=Path, required=True)
    report_cmd.add_argument("--prefix", default="")
    report_cmd.add_argument("--losers", default="[]")
    report_cmd.add_argument("--publish-result", default="")
    report_cmd.add_argument("--publish-report", default="")
    report_cmd.add_argument("--digest", default="")
    report_cmd.add_argument("--run-url", default="")
    report_cmd.add_argument("--output", type=Path, required=True)
    report_cmd.add_argument("--failed-output", type=Path, required=True)
    marker_cmd = commands.add_parser("marker")
    marker_cmd.add_argument("body", type=Path)
    pattern_cmd = commands.add_parser("pattern")
    pattern_cmd.add_argument("--wave", default="")
    pattern_cmd.add_argument("--prefix", default="")
    args = parser.parse_args(argv)
    if args.command == "pattern":
        print(f"pattern={artifact_pattern(args.wave, args.prefix)}")
        return 0
    if args.command == "report":
        return _cli_report(args)
    if args.command == "marker":
        print(json.dumps(failed_marker(args.body.read_text()), separators=(",", ":")))
        return 0
    if args.command == "assemble":
        return _cli_assemble(args)
    if args.command == "failures":
        return _cli_failures(args)
    assert_gate_enforced(load_workflow(), load_workflow(PUBLISH_WORKFLOW))
    print("publish gate enforced: every wave finishes, a failed package keeps its "
          "previous build, precedence runs, and the Hummingbird-only transaction "
          "validates before the image publishes")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
