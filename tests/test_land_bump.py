#!/usr/bin/env python3
"""The no-queue landing path rebuilds a bump that fell behind main instead of
failing its SHA-pinned merge.

tools/land_bump.py runs in the enqueue job when no merge queue exists on main.
Before the fix it did one `gh api PUT pulls/merge` and died with HTTP 405 the
moment the built head was no longer the PR tip -- because a newer daily bump
force-updated the branch, or main advanced, while the gate was still building.
So the stale enqueue was abandoned and the bump never landed.

land() fixes that by re-reading the live pull request once and taking exactly
one path: enqueue when a queue exists, merge the exact built head when the PR
still sits at it, or rebase onto main and re-dispatch the gate for a fresh
exact-head verdict when the head moved or fell behind main while the gate built.
The re-dispatched gate re-triggers the enqueue job, which lands the fresh head --
so the tool never merges a head the gate has not rebuilt, never arms durable
auto-merge, and never relaxes strict freshness. Every one of those paths -- plus
a closed PR and an already-merged PR -- is asserted here against a mocked gh, so
a regression in the decision is caught without any network.
"""

from __future__ import annotations

import json
import unittest
from tools import land_bump
from tools.land_bump import (
    ENQUEUE_MUTATION,
    LANDING_QUERY,
    LandingError,
    MovedHeadError,
    PrStatus,
    land,
)

REPOSITORY = "projectbluefin/utah-packages"
SHA = "a" * 40
OTHER_SHA = "b" * 40


class FakeGh:
    """Records calls and replays scripted responses."""

    def __init__(
        self,
        *,
        queue_id=None,
        pr_id="pull-123",
        state="OPEN",
        head_ref_oid=SHA,
        behind_count=0,
        head_ref_name="bump/upstream-sources",
        merge_status=None,
        merge_message="",
        merge_stdout='{"merged": true}',
        redispatched=0,
        wait_checks_calls=0,
    ) -> None:
        self.queue_id = queue_id
        self.pr_id = pr_id
        self.state = state
        self.head_ref_oid = head_ref_oid
        self.behind_count = behind_count
        self.head_ref_name = head_ref_name
        self.merge_status = merge_status
        self.merge_message = merge_message
        self.merge_stdout = merge_stdout
        self.redispatched = redispatched
        self.wait_checks_calls = wait_checks_calls
        self.enqueued_shas = []
        self.merge_calls = []

    def queue_and_pr(self, repository, pr):
        return self.queue_id, self.pr_id

    def enqueue(self, repository, pull_request_id, sha):
        self.enqueued_shas.append(sha)

    def pr_status(self, repository, pr):
        return PrStatus(
            state=self.state,
            head_ref_oid=self.head_ref_oid,
            behind_count=self.behind_count,
            head_ref_name=self.head_ref_name,
        )

    def wait_checks(self, repository, pr):
        self.wait_checks_calls += 1

    def merge(self, repository, pr, sha):
        if self.merge_status == "405":
            raise MovedHeadError("head moved")
        payload = {}
        if self.merge_stdout:
            payload.update(json.loads(self.merge_stdout))
        if self.merge_status:
            payload["status"] = self.merge_status
        if self.merge_message:
            payload["message"] = self.merge_message
        if payload.get("merged") is not True:
            raise LandingError(f"merge failed: {payload}")
        self.merge_calls.append(sha)

    def redispatch_gate(self, repository, pr, branch):
        self.redispatched += 1


class FakeGit:
    def __init__(self) -> None:
        self.rebases = 0

    def rebase_onto_main(self, repository, pr, branch):
        self.rebases += 1
        return OTHER_SHA


class EnqueuedTests(unittest.TestCase):
    def test_when_a_queue_exists_it_enqueues_the_exact_head(self) -> None:
        gh = FakeGh(queue_id="queue-1")
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "enqueued")
        self.assertEqual(gh.enqueued_shas, [SHA])
        # It never touched the merge path or the gate when a queue exists.
        self.assertEqual(gh.merge_calls, [])
        self.assertEqual(gh.redispatched, 0)
        self.assertEqual(git.rebases, 0)


class MergedTests(unittest.TestCase):
    def test_it_merges_when_the_pr_still_sits_at_the_built_head(self) -> None:
        gh = FakeGh(head_ref_oid=SHA, behind_count=0)
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "merged")
        # It waited for the required checks on that exact head, then merged.
        self.assertEqual(gh.wait_checks_calls, 1)
        self.assertEqual(gh.merge_calls, [SHA])
        self.assertEqual(git.rebases, 0)
        self.assertEqual(gh.redispatched, 0)

    def test_an_already_merged_pr_reports_merged_without_remerging(self) -> None:
        gh = FakeGh(state="MERGED")
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "merged")
        self.assertEqual(gh.merge_calls, [])
        self.assertEqual(git.rebases, 0)

    def test_a_head_that_moves_before_the_merge_is_rebuilt(self) -> None:
        # The fresh read passes, but the merge endpoint 405s because the head
        # moved in the gap; the tool rebases onto main and re-dispatches the
        # gate rather than merging the stale head.
        gh = FakeGh(head_ref_oid=SHA, behind_count=0, merge_status="405")
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "rebased")
        self.assertEqual(git.rebases, 1)
        self.assertEqual(gh.redispatched, 1)
        # Nothing was merged: the fresh head has to earn its own verdict first.
        self.assertEqual(gh.merge_calls, [])


class BehindTests(unittest.TestCase):
    def test_a_pr_behind_main_rebases_and_repatches_the_gate(self) -> None:
        gh = FakeGh(head_ref_oid=SHA, behind_count=3)
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "rebased")
        # It updated the branch from main and required a fresh verdict.
        self.assertEqual(git.rebases, 1)
        self.assertEqual(gh.redispatched, 1)
        self.assertEqual(gh.merge_calls, [])

    def test_a_pr_whose_head_moved_but_is_not_behind_also_rebases(self) -> None:
        # headRefOid != sha means the built head is no longer the PR tip, even
        # when behind_count is zero; the same rebuild-and-retry applies.
        gh = FakeGh(head_ref_oid=OTHER_SHA, behind_count=0)
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "rebased")
        self.assertEqual(git.rebases, 1)
        self.assertEqual(gh.redispatched, 1)


class ClosedTests(unittest.TestCase):
    def test_a_closed_pull_request_never_merges(self) -> None:
        gh = FakeGh(state="CLOSED")
        git = FakeGit()
        with self.assertRaises(LandingError):
            land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(gh.merge_calls, [])
        self.assertEqual(git.rebases, 0)


class CliTests(unittest.TestCase):
    def test_help_lists_required_arguments(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            land_bump.main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_public_surface_and_gate_reference(self) -> None:
        # The real callables build the same commands the workflow used; the tool
        # re-dispatches exactly the gate that produces the fresh verdict.
        self.assertEqual(land_bump.GATE_WORKFLOW, "bump-upstream-gate.yml")
        self.assertIn("mergeQueue", LANDING_QUERY)
        self.assertIn("expectedHeadOid", ENQUEUE_MUTATION)


if __name__ == "__main__":
    unittest.main()
