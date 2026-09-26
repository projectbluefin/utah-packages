#!/usr/bin/env python3
"""A run script that contains ${{ }} is evaluated as one expression.

GitHub then rejects the whole workflow -- and any workflow that calls it --
with "Exceeded max expression length 21000", before a single job starts.
build-stage.yml's container build script is over 30000 characters, so one
${{ }} in it took the canary down as "a workflow file issue" with no log.
Pass values through env: instead.
"""

from pathlib import Path
import unittest

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
LIMIT = 21000


def scripts(workflow: dict):
    for job_name, job in (workflow.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            if "run" in step:
                yield f"{job_name}[{index}] {step.get('name', '')}", step["run"]


class ExpressionLengthTests(unittest.TestCase):
    def test_no_long_run_script_contains_an_expression(self) -> None:
        offenders = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for where, run in scripts(yaml.safe_load(path.read_text())):
                if "${{" in run and len(run) >= LIMIT:
                    offenders.append(f"{path.name}: {where} ({len(run)} characters)")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
