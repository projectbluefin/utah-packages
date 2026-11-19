"""RPM artifacts are fetched by exact name, never by a capped or REST listing.

Run 44386298520: download-artifact with a token started every download at
once over REST; publish0 hit the secondary rate limit and every wave-1 build
exhausted the installation's REST budget, then built on without earlier
waves' RPMs because that step was continue-on-error. These pin the fix:
tools/fetch-artifacts/fetch.mjs, named from prepare's stage map.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from tools.publish_gate import artifact_names
from tools.rebuild_plan import stage_outputs

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def steps(workflow: dict):
    for job in workflow["jobs"].values():
        yield from job.get("steps", [])


class NamesTests(unittest.TestCase):
    MAP = {"glib2": 0, "gtk4": 1, "mutter": 2}

    def test_a_publication_covers_waves_through_its_own(self) -> None:
        self.assertEqual(artifact_names(self.MAP, "c-", through=1),
                         ["c-rpm-s0-glib2", "c-rpm-s1-gtk4"])
        self.assertEqual(len(artifact_names(self.MAP, "")), 3)

    def test_a_build_stage_takes_only_strictly_earlier_waves(self) -> None:
        self.assertEqual(artifact_names(self.MAP, "", below=2), ["rpm-s0-glib2", "rpm-s1-gtk4"])
        self.assertEqual(artifact_names(self.MAP, "", below=0), [])

    def test_prepare_emits_the_stage_map(self) -> None:
        outputs = stage_outputs([{"name": "a", "stage": 0}, {"name": "b", "stage": 1}],
                                {"a": 0, "b": 3})
        self.assertEqual(json.loads(outputs["stage_map"]), {"a": 0, "b": 3})


class WorkflowTests(unittest.TestCase):
    def test_no_rpm_download_uses_a_listing(self) -> None:
        for name in ("build-stage.yml", "publish-repository.yml"):
            text = (WORKFLOWS / name).read_text()
            self.assertNotIn("github-token: ${{ github.token }}", text, name)
            self.assertNotIn("ACTIONS_ARTIFACT_MAX_ARTIFACT_COUNT", text, name)
            for step in steps(load(name)):
                uses = step.get("uses", "")
                if uses.startswith("actions/download-artifact"):
                    self.assertIn("name", step["with"], (name, step))
                    self.assertNotIn("pattern", step["with"], (name, step))

    def test_earlier_waves_are_collected_fail_closed(self) -> None:
        build = load("build-stage.yml")
        collect = next(s for s in steps(build) if s.get("name") == "Collect RPMs built by earlier stages")
        self.assertIn("fetch-artifacts/fetch.mjs", collect["with"]["script"])
        self.assertNotIn("continue-on-error", collect)

    def test_every_reusable_call_passes_the_stage_map(self) -> None:
        rebuild = load("rebuild-rpms.yml")
        calls = [job for job in rebuild["jobs"].values()
                 if str(job.get("uses", "")).endswith(("build-stage.yml", "publish-repository.yml"))]
        self.assertGreater(len(calls), 10)
        for job in calls:
            self.assertEqual(job["with"]["stage_map"], "${{ needs.prepare.outputs.stage_map }}")
        self.assertIn("stage_map", rebuild["jobs"]["prepare"]["outputs"])
        for name in ("build-stage.yml", "publish-repository.yml"):
            spec = load(name)[True]["workflow_call"]["inputs"]["stage_map"]
            self.assertTrue(spec["required"], name)

    def test_the_client_is_locked(self) -> None:
        package = json.loads((ROOT / "tools/fetch-artifacts/package.json").read_text())
        version = package["dependencies"]["@actions/artifact"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        lock = json.loads((ROOT / "tools/fetch-artifacts/package-lock.json").read_text())
        self.assertEqual(lock["packages"]["node_modules/@actions/artifact"]["version"], version)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FetchToolTests(unittest.TestCase):
    def test_node_suite(self) -> None:
        result = subprocess.run(["node", "--test", "tests/js/fetch_artifacts.test.mjs"], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
