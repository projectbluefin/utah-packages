#!/usr/bin/env python3

import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
PACKIT_CONFIG = ROOT / ".packit.yaml"
PACKIT_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-pilot.yml"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"


from tools.packit_workflow import package_names


class PackitSrpmTests(unittest.TestCase):
    def test_workflow_stages_verified_sources_for_every_configured_package(self) -> None:
        config_packages = set(package_names(PACKIT_CONFIG))
        workflow = PACKIT_WORKFLOW.read_text()
        source_packages = {
            package["name"]
            for package in json.loads(SOURCE_CONFIG.read_text())["packages"]
        }

        self.assertEqual(len(config_packages), 193)
        self.assertEqual(config_packages - source_packages, set())
        self.assertTrue(
            {"adw-gtk3-theme", "bootc", "igt-gpu-tools", "mesa", "runc"}
            <= config_packages
        )
        self.assertIn("python3 tools/packit_workflow.py packages", workflow)
        self.assertIn("fromJson(needs.discover.outputs.packages)", workflow)
        self.assertIn("--stage-into packages", workflow)
        self.assertIn("--verify-staged packages", workflow)
        self.assertIn("packit srpm --preserve-spec", workflow)
        self.assertIn("- tools/packit_source0.py", workflow)
        self.assertIn("- tools/packit_workflow.py", workflow)
        self.assertRegex(workflow, r"(?m)^  push:\n    branches: \[main\]$")
        self.assertIn("create-archive:", PACKIT_CONFIG.read_text())
        self.assertIn("tools/packit_source0.py", PACKIT_CONFIG.read_text())
        self.assertIn(
            "quay.io/packit/packit@sha256:8a1784251c51eed7a094820c894e2ee7f4ed4bbce4eb78eb172a04de3fae43e1",
            workflow,
        )
        self.assertNotIn(
            "149e6e06d3e5fb2f10d19760c8a0031c7d8825e7bb91a5f4a7ab9b927c947494",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
