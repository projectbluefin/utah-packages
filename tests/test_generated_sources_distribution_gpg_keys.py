#!/usr/bin/env python3
"""Metadata and source-lock coverage for distribution-gpg-keys generation."""

import json
from pathlib import Path
import unittest

from tools import generated_sources


ROOT = Path(__file__).resolve().parent.parent


class DistributionGpgKeysMetadataTests(unittest.TestCase):
    def test_distribution_gpg_keys_metadata_pins_its_tag_commit(self):
        package_dir = ROOT / "packages" / "distribution-gpg-keys"
        metadata = generated_sources.metadata_for("distribution-gpg-keys", package_dir)
        self.assertEqual(metadata["filename"], "distribution-gpg-keys-1.123.tar.gz")
        self.assertIn(
            "tag distribution-gpg-keys-1.123-1 "
            "(commit 6f5f4883ceabd6c3d389ecd913b60675b61563da)",
            metadata["generate"]["input"],
        )
        lock = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        entry = next(p for p in lock["packages"] if p["name"] == "distribution-gpg-keys")
        self.assertEqual({key: entry[key] for key in metadata}, metadata)
        self.assertIn(
            f"SHA512 ({entry['filename']}) = {entry['sha512']}",
            (package_dir / "sources").read_text(),
        )
