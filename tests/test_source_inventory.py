#!/usr/bin/env python3
"""Source-lock coverage for every recipe plus bootstrap merge/selection behavior."""

import json
from pathlib import Path
import unittest

from tools.bootstrap_upstream_sources import (
    generated_candidate,
    merge_candidates,
    plan_targets,
)
from tools.package_inventory import inventory


ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "upstream-sources.json"


def normalized(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


class SourceCoverageTests(unittest.TestCase):
    def test_every_recipe_has_a_source_lock(self):
        records = inventory(ROOT)
        self.assertEqual(
            [record.name for record in records if not record.source_locked],
            [],
        )


class MergeCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.existing = json.loads(CONFIG.read_text())

    def test_merge_without_candidates_preserves_existing_entries(self):
        merged = merge_candidates(self.existing, [])
        self.assertEqual(normalized(merged), normalized(self.existing))

    def test_merge_appends_new_entries_after_existing_ones(self):
        candidate = {
            "name": "brand-new-package",
            "version": "1.0",
            "url": "https://example.org/brand-new-package-1.0.tar.gz",
            "filename": "brand-new-package-1.0.tar.gz",
            "sha512": "ab" * 64,
        }
        merged = merge_candidates(self.existing, [candidate])
        self.assertEqual(merged["packages"][:-1], self.existing["packages"])
        self.assertEqual(merged["packages"][-1], candidate)

    def test_merge_refuses_to_replace_an_existing_lock(self):
        existing_entry = dict(self.existing["packages"][0])
        existing_entry["sha512"] = "ff" * 64
        with self.assertRaisesRegex(ValueError, "already exists"):
            merge_candidates(self.existing, [existing_entry])

    def test_merge_refuses_duplicate_candidates(self):
        candidate = dict(self.existing["packages"][0])
        candidate["name"] = "brand-new-package"
        with self.assertRaisesRegex(ValueError, "duplicate candidate"):
            merge_candidates(self.existing, [candidate, dict(candidate)])


class TargetSelectionTests(unittest.TestCase):
    def test_hummingbird_supplied_packages_are_skipped_by_default(self):
        targets = plan_targets(ROOT / "packages", {"dracut": ["dracut"]})
        self.assertNotIn("dracut", [path.name for path in targets])
        self.assertEqual(len(targets), 192)

    def test_explicit_selection_processes_a_hummingbird_supplied_package(self):
        targets = plan_targets(ROOT / "packages", {"dracut": ["dracut"]}, only="dracut")
        self.assertEqual([path.name for path in targets], ["dracut"])

    def test_explicit_selection_requires_an_existing_recipe(self):
        with self.assertRaisesRegex(ValueError, "no package recipe"):
            plan_targets(ROOT / "packages", {}, only="not-a-package")


class GeneratedSourceTests(unittest.TestCase):
    def manifest_hash(self, package: str, filename: str) -> str:
        prefix = f"SHA512 ({filename}) = "
        for line in (ROOT / "packages" / package / "sources").read_text().splitlines():
            if line.startswith(prefix):
                return line[len(prefix):]
        raise AssertionError(f"{filename} is not pinned in packages/{package}/sources")

    def assert_content_addressed(self, candidate: dict) -> None:
        self.assertTrue(candidate["url"].startswith("https://src.fedoraproject.org/repo/pkgs/"))
        self.assertIn(f"/sha512/{candidate['sha512']}/", candidate["url"])
        self.assertTrue(candidate["url"].endswith(f"/{candidate['filename']}"))
        self.assertEqual(candidate["sha512"], self.manifest_hash(candidate["name"], candidate["filename"]))

    def test_gcc_lock_tracks_the_vendor_branch_snapshot_archive(self):
        candidate = generated_candidate(ROOT / "packages" / "gcc")
        self.assertEqual(candidate["name"], "gcc")
        self.assertEqual(candidate["version"], "16.2.1")
        self.assertEqual(candidate["filename"], "gcc-16.2.1-20260819.tar.xz")
        self.assert_content_addressed(candidate)
        self.assertIn("95ef1679dd68f27b3d056a497318089d85aa0d55", candidate["generated"]["input"])
        self.assertIn("git archive", candidate["generated"]["method"])
        self.assertEqual(candidate["generated"]["script"], "packages/gcc/update-gcc.sh")

    def test_intel_media_driver_free_lock_tracks_the_stripped_archive(self):
        candidate = generated_candidate(ROOT / "packages" / "intel-media-driver-free")
        self.assertEqual(candidate["name"], "intel-media-driver-free")
        self.assertEqual(candidate["version"], "26.2.4")
        # The recipe consumes the stripped -free archive; the unstripped
        # upstream tag archive must not be locked in its place.
        self.assertEqual(candidate["filename"], "intel-media-26.2.4-free.tar.gz")
        self.assert_content_addressed(candidate)
        self.assertIn("intel-media-26.2.4.tar.gz", candidate["generated"]["input"])
        self.assertEqual(candidate["generated"]["script"], "packages/intel-media-driver-free/strip.py")

    def test_tailscale_lock_tracks_the_vendored_archive(self):
        candidate = generated_candidate(ROOT / "packages" / "tailscale")
        self.assertEqual(candidate["name"], "tailscale")
        self.assertEqual(candidate["version"], "1.98.8")
        self.assertEqual(candidate["filename"], "tailscale-1.98.8-vendored.tar.xz")
        self.assert_content_addressed(candidate)
        self.assertIn("v1.98.8", candidate["generated"]["input"])
        self.assertIn("go mod vendor", candidate["generated"]["method"])
        self.assertEqual(candidate["generated"]["script"], "packages/tailscale/create-vendor-tarball.sh")

    def test_recipe_without_generated_source0_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no generated source resolver"):
            generated_candidate(ROOT / "packages" / "zsh")


if __name__ == "__main__":
    unittest.main()
