#!/usr/bin/env python3

from pathlib import Path
import unittest

from tools.package_inventory import inventory


ROOT = Path(__file__).resolve().parent.parent


class PackageInventoryTests(unittest.TestCase):
    def test_inventory_reports_every_recipe_fully_source_locked(self):
        records = inventory(ROOT)
        assert len(records) == 193
        assert {r.name for r in records if not r.source_locked} == set()


if __name__ == "__main__":
    unittest.main()
