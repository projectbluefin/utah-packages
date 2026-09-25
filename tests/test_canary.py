#!/usr/bin/env python3
"""The canary's decisions: when it runs, and what counts as a pass."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from tools import canary

ROOT = Path(__file__).resolve().parent.parent
CANARY = ROOT / ".github" / "workflows" / "canary.yml"


def job(name: str, build: str | None, restore: str | None, conclusion="success") -> dict:
    steps = []
    if restore is not None:
        steps.append({"name": canary.RESTORE_STEP, "conclusion": restore})
    if build is not None:
        steps.append({"name": canary.BUILD_STEP, "conclusion": build})
    return {"name": name, "conclusion": conclusion, "steps": steps}


SET = {"libical", "vulkan-headers", "vulkan-loader"}


def healthy_jobs() -> list[dict]:
    jobs = [
        job('pass1 / rebuild0 (["libical", "vulkan-headers"]) / build (libical)', "success", "success"),
        job('pass1 / rebuild0 (["libical", "vulkan-headers"]) / build (vulkan-headers)', "success", "success"),
        job('pass1 / rebuild4 (["vulkan-loader"]) / build (vulkan-loader)', "success", "success"),
        job("pass1 / precedence", None, None),
    ]
    for name in ("pass2", "pass3"):
        jobs += [
            job(f'{name} / rebuild0 (["libical"]) / build (libical)', "skipped", "success"),
            job(f'{name} / rebuild0 (["vulkan-headers"]) / build (vulkan-headers)', "skipped", "success"),
            job(f'{name} / rebuild4 (["vulkan-loader"]) / build (vulkan-loader)', "skipped", "success"),
        ]
    jobs.append(job(
        'pass3 / rebuild0 (["python-typing-inspection"]) / build (python-typing-inspection)',
        "success", "success",
    ))
    return jobs


class TouchesPipelineTests(unittest.TestCase):
    def test_pipeline_paths_run_the_canary(self) -> None:
        for path in (
            ".github/workflows/rebuild-rpms.yml",
            ".github/workflows/build-stage.yml",
            ".github/actions/load-buildroot/action.yml",
            "tools/publish_gate.py",
            "config/upstream-sources.json",
            "Containerfile.repo",
        ):
            with self.subTest(path=path):
                self.assertTrue(canary.touches_pipeline(["docs/x.md", path]))

    def test_recipes_and_docs_do_not(self) -> None:
        self.assertFalse(canary.touches_pipeline([
            "packages/fish/fish.spec", "docs/architecture.md", "AGENTS.md", "tests/test_x.py",
        ]))
        self.assertFalse(canary.touches_pipeline([]))


class SaltTests(unittest.TestCase):
    def test_the_salt_is_stable_and_covers_the_build_path(self) -> None:
        self.assertEqual(canary.salt(), canary.salt())
        self.assertRegex(canary.salt(), r"^canary-[0-9a-f]{16}$")
        self.assertIn(".github/workflows/build-stage.yml", canary.BUILD_PATH)
        for relative in canary.BUILD_PATH:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_a_build_path_change_moves_the_salt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in canary.BUILD_PATH:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text("x")
            before = canary.salt(root)
            (root / canary.BUILD_PATH[0]).write_text("y")
            self.assertNotEqual(before, canary.salt(root))


class LayerTests(unittest.TestCase):
    def test_two_layers_metadata_first_is_accepted(self) -> None:
        manifest = {"layers": [{"size": 10_000}, {"size": 90_000_000}]}
        self.assertEqual(canary.check_layers(manifest), [])

    def test_one_layer_is_refused(self) -> None:
        self.assertTrue(canary.check_layers({"layers": [{"size": 2_000_000_000}]}))

    def test_payload_first_is_refused(self) -> None:
        manifest = {"layers": [{"size": 90_000_000}, {"size": 10_000}]}
        self.assertTrue(canary.check_layers(manifest))

    def test_primary_sources_reads_a_gzip_primary(self) -> None:
        body = (
            '<metadata xmlns="http://linux.duke.edu/metadata/common" '
            'xmlns:rpm="http://linux.duke.edu/metadata/rpm">'
            "<package><name>libical</name><format>"
            "<rpm:sourcerpm>libical-2.5.0-1.hum1.bfin.src.rpm</rpm:sourcerpm>"
            "</format></package></metadata>"
        )
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml.gz").write_bytes(gzip.compress(body.encode()))
            self.assertEqual(canary.primary_sources(repodata), {"libical"})


class CacheVerdictTests(unittest.TestCase):
    def verdict(self, jobs: list[dict]) -> list[str]:
        return canary.cache_problems(
            canary.build_outcomes(jobs), SET, "python-typing-inspection"
        )

    def test_a_healthy_canary_passes(self) -> None:
        outcomes = canary.build_outcomes(healthy_jobs())
        self.assertEqual(outcomes["pass1"]["vulkan-loader"], "compiled")
        self.assertEqual(outcomes["pass2"]["vulkan-loader"], "cache hit")
        self.assertEqual(self.verdict(healthy_jobs()), [])

    def test_a_compile_in_pass2_fails(self) -> None:
        jobs = healthy_jobs()
        for entry in jobs:
            if entry["name"].startswith("pass2") and entry["name"].endswith("(vulkan-headers)"):
                entry["steps"][1]["conclusion"] = "success"
        problems = self.verdict(jobs)
        self.assertEqual(len(problems), 1)
        self.assertIn("pass2: vulkan-headers was compiled", problems[0])

    def test_a_miss_caused_by_the_perturbation_fails(self) -> None:
        jobs = healthy_jobs()
        for entry in jobs:
            if entry["name"].startswith("pass3") and entry["name"].endswith("(libical)"):
                entry["steps"][1]["conclusion"] = "success"
        self.assertIn("pass3: libical was compiled, not a cache hit", self.verdict(jobs))

    def test_the_perturbed_package_must_compile(self) -> None:
        jobs = healthy_jobs()
        jobs[-1]["steps"][1]["conclusion"] = "skipped"
        self.assertTrue(any("must compile" in p for p in self.verdict(jobs)))

    def test_a_missing_build_is_a_failure_not_a_pass(self) -> None:
        jobs = [j for j in healthy_jobs() if not j["name"].startswith("pass2")]
        self.assertTrue(any(p.startswith("pass2 built []") for p in self.verdict(jobs)))

    def test_the_summary_names_every_outcome(self) -> None:
        outcomes = canary.build_outcomes(healthy_jobs())
        text = canary.summary(outcomes, [])
        self.assertIn("| pass2 | `vulkan-headers` | cache hit |", text)


class WorkflowShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = yaml.safe_load(CANARY.read_text())
        cls.jobs = cls.workflow["jobs"]

    def test_the_canary_set_spans_two_stages_with_a_reverse_dependency(self) -> None:
        from tools.package_inventory import source_locks

        members = json.loads(self.workflow["env"]["CANARY_SET"])
        self.assertEqual(set(members), SET)
        locks = source_locks(ROOT)
        stages = {name: locks[name].get("stage") or 0 for name in members}
        self.assertGreater(len(set(stages.values())), 1)
        spec = (ROOT / "packages" / "vulkan-loader" / "vulkan-loader.spec").read_text()
        self.assertRegex(spec, r"(?m)^BuildRequires:\s+vulkan-headers = %\{version\}$")
        self.assertLess(stages["vulkan-headers"], stages["vulkan-loader"])

    def test_every_canary_source_is_on_the_lookaside(self) -> None:
        from tools.package_inventory import source_locks

        locks = source_locks(ROOT)
        members = json.loads(self.workflow["env"]["CANARY_SET"]) + ["python-typing-inspection"]
        for name in members:
            with self.subTest(name=name):
                self.assertTrue(
                    locks[name]["url"].startswith("https://src.fedoraproject.org/repo/pkgs/"),
                    "a canary must not depend on a flaky upstream host",
                )

    def test_it_runs_on_every_pull_request_and_the_gate_always_reports(self) -> None:
        triggers = self.workflow.get("on", self.workflow.get(True))
        self.assertIn("pull_request", triggers)
        self.assertIsNone(triggers["pull_request"], "paths are filtered in a job, not here")
        gate = self.jobs["canary"]
        self.assertEqual(gate["name"], "Canary")
        self.assertEqual(gate["if"], "always()")
        self.assertEqual(
            set(gate["needs"]),
            {name for name in self.jobs if name != "canary"},
        )

    def test_only_pass1_and_pass4_publish_and_passes_2_and_3_follow_pass1(self) -> None:
        self.assertNotIn("skip_publish", self.jobs["pass1"]["with"])
        self.assertNotIn("skip_publish", self.jobs["pass4"]["with"])
        for name in ("pass2", "pass3"):
            self.assertTrue(self.jobs[name]["with"]["skip_publish"])
            self.assertIn("pass1", self.jobs[name]["needs"])
        self.assertEqual(
            self.jobs["pass3"]["with"]["perturb"], '["python-typing-inspection"]'
        )

    def test_pass4_fails_one_package_on_purpose_and_is_judged_separately(self) -> None:
        pass4 = self.jobs["pass4"]["with"]
        self.assertEqual(pass4["inject_failure"], '["vulkan-loader"]')
        self.assertEqual(pass4["publish_tag"], "${{ needs.changes.outputs.tag }}")
        verify = self.jobs["verify-failure"]
        self.assertIn("always()", verify["if"])
        script = verify["steps"][-1]["run"]
        self.assertIn("\'[\"vulkan-loader\"]\'", script)
        self.assertIn('test "$DIGEST" != "$PASS1_DIGEST"', script)
        gate = self.jobs["canary"]["steps"][0]["run"]
        self.assertIn('.key != "pass4"', gate)

    def test_every_pass_shares_one_salt_and_its_own_artifact_prefix(self) -> None:
        passes = [n for n, j in self.jobs.items() if j.get("uses")]
        prefixes = {self.jobs[n]["with"]["artifact_prefix"] for n in passes}
        self.assertEqual(len(prefixes), len(passes))
        salts = {self.jobs[n]["with"]["cache_salt"] for n in passes}
        self.assertEqual(salts, {"${{ needs.changes.outputs.salt }}"})


if __name__ == "__main__":
    unittest.main()
