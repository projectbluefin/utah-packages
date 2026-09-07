#!/usr/bin/env python3
"""Coverage for tools/check_workflow_quoting.py, the gate run by rebuild-rpms.yml.

The tool resolves .github/workflows relative to its own location, so each case
copies the script into a throwaway tree and writes the workflows it should see.
That keeps the failure cases hypothetical -- no test needs a real broken
workflow committed to the repository to prove the gate fires.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tools" / "check_workflow_quoting.py"

CLEAN_BLOCK = """\
jobs:
  build:
    steps:
      - run: |
          docker run --rm image bash -exc '
            set -eu
            dnf install -y make
            echo this job own diagnostic
          '
"""

APOSTROPHE_BLOCK = """\
jobs:
  build:
    steps:
      - run: |
          docker run --rm image bash -exc '
            set -eu
            # Red Hat's disttag differs from ours
            dnf install -y make
          '
"""


class CheckWorkflowQuotingTests(unittest.TestCase):
    def run_checker(self, workflows: dict[str, str]) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            shutil.copy(CHECKER, root / "tools" / CHECKER.name)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            for name, content in workflows.items():
                (workflow_dir / name).write_text(content)
            return subprocess.run(
                [sys.executable, str(root / "tools" / CHECKER.name)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_passes_a_build_script_with_no_apostrophe(self) -> None:
        result = self.run_checker({"rebuild-rpms.yml": CLEAN_BLOCK})
        assert result.returncode == 0, result.stderr
        assert "checked 1 workflows" in result.stdout

    def test_fails_on_an_apostrophe_inside_the_build_script(self) -> None:
        result = self.run_checker({"rebuild-rpms.yml": APOSTROPHE_BLOCK})
        assert result.returncode == 1
        assert "rebuild-rpms.yml:7" in result.stderr
        assert "Red Hat's disttag" in result.stderr
        assert "Rephrase to avoid the apostrophe" in result.stderr

    def test_ignores_an_apostrophe_outside_any_build_script(self) -> None:
        outside = (
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      # Fedora's own comment, not inside a bash -exc body\n"
            "      - run: echo hello\n"
        )
        result = self.run_checker({"rebuild-rpms.yml": outside})
        assert result.returncode == 0, result.stderr

    def test_checks_every_workflow_not_only_rebuild_rpms(self) -> None:
        result = self.run_checker(
            {"rebuild-rpms.yml": CLEAN_BLOCK, "build-stage.yml": APOSTROPHE_BLOCK}
        )
        assert result.returncode == 1
        assert "build-stage.yml:7" in result.stderr
        assert "rebuild-rpms.yml:" not in result.stderr

    def test_reports_every_offending_line_in_one_run(self) -> None:
        two_offenders = textwrap.dedent(
            """\
            jobs:
              build:
                steps:
                  - run: |
                      docker run --rm image bash -exc '
                        # AlmaLinux's counter
                        # Fedora's release
                      '
            """
        )
        result = self.run_checker({"rebuild-rpms.yml": two_offenders})
        assert result.returncode == 1
        assert "rebuild-rpms.yml:6" in result.stderr
        assert "rebuild-rpms.yml:7" in result.stderr

    def test_scans_a_later_block_after_an_earlier_one_closed(self) -> None:
        two_blocks = textwrap.dedent(
            """\
            jobs:
              build:
                steps:
                  - run: |
                      docker run --rm image bash -exc '
                        echo clean
                      '
                  - run: |
                      docker run --rm image bash -exc '
                        # Red Hat's second block
                      '
            """
        )
        result = self.run_checker({"rebuild-rpms.yml": two_blocks})
        assert result.returncode == 1
        assert "rebuild-rpms.yml:10" in result.stderr

    def test_excludes_the_opening_and_closing_lines_from_the_scan(self) -> None:
        """The quotes that delimit the script are not themselves offenders."""
        result = self.run_checker({"rebuild-rpms.yml": CLEAN_BLOCK})
        assert result.returncode == 0, result.stderr

    def test_ignores_a_block_that_is_never_closed(self) -> None:
        """Documents current behaviour: an unterminated body is not scanned."""
        unterminated = textwrap.dedent(
            """\
            jobs:
              build:
                steps:
                  - run: |
                      docker run --rm image bash -exc '
                        # Red Hat's apostrophe in an unclosed body
            """
        )
        result = self.run_checker({"rebuild-rpms.yml": unterminated})
        assert result.returncode == 0, result.stderr

    def test_counts_the_workflows_it_scanned(self) -> None:
        result = self.run_checker(
            {
                "rebuild-rpms.yml": CLEAN_BLOCK,
                "build-stage.yml": CLEAN_BLOCK,
                "validate.yml": "jobs:\n  validate:\n    steps: []\n",
            }
        )
        assert result.returncode == 0, result.stderr
        assert "checked 3 workflows" in result.stdout

    def test_the_checked_in_workflows_pass_their_own_gate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "no build script contains a quote that would close it" in result.stdout


if __name__ == "__main__":
    unittest.main()
