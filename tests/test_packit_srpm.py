#!/usr/bin/env python3

import json
import re
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parent.parent
PACKIT_CONFIG = ROOT / ".packit.yaml"
PACKIT_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-pilot.yml"
# The per-package steps moved into a reusable workflow so the pilot can fan out
# over chunks: 399 packages in one matrix exceeds the 256-job cap, which GitHub
# expands to nothing rather than rejecting.
PACKIT_CHUNK_WORKFLOW = ROOT / ".github" / "workflows" / "packit-srpm-chunk.yml"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"


from tools.packit_workflow import MATRIX_CHUNK, package_chunks, package_names


class PackitSrpmTests(unittest.TestCase):
    def test_only_dispatch_launches_the_full_srpm_matrix(self) -> None:
        workflow = yaml.safe_load(PACKIT_WORKFLOW.read_text())
        triggers = workflow.get("on", workflow.get(True, {}))
        self.assertEqual(set(triggers), {"workflow_dispatch"})

    def test_workflow_stages_verified_sources_for_every_configured_package(self) -> None:
        config_packages = set(package_names(PACKIT_CONFIG))
        workflow = PACKIT_WORKFLOW.read_text() + PACKIT_CHUNK_WORKFLOW.read_text()
        source_packages = {
            package["name"]
            for package in json.loads(SOURCE_CONFIG.read_text())["packages"]
        }

        self.assertEqual(len(config_packages), 399)
        self.assertEqual(config_packages - source_packages, set())
        self.assertTrue(
            {"adw-gtk3-theme", "igt-gpu-tools", "mesa", "runc", "webkitgtk"}
            <= config_packages
        )
        self.assertIn("python3 tools/packit_workflow.py packages", workflow)
        # The matrix now fans out over chunks, and each chunk fans out over its
        # own packages; both halves have to stay present.
        self.assertIn("fromJson(needs.discover.outputs.chunks)", workflow)
        self.assertIn("fromJson(inputs.packages)", workflow)
        self.assertIn("python3 tools/packit_workflow.py chunks", workflow)
        self.assertIn("--stage-into packages", workflow)
        self.assertIn("--verify-staged packages", workflow)
        self.assertIn("packit srpm --preserve-spec", workflow)
        self.assertIn("create-archive:", PACKIT_CONFIG.read_text())
        self.assertIn("tools/packit_source0.py", PACKIT_CONFIG.read_text())
        # The invariant AGENTS.md states is "pinned by digest, never a mutable
        # tag" -- not one specific digest. quay.io/packit/packit publishes only
        # :latest and republishes it, garbage-collecting the digest it replaces,
        # so a hardcoded digest here is a test that fails on upstream's
        # schedule rather than on a change to this repository. Two pins have
        # already died that way: 149e6e06 (repinned by 15a9dd5) and 8a178425,
        # which was 404 by 2026-09-17. Assert the shape, and keep both known
        # dead digests out.
        # tag@digest, not a bare digest: Renovate cannot tell what a digest-only
        # pin should track, so the tag is what lets the build-root-image manager
        # in renovate.json keep it fresh. It is still digest-pinned -- the
        # runtime resolves by digest when one is present, which is the form the
        # repository's own Containerfiles already use.
        self.assertRegex(
            workflow,
            r"quay\.io/packit/packit:[\w.-]+@sha256:[0-9a-f]{64}",
        )
        # What AGENTS.md forbids is a tag with no digest behind it.
        self.assertNotRegex(workflow, r"quay\.io/packit/packit:[\w.-]+(?!@sha256:)\s")
        for dead in (
            "149e6e06d3e5fb2f10d19760c8a0031c7d8825e7bb91a5f4a7ab9b927c947494",
            "8a1784251c51eed7a094820c894e2ee7f4ed4bbce4eb78eb172a04de3fae43e1",
        ):
            self.assertNotIn(dead, workflow)


    def test_every_chunk_fits_inside_the_matrix_cap(self) -> None:
        """399 packages in one matrix expands to zero jobs, not an error."""
        names = package_names(PACKIT_CONFIG)
        chunks = package_chunks(names)
        rebuilt = [name for chunk in chunks for name in json.loads(chunk)]

        self.assertLessEqual(MATRIX_CHUNK, 256)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(json.loads(chunk)), 256)
        self.assertEqual(rebuilt, names)


if __name__ == "__main__":
    unittest.main()
