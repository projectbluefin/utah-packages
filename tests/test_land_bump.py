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
from subprocess import CalledProcessError
from tools import land_bump
from tools.land_bump import (
    ENQUEUE_MUTATION,
    LANDING_QUERY,
    LandingError,
    MovedHeadError,
    PrStatus,
    SubprocessGh,
    SubprocessGit,
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
        resyncs=0,
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
        self.resyncs = resyncs
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

    def resync_count(self, repository, pr):
        return self.resyncs

    def set_resync_count(self, repository, pr, count):
        self.resyncs = count


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


class ResyncLimitTests(unittest.TestCase):
    def test_it_counts_each_re_sync_up_to_the_limit(self) -> None:
        # At MAX_RESYNC-1 the tool still re-syncs, records the new count, and
        # re-dispatches; the very next stale head is the one that trips the cap.
        gh = FakeGh(
            head_ref_oid=SHA, behind_count=5, resyncs=land_bump.MAX_RESYNC - 1
        )
        git = FakeGit()
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "rebased")
        self.assertEqual(gh.resyncs, land_bump.MAX_RESYNC)
        self.assertEqual(git.rebases, 1)
        self.assertEqual(gh.redispatched, 1)
        self.assertEqual(gh.merge_calls, [])

    def test_it_refuses_a_re_sync_past_the_limit(self) -> None:
        # After MAX_RESYNC re-syncs the bump has not produced a fresh verdict;
        # the tool fails closed and leaves it for a human rather than looping.
        gh = FakeGh(head_ref_oid=SHA, behind_count=5, resyncs=land_bump.MAX_RESYNC)
        git = FakeGit()
        with self.assertRaises(LandingError):
            land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        # Nothing was rebased or re-dispatched: the count is left untouched.
        self.assertEqual(gh.resyncs, land_bump.MAX_RESYNC)
        self.assertEqual(git.rebases, 0)
        self.assertEqual(gh.redispatched, 0)
        self.assertEqual(gh.merge_calls, [])


class ClosedTests(unittest.TestCase):
    def test_a_closed_pull_request_never_merges(self) -> None:
        gh = FakeGh(state="CLOSED")
        git = FakeGit()
        with self.assertRaises(LandingError):
            land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(gh.merge_calls, [])
        self.assertEqual(git.rebases, 0)


# --------------------------------------------------------------------------- #
# The real SubprocessGh persistence, scripted so the label-create-before-add
# ordering and the land() call order are verified end to end (no network).
# --------------------------------------------------------------------------- #


class RecordingGh(SubprocessGh):
    """The real SubprocessGh with its subprocess.run scripted. Every gh command
    is appended to ``log`` (when given); ``labels`` answers the resync-count
    read, ``status`` answers the pr_status read, and ``fail_on`` makes a chosen
    command raise so a probe can fail the label edit."""

    def __init__(
        self,
        repository,
        *,
        labels=None,
        status=None,
        fail_on=None,
        log=None,
    ) -> None:
        super().__init__(repository)
        self._labels = labels or []
        self._status = status or {
            "state": "OPEN",
            "headRefOid": OTHER_SHA,
            "behindBy": {"count": 5},
            "headRefName": "bump/upstream-sources",
        }
        self._fail_on = fail_on or set()
        self.log = log

    def _gh(self, *args):
        cmd = ["gh", *args]
        if self.log is not None:
            self.log.append(cmd)
        if args[0] == "api" and args[1] == "graphql":
            # No merge queue: exercise the no-queue landing path.
            return json.dumps({
                "data": {
                    "repository": {
                        "mergeQueue": {},
                        "pullRequest": {
                            "state": "OPEN",
                            "baseRefName": "main",
                            "isCrossRepository": False,
                            "id": "PR_123",
                        },
                    },
                },
            })
        if args[0] == "pr" and args[1] == "view" and "--json" in args:
            if args[args.index("--json") + 1] == "labels":
                return json.dumps({"labels": self._labels})
            return json.dumps(self._status)
        if args[0] == "label" and args[1] == "create":
            return ""
        if args[0] == "pr" and args[1] == "edit":
            if "edit" in self._fail_on:
                raise CalledProcessError(1, cmd)
            return ""
        if args[0] == "workflow" and args[1] == "run":
            return ""
        raise AssertionError(f"unexpected gh command: {cmd}")


class RecordingGit:
    """Records each rebase onto a shared ``log`` so its order relative to the
    gh persistence and dispatch calls can be asserted."""

    def __init__(self, log=None) -> None:
        self.log = log
        self.rebases = 0

    def rebase_onto_main(self, repository, pr, branch):
        self.rebases += 1
        if self.log is not None:
            self.log.append(("rebase", repository, pr, branch))
        return "c" * 40


class ResyncLabelAdapterTests(unittest.TestCase):
    """The persistence adapter, exercised through the real SubprocessGh so the
    label-create-before-add ordering is actually verified end to end."""

    def _gh(self, *, labels=None, fail_on=None, log=None):
        return RecordingGh(REPOSITORY, labels=labels, fail_on=fail_on, log=log)

    def test_first_re_sync_creates_the_label_then_adds_it(self) -> None:
        log = []
        gh = self._gh(labels=[], log=log)
        gh.set_resync_count(REPOSITORY, 123, 1)
        # The label exists in the repo before gh pr edit can add it, and the
        # first re-sync has no older count to drop.
        self.assertEqual(
            log[0],
            ["gh", "label", "create", "bump-resync:1", "-R", REPOSITORY,
             "--color", "ededed", "--force"],
        )
        self.assertEqual(
            log[1],
            ["gh", "pr", "edit", "123", "-R", REPOSITORY,
             "--add-label", "bump-resync:1"],
        )

    def test_a_later_re_sync_adds_before_removing_the_old_count(self) -> None:
        # Creating the new label before removing the old one means a failure
        # between the two can never lose the saved budget.
        log = []
        gh = self._gh(labels=["bump-resync:1"], log=log)
        gh.set_resync_count(REPOSITORY, 123, 2)
        self.assertEqual(len(log), 2)
        create, edit = log
        self.assertEqual(create[2], "create")
        self.assertEqual(create[3], "bump-resync:2")
        self.assertEqual(edit[2], "edit")
        self.assertEqual(edit[edit.index("--add-label") + 1], "bump-resync:2")
        self.assertEqual(edit[edit.index("--remove-label") + 1], "bump-resync:1")
        self.assertLess(edit.index("--add-label"), edit.index("--remove-label"))

    def test_resync_count_is_zero_without_any_label(self) -> None:
        self.assertEqual(self._gh(labels=[]).resync_count(REPOSITORY, 123), 0)

    def test_resync_count_reads_the_highest_count_label(self) -> None:
        gh = self._gh(
            labels=[{"name": "bump-resync:1"}, {"name": "bump-resync:3"}]
        )
        self.assertEqual(gh.resync_count(REPOSITORY, 123), 3)


class ResyncPersistenceOrderTests(unittest.TestCase):
    """In land() the counter is persisted before the branch is rewritten and the
    gate re-dispatched, so a failed save never leaves a rebased, undispatched
    branch behind."""

    def test_persistence_precedes_rebase_and_dispatch(self) -> None:
        log = []
        gh = RecordingGh(REPOSITORY, labels=[], log=log)
        git = RecordingGit(log=log)
        outcome = land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(outcome, "rebased")
        create_idx = next(i for i, c in enumerate(log) if isinstance(c, list) and len(c) > 2 and c[2] == "create")
        rebase_idx = next(i for i, c in enumerate(log) if isinstance(c, tuple))
        dispatch_idx = next(i for i, c in enumerate(log) if isinstance(c, list) and len(c) > 2 and c[2] == "run")
        self.assertLess(create_idx, rebase_idx)
        self.assertLess(rebase_idx, dispatch_idx)

    def test_a_failed_label_save_touches_no_branch(self) -> None:
        # The label addition fails: the save raises before the branch is
        # rewritten, so nothing is rebased and the gate is not re-dispatched.
        log = []
        gh = RecordingGh(REPOSITORY, labels=[], fail_on={"edit"}, log=log)
        git = RecordingGit(log=log)
        with self.assertRaises(CalledProcessError):
            land(repository=REPOSITORY, pr=123, sha=SHA, gh=gh, git=git)
        self.assertEqual(git.rebases, 0)
        self.assertFalse(any(isinstance(c, tuple) for c in log))
        self.assertFalse(
            any(isinstance(c, list) and len(c) > 2 and c[2] == "run" for c in log)
        )


class RealInvocationTests(unittest.TestCase):
    """The decision paths are mocked, but queue_and_pr / rebase_onto_main run the
    real `gh`/`git` invocations the enqueue job depends on. These lock in the
    flags a plain decision test would never catch: the Int! PR variable must go
    with -F (GitHub refuses to coerce a -f string), and the rebase must clone and
    set an identity before touching the PR branch."""

    def _patch(self, record):
        class R:
            def __init__(self, stdout=""):
                self.stdout = stdout

        def fake_run(cmd, **kw):
            record.append(list(cmd))
            # queue_and_pr reads pullRequest.id from the graphql response.
            if cmd[1:3] == ["api", "graphql"]:
                return R(json.dumps({
                    "data": {"repository": {
                        "mergeQueue": {},
                        "pullRequest": {
                            "state": "OPEN",
                            "baseRefName": "main",
                            "isCrossRepository": False,
                            "id": "PR_123",
                        },
                    }},
                }))
            return R()

        orig = land_bump.subprocess.run
        land_bump.subprocess.run = fake_run
        self.addCleanup(lambda: setattr(land_bump.subprocess, "run", orig))
        return record

    def test_queue_and_pr_sends_the_int_pr_with_F(self) -> None:
        calls = self._patch([])
        gh = SubprocessGh(REPOSITORY)
        queue_id, pr_id = gh.queue_and_pr(REPOSITORY, 123)
        self.assertIsNone(queue_id)
        self.assertEqual(pr_id, "PR_123")
        graphql = next(c for c in calls if c[1:3] == ["api", "graphql"])
        self.assertIn("-F", graphql)
        self.assertIn("pr=123", graphql)
        # $pr is Int! in LANDING_QUERY; -f passes a string GitHub refuses to
        # coerce ("Could not coerce value to Int"), so it must go with -F.
        self.assertNotIn("-f pr=123", " ".join(graphql))

    def test_rebase_sets_identity_before_rebase_and_pushes_the_fork(self) -> None:
        calls = self._patch([])
        git = SubprocessGit("/tmp/empty")
        git.rebase_onto_main(REPOSITORY, 123, "bump/upstream-sources")
        # `gh pr checkout` performs the clone; the author identity is set on the
        # freshly checked-out branch before the rebase replays bump commits.
        checkout_idx = next(i for i, c in enumerate(calls) if c[:3] == ["gh", "pr", "checkout"])
        self.assertEqual(calls[checkout_idx][3:], ["123", "-R", REPOSITORY])
        self.assertTrue(any(c[:3] == ["git", "config", "user.email"] for c in calls[checkout_idx:]))
        self.assertTrue(any(c[:3] == ["git", "config", "user.name"] for c in calls[checkout_idx:]))
        tail = calls[checkout_idx:]
        self.assertIn(["git", "fetch", "origin", "main"], tail)
        self.assertIn(["git", "rebase", "origin/main"], tail)
        self.assertIn(
            ["git", "push", "--force-with-lease", "origin", "HEAD:bump/upstream-sources"],
            tail,
        )


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
        # Re-syncs are bounded so a gate that keeps falling behind main cannot
        # loop forever; the cap is a public, tested constant.
        self.assertEqual(land_bump.MAX_RESYNC, 3)


if __name__ == "__main__":
    unittest.main()
