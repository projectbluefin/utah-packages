"""A matrix job must never consume a sibling's partially built repository."""

import fnmatch
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from tools.package_inventory import KNOWN_STAGES

ROOT = Path(__file__).resolve().parents[1]


class BuildStageTests(unittest.TestCase):
    def test_artifact_selector_contains_only_strictly_earlier_stages(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/build-stage.yml").read_text())
        steps = workflow["jobs"]["build"]["steps"]
        selector = next(step for step in steps if step.get("id") == "prior")
        download = next(step for step in steps if step.get("name") == "Collect RPMs built by earlier stages")
        self.assertEqual(selector["if"], "inputs.stage != '0'")
        self.assertEqual(download["if"], "inputs.stage != '0'")
        for stage in sorted(KNOWN_STAGES - {0}):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "output"
                subprocess.run(["bash", "-eu", "-c", selector["run"]], check=True,
                               env={**os.environ, "STAGE": str(stage), "GITHUB_OUTPUT": str(output)})
                pattern = output.read_text().strip().removeprefix("pattern=")
                artifacts = [f"rpm-s{n}-package" for n in KNOWN_STAGES]
                self.assertEqual(fnmatch.filter(artifacts, pattern), artifacts[:stage])

    def test_workflow_and_inventory_support_the_same_stages(self):
        jobs = yaml.safe_load((ROOT / ".github/workflows/rebuild-rpms.yml").read_text())["jobs"]
        declared = {int(name.removeprefix("rebuild")) for name in jobs if name.startswith("rebuild")}
        self.assertEqual(declared, KNOWN_STAGES)
        self.assertTrue({f"rebuild{n}" for n in declared} <= set(jobs["publish"]["needs"]))

    def test_webrtc_precedes_desktop_consumers_of_the_new_abseil_abi(self):
        packages = json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
        stage = {p["name"]: p.get("stage", 0) for p in packages}
        self.assertLess(stage["abseil-cpp"], stage["webrtc-audio-processing"])
        self.assertLess(stage["webrtc-audio-processing"], stage["gtk4"])
        self.assertLess(stage["webrtc-audio-processing"], stage["mutter"])
        self.assertLess(stage["evolution-data-server"], stage["evolution-ews"])
