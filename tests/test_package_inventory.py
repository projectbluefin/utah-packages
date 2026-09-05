#!/usr/bin/env python3

from pathlib import Path
import unittest

from tools.package_inventory import inventory


ROOT = Path(__file__).resolve().parent.parent


class PackageInventoryTests(unittest.TestCase):
    def test_inventory_reports_every_recipe_and_current_gaps(self):
        records = inventory(ROOT)
        assert len(records) == 193
        assert {r.name for r in records if not r.source_locked} == {
            "dracut", "evolution-ews", "firewalld", "fish", "gcc", "git",
            "intel-media-driver-free", "ntfs-3g", "openssh", "rust-bootupd",
            "shared-mime-info", "tailscale", "zsh",
        }


if __name__ == "__main__":
    unittest.main()
