#!/usr/bin/env python3
"""The hermetic lane backs off between network retries (#1208).

online() in tools/hermetic_build.sh retries the two network steps. A fixed
pause between attempts put four librepo retries into one bad minute on the
container lane, which is why the shared helper escalates its waits. The
hermetic lane must do the same without losing its cleanup between attempts.
"""

from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "hermetic_build.sh"


def online_source() -> str:
    found = re.search(r"^online\(\) \{\n.*?^\}\n", SCRIPT.read_text(), re.M | re.S)
    assert found, "hermetic_build.sh no longer defines online()"
    return found.group(0)


def run(failures: int, attempts: int = 3, output: str = "DOWN") -> tuple:
    """Source online() and retry a step that fails `failures` times.

    Returns the exit code, the waits it slept, the number of attempts, the
    number of cleanups and the infra-failure marker text (None when absent).
    """
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        sleeps = work / "sleeps"
        calls = work / "calls"
        cleanups = work / "cleanups"
        program = (
            "set -o pipefail\n"
            f"{online_source()}\n"
            f'sleep() {{ echo "$1" >> {sleeps}; }}\n'
            'infra_failed() { grep -q DOWN "$1"; }\n'
            "fake_step() {\n"
            f"  echo x >> {calls}\n"
            f'  [ "$(wc -l < {calls})" -gt {failures} ] || {{ echo {shlex.quote(output)}; return 7; }}\n'
            "}\n"
            f"cleanup() {{ echo x >> {cleanups}; }}\n"
            "PACKAGE=demo\n"
            "NET_RETRY_PAUSE=15\n"
            "NET_RETRY_BASE=5\n"
            "NET_RETRY_FACTOR=3\n"
            f"NET_ATTEMPTS={attempts}\n"
            f"REPORT_DIR={work}/reports\n"
            "online 'lock fetch' cleanup fake_step\n"
        )
        result = subprocess.run(
            ["bash", "-e", "-c", program],
            env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True,
        )
        waits = sleeps.read_text().split() if sleeps.exists() else []
        attempts_made = calls.read_text().count("x") if calls.exists() else 0
        cleanups_made = cleanups.read_text().count("x") if cleanups.exists() else 0
        marker = work / "reports" / "infra-failure"
        text = marker.read_text().strip() if marker.exists() else None
    return result.returncode, waits, attempts_made, cleanups_made, text


class HermeticBackoffTests(unittest.TestCase):
    def test_waits_escalate_like_the_shared_helper(self) -> None:
        code, waits, attempts, cleanups, marker = run(failures=2)
        self.assertEqual(code, 0)
        self.assertEqual(waits, ["5", "15"])
        self.assertEqual(attempts, 3)
        self.assertEqual(cleanups, 2)
        self.assertIsNone(marker)

    def test_a_fourth_attempt_reaches_forty_five_seconds(self) -> None:
        code, waits, attempts, cleanups, marker = run(failures=10, attempts=4)
        self.assertNotEqual(code, 0)
        self.assertEqual(waits, ["5", "15", "45"])
        self.assertEqual(attempts, 4)
        self.assertEqual(cleanups, 3)
        self.assertEqual(marker, "lock fetch")

    def test_a_dependency_error_is_not_an_outage(self) -> None:
        code, waits, attempts, cleanups, marker = run(
            failures=10, output="No match for argument: missing-devel"
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(waits, ["5", "15"])
        self.assertIsNone(marker)


if __name__ == "__main__":
    unittest.main()
