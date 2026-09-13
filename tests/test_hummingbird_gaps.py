#!/usr/bin/env python3
"""Cover the Hummingbird gap report in ``tools/recalculate_hummingbird_gaps.py``.

The gap report is the only measurement of how much of Bluefin's package
contract Hummingbird can already satisfy, and it had no unit coverage.  Two
rules carry the meaning and were unpinned: ``lines`` must drop comments and
blanks so a commented-out package is not counted as shipped, and ``main`` must
include every manifest section except ``excluded`` so a version-specific list
is still part of the contract.

These tests build manifests and package lists on disk; nothing pulls an image.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from tools import recalculate_hummingbird_gaps as gaps


class LinesTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="gaps-test-"))
        path = directory / "packages.txt"
        path.write_text(text)
        return path

    def test_strips_whitespace_and_blank_lines(self):
        self.assertEqual(gaps.lines(self.write("  fish  \n\n\tgrub2\n \n")), {"fish", "grub2"})

    def test_drops_comment_lines(self):
        self.assertEqual(gaps.lines(self.write("fish\n#grub2\n# a note\n")), {"fish"})

    def test_indented_comment_is_kept_because_the_check_is_unstripped(self):
        # ``startswith`` runs on the raw line, so a leading-space comment is
        # retained. Pinned so the behaviour cannot change unnoticed.
        self.assertEqual(gaps.lines(self.write("fish\n  #grub2\n")), {"fish", "#grub2"})

    def test_duplicates_collapse(self):
        self.assertEqual(gaps.lines(self.write("fish\nfish\n")), {"fish"})

    def test_empty_file_is_an_empty_set(self):
        self.assertEqual(gaps.lines(self.write("")), set())


class MainTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="gaps-main-"))

    def run_main(self, manifest: str, image: str, repo: str, extra=()):
        manifest_path = self.root / "manifest.toml"
        image_path = self.root / "image.txt"
        repo_path = self.root / "repo.txt"
        output = self.root / "reports" / "hummingbird-gap.json"
        manifest_path.write_text(manifest)
        image_path.write_text(image)
        repo_path.write_text(repo)
        argv = [
            "recalculate_hummingbird_gaps.py",
            "--manifest", str(manifest_path),
            "--image-packages", str(image_path),
            "--repo-packages", str(repo_path),
            "--output", str(output),
            "--image", "ghcr.io/example/hummingbird:latest",
            *extra,
        ]
        with mock.patch("sys.argv", argv):
            code = gaps.main()
        return code, json.loads(output.read_text())

    def test_partitions_contract_across_image_repo_and_missing(self):
        code, report = self.run_main(
            "[base]\npackages = ['fish', 'grub2', 'mozjs140']\n",
            "fish\n",
            "grub2\n",
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["available_from_image"], ["fish"])
        self.assertEqual(report["available_from_repo_only"], ["grub2"])
        self.assertEqual(report["missing_from_hummingbird"], ["mozjs140"])
        self.assertEqual(report["counts"],
                         {"contract": 3, "image": 1, "repo_only": 1, "missing": 1})

    def test_image_wins_over_repo_so_repo_only_excludes_it(self):
        _, report = self.run_main(
            "[base]\npackages = ['fish']\n",
            "fish\n",
            "fish\n",
        )
        self.assertEqual(report["available_from_image"], ["fish"])
        self.assertEqual(report["available_from_repo_only"], [])
        self.assertEqual(report["counts"]["repo_only"], 0)

    def test_excluded_section_is_not_part_of_the_contract(self):
        _, report = self.run_main(
            "[base]\npackages = ['fish']\n\n[excluded]\npackages = ['firefox']\n",
            "",
            "",
        )
        self.assertEqual(report["contract_binary_packages"], ["fish"])
        self.assertNotIn("firefox", report["missing_from_hummingbird"])

    def test_version_specific_sections_stay_in_the_contract(self):
        _, report = self.run_main(
            "[base]\npackages = ['fish']\n\n[f43]\npackages = ['grub2']\n",
            "",
            "",
        )
        self.assertEqual(report["contract_binary_packages"], ["fish", "grub2"])
        self.assertEqual(report["counts"]["contract"], 2)

    def test_non_table_and_packageless_sections_are_tolerated(self):
        _, report = self.run_main(
            "schema = 2\n\n[base]\npackages = ['fish']\n\n[notes]\ncomment = 'no packages key'\n",
            "fish\n",
            "",
        )
        self.assertEqual(report["contract_binary_packages"], ["fish"])
        self.assertEqual(report["counts"]["contract"], 1)

    def test_duplicate_package_across_sections_counts_once(self):
        _, report = self.run_main(
            "[base]\npackages = ['fish']\n\n[f43]\npackages = ['fish']\n",
            "",
            "",
        )
        self.assertEqual(report["counts"]["contract"], 1)

    def test_image_packages_outside_the_contract_are_ignored(self):
        _, report = self.run_main(
            "[base]\npackages = ['fish']\n",
            "fish\nsomething-else\n",
            "another-thing\n",
        )
        self.assertEqual(report["counts"], {"contract": 1, "image": 1, "repo_only": 0, "missing": 0})

    def test_output_lists_are_sorted_and_image_ref_is_recorded(self):
        _, report = self.run_main(
            "[base]\npackages = ['zsh', 'fish', 'grub2']\n",
            "",
            "",
        )
        self.assertEqual(report["contract_binary_packages"], ["fish", "grub2", "zsh"])
        self.assertEqual(report["missing_from_hummingbird"], ["fish", "grub2", "zsh"])
        self.assertEqual(report["image"], "ghcr.io/example/hummingbird:latest")

    def test_measured_at_is_utc_iso8601(self):
        _, report = self.run_main("[base]\npackages = ['fish']\n", "", "")
        stamp = datetime.fromisoformat(report["measured_at"])
        self.assertIsNotNone(stamp.tzinfo)
        self.assertEqual(stamp.utcoffset().total_seconds(), 0)

    def test_output_parent_directory_is_created(self):
        output = self.root / "deep" / "nested" / "gap.json"
        manifest = self.root / "m.toml"
        manifest.write_text("[base]\npackages = ['fish']\n")
        empty = self.root / "empty.txt"
        empty.write_text("")
        argv = [
            "recalculate_hummingbird_gaps.py",
            "--manifest", str(manifest),
            "--image-packages", str(empty),
            "--repo-packages", str(empty),
            "--output", str(output),
            "--image", "ghcr.io/example/hummingbird:latest",
        ]
        with mock.patch("sys.argv", argv):
            self.assertEqual(gaps.main(), 0)
        self.assertTrue(output.exists())
        self.assertTrue(output.read_text().endswith("\n"))


class RealManifestTests(unittest.TestCase):
    """The default manifest must stay loadable by the shape ``main`` expects."""

    def test_default_manifest_yields_a_non_empty_contract(self):
        import tomllib

        root = Path(__file__).resolve().parent.parent
        manifest_path = root / "config" / "bluefin-packages.toml"
        self.assertTrue(manifest_path.exists(), f"missing {manifest_path}")
        manifest = tomllib.loads(manifest_path.read_text())
        contract = set()
        for section, values in manifest.items():
            if section != "excluded" and isinstance(values, dict):
                contract.update(values.get("packages", []))
        self.assertTrue(contract, "contract must not be empty")
        excluded = set(manifest.get("excluded", {}).get("packages", []))
        self.assertFalse(contract & excluded, "excluded packages leaked into the contract")


if __name__ == "__main__":
    unittest.main()
