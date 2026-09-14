#!/usr/bin/env python3
"""Coverage for tools/check_build_container_pinning.py, the guard for issue #43.

The tool resolves .github/workflows relative to its own location, so each case
copies the script into a throwaway tree and writes the workflows it should see.
That keeps the failure cases hypothetical -- no test needs a real broken
workflow committed to the repository to prove the guard fires.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tools" / "check_build_container_pinning.py"

PINNED_BLOCK = """\
jobs:
  build:
    steps:
      - run: quay.io/fedora/fedora@sha256:a58a82ed658c109c104e97fdcce52690337cff52e68dc8fa9c033a5fe38dfeec bash -exc '
            set -eu
            echo this build image is digest-pinned
          '
"""

MUTABLE_BLOCK = """\
jobs:
  build:
    steps:
      - run: quay.io/fedora/fedora:44 bash -exc '
            set -eu
            echo this build image uses a mutable tag
          '
"""


class BuildContainerPinningTests(unittest.TestCase):
    def run_guard(self, workflows: dict[str, str]) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            shutil.copy(GUARD, root / "tools" / GUARD.name)
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            for name, content in workflows.items():
                (workflow_dir / name).write_text(content)
            return subprocess.run(
                [sys.executable, str(root / "tools" / GUARD.name)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_passes_a_build_image_pinned_by_digest(self) -> None:
        result = self.run_guard({"build-stage.yml": PINNED_BLOCK})
        assert result.returncode == 0, result.stderr
        assert "digest-pinned" in result.stdout

    def test_fails_a_build_image_referenced_by_a_mutable_tag(self) -> None:
        result = self.run_guard({"build-stage.yml": MUTABLE_BLOCK})
        assert result.returncode == 1
        assert "build-stage.yml:4" in result.stderr
        assert "quay.io/fedora/fedora:44" in result.stderr
        assert "digest pin" in result.stderr

    def test_ignores_a_mutable_tag_mentioned_only_in_a_comment(self) -> None:
        """Documenting the pre-pin tag, as packit-srpm-pilot.yml does, is not a use."""
        comment_only = (
            "jobs:\n"
            "  note:\n"
            "    steps:\n"
            "      # quay.io/packit/packit:latest was the old pin, documented here\n"
            "      - run: echo done\n"
        )
        result = self.run_guard({"packit-srpm-pilot.yml": comment_only})
        assert result.returncode == 0, result.stderr

    def test_checks_every_workflow_not_only_build_stage(self) -> None:
        result = self.run_guard(
            {"build-stage.yml": PINNED_BLOCK, "rebuild-rpms.yml": MUTABLE_BLOCK}
        )
        assert result.returncode == 1
        assert "rebuild-rpms.yml:4" in result.stderr
        assert "build-stage.yml:" not in result.stderr

    def test_reports_every_unpinned_image_in_one_run(self) -> None:
        two = self.run_guard(
            {
                "build-stage.yml": MUTABLE_BLOCK,
                "recalculate-hummingbird-gaps.yml": (
                    "jobs:\n"
                    "  m:\n"
                    "    steps:\n"
                    "      - run: podman run --rm quay.io/hummingbird-community/bootc-os:latest true\n"
                ),
            }
        )
        assert two.returncode == 1
        assert "build-stage.yml:4" in two.stderr
        assert "bootc-os:latest" in two.stderr

    def test_counts_the_workflows_it_scanned(self) -> None:
        result = self.run_guard(
            {
                "build-stage.yml": PINNED_BLOCK,
                "rebuild-rpms.yml": PINNED_BLOCK,
                "validate.yml": "jobs:\n  v:\n    steps: []\n",
            }
        )
        assert result.returncode == 0, result.stderr
        assert "checked 3 workflows" in result.stdout

    def test_the_committed_workflows_pass_their_own_guard(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GUARD)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "every quay.io build image is digest-pinned" in result.stdout


if __name__ == "__main__":
    unittest.main()
