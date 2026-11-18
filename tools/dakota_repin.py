#!/usr/bin/env python3
"""Move the Dakota pin in config/dakota.json to Dakota's newest publish run.

refresh-dakota.yml runs this. The workflow is plumbing (``gh``, ``skopeo``,
``tools/audit_dakota.py``); what it decides lives here, where it is under test:

    dakota_repin.py resolve --out work/repin.json
        Find the newest successful publish.yml run on Dakota's ``testing``
        branch that still has its ``sbom-dakota`` and ``digest-default``
        artifacts, prove its commit is on ``testing``, read the image digest
        from ``digest-default`` and the junction refs from the ``.bst`` files at
        that commit, and write the proposed ``source`` with ``changed``: false
        when it names the revision and digest config/dakota.json already pins.
    dakota_repin.py apply work/repin.json
        Write the proposed ``source`` into config/dakota.json, nothing else.
    dakota_repin.py checkout --into work/src
        Fetch Dakota, gnome-build-meta, freedesktop-sdk and
        freedesktop-sdk-extra at the commits config/dakota.json pins, for
        ``audit_dakota.py --import-build-facts``.
    dakota_repin.py pr-body --before OLD.json --after NEW.json --repin work/repin.json
        The pull request body: the pin move, the disposition counts before
        and after, the version drift summary, the patch and option summary and
        any contract problem.

The revision and digest come from Dakota's own ``digest-default`` record of
the run, never from the SBOM or the image being checked: ``--import-sbom``
then refuses an SBOM of another revision and a layout without that digest, so
both checks still compare two independent sources.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit_dakota import (  # noqa: E402
    DAKOTA_PROJECT,
    DISPOSITIONS,
    FDSDK_EXTRA_PROJECT,
    FDSDK_PROJECT,
    GBM_PROJECT,
    contract_problems,
    expected_build_refs,
    junction_commit,
    load_pin,
    read_snapshot,
)

ROOT = Path(__file__).resolve().parent.parent
DAKOTA_REPO = "projectbluefin/dakota"
DAKOTA_IMAGE = "ghcr.io/projectbluefin/dakota"
BRANCH = "testing"
SBOM_ARTIFACT = "sbom-dakota"
DIGEST_ARTIFACT = "digest-default"
JUNCTIONS = ("gnome-build-meta.bst", "freedesktop-sdk.bst")
# How many recent successful runs to look through for one whose artifacts
# have not expired yet.
RUN_WINDOW = 20
# Drift rows listed in the pull request body; the full list is in the report.
BODY_DRIFT_ROWS = 40

# Where --import-build-facts reads each project's .bst files from.
PROJECT_REMOTES = {
    DAKOTA_PROJECT: "https://github.com/projectbluefin/dakota.git",
    GBM_PROJECT: "https://gitlab.gnome.org/GNOME/gnome-build-meta.git",
    FDSDK_PROJECT: "https://gitlab.com/freedesktop-sdk/freedesktop-sdk.git",
    FDSDK_EXTRA_PROJECT: "https://gitlab.com/freedesktop-sdk/freedesktop-sdk-extra.git",
}

_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


# --- Run selection ---------------------------------------------------------------

def candidate_runs(runs: list[dict]) -> list[dict]:
    """Successful publish runs of ``testing``, newest first.

    A merge-queue publish (``gh-readonly-queue/testing/...``) pushes only a
    ``:SHA`` tag and its commit may never land, so only ``testing`` itself
    counts; so does a pull request trigger, which publish.yml skips anyway.
    """
    out = [run for run in runs
           if run.get("head_branch") == BRANCH
           and run.get("status") == "completed"
           and run.get("conclusion") == "success"
           and run.get("event") != "pull_request"
           and _SHA.fullmatch(run.get("head_sha") or "")]
    return sorted(out, key=lambda run: (run.get("created_at") or "", run["id"]), reverse=True)


def has_artifacts(artifacts: list[dict]) -> bool:
    """Both artifacts the re-pin reads are present and unexpired."""
    live = {a.get("name") for a in artifacts if not a.get("expired")}
    return {SBOM_ARTIFACT, DIGEST_ARTIFACT} <= live


def select_run(runs: list[dict], artifacts_of: Callable[[int], list[dict]],
               on_branch: Callable[[str], bool]) -> dict | None:
    """The newest candidate run with both artifacts whose commit is on ``testing``."""
    for run in candidate_runs(runs)[:RUN_WINDOW]:
        if not has_artifacts(artifacts_of(run["id"])):
            continue
        if not on_branch(run["head_sha"]):
            print(f"skipping run {run['id']}: {run['head_sha']} is not on {BRANCH}",
                  file=sys.stderr)
            continue
        return run
    return None


def compare_on_branch(compare: dict) -> bool:
    """``compare/<sha>...testing``: the commit is ``testing`` or behind it."""
    return compare.get("status") in ("identical", "ahead")


def verify_digest_record(record: dict, run: dict) -> str:
    """The default image digest from ``digest-default``, checked against the run."""
    problems = []
    if record.get("schema") != 1:
        problems.append(f"schema {record.get('schema')!r}")
    if record.get("variant") != "default":
        problems.append(f"variant {record.get('variant')!r}")
    if record.get("image") != DAKOTA_IMAGE:
        problems.append(f"image {record.get('image')!r}")
    if record.get("sha") != run["head_sha"]:
        problems.append(f"sha {record.get('sha')!r} is not the run's {run['head_sha']}")
    digest = record.get("digest") or ""
    if not _DIGEST.fullmatch(digest):
        problems.append(f"digest {digest!r}")
    if problems:
        raise ValueError(f"run {run['id']} {DIGEST_ARTIFACT}: " + "; ".join(problems))
    return digest


def junction_pin(bst_text: str) -> str:
    """A junction element's ref, in config/dakota.json's ``junctions`` shape.

    The ref alone when it already names the tracked branch
    (``freedesktop-sdk-26.08.4-0-g114ae90...`` tracking
    ``freedesktop-sdk-26.08*``), otherwise ``<track> <ref>``
    (``gnome-51 51.1-36-g8a89846...``): the bare ``git describe`` of
    gnome-build-meta does not say which branch it follows.
    """
    node = yaml.safe_load(bst_text) or {}
    if node.get("kind") != "junction":
        raise ValueError("not a junction element")
    source = next((s for s in node.get("sources") or []
                   if s.get("kind") in ("git_repo", "git") and s.get("ref")), None)
    if source is None:
        raise ValueError("junction has no git source with a ref")
    ref = str(source["ref"])
    track = str(source.get("track") or "").rstrip("*")
    if not track or ref.startswith(track):
        return ref
    return f"{source['track']} {ref}"


def proposed_source(current: dict, run: dict, digest: str, junctions: dict[str, str]) -> dict:
    """``current`` with the run's revision, SBOM, digest and junctions."""
    source = dict(current)
    source["revision"] = run["head_sha"]
    source["publish_run"] = run["id"]
    source["sbom"] = f"{DAKOTA_REPO} publish.yml run {run['id']}, artifact {SBOM_ARTIFACT}"
    source["image_digest"] = digest
    source["junctions"] = {name: junctions[name] for name in JUNCTIONS}
    return source


def pin_changed(current: dict, proposed: dict) -> bool:
    return (current.get("revision"), current.get("image_digest")) != (
        proposed["revision"], proposed["image_digest"])


# --- GitHub plumbing ---------------------------------------------------------------

def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def _gh_json(path: str):
    return json.loads(_gh("api", path))


def resolve(current: dict, gh_json=_gh_json, gh=_gh) -> dict:
    runs = gh_json(f"repos/{DAKOTA_REPO}/actions/workflows/publish.yml/runs"
                   f"?branch={BRANCH}&status=success&per_page=50")["workflow_runs"]
    run = select_run(
        runs,
        lambda run_id: gh_json(f"repos/{DAKOTA_REPO}/actions/runs/{run_id}/artifacts"
                               f"?per_page=100")["artifacts"],
        lambda sha: compare_on_branch(gh_json(f"repos/{DAKOTA_REPO}/compare/{sha}...{BRANCH}")),
    )
    if run is None:
        raise SystemExit(f"error: no successful {BRANCH} publish run of {DAKOTA_REPO} "
                         f"has {SBOM_ARTIFACT} and {DIGEST_ARTIFACT}")
    with tempfile.TemporaryDirectory() as tmp:
        gh("run", "download", str(run["id"]), "-R", DAKOTA_REPO, "-n", DIGEST_ARTIFACT, "-D", tmp)
        record = json.loads((Path(tmp) / "digest.json").read_text())
    digest = verify_digest_record(record, run)
    junctions = {
        name: junction_pin(gh("api", "-H", "Accept: application/vnd.github.raw",
                              f"repos/{DAKOTA_REPO}/contents/elements/{name}?ref={run['head_sha']}"))
        for name in JUNCTIONS
    }
    source = proposed_source(current, run, digest, junctions)
    return {"changed": pin_changed(current, source), "run": run["id"],
            "run_url": run.get("html_url"), "source": source}


def apply(pin_path: Path, source: dict) -> None:
    """Replace ``source`` only; the rest of the file keeps its shape."""
    pin = json.loads(pin_path.read_text())
    pin["source"] = source
    pin_path.write_text(json.dumps(pin, indent=2) + "\n")
    load_pin(pin_path)


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True)


def fetch_commit(url: str, commit: str, dest: Path, git=_git) -> None:
    """A shallow checkout of one commit, without the rest of the history."""
    dest.mkdir(parents=True, exist_ok=True)
    git("-C", str(dest), "init", "-q")
    git("-C", str(dest), "fetch", "-q", "--depth", "1", url, commit)
    git("-C", str(dest), "checkout", "-q", "FETCH_HEAD")


def checkout_projects(source: dict, dest: Path, git=_git) -> dict[str, Path]:
    """The four projects at the pinned commits, gnome-build-meta first.

    freedesktop-sdk-extra's commit is read from gnome-build-meta's junction
    element, so gnome-build-meta has to be on disk before it.
    """
    commits = {DAKOTA_PROJECT: source["revision"]}
    for name, project in (("gnome-build-meta.bst", GBM_PROJECT),
                          ("freedesktop-sdk.bst", FDSDK_PROJECT)):
        commit = junction_commit((source.get("junctions") or {}).get(name, ""))
        if not commit or not _SHA.fullmatch(commit):
            raise ValueError(f"source.junctions {name} names no full commit")
        commits[project] = commit
    dirs = {project: dest / project for project in PROJECT_REMOTES}
    for project in (DAKOTA_PROJECT, GBM_PROJECT, FDSDK_PROJECT):
        fetch_commit(PROJECT_REMOTES[project], commits[project], dirs[project], git)
    extra = expected_build_refs({"source": source}, dirs[GBM_PROJECT])[FDSDK_EXTRA_PROJECT]
    if not _SHA.fullmatch(extra):
        raise ValueError(f"freedesktop-sdk-extra ref {extra} is not a full commit")
    fetch_commit(PROJECT_REMOTES[FDSDK_EXTRA_PROJECT], extra, dirs[FDSDK_EXTRA_PROJECT], git)
    return dirs


# --- Pull request body --------------------------------------------------------------

def _short(value: str | None) -> str:
    return (value or "")[:12]


def _drift_totals(report: dict) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in report.get("drift", []):
        totals[item["classification"]] = totals.get(item["classification"], 0) + 1
    return totals


def _intent_totals(report: dict) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in report.get("build_intent") or []:
        totals[row["classification"]] = totals.get(row["classification"], 0) + 1
    return totals


def render_pr_body(before: dict, after: dict, old_source: dict, repin: dict,
                   problems: list[str]) -> str:
    new = repin["source"]
    url = new.get("url", f"https://github.com/{DAKOTA_REPO}")
    lines = [
        f"Moves the Dakota pin to the newest successful `{BRANCH}` publish run "
        f"and rebuilds the element snapshot from its SBOM and image.",
        "",
        "| | before | after |",
        "| --- | --- | --- |",
        f"| revision | `{_short(old_source.get('revision'))}` | "
        f"[`{_short(new['revision'])}`]({url}/commit/{new['revision']}) |",
        f"| publish run | {old_source.get('publish_run')} | "
        f"[{new['publish_run']}]({url}/actions/runs/{new['publish_run']}) |",
        f"| image digest | `{_short(old_source.get('image_digest', '').removeprefix('sha256:'))}` | "
        f"`{_short(new['image_digest'].removeprefix('sha256:'))}` |",
    ]
    for name in JUNCTIONS:
        lines.append(f"| `{name}` | `{(old_source.get('junctions') or {}).get(name, '')}` | "
                     f"`{new['junctions'][name]}` |")
    lines += [
        "",
        f"[Changes on Dakota]({url}/compare/{old_source.get('revision')}...{new['revision']})",
        "",
        "## Dispositions",
        "",
        "| disposition | before | after | change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for disposition in DISPOSITIONS:
        old = before["counts"].get(disposition, 0)
        now = after["counts"].get(disposition, 0)
        lines.append(f"| {disposition} | {old} | {now} | {now - old:+d} |")
    lines.append(f"| **total** | {sum(before['counts'].values())} | "
                 f"{sum(after['counts'].values())} | "
                 f"{sum(after['counts'].values()) - sum(before['counts'].values()):+d} |")

    old_queue = {k: len(v) for k, v in before.get("import_queue", {}).items()}
    new_queue = {k: len(v) for k, v in after.get("import_queue", {}).items()}
    lines += ["", "Import queue (source packages): " + ", ".join(
        f"{k} {old_queue.get(k, 0)} -> {new_queue.get(k, 0)}" for k in sorted(new_queue)) + ".",
        f"Stale mappings: {len(before.get('stale_mappings', []))} -> "
        f"{len(after.get('stale_mappings', []))}.", ""]

    old_drift, new_drift = _drift_totals(before), _drift_totals(after)
    lines += ["## Version drift of factory recipes", "",
              "| classification | before | after |", "| --- | ---: | ---: |"]
    for classification in sorted(set(old_drift) | set(new_drift)):
        lines.append(f"| {classification} | {old_drift.get(classification, 0)} | "
                     f"{new_drift.get(classification, 0)} |")
    review = [d for d in after.get("drift", []) if d["classification"] == "needs_review"]
    if review:
        lines += ["", "<details><summary>needs_review after the re-pin "
                  f"({len(review)})</summary>", "",
                  "| package | factory | Dakota | element |", "| --- | --- | --- | --- |"]
        for item in review[:BODY_DRIFT_ROWS]:
            lines.append(f"| {item['rpm']} | {item['factory_version'] or '—'} | "
                         f"{item['dakota_version'] or '—'} | `{item['element']}` |")
        if len(review) > BODY_DRIFT_ROWS:
            lines.append(f"| … | | | {len(review) - BODY_DRIFT_ROWS} more in the report |")
        lines += ["", "</details>"]

    old_intent = _intent_totals(before)
    new_intent = _intent_totals(after)
    if new_intent:
        lines += ["", "## Patches and build options of factory recipes", "",
                  "| classification | before | after |", "| --- | ---: | ---: |"]
        for classification in sorted(set(old_intent) | set(new_intent)):
            lines.append(f"| {classification} | {old_intent.get(classification, 0)} | "
                         f"{new_intent.get(classification, 0)} |")

    lines += ["", "## Contract", ""]
    if problems:
        lines.append("`just dakota-audit` fails on this pin until these are fixed on this "
                     "branch (an override, alias or config entry names an element the new "
                     "snapshot dropped or renamed):")
        lines.append("")
        lines += [f"- {problem}" for problem in problems]
    else:
        lines.append("- the mapping names exactly the snapshot's elements; every reviewer "
                     "decision names one of them.")
    lines += [
        "",
        "Generated by `refresh-dakota.yml` with `tools/dakota_repin.py` and "
        "`tools/audit_dakota.py --import-sbom ... --refresh`. Review the "
        "`config/dakota.json` diff for dispositions that moved; this workflow never "
        "merges. The full report is in the `dakota-audit` artifact of this pull "
        "request's `validate.yml` run. See `docs/skills/dakota-parity.md`.",
    ]
    return "\n".join(lines) + "\n"


# --- CLI ------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pin", type=Path, default=ROOT / "config" / "dakota.json")
    sub = parser.add_subparsers(dest="command", required=True)
    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("--out", type=Path, required=True)
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("repin", type=Path)
    p_checkout = sub.add_parser("checkout")
    p_checkout.add_argument("--into", type=Path, required=True)
    p_body = sub.add_parser("pr-body")
    p_body.add_argument("--before", type=Path, required=True,
                        help="audit report JSON of the old pin")
    p_body.add_argument("--after", type=Path, required=True,
                        help="audit report JSON of the new pin")
    p_body.add_argument("--repin", type=Path, required=True)
    p_body.add_argument("--old-pin", type=Path, required=True,
                        help="config/dakota.json before the re-pin")
    p_body.add_argument("--snapshot", type=Path, default=ROOT / "config" / "dakota-elements.tsv")
    args = parser.parse_args(argv)

    if args.command == "resolve":
        current = json.loads(args.pin.read_text())["source"]
        result = resolve(current)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n")
        state = "moves" if result["changed"] else "is unchanged at"
        print(f"pin {state} {result['source']['revision']} "
              f"(run {result['run']}, {result['source']['image_digest']})")
        return 0
    if args.command == "checkout":
        dirs = checkout_projects(load_pin(args.pin)["source"], args.into)
        for project, path in dirs.items():
            print(f"{project}: {path}")
        return 0
    if args.command == "apply":
        apply(args.pin, json.loads(args.repin.read_text())["source"])
        print(f"source written: {args.pin}")
        return 0
    repin = json.loads(args.repin.read_text())
    pin = load_pin(args.pin)
    problems = contract_problems(pin, read_snapshot(args.snapshot))
    sys.stdout.write(render_pr_body(
        json.loads(args.before.read_text()), json.loads(args.after.read_text()),
        json.loads(args.old_pin.read_text())["source"], repin, problems))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
