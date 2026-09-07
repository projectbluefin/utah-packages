#!/usr/bin/env python3
"""Cover ``tools/check_workflow_quoting.py``, which had no unit tests.

The tool is the only thing standing between an apostrophe in a comment and 36
simultaneously dead stage-0 jobs, and it is a module-level script with no
importable function. So it is exercised the way CI runs it: copied into a
throwaway tree beside synthetic ``.github/workflows`` files and executed.
"""

import shutil
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "check_workflow_quoting.py"


def run(workflows: dict[str, str]) -> subprocess.CompletedProcess:
    """Run the checker against ``workflows`` in an isolated repository tree."""
    directory = tempfile.TemporaryDirectory()
    try:
        root = Path(directory.name)
        (root / "tools").mkdir()
        shutil.copy(TOOL, root / "tools" / TOOL.name)
        workflows_dir = root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        for name, body in workflows.items():
            (workflows_dir / name).write_text(body)
        return subprocess.run(
            [sys.executable, str(root / "tools" / TOOL.name)],
            capture_output=True,
            text=True,
        )
    finally:
        directory.cleanup()


CLEAN = """\
jobs:
  build:
    steps:
      - run: |
          docker run image bash -exc '
            # Fedora own noopenh264 repo is not wanted here.
            dnf -y install make
          '
"""

OFFENDING = """\
jobs:
  build:
    steps:
      - run: |
          docker run image bash -exc '
            # Fedora's noopenh264 repo is not wanted here.
            dnf -y install make
          '
"""


class CheckWorkflowQuotingTests(unittest.TestCase):
    def test_clean_script_passes_and_reports_the_count(self) -> None:
        result = run({"rebuild-rpms.yml": CLEAN})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checked 1 workflows", result.stdout)

    def test_apostrophe_inside_the_script_fails(self) -> None:
        result = run({"rebuild-rpms.yml": OFFENDING})
        self.assertEqual(result.returncode, 1)
        self.assertIn("rebuild-rpms.yml:6", result.stderr)
        self.assertIn("Fedora's", result.stderr)

    def test_apostrophe_outside_the_script_is_allowed(self) -> None:
        outside = "# Fedora's comment lives out here.\n" + CLEAN
        self.assertEqual(run({"rebuild-rpms.yml": outside}).returncode, 0)

    def test_closing_delimiter_line_is_not_itself_an_offender(self) -> None:
        # The lone ``'`` that ends the script must not be reported as a quote
        # inside the script, or every clean workflow would fail.
        result = run({"rebuild-rpms.yml": CLEAN})
        self.assertNotIn("offend", result.stderr.lower())

    def test_every_workflow_is_checked_not_just_rebuild_rpms(self) -> None:
        result = run({"rebuild-rpms.yml": CLEAN, "build-stage.yml": OFFENDING})
        self.assertEqual(result.returncode, 1)
        self.assertIn("build-stage.yml", result.stderr)

    def test_all_offending_lines_are_listed(self) -> None:
        both = OFFENDING.replace("dnf -y install make", "echo Red Hat's mirror")
        result = run({"rebuild-rpms.yml": both})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Fedora's", result.stderr)
        self.assertIn("Red Hat's", result.stderr)

    def test_second_script_block_in_the_same_workflow_is_checked(self) -> None:
        result = run({"rebuild-rpms.yml": CLEAN + OFFENDING})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Fedora's", result.stderr)

    def test_unterminated_script_block_is_not_reported(self) -> None:
        # Without a closing delimiter there is no script body to judge; the
        # tool must not guess and must not crash.
        unterminated = OFFENDING.rsplit("'", 1)[0]
        self.assertEqual(run({"rebuild-rpms.yml": unterminated}).returncode, 0)

    def test_no_workflows_at_all_still_passes(self) -> None:
        result = run({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("checked 0 workflows", result.stdout)

    def test_repository_workflows_pass_today(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL)], capture_output=True, text=True, cwd=ROOT
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
