#!/usr/bin/env python3
"""Land a built bump in the no-queue path of the daily bump pipeline.

tools/land_bump.py decides; .github/workflows/bump-upstream-enqueue.yml acts.
When no merge queue exists on main, the enqueue job lands the built head with a
single SHA-pinned merge. That is safe only while the pull request still sits at
that exact head -- but a newer daily bump can force-update the branch (or main
can advance) while the gate is still building, so the built head is no longer
the PR tip and the SHA-pinned merge fails with HTTP 405. The stale enqueue is
then abandoned and the bump never lands.

land() fixes that without relaxing the invariant. It re-reads the live pull
request once and takes exactly one path:

  * if a merge queue exists, it enqueues the built head with an explicit
    expectedHeadOid (the durable, queue-gated path);
  * if the PR is still at the exact built head, it waits for the required checks
    on that head and merges (the existing single-Sha-pinned path);
  * if the PR is stale -- its tip moved or it fell behind main while the gate
    built -- it rebases the branch onto main, re-dispatches the gate so a fresh
    exact-head verdict (Canary, Unit tests, Runtime contract) is produced on the
    new head, and lets the re-triggered enqueue job land that fresh head.

It never arms durable auto-merge, never merges a head the gate has not rebuilt,
and never relaxes strict freshness. Re-dispatching the gate (rather than
merging a stale head) means the re-triggered enqueue job performs the only
merge of the fresh head, so there is no double-merge. The merge endpoint's own
SHA-pinned guard is the final check, so a head that moves between the freshness
read and the merge is caught by MovedHeadError and rebuilt the same way.

The core land() takes injectable gh and git callables so every path -- queue,
fresh, behind, moved, closed -- is unit-tested without network. The CLI wires
those callables to `gh`, `git`, and `jq` the way the workflow runs them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

# GraphQL, identical in shape to the inline query in bump-upstream-enqueue.yml:
# a queue id selects the queue path; the pull request must be open, on main,
# same-repository, and must exist. Errors or a malformed response never select
# the non-queue merge path.
LANDING_QUERY = """
query($owner: String!, $name: String!, $pr: Int!) {
  repository(owner: $owner, name: $name) {
    mergeQueue(branch: "main") { id }
    pullRequest(number: $pr) {
      id state baseRefName headRefOid isCrossRepository
    }
  }
}
"""

ENQUEUE_MUTATION = """
mutation($pr: ID!, $sha: GitObjectID!) {
  enqueuePullRequest(input: {pullRequestId: $pr, expectedHeadOid: $sha}) {
    mergeQueueEntry { id }
  }
}
"""

GATE_WORKFLOW = "bump-upstream-gate.yml"

# A stale re-sync rebases the branch onto main and re-dispatches the gate so a
# fresh exact-head verdict is produced. That gate can fall behind again if main
# keeps advancing, so re-syncs are bounded: after MAX_RESYNC the tool fails
# closed and leaves the bump for a human instead of looping forever.
MAX_RESYNC = 3
# The re-sync count is carried on the PR as a labelled counter (bump-resync:N)
# so it survives across the separate enqueue runs that each perform one re-sync.
RESYNC_LABEL = "bump-resync"


class LandingError(Exception):
    """A decision the pipeline must fail closed on, never merge blindly."""


class MovedHeadError(LandingError):
    """The head moved between the freshness read and the merge; rebuild it."""


@dataclass
class PrStatus:
    state: str
    head_ref_oid: str
    behind_count: int
    head_ref_name: str


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise LandingError(message)


def _validate_landing(payload: dict) -> dict:
    """Fail closed on anything the inline jq used to guard the merge path."""
    _require(
        (payload.get("errors") or []) == [],
        "GraphQL returned errors while reading the merge queue; refusing to merge",
    )
    repo = payload.get("data", {}).get("repository", {})
    _require(
        isinstance(repo, dict) and "mergeQueue" in repo,
        "GraphQL response did not carry the merge queue; refusing to merge",
    )
    pr = repo.get("pullRequest", {})
    _require(
        isinstance(pr, dict)
        and pr.get("state") == "OPEN"
        and pr.get("baseRefName") == "main"
        and not pr.get("isCrossRepository")
        and isinstance(pr.get("id"), str) and pr.get("id"),
        "pull request is not an open same-repository PR on main; refusing to merge",
    )
    return pr


def land(
    *,
    repository: str,
    pr: int,
    sha: str,
    gh: object,
    git: object,
) -> str:
    """Land the built head on ``sha`` in the no-queue path.

    ``gh`` and ``git`` are injectable callables so the paths are unit-tested
    without network. ``gh`` needs: ``queue_and_pr`` returning
    ``(merge_queue_id_or_None, pull_request_id)``, ``enqueue`` taking
    ``(repository, pull_request_id, sha)``, ``pr_status`` returning a
    ``PrStatus``, ``wait_checks`` taking ``(repository, pr)``, ``merge`` taking
    ``(repository, pr, sha)`` (raising ``MovedHeadError`` on a 405), and
    ``redispatch_gate`` taking ``(repository, pr, branch)``; ``resync_count``
    taking ``(repository, pr)`` returning the number of prior re-syncs, and
    ``set_resync_count`` taking ``(repository, pr, count)``. ``git`` needs
    ``rebase_onto_main`` returning the new head SHA.

    Returns ``"enqueued"``, ``"merged"``, or ``"rebased"``. On ``"rebased"`` the
    gate was re-dispatched and will re-trigger the enqueue job, which lands the
    fresh head after its own exact-head verdict.
    """
    queue_id, pull_request_id = gh.queue_and_pr(repository, pr)
    if queue_id is not None:
        gh.enqueue(repository, pull_request_id, sha)
        return "enqueued"

    status = gh.pr_status(repository, pr)
    if status.state == "MERGED":
        return "merged"
    if status.state != "OPEN":
        raise LandingError(
            f"pull request {pr} is {status.state}, not OPEN; cannot land"
        )

    if status.head_ref_oid == sha and status.behind_count == 0:
        # The built head is still the PR tip: wait for the required checks on
        # that exact head, then the single SHA-pinned merge.
        gh.wait_checks(repository, pr)
        try:
            gh.merge(repository, pr, sha)
            return "merged"
        except MovedHeadError:
            # The head moved between the freshness read and the merge; fall
            # through to the rebase path below.
            pass

    # Stale: the built head is no longer the PR tip, either because the branch
    # moved or because it fell behind main while the gate built. Reserve the
    # re-sync on the PR first (so a crash before the rebuild still consumes the
    # budget), rebase the branch onto main, then re-dispatch the gate so a fresh
    # exact-head verdict is produced on the new head and the re-triggered
    # enqueue job lands it. Never arm durable auto-merge; never relax strict
    # freshness. The re-sync is bounded: a gate that keeps falling behind main
    # is retried only up to MAX_RESYNC times, then the tool fails closed and
    # leaves the bump for a human instead of looping forever.
    resyncs = gh.resync_count(repository, pr)
    if resyncs >= MAX_RESYNC:
        raise LandingError(
            f"bump {pr} was rebased {MAX_RESYNC} times without a fresh "
            f"exact-head verdict; leaving it for a human"
        )
    gh.set_resync_count(repository, pr, resyncs + 1)
    git.rebase_onto_main(repository, pr, status.head_ref_name)
    gh.redispatch_gate(repository, pr, status.head_ref_name)
    return "rebased"


# --------------------------------------------------------------------------- #
# Real callables, wired to `gh`, `git`, and `jq` exactly as the workflow runs.
# --------------------------------------------------------------------------- #


class SubprocessGh:
    def __init__(self, repository: str) -> None:
        self.repository = repository

    def _gh(self, *args: str) -> str:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    def queue_and_pr(self, repository: str, pr: int) -> tuple[Optional[str], str]:
        owner, name = repository.split("/", 1)
        raw = self._gh(
            "api", "graphql",
            "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"pr={pr}",
            "-f", "query={}".format(LANDING_QUERY),
        )
        payload = json.loads(raw)
        pr_id = _validate_landing(payload)["id"]
        # A merge queue absent on main is GraphQL null; the no-queue path lands
        # the built head instead of enqueuing it.
        merge_queue = (payload.get("data", {}).get("repository", {}) or {}).get(
            "mergeQueue"
        ) or {}
        queue_id = merge_queue.get("id")
        if not queue_id:
            return None, pr_id
        return queue_id, pr_id

    def enqueue(self, repository: str, pull_request_id: str, sha: str) -> None:
        self._gh(
            "api", "graphql",
            "-f", f"pr={pull_request_id}", "-f", f"sha={sha}",
            "-f", "query={}".format(ENQUEUE_MUTATION),
        )

    def pr_status(self, repository: str, pr: int) -> PrStatus:
        raw = self._gh(
            "pr", "view", str(pr), "-R", repository,
            "--json", "state,headRefOid,behindBy,headRefName",
        )
        data = json.loads(raw)
        return PrStatus(
            state=data["state"],
            head_ref_oid=data["headRefOid"],
            # `gh pr view --json behindBy` reports the GraphQL StaleState object
            # {"count": N}, never a bare int; read the count out of it.
            behind_count=int(data["behindBy"]["count"]),
            head_ref_name=data["headRefName"],
        )

    def wait_checks(self, repository: str, pr: int) -> None:
        self._gh("pr", "checks", str(pr), "-R", repository, "--required", "--watch")

    def merge(self, repository: str, pr: int, sha: str) -> None:
        proc = subprocess.run(
            [
                "gh", "api", "--method", "PUT",
                f"repos/{repository}/pulls/{pr}/merge",
                "-f", f"sha={sha}", "-f", "merge_method=squash",
            ],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise LandingError(
                f"merge response was not JSON; refusing to merge: {proc.stdout[:200]}"
            )
        if data.get("merged") is True:
            return
        if data.get("status") == "405" or "Head sha" in (proc.stdout + proc.stderr):
            raise MovedHeadError(
                f"merge rejected: the PR head no longer matches {sha}"
            )
        raise LandingError(
            f"merge failed: {proc.stdout[:200]} {proc.stderr[:200]}"
        )

    def redispatch_gate(self, repository: str, pr: int, branch: str) -> None:
        self._gh(
            "workflow", "run", GATE_WORKFLOW, "-R", repository,
            "--ref", branch, "-f", f"pr={pr}",
        )

    def resync_count(self, repository: str, pr: int) -> int:
        # The counter is a labelled value (bump-resync:N) so it survives across
        # the separate enqueue runs that each do one re-sync; 0 means no label.
        raw = self._gh(
            "pr", "view", str(pr), "-R", repository, "--json", "labels"
        )
        count = 0
        for label in json.loads(raw).get("labels", []):
            name = label.get("name", "")
            if name.startswith(RESYNC_LABEL + ":"):
                count = max(count, int(name.split(":", 1)[1]))
        return count

    def set_resync_count(self, repository: str, pr: int, count: int) -> None:
        # Create the destination label first (idempotent with --force) so the
        # counter survives even if the PR edit below fails: `gh pr edit
        # --add-label` refuses a label that does not exist in the repository.
        # The first re-sync sets bump-resync:1, so there is no older label to
        # remove yet; afterwards the previous count label is dropped. Creating
        # the new label before removing the old one means a failure between the
        # two can never lose the saved budget.
        self._gh(
            "label", "create", f"{RESYNC_LABEL}:{count}", "-R", repository,
            "--color", "ededed", "--force",
        )
        args = [
            "pr", "edit", str(pr), "-R", repository, "--add-label",
            f"{RESYNC_LABEL}:{count}",
        ]
        if count > 1:
            args.extend(["--remove-label", f"{RESYNC_LABEL}:{count - 1}"])
        self._gh(*args)


class SubprocessGit:
    def __init__(self, workdir: str) -> None:
        self.workdir = workdir

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    def rebase_onto_main(self, repository: str, pr: int, branch: str) -> str:
        # `gh pr checkout` clones the pull request's branch into the throwaway
        # workdir and points origin at it; set an author identity first so the
        # replayed bump commits can be authored, then rebase onto the latest
        # main and force-push the rewritten branch back to the fork.
        subprocess.run(
            ["gh", "pr", "checkout", str(pr), "-R", repository],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            check=True,
        )
        self._git("config", "user.email", "scanner@hive.local")
        self._git("config", "user.name", "Hive Scanner")
        self._git("fetch", "origin", "main")
        self._git("rebase", "origin/main")
        self._git("push", "--force-with-lease", "origin", f"HEAD:{branch}")
        return self._git("rev-parse", "HEAD")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)

    # A throwaway workdir keeps the fresh runner clean; gh pr checkout clones
    # the repo into it.
    workdir = subprocess.run(
        ["mktemp", "-d"], capture_output=True, text=True, check=True,
    ).stdout.strip()

    gh = SubprocessGh(args.repository)
    git = SubprocessGit(workdir)

    outcome = land(
        repository=args.repository,
        pr=args.pr,
        sha=args.sha,
        gh=gh,
        git=git,
    )
    print(f"land_bump: {outcome} bump {args.pr} in {args.repository}")
    if outcome == "rebased":
        # The re-dispatched gate will rebuild the new head and re-trigger the
        # enqueue job, which then lands it. Success here means the rebuild is
        # underway, not that the PR merged.
        print(
            "land_bump: the pull request was behind main; it was rebased onto "
            "main and the gate re-dispatched. It will land once a fresh exact-head "
            "verdict is produced."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
