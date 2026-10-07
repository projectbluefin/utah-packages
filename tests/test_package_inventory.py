#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import rebuild_matrix
from tools.package_inventory import (
    inventory,
    load_source_locks,
    parse_explicit_feed,
    parse_feed_url,
    source_locks,
)


ROOT = Path(__file__).resolve().parent.parent


class PackageInventoryTests(unittest.TestCase):
    def test_inventory_reports_every_recipe_fully_source_locked(self):
        records = inventory(ROOT)
        # The inventory size is the recipe count for the rebuild set; the
        # agreement gate asserts the same set under packages/, the source
        # lock, and .packit.yaml, so any discrepancy fails elsewhere.
        assert len(records) == len(source_locks(ROOT))
        assert {r.name for r in records if not r.source_locked} == set()
        assert {r.name for r in records if r.provenance is None} == set()
        assert {r.name for r in records if not r.provenance_branch} == set()


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

    def test_forge_shaped_feed_is_accepted(self):
        entry = {
            "name": "demo",
            "sha512": "0" * 128,
            "feed": "https://github.com/a/b/archive/v1.tar.gz",
        }
        config = self._write_config([entry])
        assert load_source_locks(config)["demo"]["feed"] == entry["feed"]

    def test_gnome_and_anitya_feeds_are_accepted(self):
        for feed in (
            "https://download.gnome.org/sources/gtk/3.24/gtk-3.24.52.tar.xz",
            "https://release-monitoring.org/project/1764",
        ):
            with self.subTest(feed=feed):
                entry = {"name": "demo", "sha512": "0" * 128, "feed": feed}
                config = self._write_config([entry])
                assert load_source_locks(config)["demo"]["feed"] == feed

    def test_explicit_feed_shapes_are_parsed(self):
        self.assertEqual(
            parse_explicit_feed("https://download.gnome.org/sources/gtk/3.24/gtk-3.24.52.tar.xz"),
            {"forge": "gnome", "module": "gtk"},
        )
        self.assertEqual(
            parse_explicit_feed("https://release-monitoring.org/project/1764"),
            {"forge": "anitya", "id": "1764"},
        )
        # A lock's own URLs are read by parse_feed_url, which must not claim
        # either shape as a forge mirror.
        self.assertIsNone(parse_feed_url("https://release-monitoring.org/project/1764"))
        self.assertIsNone(
            parse_feed_url("https://download.gnome.org/sources/gtk/3.24/gtk-3.24.52.tar.xz")
        )
        self.assertIsNone(parse_explicit_feed("https://release-monitoring.org/projects/?name=x"))

    def test_unparseable_feed_is_a_contract_violation(self):
        entry = {
            "name": "demo",
            "sha512": "0" * 128,
            "feed": "https://example.com/some/tarball-1.0.tar.gz",
        }
        config = self._write_config([entry])
        with self.assertRaisesRegex(ValueError, "unparseable feed"):
            load_source_locks(config)


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
