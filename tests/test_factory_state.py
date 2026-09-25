#!/usr/bin/env python3
"""The per-package state recorded on the published image."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import factory_state
from tools.factory_state import LABEL, changed, merge, parse_labels

ROOT = Path(__file__).resolve().parent.parent


class DigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "config").mkdir()
        (self.tmp / "config" / "buildroot-image").write_text("ghcr.io/x@sha256:1\n")
        (self.tmp / "config" / "hummingbird.repo").write_text("[hb]\n")
        (self.tmp / "packages" / "fish").mkdir(parents=True)
        (self.tmp / "packages" / "fish" / "fish.spec").write_text("Name: fish\n")
        self.entry = {"name": "fish", "version": "4.1", "sha512": "a"}

    def digest(self, entry=None) -> str:
        return factory_state.input_digest(
            self.tmp, entry or self.entry, factory_state.shared_digest(self.tmp)
        )

    def test_stable(self) -> None:
        self.assertEqual(self.digest(), self.digest())
        self.assertRegex(self.digest(), r"^[0-9a-f]{16}$")

    def test_recipe_inventory_and_build_root_all_move_it(self) -> None:
        before = self.digest()
        self.assertNotEqual(before, self.digest(dict(self.entry, sha512="b")))
        self.assertNotEqual(before, self.digest(dict(self.entry, stage=3)))
        (self.tmp / "packages" / "fish" / "fix.patch").write_text("--- a\n")
        after_patch = self.digest()
        self.assertNotEqual(before, after_patch)
        (self.tmp / "config" / "buildroot-image").write_text("ghcr.io/x@sha256:2\n")
        self.assertNotEqual(after_patch, self.digest())

    def test_the_real_inventory_digests(self) -> None:
        from tools.package_inventory import source_locks

        digests = factory_state.current(ROOT, source_locks(ROOT))
        self.assertEqual(len(digests), len(source_locks(ROOT)))


class ChangedTests(unittest.TestCase):
    STATE = {
        "inputs": {"fish": "f1", "gtk4": "g1", "webkitgtk": "w1", "flaky": "x1"},
        "failed": {"webkitgtk": "w2", "flaky": "x1"},
    }
    DIGESTS = {"fish": "f1", "gtk4": "g2", "webkitgtk": "w2", "flaky": "x1", "new": "n1"}

    def test_a_push_rebuilds_what_moved_and_holds_known_failures(self) -> None:
        moved, held = changed(self.STATE, self.DIGESTS, retry_failed=False)
        self.assertEqual(moved, {"gtk4", "new"})
        self.assertEqual(held, {"webkitgtk"})

    def test_the_schedule_retries_every_failure(self) -> None:
        moved, held = changed(self.STATE, self.DIGESTS, retry_failed=True)
        self.assertEqual(moved, {"gtk4", "new", "webkitgtk", "flaky"})
        self.assertEqual(held, set())

    def test_a_new_edit_to_a_failing_package_is_not_held(self) -> None:
        digests = dict(self.DIGESTS, webkitgtk="w3")
        moved, held = changed(self.STATE, digests, retry_failed=False)
        self.assertIn("webkitgtk", moved)
        self.assertEqual(held, set())


class MergeTests(unittest.TestCase):
    DIGESTS = {"fish": "f2", "gtk4": "g2", "mutter": "m1", "libfoo": "l1", "gone": "z"}

    def test_replaced_trusted_failed_and_pruned(self) -> None:
        seed = {"inputs": {"fish": "f1", "gtk4": "g1", "gone": "z"}, "failed": {"fish": "f1"}}
        state = merge(seed, self.DIGESTS, trusted=["mutter"], replaced=["fish", "libfoo"],
                      failed=["gtk4"], pruned=["gone"])
        self.assertEqual(state["inputs"], {"fish": "f2", "gtk4": "g1", "libfoo": "l1", "mutter": "m1"})
        # fish built, so its old failure is forgotten; gtk4 keeps g1 and is failing at g2.
        self.assertEqual(state["failed"], {"gtk4": "g2"})

    def test_the_first_labelled_image_learns_from_the_plan(self) -> None:
        state = merge(None, self.DIGESTS, trusted=["mutter", "gtk4"], replaced=["fish"],
                      failed=[], pruned=[])
        self.assertEqual(state["inputs"], {"fish": "f2", "gtk4": "g2", "mutter": "m1"})

    def test_a_trusted_package_never_overwrites_a_recorded_digest(self) -> None:
        state = merge({"inputs": {"gtk4": "g1"}, "failed": {}}, self.DIGESTS,
                      trusted=["gtk4"], replaced=[], failed=[], pruned=[])
        self.assertEqual(state["inputs"]["gtk4"], "g1")

    def test_labels_round_trip(self) -> None:
        state = merge(None, self.DIGESTS, trusted=[], replaced=["fish"], failed=["gtk4"], pruned=[])
        labels = {LABEL: json.dumps(state), "org.opencontainers.image.revision": "abc"}
        self.assertEqual(parse_labels(labels), state)
        self.assertIsNone(parse_labels({}))
        self.assertIsNone(parse_labels(None))


if __name__ == "__main__":
    unittest.main()
