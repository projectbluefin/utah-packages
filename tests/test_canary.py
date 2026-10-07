#!/usr/bin/env python3
"""The canary's decisions: when it runs, and what counts as a pass."""

import contextlib
import gzip
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

from tools import canary

ROOT = Path(__file__).resolve().parent.parent
CANARY = ROOT / ".github" / "workflows" / "canary.yml"
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"


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


class FlakyCheckVerdictTests(unittest.TestCase):
    JOBS = [job('pass4 / rebuild0 (["libical"]) / build (libical)', "success", "success")]
    GOOD = [
        {"title": "flaky %check retry", "message": "libical failed in %check (exit 1); retrying the build once"},
        {"title": "flaky %check", "message": "libical failed %check once and passed on retry"},
    ]

    def test_a_retried_compile_passes(self) -> None:
        self.assertEqual(canary.flaky_problems(self.JOBS, "pass4", "libical", self.GOOD), [])

    def test_a_cache_hit_proves_nothing(self) -> None:
        hit = [job('pass4 / rebuild0 (["libical"]) / build (libical)', "skipped", "success")]
        self.assertTrue(canary.flaky_problems(hit, "pass4", "libical", self.GOOD))

    def test_a_missing_retry_annotation_fails(self) -> None:
        self.assertTrue(canary.flaky_problems(self.JOBS, "pass4", "libical", self.GOOD[1:]))
        self.assertTrue(canary.flaky_problems(self.JOBS, "pass4", "libical", self.GOOD[:1]))


class StateAndIncrementalTests(unittest.TestCase):
    def test_the_state_label_must_record_the_set(self) -> None:
        label = json.dumps({"inputs": {name: "0" * 16 for name in SET}, "failed": {}})
        config = {"config": {"Labels": {"org.projectbluefin.factory.state": label}}}
        self.assertEqual(canary.check_state(config, SET), [])
        self.assertTrue(canary.check_state({"config": {"Labels": {}}}, SET))
        self.assertTrue(canary.check_state(config, SET | {"extra"}))

    def test_incremental_selection_and_waves(self) -> None:
        jobs = [
            job('pass5 / rebuild0 (["vulkan-headers"]) / build (vulkan-headers)', "success", "success"),
            job('pass5 / rebuild1 (["vulkan-loader"]) / build (vulkan-loader)', "skipped", "success"),
        ]
        expected = {"vulkan-headers": 0, "vulkan-loader": 1}
        self.assertEqual(canary.incremental_problems(
            jobs, ["vulkan-headers", "vulkan-loader"], expected, "pass5"), [])
        # libical selected too: not incremental.
        self.assertTrue(canary.incremental_problems(
            jobs, ["libical", "vulkan-headers", "vulkan-loader"], expected, "pass5"))
        # vulkan-loader at its config stage 4: waves not solved.
        staged = [dict(jobs[0]), dict(jobs[1], name='pass5 / rebuild4 (["vulkan-loader"]) / build (vulkan-loader)')]
        self.assertTrue(canary.incremental_problems(
            staged, ["vulkan-headers", "vulkan-loader"], expected, "pass5"))
        # Nothing selected at all -- what a missing state label produces.
        self.assertTrue(canary.incremental_problems([], [], expected, "pass5"))


class HermeticVerdictTests(unittest.TestCase):
    @staticmethod
    def lock(*rpms):
        return {"buildroot": {"rpms": [{"name": n, "url": u} for n, u in rpms]},
                "bootstrap": {"pull_digest": "sha256:" + "a" * 64}}

    def locks(self):
        return {
            "libical": self.lock(("gcc", "https://x/gcc.rpm")),
            "vulkan-headers": self.lock(("cmake", "https://x/cmake.rpm")),
            "vulkan-loader": self.lock(
                ("vulkan-headers", "file:///work/prior/result/noarch/vulkan-headers.rpm")),
        }

    def test_a_locked_offline_build_of_the_set_passes(self) -> None:
        outcomes = {"libical": "compiled", "vulkan-headers": "cache hit", "vulkan-loader": "compiled"}
        self.assertEqual(canary.hermetic_problems(
            outcomes, self.locks(), SET, {"vulkan-loader": "vulkan-headers"}), [])

    def test_a_stage_provider_from_the_network_is_refused(self) -> None:
        locks = self.locks()
        locks["vulkan-loader"] = self.lock(("vulkan-headers", "https://fedora/vulkan-headers.rpm"))
        outcomes = dict.fromkeys(SET, "compiled")
        self.assertTrue(canary.hermetic_problems(
            outcomes, locks, SET, {"vulkan-loader": "vulkan-headers"}))

    def test_a_missing_lock_or_bootstrap_pin_is_refused(self) -> None:
        outcomes = dict.fromkeys(SET, "compiled")
        locks = self.locks()
        del locks["libical"]
        self.assertTrue(canary.hermetic_problems(outcomes, locks, SET, {}))
        locks = self.locks()
        locks["libical"]["bootstrap"] = {}
        self.assertTrue(canary.hermetic_problems(outcomes, locks, SET, {}))

    def test_read_locks_from_downloaded_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("p6-lock-s0-vulkan-headers", "p6-lock-s1-vulkan-loader"):
                (root / name / "lock").mkdir(parents=True)
                (root / name / "lock" / "buildroot_lock.json").write_text(json.dumps({"n": name}))
            locks = canary.read_locks(root)
        self.assertEqual(sorted(locks), ["vulkan-headers", "vulkan-loader"])

    def test_a_hermetic_offline_build_counts_as_compiled(self) -> None:
        jobs = [{"name": 'pass6 / rebuild0 (["libical"]) / build (libical)', "conclusion": "success",
                 "steps": [{"name": canary.RESTORE_STEP, "conclusion": "success"},
                           {"name": canary.BUILD_STEP, "conclusion": "skipped"},
                           {"name": canary.HERMETIC_BUILD_STEP, "conclusion": "success"}]}]
        self.assertEqual(canary.build_outcomes(jobs)["pass6"]["libical"], "compiled")


class EarlyPublishTests(unittest.TestCase):
    def jobs(self, oci="success", early_end="2026-09-26T02:05:00Z"):
        return [
            {"name": "pass1 / publish0 / publish", "completed_at": early_end,
             "steps": [{"name": "Publish the repository as an OCI image", "conclusion": oci}]},
            {"name": "pass1 / publish / publish", "started_at": "2026-09-26T02:09:00Z", "steps": []},
        ]

    def test_an_early_image_before_the_final_one_passes(self) -> None:
        self.assertEqual(canary.early_publish_problems(self.jobs(), "pass1", 0), [])

    def test_no_image_or_a_late_one_fails(self) -> None:
        self.assertTrue(canary.early_publish_problems(self.jobs(oci="skipped"), "pass1", 0))
        self.assertTrue(canary.early_publish_problems(self.jobs(early_end="2026-09-26T02:10:00Z"), "pass1", 0))
        self.assertTrue(canary.early_publish_problems([], "pass1", 0))


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

    def test_pass5_is_incremental_against_pass1s_digest(self) -> None:
        pass5 = self.jobs["pass5"]
        self.assertEqual(pass5["needs"], ["changes", "pass1"])
        self.assertNotIn("full", pass5["with"])
        self.assertEqual(pass5["with"]["factory_tag"], "${{ needs.pass1.outputs.digest }}")
        self.assertEqual(pass5["with"]["perturb"], '["vulkan-headers"]')
        self.assertTrue(pass5["with"]["skip_publish"])
        spec = (ROOT / "packages" / "vulkan-loader" / "vulkan-loader.spec").read_text()
        self.assertIn("vulkan-headers", spec)

    def test_every_pass_shares_one_salt_and_its_own_artifact_prefix(self) -> None:
        passes = [n for n, j in self.jobs.items() if j.get("uses")]
        prefixes = {self.jobs[n]["with"]["artifact_prefix"] for n in passes}
        self.assertEqual(len(prefixes), len(passes))
        salts = {self.jobs[n]["with"]["cache_salt"] for n in passes}
        self.assertEqual(salts, {"${{ needs.changes.outputs.salt }}"})


class BuildStageShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = yaml.safe_load(BUILD_STAGE.read_text())
        cls.jobs = cls.workflow["jobs"]

    def test_plan_filters_injected_failures_before_build_matrix(self) -> None:
        self.assertIn("plan", self.jobs)
        plan_outputs = self.jobs["plan"]["outputs"]
        self.assertIn("packages", plan_outputs)
        build = self.jobs["build"]
        self.assertEqual(build.get("needs"), "plan")
        self.assertIn("needs.plan.outputs.packages != '[]'", build.get("if", ""))
        self.assertIn("needs.plan.outputs.packages", build["strategy"]["matrix"]["package"])
        self.assertNotIn("continue-on-error", build)
        for step in build["steps"]:
            self.assertNotIn("Fail this package on purpose for the canary", step.get("name", ""))

    def test_filter_drops_injected_packages(self) -> None:
        import subprocess

        filter_cmd = (
            'jq -c --argjson drop "${INJECT:-[]}" '
            "'map(select(. as $p | $drop | index($p) | not))' <<<\"$PACKAGES\""
        )

        def run_filter(packages: str, inject: str) -> list[str]:
            res = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", filter_cmd],
                env={"PACKAGES": packages, "INJECT": inject},
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(res.stdout)

        self.assertEqual(
            run_filter('["libical", "vulkan-headers", "vulkan-loader"]', ""),
            ["libical", "vulkan-headers", "vulkan-loader"],
        )
        self.assertEqual(
            run_filter('["libical", "vulkan-headers", "vulkan-loader"]', '["vulkan-loader"]'),
            ["libical", "vulkan-headers"],
        )
        self.assertEqual(
            run_filter('["vulkan-loader"]', '["vulkan-loader"]'),
            [],
        )


class MainTests(unittest.TestCase):
    """The command line .github/workflows/canary.yml actually gates on.

    Every step in canary.yml reads an exit status from ``canary.py``: zero is a
    pass, non-zero fails the step. The predicates above are proven directly, so
    what is left to prove is the layer between them and the workflow -- that
    each subcommand routes to its predicate with the arguments it was handed,
    that a problem list becomes exit 1 and an empty one exit 0, and that the
    operator sees the ``::error`` annotation or the step summary that explains
    the verdict. Getting any of that wrong leaves the canary green by accident.
    """

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="canary-main-")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)

    def run_main(self, argv: list[str], stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = canary.main(argv)
        return code, out.getvalue(), err.getvalue()

    def jobs_file(self, jobs: list[dict], name: str = "jobs.json") -> str:
        path = self.work / name
        path.write_text(json.dumps(jobs))
        return str(path)

    # -- touches-pipeline (canary.yml:124) ---------------------------------
    #
    # The workflow branches on the status directly, so an inverted exit would
    # skip the canary on exactly the changes it exists to catch.

    def test_touches_pipeline_exits_zero_for_a_pipeline_change(self) -> None:
        code, _, _ = self.run_main(
            ["touches-pipeline"], "docs/architecture.md\ntools/publish_gate.py\n"
        )
        self.assertEqual(code, 0)

    def test_touches_pipeline_exits_one_for_recipes_and_docs(self) -> None:
        code, _, _ = self.run_main(
            ["touches-pipeline"], "packages/fish/fish.spec\ndocs/architecture.md\n"
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.run_main(["touches-pipeline"], "")[0], 1)

    # -- salt (canary.yml:149) ---------------------------------------------

    def test_salt_prints_the_cache_namespace_on_stdout(self) -> None:
        code, out, _ = self.run_main(["salt"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), canary.salt())
        self.assertRegex(out.strip(), r"^canary-[0-9a-f]{16}$")

    # -- verify-image (canary.yml:195, :314) -------------------------------

    def test_verify_image_passes_its_arguments_through_and_reports_success(self) -> None:
        seen = {}

        def stub(image, utah_reader, expected, expect_state=False):
            seen.update(image=image, utah_reader=utah_reader, expected=expected,
                        expect_state=expect_state)
            return []

        with mock.patch.object(canary, "verify_image", stub):
            code, out, err = self.run_main([
                "verify-image", "ghcr.io/x/y@sha256:" + "a" * 64,
                "--utah-reader", "/tmp/reader.py",
                "--expect", json.dumps(sorted(SET)),
                "--expect-state",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(seen["image"], "ghcr.io/x/y@sha256:" + "a" * 64)
        self.assertEqual(seen["utah_reader"], Path("/tmp/reader.py"))
        self.assertEqual(seen["expected"], SET)
        self.assertTrue(seen["expect_state"])
        self.assertIn("carries exactly the canary set", out)
        self.assertEqual(err, "")

    def test_verify_image_annotates_and_fails_on_a_problem(self) -> None:
        with mock.patch.object(canary, "verify_image", lambda *a, **k: ["one layer"]):
            code, _, err = self.run_main([
                "verify-image", "ghcr.io/x/y@sha256:" + "a" * 64,
                "--utah-reader", "/tmp/reader.py", "--expect", "[]",
            ])
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary image::one layer", err)

    # -- verify-flaky (canary.yml:312) -------------------------------------

    FLAKY_JOB = 'pass4 / rebuild0 (["libical"]) / build (libical)'

    def flaky_annotations(self) -> list[dict]:
        return [
            {"title": "flaky %check retry",
             "message": "libical failed in %check (exit 1); retrying the build once"},
            {"title": "flaky %check", "message": "libical failed %check once and passed on retry"},
        ]

    def run_flaky(self, jobs: list[dict], annotations: list[dict]) -> tuple[int, str, str, mock.Mock]:
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps(annotations), stderr="")
        with mock.patch.object(canary.subprocess, "run", return_value=completed) as run, \
                mock.patch.dict(os.environ, {"REPOSITORY": "projectbluefin/utah-packages"}):
            code, out, err = self.run_main([
                "verify-flaky", self.jobs_file(jobs), "--pass", "pass4", "--package", "libical",
            ])
        return code, out, err, run

    def test_verify_flaky_reads_the_annotations_for_the_matching_job(self) -> None:
        jobs = [dict(job(self.FLAKY_JOB, "success", "success"), id=4242)]
        code, out, err, run = self.run_flaky(jobs, self.flaky_annotations())
        self.assertEqual(code, 0)
        self.assertIn("failed %check once, was retried, and built", out)
        self.assertEqual(err, "")
        self.assertIn(
            "repos/projectbluefin/utah-packages/check-runs/4242/annotations",
            run.call_args.args[0],
        )

    def test_verify_flaky_fails_without_the_retry_annotations(self) -> None:
        jobs = [dict(job(self.FLAKY_JOB, "success", "success"), id=4242)]
        code, _, err, _ = self.run_flaky(jobs, [])
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary flaky check::", err)

    def test_verify_flaky_fails_without_calling_gh_when_the_job_is_absent(self) -> None:
        code, _, err, run = self.run_flaky([], self.flaky_annotations())
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary flaky check::", err)
        run.assert_not_called()

    # -- verify-incremental (canary.yml:351) -------------------------------

    INCREMENTAL_JOBS = [
        job('pass5 / rebuild0 (["vulkan-headers"]) / build (vulkan-headers)', "success", "success"),
        job('pass5 / rebuild1 (["vulkan-loader"]) / build (vulkan-loader)', "skipped", "success"),
    ]
    INCREMENTAL_EXPECT = json.dumps({"vulkan-headers": 0, "vulkan-loader": 1})

    def test_verify_incremental_accepts_exactly_the_change_and_its_dependent(self) -> None:
        code, out, err = self.run_main([
            "verify-incremental", self.jobs_file(self.INCREMENTAL_JOBS),
            "--build-list", json.dumps(["vulkan-headers", "vulkan-loader"]),
            "--expect", self.INCREMENTAL_EXPECT,
        ])
        self.assertEqual(code, 0)
        self.assertIn("### Canary incremental selection", out)
        self.assertEqual(err, "")

    def test_verify_incremental_fails_when_the_selection_is_too_wide(self) -> None:
        code, _, err = self.run_main([
            "verify-incremental", self.jobs_file(self.INCREMENTAL_JOBS),
            "--build-list", json.dumps(sorted(SET)),
            "--expect", self.INCREMENTAL_EXPECT,
        ])
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary incremental::", err)

    # -- verify-hermetic (canary.yml:379) ----------------------------------

    def hermetic_locks(self, staged: bool = True) -> str:
        directory = self.work / "locks"
        staged_url = "file:///work/prior/result/noarch/vulkan-headers.rpm"
        rpms = {
            "libical": ("gcc", "https://fedora/gcc.rpm"),
            "vulkan-headers": ("cmake", "https://fedora/cmake.rpm"),
            "vulkan-loader": (
                "vulkan-headers",
                staged_url if staged else "https://fedora/vulkan-headers.rpm",
            ),
        }
        for index, package in enumerate(sorted(rpms)):
            name, url = rpms[package]
            path = directory / f"p1-lock-s{index}-{package}" / "lock"
            path.mkdir(parents=True)
            (path / "buildroot_lock.json").write_text(json.dumps({
                "buildroot": {"rpms": [{"name": name, "url": url}]},
                "bootstrap": {"pull_digest": "sha256:" + "a" * 64},
            }))
        return str(directory)

    def hermetic_jobs(self) -> list[dict]:
        return [
            job(f'pass1 / rebuild0 (["{package}"]) / build ({package})', "success", "success")
            for package in sorted(SET)
        ]

    def run_hermetic(self, locks: str) -> tuple[int, str, str]:
        return self.run_main([
            "verify-hermetic", self.jobs_file(self.hermetic_jobs()),
            "--pass", "pass1", "--locks", locks, "--set", json.dumps(sorted(SET)),
            "--stage-dependency", "vulkan-loader=vulkan-headers",
        ])

    def test_verify_hermetic_accepts_locked_offline_builds(self) -> None:
        code, out, err = self.run_hermetic(self.hermetic_locks())
        self.assertEqual(code, 0)
        self.assertIn("### Canary hermetic lane", out)
        self.assertIn("- `vulkan-loader`: compiled, 1 locked packages", out)
        self.assertEqual(err, "")

    def test_verify_hermetic_fails_when_a_stage_provider_came_from_the_network(self) -> None:
        code, _, err = self.run_hermetic(self.hermetic_locks(staged=False))
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary hermetic::", err)

    # -- verify-built (canary.yml:417) -------------------------------------

    def built_jobs(self, conclusion: str = "success") -> list[dict]:
        return [
            job(f'pass6 / rebuild0 (["{package}"]) / build ({package})', conclusion, "success")
            for package in sorted(SET)
        ]

    def test_verify_built_accepts_the_whole_set_and_summarises_it(self) -> None:
        code, out, err = self.run_main([
            "verify-built", self.jobs_file(self.built_jobs()),
            "--pass", "pass6", "--set", json.dumps(sorted(SET)),
        ])
        self.assertEqual(code, 0)
        self.assertIn("### Canary pass6", out)
        for package in SET:
            self.assertIn(f"- `{package}`: compiled", out)
        self.assertEqual(err, "")

    def test_verify_built_fails_when_a_package_did_not_build(self) -> None:
        code, _, err = self.run_main([
            "verify-built", self.jobs_file(self.built_jobs()[:1]),
            "--pass", "pass6", "--set", json.dumps(sorted(SET)),
        ])
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary pass6::", err)

    # -- verify-early (canary.yml:220) -------------------------------------

    def early_jobs(self, oci: str = "success") -> list[dict]:
        return [
            {"name": "pass1 / publish0 / publish", "completed_at": "2026-09-26T02:05:00Z",
             "steps": [{"name": "Publish the repository as an OCI image", "conclusion": oci}]},
            {"name": "pass1 / publish / publish", "started_at": "2026-09-26T02:09:00Z",
             "steps": []},
        ]

    def test_verify_early_accepts_a_wave_published_before_the_final_image(self) -> None:
        code, out, err = self.run_main([
            "verify-early", self.jobs_file(self.early_jobs()), "--pass", "pass1", "--wave", "0",
        ])
        self.assertEqual(code, 0)
        self.assertIn("wave 0 published on its own", out)
        self.assertEqual(err, "")

    def test_verify_early_fails_when_the_wave_pushed_no_image(self) -> None:
        code, _, err = self.run_main([
            "verify-early", self.jobs_file(self.early_jobs(oci="skipped")),
            "--pass", "pass1", "--wave", "0",
        ])
        self.assertEqual(code, 1)
        self.assertIn("::error title=canary early publish::", err)

    # -- verify-cache (canary.yml:435) -------------------------------------

    def run_cache(self, jobs: list[dict]) -> tuple[int, str, str]:
        return self.run_main([
            "verify-cache", self.jobs_file(jobs),
            "--set", json.dumps(sorted(SET)), "--perturbed", "python-typing-inspection",
        ])

    def test_verify_cache_accepts_a_healthy_run_and_prints_the_step_summary(self) -> None:
        code, out, err = self.run_cache(healthy_jobs())
        self.assertEqual(code, 0)
        self.assertIn("| pass2 | `vulkan-headers` | cache hit |", out)
        self.assertIn("pass3 compiled only the perturbed package", out)
        self.assertEqual(err, "")

    def test_verify_cache_fails_when_a_cached_package_was_recompiled(self) -> None:
        jobs = healthy_jobs()
        for entry in jobs:
            if entry["name"].startswith("pass2") and entry["name"].endswith("(vulkan-headers)"):
                entry["steps"][1]["conclusion"] = "success"
        code, out, err = self.run_cache(jobs)
        self.assertEqual(code, 1)
        self.assertIn("**Failed:**", out)
        self.assertIn("::error title=canary cache::pass2: vulkan-headers was compiled", err)

    # -- the subcommand set itself -----------------------------------------

    def test_every_subcommand_the_workflow_invokes_is_dispatched(self) -> None:
        """A rename in canary.py that canary.yml did not follow fails here."""
        invoked = set(re.findall(
            r"canary\.py\s+([a-z-]+)", (ROOT / ".github" / "workflows" / "canary.yml").read_text()
        ))
        self.assertTrue(invoked)
        for command in sorted(invoked):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit) as raised:
                    self.run_main([command, "--help"])
                self.assertEqual(raised.exception.code, 0)

    def test_an_unknown_subcommand_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            self.run_main(["verify-everything"])
        self.assertNotEqual(raised.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
