#!/usr/bin/env python3
"""Exercise queue decisions: no build dispatch, and unproven groups fail closed.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def triggers(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))



class QueueDecisionScriptTests(unittest.TestCase):
    """Run the two canary.yml scripts the queue path executes, with python3 stubbed."""

    @classmethod
    def setUpClass(cls):
        jobs = load("canary.yml")["jobs"]
        cls.paths = next(s for s in jobs["changes"]["steps"] if s.get("id") == "paths")
        cls.decide = next(s for s in jobs["canary"]["steps"] if s.get("name") == "Decide")

    def run_script(self, step: dict, env: dict, python_exit: int = 0) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub = tmp / "bin" / "python3"
            stub.parent.mkdir()
            stub.write_text(f'#!/bin/sh\nexit {python_exit}\n')
            stub.chmod(0o755)
            output = tmp / "output"
            output.touch()
            done = subprocess.run(
                ["bash", "-c", step["run"]], capture_output=True, text=True, cwd=tmp,
                env={"PATH": f"{stub.parent}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(output),
                     "CANARY_SET": '["libical"]', **env},
            )
            values = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
            return done.returncode, values

    def queue_env(self) -> dict:
        return {"EVENT": "merge_group", "PR": "", "HEAD_REPO": "", "REPO": "o/r", "SHA": "d" * 40,
                "QUEUE_REF": "refs/heads/gh-readonly-queue/main/pr-7-" + "c" * 40, "QUEUE_SHA": "d" * 40}

    def test_changes_never_asks_for_a_build_and_records_the_proof(self):
        for python_exit, verdict in ((0, "proven"), (1, "unproven"), (2, "unproven")):
            with self.subTest(python_exit=python_exit):
                code, out = self.run_script(self.paths, self.queue_env(), python_exit)
                self.assertEqual(code, 0)
                self.assertEqual(out, {"run": "false", "fork": "false", "queue": verdict})

    def test_the_gate_passes_a_merge_group_only_on_a_recorded_proof(self):
        base = {"EVENT": "merge_group", "RUN": "", "FORK": "", "RESULTS": "{}", "REPO": "o/r",
                "PR": "", "HEAD_SHA": "d" * 40}
        for queue, expected in (("proven", 0), ("unproven", 1), ("", 1)):
            with self.subTest(queue=queue):
                code, _ = self.run_script(self.decide, {**base, "QUEUE": queue})
                self.assertEqual(code, expected)

    def test_a_queue_proof_never_passes_a_pull_request(self):
        # A stray queue=proven must not short-circuit a pull request's results.
        code, _ = self.run_script(self.decide, {
            "EVENT": "pull_request", "QUEUE": "proven", "RUN": "true", "FORK": "false",
            "RESULTS": '{"pass1": {"result": "failure"}}', "REPO": "o/r", "PR": "7", "HEAD_SHA": "d" * 40,
        })
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
