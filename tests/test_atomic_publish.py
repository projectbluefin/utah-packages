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

from tools.publish_gate import (
    STAGES,
    assert_gate_enforced,
    load_workflow,
    publish_allowed,
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

    def test_transaction_validation_is_not_skippable(self):
        steps = self.workflow["jobs"]["publish"]["steps"]
        validate = next(
            i for i, step in enumerate(steps)
            if "Hummingbird-only consumer transaction" in str(step.get("name", ""))
        )
        self.assertNotIn("if", steps[validate])


if __name__ == "__main__":
    unittest.main()
