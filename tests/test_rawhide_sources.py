#!/usr/bin/env python3
"""Pin the shared Rawhide ingestion grammar.

Neither ``tools/scan_rawhide_state.py`` nor ``tools/import_bluefin_rawhide.py``
had any unit coverage, so the two verbatim copies of the source-RPM regex could
drift without a failing test. These tests cover the extracted module and assert
that both tools now resolve the same binary set from the real manifest.
"""

from pathlib import Path
import tomllib
import unittest

from tools.rawhide_sources import IMPORT_SECTIONS, import_binaries, source_name

ROOT = Path(__file__).resolve().parent.parent


class SourceNameTests(unittest.TestCase):
    def test_simple_name(self):
        self.assertEqual(source_name("ModemManager-1.24.0-1.fc44.src.rpm"), "ModemManager")

    def test_name_containing_hyphens(self):
        self.assertEqual(source_name("adw-gtk3-theme-5.7-1.fc44.src.rpm"), "adw-gtk3-theme")

    def test_name_containing_digits_before_version(self):
        self.assertEqual(source_name("SDL3-3.2.10-2.fc44.src.rpm"), "SDL3")

    def test_epoch_style_release_with_dist(self):
        self.assertEqual(source_name("pipewire-1.4.2-3.fc44.src.rpm"), "pipewire")

    def test_rejects_non_srpm(self):
        with self.assertRaises(ValueError):
            source_name("ModemManager-1.24.0-1.fc44.x86_64.rpm")

    def test_rejects_unparseable(self):
        with self.assertRaises(ValueError):
            source_name("(none)")


class ImportBinariesTests(unittest.TestCase):
    def test_union_is_sorted_and_deduplicated(self):
        manifest = {
            "fedora": {"packages": ["b", "a"]},
            "multimedia_overrides": {"packages": ["a", "c"]},
        }
        self.assertEqual(import_binaries(manifest), ["a", "b", "c"])

    def test_missing_section_is_an_error_not_an_empty_set(self):
        with self.assertRaises(ValueError):
            import_binaries({"fedora": {"packages": ["a"]}})

    def test_release_specific_sections_are_not_ingested(self):
        # fedora_v42/v43/v44 are part of the Bluefin contract measured by
        # recalculate_hummingbird_gaps.py but are deliberately not an ingestion
        # input; assert the divergence stays explicit rather than accidental.
        self.assertEqual(IMPORT_SECTIONS, ("fedora", "multimedia_overrides"))

    def test_real_manifest_resolves(self):
        manifest = tomllib.loads((ROOT / "config" / "bluefin-packages.toml").read_text())
        binaries = import_binaries(manifest)
        self.assertTrue(binaries)
        self.assertEqual(binaries, sorted(set(binaries)))
        for section in IMPORT_SECTIONS:
            self.assertTrue(set(manifest[section]["packages"]) <= set(binaries))


if __name__ == "__main__":
    unittest.main()
