#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import rebuild_matrix
from tools.package_inventory import inventory, load_source_locks, source_locks


ROOT = Path(__file__).resolve().parent.parent


class PackageInventoryTests(unittest.TestCase):
    def test_inventory_reports_every_recipe_fully_source_locked(self):
        records = inventory(ROOT)
        assert len(records) == 399
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


class RebuildMatrixContractTests(unittest.TestCase):
    def _create_root(self, packages: list[dict]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        config = root / "config"
        config.mkdir(parents=True)
        (config / "upstream-sources.json").write_text(
            json.dumps({"packages": packages})
        )
        return root

    def test_duplicate_lock_aborts_main(self):
        entry = {"name": "demo", "sha512": "0" * 128}
        root = self._create_root([entry, dict(entry)])
        with mock.patch.object(rebuild_matrix, "ROOT", root):
            with self.assertRaisesRegex(ValueError, "duplicate source lock"):
                rebuild_matrix.main()

    def test_unknown_stage_aborts_main(self):
        root = self._create_root([{"name": "demo", "sha512": "0" * 128, "stage": 99}])
        with mock.patch.object(rebuild_matrix, "ROOT", root):
            with self.assertRaisesRegex(ValueError, "unknown stage"):
                rebuild_matrix.main()

    def test_duplicate_lock_aborts_changed_inventory(self):
        entry = {"name": "demo", "sha512": "0" * 128}
        root = self._create_root([entry, dict(entry)])
        with mock.patch.object(rebuild_matrix, "ROOT", root):
            with mock.patch(
                "subprocess.check_output",
                return_value=json.dumps({"packages": []}),
            ):
                with self.assertRaisesRegex(ValueError, "duplicate source lock"):
                    rebuild_matrix.changed_inventory("a" * 40, [rebuild_matrix.INVENTORY])

    def test_decision_routes_through_source_locks(self):
        source = (ROOT / "tools" / "rebuild_matrix.py").read_text()
        self.assertIn("from tools.package_inventory import source_locks", source)
        self.assertIn("source_locks(ROOT)", source)
        self.assertNotIn("(ROOT / INVENTORY).read_text()", source)


if __name__ == "__main__":
    unittest.main()
