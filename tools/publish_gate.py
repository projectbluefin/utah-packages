#!/usr/bin/env python3
"""The atomic-publish gate for the Utah factory.

ghcr.io/.../utah-packages:latest is the only digest consumers read. It may move
only when the whole selected package set is coherent: every selected rebuild
wave and the precedence check succeed, and the composed Hummingbird-only consumer
transaction resolves against the repository being published. Any selected package
failure, precedence failure, or unresolved transaction leaves the published
digest unchanged; the failed run's successful RPMs are retained as Actions
artifacts for diagnosis but never reach the consumer tag.

This module encodes that gate in two forms that must agree:

* ``publish_allowed`` is a pure decision function over the job outcomes. The
  regression test drives it through every failure mode.
* ``assert_gate_enforced`` reads ``.github/workflows/rebuild-rpms.yml`` and
  checks the publish job's own ``if:`` and step order encode the same gate, so
  the workflow and the decision function cannot drift apart.

The workflow's native ``if:`` is the gate that actually runs; this module proves
it holds and keeps it honest.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REBUILD_WORKFLOW = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "rebuild-rpms.yml"
)

# The five build waves the publish job waits on, in wave order.
STAGES = ("rebuild0", "rebuild1", "rebuild2", "rebuild3", "rebuild4")


def publish_allowed(
    *,
    stages: list[str],
    precedence: str,
    transaction_resolved: bool,
    is_fork_pull_request: bool,
) -> bool:
    """Whether the consumer OCI tag may move for this run.

    ``stages`` is the sequence of rebuild-wave results, ``precedence`` the
    precedence-check result, ``transaction_resolved`` whether the Hummingbird-only
    consumer transaction validated, and ``is_fork_pull_request`` whether a fork
    pull request -- whose read-only token cannot push -- is publishing.
    """
    if is_fork_pull_request:
        return False
    if not transaction_resolved:
        return False
    if precedence != "success":
        return False
    # A wave with no packages is skipped, which is fine; a failed wave is not.
    return all(result in ("success", "skipped") for result in stages)


def _normalized(gate: str) -> str:
    return re.sub(r"\s+", " ", gate).strip()


def assert_gate_enforced(workflow: dict) -> None:
    """The publish job must encode exactly the gate ``publish_allowed`` models."""
    try:
        publish = workflow["jobs"]["publish"]
    except (KeyError, TypeError) as error:
        raise AssertionError("rebuild-rpms.yml has no publish job") from error

    gate = _normalized(str(publish.get("if", "")))

    # Each rebuild wave may pass or be empty, but a failed wave must not publish.
    for stage in STAGES:
        clause = (
            f"needs.{stage}.result == 'success' || "
            f"needs.{stage}.result == 'skipped'"
        )
        if clause not in gate:
            raise AssertionError(
                f"publish gate must allow {stage} only on success or skip"
            )
        if f"needs.{stage}.result == 'failure'" in gate:
            raise AssertionError(f"publish gate must never publish when {stage} fails")

    # A precedence failure must never publish.
    if "needs.precedence.result == 'success'" not in gate:
        raise AssertionError("publish gate must require precedence to succeed")

    # A fork pull request has a read-only GITHUB_TOKEN and cannot push; the gate
    # must say so rather than let the push fail noisily later.
    if "pull_request.head.repo.full_name" not in gate:
        raise AssertionError("publish gate must exclude fork pull requests")

    _assert_transaction_before_publish(publish)


def _assert_transaction_before_publish(publish: dict) -> None:
    steps = publish.get("steps", [])
    names = [str(step.get("name", "")) for step in steps]
    try:
        validate = next(
            i for i, name in enumerate(names)
            if "Hummingbird-only consumer transaction" in name
        )
    except StopIteration:
        raise AssertionError(
            "publish job must validate the Hummingbird-only consumer transaction"
        ) from None
    try:
        publish_step = next(
            i for i, name in enumerate(names)
            if "Publish the repository as an OCI image" in name
        )
    except StopIteration:
        raise AssertionError(
            "publish job must publish the repository as an OCI image"
        ) from None
    if not validate < publish_step:
        raise AssertionError(
            "the Hummingbird-only transaction must validate before the image publishes"
        )
    # The validation runs whenever the publish job runs and its non-zero exit
    # fails the job before the image step; it must not be skippable.
    if "if" in steps[validate]:
        raise AssertionError("the transaction validation must not be skippable")


def load_workflow(path: Path = REBUILD_WORKFLOW) -> dict:
    with path.open() as handle:
        return yaml.safe_load(handle)


def main() -> int:
    workflow = load_workflow()
    assert_gate_enforced(workflow)
    print("publish gate enforced: every rebuild wave and precedence must pass, "
          "the Hummingbird-only transaction validates before the image publishes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
