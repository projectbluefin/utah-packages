#!/usr/bin/env python3
"""Decisions for running Canary on a fork pull request a maintainer reviewed.

A fork pull request cannot publish the canary image: its token has no
``packages: write``. ``canary-fork-pr.yml`` is the maintainer's button. It copies
the pull request's head commit into ``canary/pr-<N>`` in this repository and
dispatches ``canary.yml`` there, so the required ``Canary`` check lands on the
very commit the pull request is at.

This module only decides whether that copy is allowed. It never runs, builds or
checks out the pull request's code; the workflow that calls it does not either.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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


def has_proof(runs: list[dict], pr: int, head_sha: str) -> bool:
    """Whether a maintainer-run Canary already passed on exactly this commit.

    Only a run of canary.yml dispatched on this repository's own ``canary/pr-<N>``
    branch counts, at the pull request's current head, to completion with success.
    A fork cannot create that branch or dispatch that run, so it is not something
    a pull request can claim for itself.
    """
    branch = branch_for(pr)
    return any(
        run.get("event") == "workflow_dispatch"
        and run.get("head_branch") == branch
        and run.get("head_sha") == head_sha
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        for run in runs
    )


def proof_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fork_canary.py proof")
    parser.add_argument("--runs-json", required=True, type=Path)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)
    if not FULL_SHA.fullmatch(args.head_sha):
        print(f"::error title=fork canary::not a full commit sha: {args.head_sha!r}")
        return 1
    data = json.loads(args.runs_json.read_text())
    runs = data.get("workflow_runs", []) if isinstance(data, dict) else data
    if has_proof(runs, args.pr, args.head_sha):
        print(
            f"::notice title=fork canary::a maintainer-run Canary passed on "
            f"{args.head_sha[:12]} from {branch_for(args.pr)}"
        )
        return 0
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
