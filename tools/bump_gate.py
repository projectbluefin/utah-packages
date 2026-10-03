#!/usr/bin/env python3
"""Decide whether the daily upstream bump may merge itself.

.github/workflows/bump-upstream-gate.yml builds the packages a bump pull
request changed, through rebuild-rpms.yml itself, and merges the pull request
only when every one of them built. This file holds the decisions, so they
are tested rather than restated in shell:

    bump_gate.py plan --base REV --head REV
        print {"packages": [...]}: the recipes the bump changed. Exits 1 when
        the diff touches anything a bump may not (only the lock and the
        recipes are allowed: an automatic merge must never carry a pipeline
        or a workflow change), or names a recipe the inventory does not know.

    bump_gate.py decide --bumped JSON --build-list JSON --failed JSON
                        --result RESULT --sha SHA --run-url URL --comment FILE
        exit 0 only when the build job succeeded, every bumped package was
        selected, and none failed. Otherwise exit 1 and write the pull
        request comment naming why, with a marker so a repeat of the same
        verdict on the same commit is not posted twice.

    bump_gate.py seen --sha SHA --failed JSON < comment-bodies
        exit 0 when a comment with this exact verdict was already posted.
        Reads the pull request's comment bodies as raw text on stdin.

Fail closed throughout: anything the gate cannot account for -- a missing
output, a skipped build, a package that was never selected -- is a reason
not to merge.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = "config/upstream-sources.json"
# Exactly what bump-upstream-sources.yml commits (create-pull-request add-paths).
ALLOWED = (LOCK, "packages/")
MARKER = re.compile(r"<!-- bump-gate: sha=([0-9a-f]+) failed=(\[.*?\]) -->")


def disallowed(paths: list[str]) -> list[str]:
    """Changed paths outside what a bump commits."""
    return sorted(
        path for path in paths
        if path and path != LOCK and not path.startswith("packages/")
    )


def locks_by_name(document: dict | None) -> dict[str, dict]:
    return {entry["name"]: entry for entry in (document or {}).get("packages", [])}


def bumped(base: dict[str, dict], head: dict[str, dict], paths: list[str]) -> list[str]:
    """Recipes whose lock entry or recipe directory changed between base and head."""
    names = {name for name, entry in head.items() if base.get(name) != entry}
    names |= {name for name in base if name not in head}
    for path in paths:
        parts = path.split("/")
        if parts[0] == "packages" and len(parts) > 2:
            names.add(parts[1])
    return sorted(names)


@dataclass
class Verdict:
    ok: bool
    failed: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _names(raw: str) -> list[str] | None:
    """A JSON array of names, or None when the output is missing or malformed."""
    try:
        value = json.loads(raw or "null")
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value


def verdict(bumped_raw: str, build_list_raw: str, failed_raw: str, result: str) -> Verdict:
    """Merge only when every bumped package was built by a successful run."""
    wanted = _names(bumped_raw)
    build_list = _names(build_list_raw)
    failed = _names(failed_raw)
    reasons = []
    if not wanted:
        reasons.append("no bumped packages were named, so there is nothing the build proved")
    if result != "success":
        reasons.append(f"the build job concluded `{result or 'unknown'}`, not `success`")
    if build_list is None:
        reasons.append("the build did not report which packages it selected")
    if failed is None:
        reasons.append("the build did not report which packages failed")
    names = sorted(set(failed or []) & set(wanted or [])) if failed else []
    if names:
        reasons.append("bumped packages failed to build: " + ", ".join(f"`{n}`" for n in names))
    if failed:
        other = sorted(set(failed) - set(wanted or []))
        if other:
            reasons.append("other packages failed in the same run: " + ", ".join(f"`{n}`" for n in other))
    if wanted and build_list is not None:
        missing = sorted(set(wanted) - set(build_list))
        if missing:
            reasons.append(
                "bumped packages were not selected, so nothing built them: "
                + ", ".join(f"`{n}`" for n in missing)
            )
    return Verdict(ok=not reasons, failed=sorted(failed or []), reasons=reasons)


def marker(sha: str, failed: list[str]) -> str:
    return f"<!-- bump-gate: sha={sha} failed={json.dumps(sorted(failed), separators=(',', ':'))} -->"


def already_posted(text: str, sha: str, failed: list[str]) -> bool:
    """Whether `text` (every earlier comment) carries this exact verdict's marker."""
    want = (sha, sorted(failed))
    return any(
        (match.group(1), sorted(json.loads(match.group(2)))) == want
        for match in MARKER.finditer(text or "")
    )


def comment(result: Verdict, sha: str, run_url: str) -> str:
    lines = [
        f"The bump gate did not merge this pull request at `{sha[:12]}`.",
        "",
        *[f"- {reason}" for reason in result.reasons],
        "",
        f"Build: {run_url}",
        "",
        "Nothing was merged or published. The next daily bump retries the gate; "
        "a fix to a failing recipe goes in its own pull request, and this one "
        "can then be gated again by dispatching `bump-upstream-gate.yml` on "
        "`bump/upstream-sources` with this pull request number.",
        "",
        marker(sha, result.failed),
    ]
    return "\n".join(lines) + "\n"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def _lock_at(rev: str) -> dict | None:
    try:
        return json.loads(_git("show", f"{rev}:{LOCK}"))
    except subprocess.CalledProcessError:
        return None


def _cli_plan(args: argparse.Namespace) -> int:
    paths = _git("diff", "--name-only", args.base, args.head).splitlines()
    bad = disallowed(paths)
    if bad:
        print("a bump may change only the lock and the recipes; this one also changes:",
              file=sys.stderr)
        for path in bad:
            print(f"  {path}", file=sys.stderr)
        return 1
    head = locks_by_name(_lock_at(args.head))
    names = bumped(locks_by_name(_lock_at(args.base)), head, paths)
    unknown = sorted(set(names) - set(head))
    if unknown:
        print(f"not in the head inventory, so the gate cannot build them: {', '.join(unknown)}",
              file=sys.stderr)
        return 1
    if not names:
        print("the diff changes no recipe; nothing to gate", file=sys.stderr)
        return 1
    print(json.dumps({"packages": names}, separators=(",", ":")))
    return 0


def _cli_decide(args: argparse.Namespace) -> int:
    result = verdict(args.bumped, args.build_list, args.failed, args.result)
    if result.ok:
        print(f"every bumped package built: {args.bumped}")
        return 0
    for reason in result.reasons:
        print(f"::error title=bump gate::{reason}")
    args.comment.write_text(comment(result, args.sha, args.run_url))
    args.failed_output.write_text(json.dumps(result.failed))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan")
    plan_cmd.add_argument("--base", required=True)
    plan_cmd.add_argument("--head", required=True)
    decide_cmd = commands.add_parser("decide")
    decide_cmd.add_argument("--bumped", required=True)
    decide_cmd.add_argument("--build-list", default="")
    decide_cmd.add_argument("--failed", default="")
    decide_cmd.add_argument("--result", default="")
    decide_cmd.add_argument("--sha", required=True)
    decide_cmd.add_argument("--run-url", required=True)
    decide_cmd.add_argument("--comment", type=Path, required=True)
    decide_cmd.add_argument("--failed-output", type=Path, required=True)
    seen_cmd = commands.add_parser("seen")
    seen_cmd.add_argument("--sha", required=True)
    seen_cmd.add_argument("--failed", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _cli_plan(args)
    if args.command == "decide":
        return _cli_decide(args)
    return 0 if already_posted(sys.stdin.read(), args.sha, json.loads(args.failed)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
