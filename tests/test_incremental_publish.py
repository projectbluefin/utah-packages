#!/usr/bin/env python3
"""Regression test: publication is incremental, and still gated.

The consumer factory tag (ghcr.io/.../utah-packages:latest) moves only from the
rebuild-rpms.yml publish job. It used to move only when every selected package
built; one flaky test then held back every other package. The rule is now the
one Fedora and Hummingbird follow, and this proves it:

* ``publish_allowed`` in ``tools/publish_gate.py`` publishes after a failed
  build wave -- the failed packages keep their previous build -- and still
  refuses for a precedence check that did not run, an unresolved
  Hummingbird-only consumer transaction, a fork pull request, or a run that
  changed nothing;
* ``assemble`` replaces a built package's RPMs by *source* package, keeps a
  failed or precedence-losing package at its previous build, and leaves every
  other seeded package untouched;
* the workflow's own publish job encodes the same rule, with the
  Hummingbird-only transaction validated before the OCI image is published,
  the repodata-first layer order Utah reads, and a verified seed.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.publish_gate import (
    STAGES,
    apply,
    assemble,
    assert_gate_enforced,
    failed_marker,
    failures_from_artifacts,
    load_workflow,
    publish_allowed,
    rebuild_stages,
    render_report,
)


class PublishAllowedTests(unittest.TestCase):
    """The decision the publish job's `if:` and its steps make together."""

    def _ok(self, **overrides):
        params = dict(
            stages=["success"] * len(STAGES),
            precedence="success",
            transaction_resolved=True,
            is_fork_pull_request=False,
            replaced=3,
            pruned=0,
        )
        params.update(overrides)
        return params

    def test_full_success_publishes(self):
        self.assertTrue(publish_allowed(**self._ok()))

    def test_a_skipped_wave_still_publishes(self):
        stages = list(self._ok()["stages"])
        stages[2] = "skipped"
        self.assertTrue(publish_allowed(**self._ok(stages=stages)))

    def test_a_failed_build_wave_still_publishes_what_built(self):
        # The rule this replaced: one failed wave vetoed every package. Now
        # the failed packages keep their previous build and the rest publish.
        for broken in range(len(STAGES)):
            stages = list(self._ok()["stages"])
            stages[broken] = "failure"
            self.assertTrue(
                publish_allowed(**self._ok(stages=stages)),
                msg=f"{STAGES[broken]} failed and must not hold back the rest",
            )

    def test_every_wave_failing_with_nothing_built_publishes_nothing(self):
        self.assertFalse(
            publish_allowed(**self._ok(stages=["failure"] * len(STAGES), replaced=0))
        )

    def test_a_precedence_check_that_did_not_succeed_does_not_publish(self):
        # Losing packages are reported through a successful precedence job;
        # a precedence job that could not run judged nothing.
        for result in ("failure", "cancelled", "skipped"):
            self.assertFalse(publish_allowed(**self._ok(precedence=result)), result)

    def test_an_unresolved_transaction_does_not_publish(self):
        # The gate that protects Utah: however many packages built, a
        # candidate whose Hummingbird-only transaction does not resolve
        # leaves the published digest where it is.
        self.assertFalse(publish_allowed(**self._ok(transaction_resolved=False)))

    def test_a_fork_pull_request_does_not_publish(self):
        self.assertFalse(publish_allowed(**self._ok(is_fork_pull_request=True)))

    def test_a_prune_alone_publishes(self):
        self.assertTrue(publish_allowed(**self._ok(replaced=0, pruned=1)))


SEED = {
    "repository/result/x86_64/mutter-50.0-1.hum1.bfin.x86_64.rpm": "mutter",
    "repository/result/x86_64/mutter-devel-50.0-1.hum1.bfin.x86_64.rpm": "mutter",
    "repository/result/x86_64/mutter-tests-50.0-1.hum1.bfin.x86_64.rpm": "mutter",
    "repository/result/x86_64/fish-4.1-1.hum1.bfin.x86_64.rpm": "fish",
    "repository/result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm": "gtk4",
    "repository/result/noarch/adwaita-icon-theme-50-1.hum1.bfin.noarch.rpm": "adwaita-icon-theme",
}
BUILT = {
    # mutter rebuilt and dropped its -tests subpackage.
    "built/result/x86_64/mutter-50.1-1.hum1.bfin.x86_64.rpm": "mutter",
    "built/result/x86_64/mutter-devel-50.1-1.hum1.bfin.x86_64.rpm": "mutter",
    # gtk4 built but lost precedence.
    "built/result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm": "gtk4",
    # a brand-new package.
    "built/result/x86_64/libfoo-1.0-1.hum1.bfin.x86_64.rpm": "libfoo",
}


class AssembleTests(unittest.TestCase):
    def setUp(self):
        self.assembly = assemble(
            seed=SEED,
            built=BUILT,
            build_list=["mutter", "fish", "gtk4", "libfoo", "libbar"],
            losers={"gtk4"},
        )

    def test_a_built_package_replaces_every_old_subpackage(self):
        self.assertEqual(self.assembly.replaced, ["libfoo", "mutter"])
        self.assertEqual(
            self.assembly.remove,
            sorted(path for path, source in SEED.items() if source == "mutter"),
        )
        self.assertIn("built/result/x86_64/libfoo-1.0-1.hum1.bfin.x86_64.rpm", self.assembly.add)

    def test_a_failed_package_keeps_its_previous_build(self):
        self.assertIn("fish", self.assembly.failed)
        self.assertIn("fish", self.assembly.kept_previous)
        self.assertFalse(any("fish" in path for path in self.assembly.remove))

    def test_a_never_published_failure_stays_absent(self):
        self.assertEqual(self.assembly.absent, ["libbar"])

    def test_a_precedence_loser_keeps_its_previous_build(self):
        self.assertEqual(self.assembly.losers, ["gtk4"])
        self.assertIn("gtk4", self.assembly.kept_previous)
        self.assertFalse(any("gtk4" in path for path in self.assembly.add))
        self.assertFalse(any("gtk4" in path for path in self.assembly.remove))

    def test_packages_this_run_did_not_select_are_untouched(self):
        self.assertFalse(any("adwaita" in path for path in self.assembly.remove))

    def test_apply_moves_the_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in list(SEED) + list(BUILT):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(path)
            relocated = assemble(
                seed={str(root / k): v for k, v in SEED.items()},
                built={str(root / k): v for k, v in BUILT.items()},
                build_list=["mutter", "fish", "gtk4", "libfoo"],
                losers={"gtk4"},
            )
            apply(relocated, root / "repository", root / "built")
            left = sorted(
                str(path.relative_to(root)) for path in (root / "repository").rglob("*.rpm")
            )
            self.assertEqual(left, [
                "repository/result/noarch/adwaita-icon-theme-50-1.hum1.bfin.noarch.rpm",
                "repository/result/x86_64/fish-4.1-1.hum1.bfin.x86_64.rpm",
                "repository/result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm",
                "repository/result/x86_64/libfoo-1.0-1.hum1.bfin.x86_64.rpm",
                "repository/result/x86_64/mutter-50.1-1.hum1.bfin.x86_64.rpm",
                "repository/result/x86_64/mutter-devel-50.1-1.hum1.bfin.x86_64.rpm",
            ])


class BootstrapTests(unittest.TestCase):
    def test_a_bootstrap_build_never_replaces_the_real_package(self):
        from tools.publish_gate import publishable

        seed = {"repository/result/x86_64/malcontent-libs-0.13-1.hum1.bfin.x86_64.rpm": "malcontent"}
        built = publishable({
            "built/result/x86_64/malcontent-libs-0.13-0.bootstrap.hum1.bfin.x86_64.rpm": "malcontent",
            "built/result/x86_64/flatpak-1.19-1.hum1.bfin.x86_64.rpm": "flatpak",
        })
        assembly = assemble(seed=seed, built=built, build_list=["flatpak"], losers=set())
        self.assertEqual(assembly.remove, [])
        self.assertEqual(assembly.replaced, ["flatpak"])


class FailureReportTests(unittest.TestCase):
    def test_failures_come_from_the_artifact_list(self):
        names = ["rpm-s0-mutter", "rpm-s0-libfoo", "check-s0-fish", "buildroot-image",
                 "preflight-buildrequires"]
        self.assertEqual(
            failures_from_artifacts(["mutter", "fish", "libfoo"], names, "", set()),
            ["fish"],
        )

    def test_a_canary_prefix_is_honoured(self):
        names = ["p1-rpm-s0-libical", "p2-rpm-s0-libical", "p2-rpm-s4-vulkan-loader"]
        self.assertEqual(
            failures_from_artifacts(["libical", "vulkan-loader"], names, "p1-", set()),
            ["vulkan-loader"],
        )

    def test_a_precedence_loser_is_a_failure(self):
        self.assertEqual(
            failures_from_artifacts(["gtk4"], ["rpm-s4-gtk4"], "", {"gtk4"}), ["gtk4"]
        )

    def test_the_report_names_every_failure_and_what_consumers_get(self):
        body = render_report(
            failed=["fish", "gtk4", "libbar"],
            publish_result="success",
            publish_report={"replaced": ["mutter"], "kept_previous": ["fish", "gtk4"],
                            "absent": ["libbar"], "precedence_losers": ["gtk4"]},
            digest="sha256:abc",
            run_url="https://example.invalid/run/1",
        )
        self.assertIn("Published `sha256:abc`, replacing 1 source package(s).", body)
        self.assertIn("| `fish` | previous build |", body)
        self.assertIn("| `gtk4` | previous build (this build lost precedence) |", body)
        self.assertIn("| `libbar` | nothing: never published |", body)
        self.assertEqual(failed_marker(body), ["fish", "gtk4", "libbar"])

    def test_a_blocked_transaction_is_reported_as_not_published(self):
        body = render_report(failed=[], publish_result="failure", publish_report=None,
                             digest="", run_url="u")
        self.assertIn("**Not published.**", body)

    def test_no_marker_reads_as_none(self):
        self.assertIsNone(failed_marker("an issue somebody edited by hand"))


class PublishGateWorkflowTests(unittest.TestCase):
    """The workflow's own publish job must encode the same gate."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = load_workflow()

    def test_workflow_gate_matches_decision(self):
        assert_gate_enforced(self.workflow)

    def rendered_containerfile(self):
        """The Containerfile.repo the publish step writes, as printf renders it."""
        import re

        steps = self.workflow["jobs"]["publish"]["steps"]
        run = next(step for step in steps if step.get("id") == "oci")["run"]
        match = re.search(r'printf "([^"]*)" > Containerfile\.repo', run)
        self.assertIsNotNone(match, "publish no longer writes Containerfile.repo with printf")
        return match.group(1).replace("\\n", "\n").splitlines()

    def test_first_image_layer_is_repodata_only(self):
        # A contract with projectbluefin/utah: check-repo-availability.py reads
        # only manifest.layers[0], requires it under 64 MiB, and rejects any
        # entry outside repository/repodata. 9e17ca2c shipped one 2 GB layer
        # and Utah could not consume it.
        lines = self.rendered_containerfile()
        copies = [line for line in lines if line.startswith("COPY")]
        self.assertEqual(lines[0], "FROM scratch")
        self.assertEqual(copies[0], "COPY repository/repodata /repository/repodata")
        self.assertEqual(copies[1:], ["COPY repository /repository"])
        # Nothing may add a layer ahead of the metadata one.
        self.assertTrue(all(line.startswith(("FROM", "COPY")) for line in lines), lines)

    def test_transaction_validated_before_publish(self):
        names = [
            str(step.get("name", ""))
            for step in self.workflow["jobs"]["publish"]["steps"]
        ]
        validate = next(
            i for i, name in enumerate(names)
            if "Hummingbird-only consumer transaction" in name
        )
        publish_step = next(
            i for i, name in enumerate(names)
            if "Publish the repository as an OCI image" in name
        )
        self.assertLess(validate, publish_step)

    def test_declared_waves_match_the_stage_constant(self):
        self.assertEqual(rebuild_stages(self.workflow), STAGES)

    def test_a_wave_result_in_the_gate_is_rejected(self):
        # The atomic rule must not creep back: a wave's result may not veto
        # publication, because a failed package keeps its previous build.
        workflow = copy.deepcopy(self.workflow)
        workflow["jobs"]["publish"]["if"] += " && needs.rebuild3.result == 'success'"
        with self.assertRaises(AssertionError) as caught:
            assert_gate_enforced(workflow)
        self.assertIn("rebuild3", str(caught.exception))

    def test_an_added_wave_must_also_be_waited_for(self):
        workflow = copy.deepcopy(self.workflow)
        added = f"rebuild{len(STAGES)}"
        workflow["jobs"][added] = copy.deepcopy(workflow["jobs"][STAGES[-1]])
        with self.assertRaises(AssertionError) as caught:
            assert_gate_enforced(workflow)
        self.assertIn(added, str(caught.exception))

    def test_a_wave_the_publish_job_does_not_wait_for_is_rejected(self):
        # Publishing while a wave still builds would publish around it and
        # report its packages failed.
        workflow = copy.deepcopy(self.workflow)
        workflow["jobs"]["publish"]["needs"] = [
            need
            for need in workflow["jobs"]["publish"]["needs"]
            if need != STAGES[-1]
        ]
        with self.assertRaises(AssertionError) as caught:
            assert_gate_enforced(workflow)
        self.assertIn(STAGES[-1], str(caught.exception))

    def test_a_workflow_with_no_waves_is_rejected(self):
        workflow = copy.deepcopy(self.workflow)
        for stage in STAGES:
            del workflow["jobs"][stage]
        with self.assertRaises(AssertionError):
            assert_gate_enforced(workflow)

    def test_publish_must_still_require_precedence_and_prepare(self):
        for clause in ("needs.precedence.result == 'success'",
                       "needs.prepare.result == 'success'"):
            workflow = copy.deepcopy(self.workflow)
            workflow["jobs"]["publish"]["if"] = workflow["jobs"]["publish"]["if"].replace(
                clause, "true")
            with self.subTest(clause=clause), self.assertRaises(AssertionError):
                assert_gate_enforced(workflow)

    def test_the_replacement_step_comes_between_seed_and_transaction(self):
        workflow = copy.deepcopy(self.workflow)
        steps = workflow["jobs"]["publish"]["steps"]
        index = next(i for i, s in enumerate(steps)
                     if "Replace the packages this run built" in str(s.get("name")))
        steps.append(steps.pop(index))
        with self.assertRaises(AssertionError):
            assert_gate_enforced(workflow)

    def test_the_report_job_runs_even_when_publish_does_not(self):
        report = self.workflow["jobs"]["report"]
        self.assertIn("publish", report["needs"])
        self.assertTrue(report["if"].replace("${{", "").strip().startswith("always()"))
        self.assertEqual(report["permissions"]["issues"], "write")
        issue = next(s for s in report["steps"] if "tracking issue" in str(s.get("name")))
        self.assertIn("refs/heads/main", issue["if"])
        self.assertIn("inputs.publish_tag == ''", issue["if"])
        # A canary dispatched on main must not touch the tracking issue.
        self.assertIn("inputs.artifact_prefix == ''", issue["if"])

    def test_transaction_validation_is_not_skippable(self):
        steps = self.workflow["jobs"]["publish"]["steps"]
        validate = next(
            i for i, step in enumerate(steps)
            if "Hummingbird-only consumer transaction" in str(step.get("name", ""))
        )
        self.assertNotIn("if", steps[validate])


class SeedImageVerificationTests(unittest.TestCase):
    """The seed step must not copy RPMs out of an unverified image.

    Regression for the finding that the seed step pulled ghcr.io/.../:latest
    and extracted every RPM in it without checking the cosign signature this
    same workflow attaches at publish time -- so one poisoned push to the
    mutable tag would be carried forward and re-signed as verified output on
    every subsequent run.
    """

    @classmethod
    def setUpClass(cls):
        cls.workflow = load_workflow()
        cls.steps = cls.workflow["jobs"]["publish"]["steps"]

    def _step_script(self, name_substring):
        step = next(
            step for step in self.steps
            if name_substring in str(step.get("name", ""))
        )
        return step["run"]

    def test_seed_step_verifies_cosign_signature(self):
        script = self._step_script("Verify and seed repository")
        self.assertIn("cosign verify", script)
        self.assertIn("--certificate-oidc-issuer", script)
        self.assertIn("--certificate-identity", script)

    def test_seed_step_verifies_the_pulled_digest_not_the_tag(self):
        script = self._step_script("Verify and seed repository")
        verify_line = next(
            line for line in script.splitlines()
            if line.strip().startswith("cosign verify")
        )
        # Must verify the resolved ref@digest variable, never a bare
        # "image:tag" -- the tag can move again after the check.
        self.assertIn("$current", verify_line)
        self.assertNotIn(":$tag", verify_line)

    def test_cosign_verify_precedes_container_copy(self):
        script = self._step_script("Verify and seed repository")
        self.assertLess(
            script.index("cosign verify"),
            script.index("podman cp"),
            "the image must be verified before anything is copied out of it",
        )

    def test_cosign_is_installed_before_the_seed_step(self):
        names = [str(step.get("name", "")) for step in self.steps]
        install = next(i for i, name in enumerate(names) if name == "Install cosign")
        seed = next(
            i for i, name in enumerate(names)
            if "Verify and seed repository" in name
        )
        self.assertLess(install, seed)

    def test_seed_step_logs_in_where_cosign_will_look(self):
        step = next(
            step for step in self.steps
            if "Verify and seed repository" in str(step.get("name", ""))
        )
        # cosign reads $DOCKER_CONFIG/config.json, not podman's own auth
        # file, so the login must be written there for verification to see
        # any credentials the pull used.
        self.assertIn("DOCKER_CONFIG", step.get("env", {}))
        self.assertIn("--authfile", step["run"])


if __name__ == "__main__":
    unittest.main()
