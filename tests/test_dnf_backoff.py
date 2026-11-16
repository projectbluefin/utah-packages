#!/usr/bin/env python3
"""The container lane waits and retries a dnf call the Hummingbird host refused.

packages.redhat.com answers 503 for a minute at a time, and librepo's own
retries land inside that minute. vulkan-headers lost its libxml2 upgrade that
way, and libical its @buildsys-build install in the cache-key step (issue
#1160). with_backoff in tools/dnf_backoff.sh is run here, as the script
defines it, against a command that fails a set number of times.
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "dnf_backoff.sh"
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"


def with_backoff() -> str:
    found = re.search(r"^with_backoff\(\) \{\n.*?^\}\n", SCRIPT.read_text(), re.M | re.S)
    assert found, "with_backoff is not defined in dnf_backoff.sh"
    return found.group(0)


def run(failures: int, status: int = 7) -> tuple[int, list[str], list[str]]:
    """with_backoff on a fake dnf that fails `failures` times, then succeeds."""
    with tempfile.TemporaryDirectory() as directory:
        calls = Path(directory) / "calls"
        sleeps = Path(directory) / "sleeps"
        program = (
            with_backoff()
            + f'sleep() {{ echo "$1" >> {sleeps}; }}\n'
            + "fake_dnf() {\n"
            + f'  printf "%s|" "$@" >> {calls}; echo >> {calls}\n'
            + f'  [ "$(wc -l < {calls})" -gt {failures} ] || return {status}\n'
            + "}\n"
            + 'with_backoff fake_dnf -y --disablerepo=x upgrade "two words"\n'
        )
        result = subprocess.run(["bash", "-e", "-c", program], capture_output=True, text=True)
        attempts = calls.read_text().splitlines() if calls.exists() else []
        waits = sleeps.read_text().split() if sleeps.exists() else []
    return result.returncode, attempts, waits


class DnfBackoffTests(unittest.TestCase):
    def test_a_refusal_that_clears_is_waited_out(self) -> None:
        code, attempts, waits = run(failures=2)
        self.assertEqual(code, 0)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(waits, ["5", "15"])

    def test_the_command_reaches_dnf_with_its_arguments_intact(self) -> None:
        _, attempts, _ = run(failures=0)
        self.assertEqual(attempts, ["-y|--disablerepo=x|upgrade|two words|"])

    def test_a_lasting_failure_still_fails_with_its_own_status(self) -> None:
        code, attempts, waits = run(failures=10, status=7)
        self.assertEqual(code, 7)
        self.assertEqual(len(attempts), 4)
        self.assertEqual(waits, ["5", "15", "45"])

    def test_the_cache_key_step_retries_every_dnf_call_it_needs(self) -> None:
        # The cache-key step resolves the same build root as build_container.sh
        # before the build runs, so a 503 there failed libical just the same.
        workflow = yaml.safe_load(BUILD_STAGE.read_text())
        step = next(
            s for s in workflow["jobs"]["build"]["steps"]
            if s.get("name") == "Resolve the package cache key"
        )
        script = step["run"]
        self.assertIn('-v "$PWD/tools:/tools:ro,Z"', script)
        self.assertIn(". /tools/dnf_backoff.sh", script)
        required = [
            line.strip() for line in script.splitlines()
            if re.search(r"(^|\s)dnf -y ", line) and not line.rstrip().endswith("|| true")
        ]
        self.assertTrue(required)
        for line in required:
            self.assertTrue(line.startswith("with_backoff dnf "), line)


if __name__ == "__main__":
    unittest.main()
