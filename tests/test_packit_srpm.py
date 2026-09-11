#!/usr/bin/env python3

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
PACKIT_CONFIG = ROOT / ".packit.yaml"
PACKIT_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-pilot.yml"
# The per-package steps moved into a reusable workflow so the pilot can fan out
# over chunks: 342 packages in one matrix exceeds the 256-job cap, which GitHub
# expands to nothing rather than rejecting.
PACKIT_CHUNK_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-chunk.yml"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"


from tools.packit_workflow import MATRIX_CHUNK, package_chunks, package_names


class PackitSrpmTests(unittest.TestCase):
    def test_workflow_stages_verified_sources_for_every_configured_package(self) -> None:
        config_packages = set(package_names(PACKIT_CONFIG))
        workflow = PACKIT_WORKFLOW.read_text() + PACKIT_CHUNK_WORKFLOW.read_text()
        source_packages = {
            package["name"]
            for package in json.loads(SOURCE_CONFIG.read_text())["packages"]
        }

        self.assertEqual(len(config_packages), 342)
        self.assertEqual(config_packages - source_packages, set())
        self.assertTrue(
            {"adw-gtk3-theme", "bootc", "igt-gpu-tools", "mesa", "runc"}
            <= config_packages
        )
        self.assertIn("python3 tools/packit_workflow.py packages", workflow)
        # The matrix now fans out over chunks, and each chunk fans out over its
        # own packages; both halves have to stay present.
        self.assertIn("fromJson(needs.discover.outputs.chunks)", workflow)
        self.assertIn("fromJson(inputs.packages)", workflow)
        self.assertIn("python3 tools/packit_workflow.py chunks", workflow)
        self.assertIn("--stage-into packages", workflow)
        self.assertIn("--verify-staged packages", workflow)
        self.assertIn("packit srpm --preserve-spec", workflow)
        self.assertIn("- tools/packit_source0.py", workflow)
        self.assertIn("- tools/packit_workflow.py", workflow)
        self.assertRegex(workflow, r"(?m)^  push:\n    branches: \[main\]$")
        self.assertIn("create-archive:", PACKIT_CONFIG.read_text())
        self.assertIn("tools/packit_source0.py", PACKIT_CONFIG.read_text())


    def test_every_chunk_fits_inside_the_matrix_cap(self) -> None:
        """342 packages in one matrix expands to zero jobs, not an error."""
        names = package_names(PACKIT_CONFIG)
        chunks = package_chunks(names)
        rebuilt = [name for chunk in chunks for name in json.loads(chunk)]

        self.assertLessEqual(MATRIX_CHUNK, 256)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(json.loads(chunk)), 256)
        self.assertEqual(rebuilt, names)


if __name__ == "__main__":
    unittest.main()
