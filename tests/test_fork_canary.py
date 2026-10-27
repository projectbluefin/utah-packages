#!/usr/bin/env python3
"""A maintainer-reviewed fork pull request may be copied in for a Canary run, and nothing else."""

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools import fork_canary

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "canary-fork-pr.yml"

REPO = "projectbluefin/utah-packages"
REVIEWED = "a" * 40
MOVED = "b" * 40


def pr(**over):
    base = {
        "state": "open",
        "base": {"ref": "main"},
        "head": {"sha": REVIEWED, "repo": {"full_name": "someone/utah-packages"}},
        "changed_files": 1,
    }
    base.update(over)
    return base


class DecideTests(unittest.TestCase):
    def test_a_reviewed_fork_pull_request_is_copied(self):
        self.assertEqual(fork_canary.decide(pr(), ["packages/foo/foo.spec"], REPO, REVIEWED), "copy")

    def test_a_head_that_moved_since_review_is_refused(self):
        # The maintainer approved REVIEWED; a push after that is unreviewed code.
        moved = pr(head={"sha": MOVED, "repo": {"full_name": "someone/utah-packages"}})
        with self.assertRaisesRegex(fork_canary.Refused, "moved"):
            fork_canary.decide(moved, [], REPO, REVIEWED)

    def test_only_a_full_sha_is_accepted(self):
        for sha in ("", "abc123", REVIEWED[:12], REVIEWED.upper(), "main", REVIEWED + "0"):
            with self.subTest(sha=sha), self.assertRaisesRegex(fork_canary.Refused, "40-character"):
                fork_canary.decide(pr(), [], REPO, sha)

    def test_a_closed_or_non_main_pull_request_is_refused(self):
        with self.assertRaises(fork_canary.Refused):
            fork_canary.decide(pr(state="closed"), [], REPO, REVIEWED)
        with self.assertRaises(fork_canary.Refused):
            fork_canary.decide(pr(base={"ref": "release"}), [], REPO, REVIEWED)

    def test_workflow_changes_from_a_fork_are_never_copied(self):
        # canary.yml and the workflows it calls hold packages: write.
        for name in (".github/workflows/canary.yml", ".github/actions/x/action.yml", ".github/CODEOWNERS"):
            with self.subTest(name=name), self.assertRaisesRegex(fork_canary.Refused, r"\.github/"):
                fork_canary.decide(pr(), ["packages/foo/foo.spec", name], REPO, REVIEWED)

    def test_a_rename_out_of_dot_github_is_still_a_workflow_change(self):
        # The workflow lists previous_filename too, so moving a workflow away
        # is judged like editing it.
        with self.assertRaises(fork_canary.Refused):
            fork_canary.decide(pr(), ["workflows/x.yml", ".github/workflows/x.yml"], REPO, REVIEWED)

    def test_a_path_that_only_looks_like_dot_github_is_fine(self):
        for name in ("docs/.github/notes.md", "x.github/y", "packages/.github-keep/x"):
            with self.subTest(name=name):
                self.assertEqual(fork_canary.decide(pr(), [name], REPO, REVIEWED), "copy")

    def test_a_pull_request_too_large_to_list_is_refused(self):
        # pulls/N/files stops at 3000 files, so a .github/ change could hide past it.
        for count in (3000, 5000, None):
            with self.subTest(count=count), self.assertRaisesRegex(fork_canary.Refused, "by hand"):
                fork_canary.decide(pr(changed_files=count), ["packages/foo/foo.spec"], REPO, REVIEWED)
        self.assertEqual(
            fork_canary.decide(pr(changed_files=2999), ["packages/foo/foo.spec"], REPO, REVIEWED), "copy"
        )

    def test_an_in_repository_pull_request_needs_no_copy(self):
        own = pr(head={"sha": REVIEWED, "repo": {"full_name": REPO}})
        self.assertEqual(fork_canary.decide(own, [".github/workflows/x.yml"], REPO, REVIEWED), "skip")

    def test_a_deleted_fork_is_refused_not_crashed_on(self):
        gone = pr(head={"sha": REVIEWED, "repo": None})
        with self.assertRaisesRegex(fork_canary.Refused, "deleted"):
            fork_canary.decide(gone, [], REPO, REVIEWED)

    def test_branch_names_stay_inside_the_copy_namespace(self):
        self.assertEqual(fork_canary.branch_for(618), "canary/pr-618")
        self.assertTrue(fork_canary.branch_for(1).startswith(fork_canary.BRANCH_PREFIX))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, pull, files, sha=REVIEWED):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "pr.json").write_text(json.dumps(pull))
            (tmp / "files.txt").write_text("\n".join(files) + ("\n" if files else ""))
            argv = ["--pr-json", str(tmp / "pr.json"), "--files", str(tmp / "files.txt"),
                    "--repository", REPO, "--head-sha", sha]
            with mock.patch("builtins.print") as out:
                code = fork_canary.main(argv)
            return code, "\n".join(str(c.args[0]) for c in out.call_args_list)

    def test_an_approved_copy_prints_the_action_the_workflow_reads(self):
        code, out = self.run_cli(pr(), ["packages/foo/foo.spec"])
        self.assertEqual(code, 0)
        self.assertIn("action=copy", out.splitlines())

    def test_a_refusal_fails_the_run_with_an_annotation_and_no_action(self):
        code, out = self.run_cli(pr(), [".github/workflows/canary.yml"])
        self.assertEqual(code, 1)
        self.assertIn("::error", out)
        self.assertNotIn("action=", out)

    def test_an_in_repository_pull_request_succeeds_with_skip(self):
        own = pr(head={"sha": REVIEWED, "repo": {"full_name": REPO}})
        code, out = self.run_cli(own, ["packages/foo/foo.spec"])
        self.assertEqual(code, 0)
        self.assertIn("action=skip", out.splitlines())


class WorkflowTests(unittest.TestCase):
    """The workflow moves a ref; it must never run what it is moving."""

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.wf = yaml.safe_load(cls.text)
        cls.steps = cls.wf["jobs"]["dispatch"]["steps"]

    def test_it_runs_only_when_a_maintainer_dispatches_it_with_the_reviewed_commit(self):
        on = self.wf.get("on", self.wf.get(True))
        self.assertEqual(set(on), {"workflow_dispatch"})
        inputs = on["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"pr", "head_sha"})
        self.assertTrue(all(i["required"] for i in inputs.values()))

    def test_it_holds_no_more_than_it_needs(self):
        self.assertEqual(self.wf["permissions"],
                         {"contents": "write", "pull-requests": "write", "actions": "write"})

    def test_it_never_checks_out_or_runs_the_pull_request(self):
        for step in self.steps:
            if str(step.get("uses", "")).startswith("actions/checkout"):
                self.assertNotIn("ref", step.get("with", {}),
                                 "the only checkout is this workflow's own ref")
        # The fork's commit is fetched as a ref and pushed; nothing executes it.
        runs = "\n".join(s.get("run", "") for s in self.steps)
        self.assertNotRegex(runs, r"git (checkout|switch|merge|cherry-pick|rebase)")
        self.assertNotRegex(runs, r"\b(just|make|podman|docker)\b")
        self.assertRegex(runs, r'git fetch --no-tags --depth=1 origin "refs/pull/\$\{PR\}/head"')

    def test_the_commit_pushed_is_the_commit_that_was_reviewed(self):
        runs = "\n".join(s.get("run", "") for s in self.steps)
        # Fetched head must equal the reviewed sha before it is pushed, and the
        # push names that sha, never a branch that could move.
        verify = runs.index('test "$(git rev-parse FETCH_HEAD)" = "$HEAD_SHA"')
        push = runs.index('git push --force origin "${HEAD_SHA}:refs/heads/canary/pr-${PR}"')
        self.assertLess(verify, push)
        self.assertIn(fork_canary.BRANCH_PREFIX + "${PR}", runs)

    def test_the_dispatch_names_no_pr_so_an_older_canary_yml_still_runs_it_unconditionally(self):
        # The copied branch carries the pull request's own canary.yml, which may
        # predate any change to the fork guard. Without a pr input every version
        # takes the same-repository path.
        dispatch = next(s for s in self.steps if s.get("name") == "Dispatch Canary on the copy")
        self.assertIn('gh workflow run canary.yml -R "$REPOSITORY" --ref "canary/pr-${PR}"', dispatch["run"])
        self.assertNotRegex(dispatch["run"], r"-f\s+pr=")

    def test_every_later_step_waits_for_the_decision_to_copy(self):
        for name in ("Copy the reviewed commit into this repository", "Dispatch Canary on the copy",
                     "Tell the pull request"):
            step = next(s for s in self.steps if s.get("name") == name)
            self.assertEqual(step["if"], "steps.check.outputs.action == 'copy'")

    def test_copies_of_closed_pull_requests_are_cleaned_up_without_hiding_errors(self):
        cleanup = next(s for s in self.steps if str(s.get("name", "")).startswith("Delete copies"))
        # A bare `|| true` would also swallow a failed API call.
        self.assertNotRegex(cleanup["run"], r"\|\|\s*true")
        self.assertRegex(cleanup["run"], r"grep -E .*\|\| test \$\? -eq 1")
        self.assertTrue(re.search(r'"\$state" != open', cleanup["run"]))

def dispatch_run(**over):
    run = {"event": "workflow_dispatch", "head_branch": "canary/pr-622", "head_sha": REVIEWED,
           "status": "completed", "conclusion": "success"}
    run.update(over)
    return run


class ProofTests(unittest.TestCase):
    """A fork's own Canary passes only on a maintainer-run Canary at its exact head."""

    def test_a_passed_maintainer_run_on_the_exact_head_is_proof(self):
        self.assertTrue(fork_canary.has_proof([dispatch_run()], 622, REVIEWED))

    def test_anything_short_of_that_is_not_proof(self):
        for name, run in {
            "a failed run": dispatch_run(conclusion="failure"),
            "a cancelled run": dispatch_run(conclusion="cancelled"),
            "a run still going": dispatch_run(status="in_progress", conclusion=None),
            "an earlier commit": dispatch_run(head_sha=MOVED),
            "another pull request's copy": dispatch_run(head_branch="canary/pr-621"),
            "a run on main": dispatch_run(head_branch="main"),
            # The fork's own run is a pull_request event; it must not vouch for itself.
            "a pull_request run": dispatch_run(event="pull_request"),
            "a lookalike branch": dispatch_run(head_branch="canary/pr-6222"),
        }.items():
            with self.subTest(name):
                self.assertFalse(fork_canary.has_proof([run], 622, REVIEWED))

    def test_one_good_run_among_bad_ones_is_enough_and_none_is_not(self):
        runs = [dispatch_run(conclusion="failure"), dispatch_run(head_sha=MOVED), dispatch_run()]
        self.assertTrue(fork_canary.has_proof(runs, 622, REVIEWED))
        self.assertFalse(fork_canary.has_proof([], 622, REVIEWED))

    def test_the_command_reads_the_api_shape_and_sets_the_exit_status(self):
        def run_proof(payload, sha=REVIEWED):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "runs.json"
                path.write_text(json.dumps(payload))
                with mock.patch("builtins.print"):
                    return fork_canary.main(["proof", "--runs-json", str(path), "--pr", "622", "--head-sha", sha])

        self.assertEqual(run_proof({"workflow_runs": [dispatch_run()]}), 0)
        self.assertEqual(run_proof({"workflow_runs": []}), 1)
        self.assertEqual(run_proof([dispatch_run()]), 0)
        self.assertEqual(run_proof({"workflow_runs": [dispatch_run()]}, sha="abc"), 1)

    def test_the_canary_job_passes_a_fork_only_through_that_proof(self):
        canary = yaml.safe_load((ROOT / ".github/workflows/canary.yml").read_text())
        decide = next(s for s in canary["jobs"]["canary"]["steps"] if s.get("name") == "Decide")
        fork_branch = decide["run"].split('if [ "$FORK" = true ]; then', 1)[1].split("\n          fi\n", 1)[0]
        self.assertIn("tools/fork_canary.py proof", fork_branch)
        # The only way out of the fork branch with success is the proof's exit.
        self.assertEqual(fork_branch.count("exit 0"), 1)
        self.assertLess(fork_branch.index("proof"), fork_branch.index("exit 0"))
        self.assertIn("exit 1", fork_branch)


class CommandLineEntryPointTests(unittest.TestCase):
    """The workflows run the tool as a program; tests that pass argv to main() miss that."""

    def run_tool(self, *args):
        import subprocess
        import sys
        return subprocess.run([sys.executable, str(ROOT / "tools" / "fork_canary.py"), *args],
                              capture_output=True, text=True, cwd=ROOT)

    def test_the_proof_subcommand_works_when_run_as_a_program(self):
        # canary.yml calls `python3 tools/fork_canary.py proof ...`. With no argv
        # passed to main() the subcommand was parsed as the default command and
        # failed on missing --files (seen on #622).
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.json"
            path.write_text(json.dumps({"workflow_runs": [dispatch_run()]}))
            ok = self.run_tool("proof", "--runs-json", str(path), "--pr", "622", "--head-sha", REVIEWED)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertIn("maintainer-run Canary passed", ok.stdout)
            path.write_text(json.dumps({"workflow_runs": []}))
            no = self.run_tool("proof", "--runs-json", str(path), "--pr", "622", "--head-sha", REVIEWED)
            self.assertEqual(no.returncode, 1)
            self.assertNotIn("usage:", no.stderr)

    def test_the_default_command_works_when_run_as_a_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "pr.json").write_text(json.dumps(pr()))
            (tmp / "files.txt").write_text("packages/foo/foo.spec\n")
            done = self.run_tool("--pr-json", str(tmp / "pr.json"), "--files", str(tmp / "files.txt"),
                                 "--repository", REPO, "--head-sha", REVIEWED)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("action=copy", done.stdout.splitlines())


class RefreshJobTests(unittest.TestCase):
    """The refresh job holds write permissions, so it must never run the pull request."""

    @classmethod
    def setUpClass(cls):
        cls.wf = yaml.safe_load(WORKFLOW.read_text())
        cls.job = cls.wf["jobs"]["refresh"]
        cls.steps = cls.job["steps"]

    def test_there_is_no_workflow_run_refresher_to_rely_on(self):
        # A workflow_run refresher never fired for a run started by this
        # workflow's GITHUB_TOKEN dispatch (#622); waiting in this job does not
        # depend on that trigger.
        self.assertFalse((ROOT / ".github" / "workflows" / "canary-fork-refresh.yml").exists())

    def test_it_runs_only_after_a_copy_was_dispatched(self):
        self.assertEqual(self.job["needs"], "dispatch")
        self.assertEqual(self.job["if"], "needs.dispatch.outputs.action == 'copy'")

    def test_it_never_checks_out_or_runs_anything_from_the_pull_request(self):
        for step in self.steps:
            self.assertFalse(str(step.get("uses", "")).startswith("actions/checkout"))
        runs = "\n".join(s.get("run", "") for s in self.steps)
        self.assertNotRegex(runs, r"\b(just|make|podman|docker|python3?|pip)\b")

    def test_no_expression_is_interpolated_into_a_script(self):
        # Interpolating ${{ ... }} into a script is how a crafted value becomes code.
        for step in self.steps:
            self.assertNotIn("${{", step.get("run", ""))

    def test_it_waits_for_the_run_it_dispatched_and_not_an_older_one(self):
        wait = next(s for s in self.steps if s.get("id") == "wait")
        self.assertEqual(wait["env"]["SINCE"], "${{ needs.dispatch.outputs.since }}")
        self.assertIn("select(.created_at >= $since)", wait["run"])
        self.assertIn("event=workflow_dispatch&branch=${branch}", wait["run"])

    def test_a_failed_run_is_reported_and_stops_before_any_refresh(self):
        names = [s.get("name") for s in self.steps]
        failed = next(s for s in self.steps if str(s.get("name", "")).startswith("Say so"))
        self.assertEqual(failed["if"], "steps.wait.outputs.conclusion != 'success'")
        self.assertIn("exit 1", failed["run"])
        self.assertLess(names.index(failed["name"]), names.index("Re-run the pull request's Canary on the proof"))

    def test_it_refreshes_only_the_commit_that_was_proven_on_an_open_pull_request(self):
        run = next(s for s in self.steps if s.get("name", "").startswith("Re-run"))["run"]
        self.assertIn('"$(jq -r .head.sha pr.json)" != "$HEAD_SHA"', run)
        self.assertIn('"$(jq -r .state pr.json)" != open', run)

    def test_the_reopen_fallback_comes_only_after_a_quiet_rerun_failed(self):
        run = next(s for s in self.steps if s.get("name", "").startswith("Re-run"))["run"]
        self.assertLess(run.index("gh run rerun"), run.index("gh pr close"))
        self.assertLess(run.index("gh pr close"), run.index("gh pr reopen"))

    def test_a_reopen_waits_for_the_merge_commit_to_catch_up_with_the_base_branch(self):
        # A pull request's run takes its workflow file from its merge commit,
        # which GitHub recomputes only after the reopen's own run has started
        # (#622). Reopening on a stale one starts a run with the old canary.yml.
        run = next(s for s in self.steps if s.get("name", "").startswith("Re-run"))["run"]
        self.assertIn("git/ref/pull/$PR/merge", run)
        self.assertIn(".parents[0].sha", run)
        self.assertIn("never caught up", run)
        self.assertLess(run.index("started_fresh=true; fi"), run.index("gh pr close"))
        self.assertLess(run.index("gh pr reopen"), run.index("never caught up"))

    def test_only_a_run_waiting_for_approval_is_approved_and_only_after_the_reopen(self):
        run = next(s for s in self.steps if s.get("name", "").startswith("Re-run"))["run"]
        self.assertEqual(run.count("/approve"), 1)
        self.assertRegex(run, r'if \[ "\$conclusion" = action_required \]; then\s+gh api -X POST "repos/\$REPOSITORY/actions/runs/\$id/approve"')
        self.assertLess(run.index("gh pr reopen"), run.index("/approve"))




if __name__ == "__main__":
    unittest.main()
