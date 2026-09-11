#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

from tools.package_inventory import inventory, load_source_locks, source_locks


ROOT = Path(__file__).resolve().parent.parent


class PackageInventoryTests(unittest.TestCase):
    def test_inventory_reports_every_recipe_fully_source_locked(self):
        records = inventory(ROOT)
        assert len(records) == 193
        assert {r.name for r in records if not r.source_locked} == set()


class SourceLocksTests(unittest.TestCase):
    def test_returns_full_validated_entries(self):
        locks = source_locks(ROOT)
        raw = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        assert sorted(locks) == sorted(entry["name"] for entry in raw["packages"])
        for entry in raw["packages"]:
            assert locks[entry["name"]] is entry or locks[entry["name"]] == entry

    def _write_config(self, packages: list[dict]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = Path(directory.name) / "upstream-sources.json"
        config.write_text(json.dumps({"packages": packages}))
        return config

    def test_duplicate_lock_is_a_contract_violation(self):
        entry = {"name": "demo", "sha512": "0" * 128}
        config = self._write_config([entry, dict(entry)])
        with self.assertRaisesRegex(ValueError, "duplicate source lock"):
            load_source_locks(config)

    def test_unknown_stage_is_a_contract_violation(self):
        config = self._write_config([{"name": "demo", "sha512": "0" * 128, "stage": 99}])
        with self.assertRaisesRegex(ValueError, "unknown stage"):
            load_source_locks(config)

    def test_default_stage_is_zero(self):
        config = self._write_config([{"name": "demo", "sha512": "0" * 128}])
        assert load_source_locks(config)["demo"].get("stage", 0) == 0


if __name__ == "__main__":
    unittest.main()
