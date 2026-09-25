#!/usr/bin/env python3
"""Regression test: a failed build or dependency check cannot partially replace
the published factory.

The consumer factory tag (ghcr.io/.../utah-packages:latest) moves only from the
rebuild-rpms.yml publish job, and that job is gated. This proves the gate holds:

* the pure decision function ``publish_allowed`` in ``tools/publish_gate.py``
  denies publication for every failure mode -- a failed rebuild wave, a
  precedence failure, an unresolved Hummingbird-only consumer transaction, or a
  fork pull request -- and allows it only on full success;
* the workflow's own publish job encodes the same gate, with the Hummingbird-only
  transaction validated before the OCI image is published.
"""
import unittest

import copy

from tools.publish_gate import (
    STAGES,
    assert_gate_enforced,
    load_workflow,
    publish_allowed,
    rebuild_stages,
)


class PublishAllowedTests(unittest.TestCase):
    """The decision the publish job's `if:` makes, driven through each failure."""

    def _ok(self, **overrides):
        params = dict(
            stages=["success"] * len(STAGES),
            precedence="success",
            transaction_resolved=True,
            is_fork_pull_request=False,
        )
        params.update(overrides)
        return params

    def test_full_success_publishes(self):
        self.assertTrue(publish_allowed(**self._ok()))

    def test_a_skipped_wave_still_publishes(self):
        stages = list(self._ok()["stages"])
        stages[2] = "skipped"
        self.assertTrue(
            publish_allowed(
                stages=stages, precedence="success",
                transaction_resolved=True, is_fork_pull_request=False,
            )
        )

    def test_a_failed_build_wave_does_not_publish(self):
        for broken in range(len(STAGES)):
            stages = list(self._ok()["stages"])
            stages[broken] = "failure"
            self.assertFalse(
                publish_allowed(
                    stages=stages, precedence="success",
                    transaction_resolved=True, is_fork_pull_request=False,
                ),
                msg=f"{STAGES[broken]} failed must not publish",
            )

    def test_a_failed_precedence_check_does_not_publish(self):
        self.assertFalse(
            publish_allowed(**self._ok(precedence="failure"))
        )

    def test_an_unresolved_transaction_does_not_publish(self):
        # The ABI/dependency failure: the Hummingbird-only consumer transaction
        # does not resolve, so the published factory must not be partially
        # replaced by the successful builds in this run.
        self.assertFalse(
            publish_allowed(
                stages=list(STAGES), precedence="success",
                transaction_resolved=False, is_fork_pull_request=False,
            )
        )

    def test_a_fork_pull_request_does_not_publish(self):
        self.assertFalse(
            publish_allowed(**self._ok(is_fork_pull_request=True))
        )


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

    def test_an_added_wave_missing_from_the_gate_is_rejected(self):
        # Growth in this factory means adding a wave. A wave the workflow
        # declares but the publish job's `if:` does not name would let a failed
        # build publish, so discovering it is the point of this check.
        workflow = copy.deepcopy(self.workflow)
        added = f"rebuild{len(STAGES)}"
        workflow["jobs"][added] = copy.deepcopy(workflow["jobs"][STAGES[-1]])
        workflow["jobs"]["publish"]["needs"] = list(
            workflow["jobs"]["publish"]["needs"]
        ) + [added]
        with self.assertRaises(AssertionError) as caught:
            assert_gate_enforced(workflow)
        self.assertIn(added, str(caught.exception))

    def test_a_wave_the_publish_job_does_not_depend_on_is_rejected(self):
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
