#!/usr/bin/env python3
"""The required checks report in the merge queue, and the queue cannot publish.

The `main` ruleset requires `Canary`, `Unit tests` and `Runtime contract`. A
merge queue waits for each on its own `merge_group` commit and removes the
entry when one never reports, so every workflow producing one must subscribe
to `merge_group`. A queue ref is a branch nobody reviewed as such, so a
`merge_group` run must hold no token that can push, sign, attest or open
issues. These tests read the workflows and execute the decision scripts the
queue path runs.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIRED = {"Canary": "canary.yml", "Unit tests": "validate.yml", "Runtime contract": "validate.yml"}
GUARD = "github.event_name != 'merge_group'"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def triggers(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


def needs(job: dict) -> list[str]:
    value = job.get("needs", [])
    return [value] if isinstance(value, str) else list(value)


def runs_on_merge_group(jobs: dict, name: str) -> bool:
    """Whether a job can run on a merge_group event, from its `if` and its needs."""
    job = jobs[name]
    condition = str(job.get("if", ""))
    if condition.startswith(GUARD + " &&") or condition == GUARD:
        return False
    if "always()" not in condition and "cancelled()" not in condition:
        # The implicit success(): a skipped need skips this job too.
        return all(runs_on_merge_group(jobs, need) for need in needs(job))
    # always()/!cancelled() jobs run regardless, unless they also require a
    # need that cannot run to have succeeded.
    return not any(
        f"needs.{need}.result == 'success'" in condition and not runs_on_merge_group(jobs, need)
        for need in needs(job)
    )


def write_scopes(permissions) -> set[str]:
    if permissions in (None, "write-all"):
        return {"<inherited or write-all>"}
    if permissions == "read-all" or permissions == {}:
        return set()
    return {scope for scope, level in permissions.items() if level != "read"}


class RequiredChecksReportInTheQueueTests(unittest.TestCase):
    def test_every_required_check_is_a_job_of_a_workflow_that_runs_on_merge_group(self):
        for check, file in REQUIRED.items():
            with self.subTest(check=check):
                workflow = load(file)
                self.assertIn("merge_group", triggers(workflow))
                self.assertIsNone(triggers(workflow)["merge_group"], "no types or filters: every group")
                jobs = workflow["jobs"]
                matching = [name for name, job in jobs.items() if job.get("name") == check]
                self.assertEqual(len(matching), 1, f"exactly one job reports {check!r}")
                self.assertTrue(runs_on_merge_group(jobs, matching[0]),
                                f"{check!r} would never report in the queue")


class TheQueueCannotPublishTests(unittest.TestCase):
    def test_validate_is_read_only(self):
        workflow = load("validate.yml")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        for name, job in workflow["jobs"].items():
            with self.subTest(job=name):
                self.assertNotIn("permissions", job)
                self.assertNotIn("uses", job)

    def test_canary_runs_only_its_read_only_decision_jobs_on_merge_group(self):
        jobs = load("canary.yml")["jobs"]
        running = {name for name in jobs if runs_on_merge_group(jobs, name)}
        self.assertEqual(running, {"changes", "canary"})
        for name in running:
            with self.subTest(job=name):
                self.assertEqual(write_scopes(jobs[name].get("permissions")), set())

    def test_both_roots_of_every_build_carry_the_event_guard(self):
        # changes already answers run=false on a merge group; the guard keeps
        # that true even if the script changes. Every other build or publish
        # job needs pass1 or pass6.
        jobs = load("canary.yml")["jobs"]
        for name in ("pass1", "pass6"):
            with self.subTest(job=name):
                self.assertTrue(jobs[name]["if"].startswith(GUARD + " &&"))
        callers = {name for name, job in jobs.items() if job.get("uses")}
        self.assertTrue(callers)
        for name in callers:
            with self.subTest(job=name):
                self.assertFalse(runs_on_merge_group(jobs, name))

    def test_queue_runs_are_never_cancelled_by_one_another(self):
        # Each merge group has its own ref, so a per-ref group cancels nothing
        # in the queue.
        self.assertIn("github.ref", load("canary.yml")["concurrency"]["group"])


class QueueDecisionScriptTests(unittest.TestCase):
    """Run the two canary.yml scripts the queue path executes, with python3 stubbed."""

    @classmethod
    def setUpClass(cls):
        jobs = load("canary.yml")["jobs"]
        cls.paths = next(s for s in jobs["changes"]["steps"] if s.get("id") == "paths")
        cls.decide = next(s for s in jobs["canary"]["steps"] if s.get("name") == "Decide")

    def run_script(self, step: dict, env: dict, python_exit: int = 0) -> tuple[int, dict, str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            calls = tmp / "calls"
            stub = tmp / "bin" / "python3"
            stub.parent.mkdir()
            stub.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\nexit {python_exit}\n')
            stub.chmod(0o755)
            output = tmp / "output"
            output.touch()
            done = subprocess.run(
                ["bash", "-c", step["run"]], capture_output=True, text=True, cwd=tmp,
                env={"PATH": f"{stub.parent}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(output),
                     "CANARY_SET": '["libical"]', **env},
            )
            values = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
            return done.returncode, values, calls.read_text() if calls.exists() else ""

    def queue_env(self) -> dict:
        return {"EVENT": "merge_group", "PR": "", "HEAD_REPO": "", "REPO": "o/r", "SHA": "d" * 40,
                "QUEUE_REF": "refs/heads/gh-readonly-queue/main/pr-7-" + "c" * 40, "QUEUE_SHA": "d" * 40}

    def test_changes_never_asks_for_a_build_and_records_the_proof(self):
        for python_exit, verdict in ((0, "proven"), (1, "unproven"), (2, "unproven")):
            with self.subTest(python_exit=python_exit):
                code, out, calls = self.run_script(self.paths, self.queue_env(), python_exit)
                self.assertEqual(code, 0)
                self.assertEqual(out, {"run": "false", "fork": "false", "queue": verdict})
                self.assertIn("tools/canary.py merge-group --repository o/r --head-ref "
                              "refs/heads/gh-readonly-queue/main/pr-7-", calls)
                self.assertNotIn("pr-relevant", calls)

    def test_the_gate_passes_a_merge_group_only_on_a_recorded_proof(self):
        base = {"EVENT": "merge_group", "RUN": "", "FORK": "", "RESULTS": "{}", "REPO": "o/r",
                "PR": "", "HEAD_SHA": "d" * 40}
        for queue, expected in (("proven", 0), ("unproven", 1), ("", 1)):
            with self.subTest(queue=queue):
                code, _, _ = self.run_script(self.decide, {**base, "QUEUE": queue})
                self.assertEqual(code, expected)

    def test_a_queue_proof_never_passes_a_pull_request(self):
        # A stray queue=proven must not short-circuit a pull request's results.
        code, _, _ = self.run_script(self.decide, {
            "EVENT": "pull_request", "QUEUE": "proven", "RUN": "true", "FORK": "false",
            "RESULTS": '{"pass1": {"result": "failure"}}', "REPO": "o/r", "PR": "7", "HEAD_SHA": "d" * 40,
        })
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
