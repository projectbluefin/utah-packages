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
        or a workflow change), names a recipe the inventory does not know, or
        moves the lock entry of a package config/bump-review-only.txt lists
        (its upstream bytes land only through a human-reviewed pull request).

        A diff that changes nothing but config/bump-holds.json -- every bumped
        package failed and was held -- prints {"packages": [],
        "holds_only": true}: there is nothing to build, and merging it is
        what stops the next daily bump re-proposing the held versions.

    bump_gate.py decide --bumped JSON --build-list JSON --failed JSON
                        --result RESULT --sha SHA --run-url URL --comment FILE
                        --failed-output FILE --hold-output FILE [--holds-only]
        exit 0 only when the build job succeeded, every bumped package was
        selected, and none failed (or, with --holds-only, when nothing was
        bumped and nothing was built). Otherwise exit 1 and write the pull
        request comment naming why, with a marker so a repeat of the same
        verdict on the same commit is not posted twice. --hold-output gets
        the bumped packages to hold, non-empty only when the failure is
        nothing but some bumped packages failing to build (see holdable).

    bump_gate.py trim --head SHA --base REV --hold JSON --run-url URL
        in a checkout of SHA, take the held packages' lock entries and
        recipe directories back to REV and record each in
        config/bump-holds.json with the version that failed. The result is a
        strict subset of the bump plus the holds, for the caller to commit,
        push on top of SHA, and gate again.

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
# Bumps the gate refused, by package and version. upstream_bump.py does not
# propose a held version again; a newer release, or a human deleting the
# entry, releases the hold.
HOLDS = "config/bump-holds.json"
# Packages whose upstream bytes never self-merge. A bump pins the SHA-512 of
# whatever the forge serves at bump time -- nothing but the forge vouches for
# it -- so a release-side compromise (a replaced release asset, a stolen
# maintainer account) of a package that runs as root or in the boot chain
# would be built, signed and published to latest within a day with no human
# looking. upstream_bump.py reports these for review instead of applying
# them, and the gate refuses a bump pull request that moves one of their lock
# entries, whoever pushed it. The file itself is outside ALLOWED, so no
# self-merging pull request can shorten it.
REVIEW_ONLY = "config/bump-review-only.txt"
# Exactly what bump-upstream-sources.yml commits (create-pull-request add-paths).
ALLOWED = (LOCK, HOLDS, "packages/")
MARKER = re.compile(r"<!-- bump-gate: sha=([0-9a-f]+) failed=(\[.*?\]) -->")


def disallowed(paths: list[str]) -> list[str]:
    """Changed paths outside what a bump commits."""
    return sorted(
        path for path in paths
        if path and path not in (LOCK, HOLDS) and not path.startswith("packages/")
    )


def parse_holds(text: str | None) -> dict[str, dict]:
    """{name: {"version", "run", ...}} from config/bump-holds.json text.

    Missing or empty is no holds. Anything malformed raises ValueError: a
    holds file nobody can read must stop the gate, not release every hold.
    """
    if not text or not text.strip():
        return {}
    document = json.loads(text)
    holds = document.get("holds") if isinstance(document, dict) else None
    if not isinstance(holds, dict):
        raise ValueError(f"{HOLDS}: expected an object with a \"holds\" object")
    for name, hold in holds.items():
        if not isinstance(hold, dict) or not isinstance(hold.get("version"), str) \
                or not hold["version"] or not isinstance(hold.get("run", ""), str):
            raise ValueError(f"{HOLDS}: hold for {name!r} needs a version string")
    return holds


def load_holds(root: Path) -> dict[str, dict]:
    path = root / HOLDS
    return parse_holds(path.read_text() if path.is_file() else None)


def parse_review_only(text: str | None) -> set[str]:
    """Package names from config/bump-review-only.txt text; `#` starts a comment."""
    names = set()
    for line in (text or "").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            names.add(stripped)
    return names


def load_review_only(root: Path) -> set[str]:
    path = root / REVIEW_ONLY
    return parse_review_only(path.read_text() if path.is_file() else None)


def moved(base: dict[str, dict], head: dict[str, dict]) -> set[str]:
    """Packages whose lock entry differs between base and head: the bytes moved."""
    return {name for name, entry in head.items() if base.get(name) != entry}


def dump_holds(holds: dict[str, dict]) -> str:
    return json.dumps({"holds": dict(sorted(holds.items()))}, indent=2) + "\n"


def locks_by_name(document: dict | None) -> dict[str, dict]:
    return {entry["name"]: entry for entry in (document or {}).get("packages", [])}


def bumped(base: dict[str, dict], head: dict[str, dict], paths: list[str]) -> list[str]:
    """Recipes whose lock entry or recipe directory changed between base and head."""
    names = moved(base, head)
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


def holds_only_verdict(bumped_raw: str, result: str) -> Verdict:
    """A holds-only diff: merge only if the plan named nothing and nothing built."""
    reasons = []
    if _names(bumped_raw) != []:
        reasons.append("a holds-only change must name no bumped packages")
    if result != "skipped":
        reasons.append(f"a holds-only change builds nothing, but the build job concluded `{result or 'unknown'}`")
    return Verdict(ok=not reasons, reasons=reasons)


def holdable(bumped_raw: str, build_list_raw: str, failed_raw: str, result: str) -> list[str]:
    """The bumped packages to hold so the rest can merge, or [] to hold none.

    Only when the failure is fully accounted for: the build ran to a verdict
    (success or failure, not cancelled or skipped), reported both outputs,
    selected every bumped package, and every failure is a bumped package
    while at least one other bumped package built. Anything else stays the
    old fail-closed verdict, with no trimming, for a human.
    """
    wanted = _names(bumped_raw)
    build_list = _names(build_list_raw)
    failed = _names(failed_raw)
    if not wanted or build_list is None or failed is None:
        return []
    if result not in ("success", "failure"):
        return []
    if set(wanted) - set(build_list) or not failed or set(failed) - set(wanted):
        return []
    return sorted(set(failed))


def marker(sha: str, failed: list[str]) -> str:
    return f"<!-- bump-gate: sha={sha} failed={json.dumps(sorted(failed), separators=(',', ':'))} -->"


def already_posted(text: str, sha: str, failed: list[str]) -> bool:
    """Whether `text` (every earlier comment) carries this exact verdict's marker."""
    want = (sha, sorted(failed))
    return any(
        (match.group(1), sorted(json.loads(match.group(2)))) == want
        for match in MARKER.finditer(text or "")
    )


def comment(result: Verdict, sha: str, run_url: str, held: list[str] | None = None) -> str:
    if held:
        after = (
            "Nothing was merged or published. The gate is holding "
            + ", ".join(f"`{n}`" for n in held)
            + f" in `{HOLDS}` at the version that failed, taking those packages "
            "out of this pull request, and gating the rest again on a new commit. "
            "A held version is not proposed again; a newer upstream release "
            "retries it, and deleting its entry (in a pull request that also "
            "fixes the recipe) releases it sooner."
        )
    else:
        after = (
            "Nothing was merged or published. The next daily bump retries the gate; "
            "a fix to a failing recipe goes in its own pull request, and this one "
            "can then be gated again by dispatching `bump-upstream-gate.yml` on "
            "`bump/upstream-sources` with this pull request number."
        )
    lines = [
        f"The bump gate did not merge this pull request at `{sha[:12]}`.",
        "",
        *[f"- {reason}" for reason in result.reasons],
        "",
        f"Build: {run_url}",
        "",
        after,
        "",
        marker(sha, result.failed),
    ]
    return "\n".join(lines) + "\n"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def _show(rev: str, path: str) -> str | None:
    try:
        return _git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None


def _lock_at(rev: str) -> dict | None:
    text = _show(rev, LOCK)
    return json.loads(text) if text is not None else None


def trim(base: str, head: str, held: list[str], run_url: str) -> dict[str, dict]:
    """Take the held packages out of the checkout of `head`; record their holds.

    Their lock entries and recipe directories return to `base` exactly, so
    what is left is a subset of what the gate already judged. Returns the
    holds written.
    """
    head_lock = _lock_at(head)
    if head_lock is None:
        raise ValueError(f"{head} has no {LOCK}")
    base_entries = locks_by_name(_lock_at(base))
    head_entries = locks_by_name(head_lock)
    unknown = sorted(set(held) - set(head_entries))
    if unknown:
        raise ValueError(f"cannot hold what the head lock does not carry: {', '.join(unknown)}")
    packages = []
    for entry in head_lock.get("packages", []):
        if entry["name"] not in held:
            packages.append(entry)
        elif entry["name"] in base_entries:
            packages.append(base_entries[entry["name"]])
    head_lock["packages"] = packages
    (ROOT / LOCK).write_text(json.dumps(head_lock, indent=2) + "\n")
    for name in held:
        directory = f"packages/{name}"
        _git("rm", "-r", "-q", "--ignore-unmatch", "--", directory)
        if _git("ls-tree", "-d", "--name-only", base, "--", directory).strip():
            _git("checkout", base, "--", directory)

    holds = parse_holds((ROOT / HOLDS).read_text() if (ROOT / HOLDS).is_file() else None)
    for name in held:
        holds[name] = {"version": head_entries[name]["version"], "run": run_url}
    (ROOT / HOLDS).write_text(dump_holds(holds))
    return holds


def _cli_plan(args: argparse.Namespace) -> int:
    paths = _git("diff", "--name-only", args.base, args.head).splitlines()
    bad = disallowed(paths)
    if bad:
        print("a bump may change only the lock and the recipes; this one also changes:",
              file=sys.stderr)
        for path in bad:
            print(f"  {path}", file=sys.stderr)
        return 1
    try:
        parse_holds(_show(args.head, HOLDS))
    except (ValueError, json.JSONDecodeError) as error:
        print(f"the holds file does not parse: {error}", file=sys.stderr)
        return 1
    head_lock, base_lock = _lock_at(args.head), _lock_at(args.base)
    head = locks_by_name(head_lock)
    base = locks_by_name(base_lock)
    # Read at the head: the list a human last reviewed. A bump that edits the
    # list is already refused above as a disallowed path.
    guarded = sorted(moved(base, head) & parse_review_only(_show(args.head, REVIEW_ONLY)))
    if guarded:
        print(f"{REVIEW_ONLY} lists these, so their upstream bytes land only through "
              f"a human-reviewed pull request, never this gate: {', '.join(guarded)}",
              file=sys.stderr)
        return 1
    names = bumped(base, head, paths)
    unknown = sorted(set(names) - set(head))
    if unknown:
        print(f"not in the head inventory, so the gate cannot build them: {', '.join(unknown)}",
              file=sys.stderr)
        return 1
    if not names:
        # The lock may differ in bytes (a trim rewrites it) but not in content.
        changed = {path for path in paths if path}
        if HOLDS in changed and changed <= {HOLDS, LOCK} and head_lock == base_lock:
            print(json.dumps({"packages": [], "holds_only": True}, separators=(",", ":")))
            return 0
        print("the diff changes no recipe; nothing to gate", file=sys.stderr)
        return 1
    print(json.dumps({"packages": names, "holds_only": False}, separators=(",", ":")))
    return 0


def _cli_decide(args: argparse.Namespace) -> int:
    if args.holds_only:
        result = holds_only_verdict(args.bumped, args.result)
        held: list[str] = []
    else:
        result = verdict(args.bumped, args.build_list, args.failed, args.result)
        held = holdable(args.bumped, args.build_list, args.failed, args.result)
    if result.ok:
        print("only holds changed; nothing to build" if args.holds_only
              else f"every bumped package built: {args.bumped}")
        return 0
    for reason in result.reasons:
        print(f"::error title=bump gate::{reason}")
    args.comment.write_text(comment(result, args.sha, args.run_url, held))
    args.failed_output.write_text(json.dumps(result.failed))
    args.hold_output.write_text(json.dumps(held))
    return 1


def _cli_trim(args: argparse.Namespace) -> int:
    held = _names(args.hold)
    if not held:
        print("nothing to hold", file=sys.stderr)
        return 1
    try:
        holds = trim(args.base, args.head, held, args.run_url)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    for name in held:
        print(f"held {name} at {holds[name]['version']}")
    return 0


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
    decide_cmd.add_argument("--hold-output", type=Path, required=True)
    decide_cmd.add_argument("--holds-only", action="store_true")
    trim_cmd = commands.add_parser("trim")
    trim_cmd.add_argument("--base", required=True)
    trim_cmd.add_argument("--head", required=True)
    trim_cmd.add_argument("--hold", required=True)
    trim_cmd.add_argument("--run-url", required=True)
    seen_cmd = commands.add_parser("seen")
    seen_cmd.add_argument("--sha", required=True)
    seen_cmd.add_argument("--failed", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        return _cli_plan(args)
    if args.command == "decide":
        return _cli_decide(args)
    if args.command == "trim":
        return _cli_trim(args)
    return 0 if already_posted(sys.stdin.read(), args.sha, json.loads(args.failed)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
