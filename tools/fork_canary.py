#!/usr/bin/env python3
"""Decisions for running Canary on a fork pull request a maintainer reviewed.

A fork pull request cannot publish the canary image: its token has no
``packages: write``. ``canary-fork-pr.yml`` is the maintainer's button. It copies
the pull request's head commit into ``canary/pr-<N>`` in this repository and
dispatches ``canary.yml`` there, so the required ``Canary`` check lands on the
very commit the pull request is at.

This module only decides whether that copy is allowed, and whether a passed
copy proves the pull request's current head. It never runs, builds or checks out
the pull request's code; the workflow that calls it does not either.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

BRANCH_PREFIX = "canary/pr-"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
# What a push with GITHUB_TOKEN cannot carry, and what must never come from a
# fork through this path: the workflows themselves. canary.yml and the workflows
# it calls run with packages: write, so they stay the maintainer's own.
PROTECTED_PREFIX = ".github/"
# The pulls/N/files API lists at most this many files, so a larger pull request
# could hide a .github/ change from the check below.
FILES_API_LIMIT = 3000
# The only base a proof carries over on, and where canary.yml's checkout
# (fetch-depth: 0) keeps it.
BASE_REF = "main"
BASE_GIT_REF = "refs/remotes/origin/main"
# What a merge of main alone moves in a diff: the blob a hunk applies to and the
# line it starts on. The hunk's own lines, context included, stay.
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")

Git = Callable[[Sequence[str]], str]


def _git(args: Sequence[str]) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, check=True, encoding="utf-8", errors="surrogateescape",
    ).stdout


class Refused(Exception):
    """The copy is not allowed; the message says why and what to do."""


def branch_for(pr: int) -> str:
    return f"{BRANCH_PREFIX}{pr}"


def decide(pr: dict, files: list[str], repository: str, reviewed_sha: str) -> str:
    """Return ``copy`` or ``skip``; raise ``Refused`` with the reason otherwise."""
    if not FULL_SHA.fullmatch(reviewed_sha):
        raise Refused(
            "head_sha must be the full 40-character commit you reviewed, "
            f"got {reviewed_sha!r}"
        )
    if pr.get("state") != "open":
        raise Refused(f"pull request is {pr.get('state')}, not open")
    if (pr.get("base") or {}).get("ref") != "main":
        raise Refused("pull request does not target main")
    head = pr.get("head") or {}
    if head.get("sha") != reviewed_sha:
        raise Refused(
            f"the pull request head is {head.get('sha')}, not the {reviewed_sha} "
            "you reviewed: it moved. Review the new commits, then run this again "
            "with the new head"
        )
    repo = head.get("repo")
    if repo is None:
        raise Refused("the fork this pull request came from was deleted")
    if repo.get("full_name") == repository:
        return "skip"
    changed = pr.get("changed_files")
    if not isinstance(changed, int) or changed >= FILES_API_LIMIT:
        raise Refused(
            f"the pull request changes {changed} files; GitHub lists at most "
            f"{FILES_API_LIMIT}, so its .github/ changes cannot all be "
            "checked. A maintainer must review it and push the branch by hand"
        )
    protected = sorted({name for name in files if name.startswith(PROTECTED_PREFIX)})
    if protected:
        raise Refused(
            f"the pull request changes {', '.join(protected)}. Workflow changes "
            "never run with this repository's credentials from a fork; a "
            "maintainer must review them and push the branch by hand"
        )
    return "copy"


def proven_heads(runs: list[dict], pr: int) -> list[str]:
    """The commits a maintainer-run Canary passed on for this pull request, newest first.

    Only a run of canary.yml dispatched on this repository's own ``canary/pr-<N>``
    branch counts, completed with success. A fork cannot create that branch or
    dispatch that run, so it is not something a pull request can claim for itself.
    """
    branch = branch_for(pr)
    heads: list[str] = []
    for run in sorted(runs, key=lambda run: run.get("created_at") or "", reverse=True):
        sha = run.get("head_sha")
        if (
            run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == branch
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and isinstance(sha, str)
            and FULL_SHA.fullmatch(sha)
            and sha not in heads
        ):
            heads.append(sha)
    return heads


def has_proof(runs: list[dict], pr: int, head_sha: str) -> bool:
    """Whether a maintainer-run Canary already passed on exactly this commit."""
    return head_sha in proven_heads(runs, pr)


def pr_patch(head: str, base: str, git: Git = _git) -> str:
    """The pull request's own diff at ``head``: against its merge base with ``base``.

    Every byte of every hunk stays, binary payloads and mode changes included; only
    the ``index`` lines and hunk positions go, because merging main moves those
    without touching what the pull request changes.
    """
    patch = git(["diff", "--no-renames", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--binary", "--full-index", f"{base}...{head}"])
    return "\n".join(
        "@@" if HUNK_HEADER.match(line) else line
        for line in patch.split("\n")
        if not line.startswith("index ")
    )


def carry_problem(proven: str, head: str, base: str = BASE_GIT_REF, git: Git = _git) -> str | None:
    """Why a Canary that passed on ``proven`` does not prove ``head``; None when it does.

    It does only when every commit ``head`` adds after ``proven`` that is not on
    ``base`` is a merge of ``base`` that git makes by itself: two parents, one on
    ``base``, the other ``proven`` or another such merge, and a tree identical to
    ``git merge-tree`` of the two, so no conflict was resolved and nothing was
    edited in the merge. The pull request's own diff must then be unchanged. That
    leaves nothing the maintainer did not review: the rest is main's.
    """
    if git(["rev-list", "--max-count=1", proven, f"^{head}"]).strip():
        return f"{head[:12]} does not contain {proven[:12]}: it is older, or the branch was rewritten"
    added: dict[str, list[str]] = {}
    for line in git(["rev-list", "--parents", head, f"^{proven}", f"^{base}"]).splitlines():
        commit, *parents = line.split()
        added[commit] = parents
    for commit, parents in added.items():
        on_base = [p for p in parents if not git(["rev-list", "--max-count=1", p, f"^{base}"]).strip()]
        others = [p for p in parents if p not in on_base]
        if len(parents) != 2 or len(on_base) != 1 or (others[0] != proven and others[0] not in added):
            return (
                f"{commit[:12]} is not a merge of {BASE_REF} into the branch at {proven[:12]}; "
                "every other commit needs a new review"
            )
        try:
            merged = git(["merge-tree", "--write-tree", "--no-messages", others[0], on_base[0]]).split("\n")[0]
        except subprocess.CalledProcessError as error:
            if error.returncode != 1:
                raise
            return f"{commit[:12]} resolved a conflict with {BASE_REF}; the resolution needs a new review"
        if merged != git(["rev-parse", f"{commit}^{{tree}}"]).strip():
            return f"{commit[:12]} changes more than merging {BASE_REF} does; that change needs a new review"
    if pr_patch(head, base, git) != pr_patch(proven, base, git):
        return f"the pull request's own diff at {head[:12]} differs from the one proven at {proven[:12]}"
    names = git(["diff", "--no-renames", "--name-only", "-z", f"{base}...{head}"]).split("\0")
    protected = sorted(name for name in names if name.startswith(PROTECTED_PREFIX))
    if protected:
        return f"it changes {', '.join(protected)}, which never carries over; a maintainer pushes it by hand"
    return None


def proof_main(argv: list[str], git: Git = _git) -> int:
    parser = argparse.ArgumentParser(prog="fork_canary.py proof")
    parser.add_argument("--runs-json", required=True, type=Path)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-ref", required=True, help="the pull request's base branch")
    args = parser.parse_args(argv)
    if not FULL_SHA.fullmatch(args.head_sha):
        print(f"::error title=fork canary::not a full commit sha: {args.head_sha!r}")
        return 1
    data = json.loads(args.runs_json.read_text())
    runs = data.get("workflow_runs", []) if isinstance(data, dict) else data
    heads = proven_heads(runs, args.pr)
    if args.head_sha in heads:
        print(
            f"::notice title=fork canary::a maintainer-run Canary passed on "
            f"{args.head_sha[:12]} from {branch_for(args.pr)}"
        )
        return 0
    if heads and args.base_ref != BASE_REF:
        print(f"::notice title=fork canary::the pull request targets {args.base_ref!r}, not "
              f"{BASE_REF}, so only a run on its exact head counts")
        return 1
    for proven in heads:
        try:
            problem = carry_problem(proven, args.head_sha, BASE_GIT_REF, git)
        except (subprocess.CalledProcessError, OSError) as error:
            problem = f"git could not compare the two commits ({error})"
        if problem is None:
            print(
                f"::notice title=fork canary::a maintainer-run Canary passed on {proven[:12]} from "
                f"{branch_for(args.pr)}, and {args.head_sha[:12]} only merged {BASE_REF} into it "
                "without changing the pull request's own diff"
            )
            return 0
        print(f"::notice title=fork canary::the Canary that passed on {proven[:12]} does not carry "
              f"over to {args.head_sha[:12]}: {problem}")
    return 1


def main(argv: list[str] | None = None) -> int:
    # Called with no argument it is the command line; tests pass the list.
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "proof":
        return proof_main(argv[1:])
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-json", required=True, type=Path)
    parser.add_argument("--files", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)

    pr = json.loads(args.pr_json.read_text())
    files = [line for line in args.files.read_text().splitlines() if line]
    try:
        action = decide(pr, files, args.repository, args.head_sha)
    except Refused as refusal:
        print(f"::error title=fork canary::{refusal}")
        return 1
    if action == "skip":
        print(
            "::notice title=fork canary::this pull request is from this "
            "repository, so Canary already runs on it; nothing to copy"
        )
    print(f"action={action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
