#!/usr/bin/env python3

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
PACKIT_CONFIG = ROOT / ".packit.yaml"
PACKIT_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-pilot.yml"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"


class PackitSrpmTests(unittest.TestCase):
    def test_workflow_stages_verified_sources_for_every_configured_package(self) -> None:
        config_packages = {
            match.group(1)
            for line in PACKIT_CONFIG.read_text().splitlines()
            if (match := re.fullmatch(r"  ([a-z0-9][a-z0-9+.-]*):", line))
        }
        workflow = PACKIT_WORKFLOW.read_text()
        matrix_packages = set(re.findall(r"^          - ([a-z0-9][a-z0-9+.-]*)$", workflow, re.MULTILINE))
        source_packages = {
            package["name"]
            for package in json.loads(SOURCE_CONFIG.read_text())["packages"]
        }

        self.assertEqual(matrix_packages, config_packages)
        self.assertEqual(matrix_packages - source_packages, set())
        self.assertTrue(
            {"adw-gtk3-theme", "bootc", "igt-gpu-tools", "mesa", "runc"}
            <= matrix_packages
        )
        self.assertIn("--stage-into packages", workflow)
        self.assertIn("packit srpm --preserve-spec", workflow)
        self.assertRegex(workflow, r"(?m)^  push:\n    branches: \[main\]$")


if __name__ == "__main__":
    unittest.main()
