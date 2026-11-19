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


class WithheldTests(unittest.TestCase):
    """A build held back so the repository resolves is retried by every run."""

    DIGESTS = {"libnfs": "n2", "gvfs": "g2", "fish": "f1"}

    def test_a_push_retries_a_withheld_package_even_at_its_published_digest(self) -> None:
        # The weekly full rebuild built libnfs at n1 and held it back: inputs
        # still say n1, so the digest alone would never select it again.
        state = {"inputs": {"libnfs": "n2", "gvfs": "g2", "fish": "f1"},
                 "failed": {}, "withheld": {"libnfs": "n2"}}
        for retry in (False, True):
            moved, held = changed(state, self.DIGESTS, retry_failed=retry)
            self.assertEqual(moved, {"libnfs"})
            self.assertEqual(held, set())

    def test_withheld_keeps_the_previous_build_until_a_publication_replaces_it(self) -> None:
        seed = {"inputs": {"libnfs": "n1", "gvfs": "g1"}, "failed": {"libnfs": "n2"}}
        state = merge(seed, self.DIGESTS, trusted=[], replaced=["fish"], failed=[],
                      pruned=[], withheld=["libnfs", "gvfs"])
        self.assertEqual(state["inputs"]["libnfs"], "n1")
        self.assertEqual(state["withheld"], {"gvfs": "g2", "libnfs": "n2"})
        # It built, so it is no longer failing.
        self.assertEqual(state["failed"], {})
        later = merge(state, self.DIGESTS, trusted=[], replaced=["libnfs", "gvfs"],
                      failed=[], pruned=[])
        self.assertEqual(later["withheld"], {})
        self.assertEqual(later["inputs"]["libnfs"], "n2")

    def test_the_label_carries_withheld_from_one_publication_to_the_next(self) -> None:
        state = merge(None, self.DIGESTS, trusted=[], replaced=[], failed=[],
                      pruned=[], withheld=["libnfs"])
        self.assertEqual(parse_labels({LABEL: json.dumps(state)})["withheld"], {"libnfs": "n2"})
        # An image labelled before withheld existed reads as nothing withheld.
        self.assertEqual(parse_labels({LABEL: json.dumps({"inputs": {}, "failed": {}})})["withheld"], {})


    def test_a_withheld_package_that_then_fails_is_held_like_any_failure(self) -> None:
        seed = {"inputs": {"libnfs": "n1", "gvfs": "g2", "fish": "f1"},
                "failed": {}, "withheld": {"libnfs": "n2"}}
        state = merge(seed, self.DIGESTS, trusted=[], replaced=[], failed=["libnfs"],
                      pruned=[])
        self.assertEqual(state["withheld"], {})
        self.assertEqual(state["failed"], {"libnfs": "n2"})
        moved, held = changed(state, self.DIGESTS, retry_failed=False)
        self.assertEqual((moved, held), (set(), {"libnfs"}))

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


class SharedOnlyTests(unittest.TestCase):
    """A build-root move alone versus a package's own change (issue #1207)."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "config").mkdir()
        (self.tmp / "config" / "buildroot-image").write_text("ghcr.io/x@sha256:1\n")
        (self.tmp / "config" / "hummingbird.repo").write_text("[hb]\n")
        self.locks = {}
        for name in ("fish", "gtk4", "mutter"):
            (self.tmp / "packages" / name).mkdir(parents=True)
            (self.tmp / "packages" / name / f"{name}.spec").write_text(f"Name: {name}\n")
            self.locks[name] = {"name": name, "version": "1", "sha512": "a"}
        # The published state, labelled the way publish writes it.
        self.state = merge(None, factory_state.current(self.tmp, self.locks),
                           trusted=list(self.locks), replaced=[], failed=[], pruned=[],
                           shared=factory_state.shared_entry(self.tmp))

    def move_root(self) -> None:
        (self.tmp / "config" / "buildroot-image").write_text("ghcr.io/x@sha256:2\n")

    def classify(self, state=None) -> tuple[set[str], set[str]]:
        state = state or self.state
        moved, _ = changed(state, factory_state.current(self.tmp, self.locks), retry_failed=False)
        return moved, factory_state.shared_only(self.tmp, state, self.locks, moved)

    def test_a_root_move_alone_is_shared_only(self) -> None:
        self.move_root()
        moved, only = self.classify()
        self.assertEqual(moved, {"fish", "gtk4", "mutter"})
        self.assertEqual(only, {"fish", "gtk4", "mutter"})

    def test_an_edited_recipe_or_inventory_entry_is_never_shared_only(self) -> None:
        self.move_root()
        (self.tmp / "packages" / "fish" / "fix.patch").write_text("--- a\n")
        self.locks["gtk4"] = dict(self.locks["gtk4"], sha512="b")
        moved, only = self.classify()
        self.assertEqual(moved, {"fish", "gtk4", "mutter"})
        self.assertEqual(only, {"mutter"})

    def test_a_recipe_edit_without_a_root_move_is_not_shared_only(self) -> None:
        (self.tmp / "packages" / "fish" / "fix.patch").write_text("--- a\n")
        moved, only = self.classify()
        self.assertEqual((moved, only), ({"fish"}, set()))

    def test_a_label_without_shared_proves_nothing(self) -> None:
        legacy = {"inputs": self.state["inputs"], "failed": {}}
        self.move_root()
        moved, only = self.classify(legacy)
        self.assertEqual(moved, {"fish", "gtk4", "mutter"})
        self.assertEqual(only, set())

    def test_a_new_package_is_not_shared_only(self) -> None:
        self.move_root()
        (self.tmp / "packages" / "new").mkdir()
        (self.tmp / "packages" / "new" / "new.spec").write_text("Name: new\n")
        self.locks["new"] = {"name": "new", "version": "1", "sha512": "a"}
        moved, only = self.classify()
        self.assertIn("new", moved)
        self.assertNotIn("new", only)

    def test_a_hummingbird_repo_move_alone_is_not_shared_only(self) -> None:
        # The cache key does not carry hummingbird.repo, so a package changed
        # only by it could hit an entry made before the change.
        (self.tmp / "config" / "hummingbird.repo").write_text("[hb]\npriority=9\n")
        moved, only = self.classify()
        self.assertEqual(moved, {"fish", "gtk4", "mutter"})
        self.assertEqual(only, set())

    def test_a_root_and_repo_move_together_is_shared_only(self) -> None:
        self.move_root()
        (self.tmp / "config" / "hummingbird.repo").write_text("[hb]\npriority=9\n")
        self.assertEqual(self.classify()[1], {"fish", "gtk4", "mutter"})

    def test_a_partial_publish_after_a_move_keeps_the_proof(self) -> None:
        # publish0 replaces fish on the new root and stamps the new shared
        # digest; gtk4 and mutter, not yet rebuilt, keep inputs recorded under
        # the old one.
        self.move_root()
        digests = factory_state.current(self.tmp, self.locks)
        partial = merge(self.state, digests, trusted=[], replaced=["fish"], failed=[],
                        pruned=[], shared=factory_state.shared_entry(self.tmp))
        self.assertEqual(len(partial["shared"]), 2)
        moved, only = self.classify(partial)
        self.assertEqual(moved, {"gtk4", "mutter"})
        self.assertEqual(only, {"gtk4", "mutter"})

    def test_the_history_is_bounded_and_newest_first(self) -> None:
        state = self.state
        for n in range(factory_state.SHARED_HISTORY + 3):
            (self.tmp / "config" / "buildroot-image").write_text(f"ghcr.io/x@sha256:{n + 10}\n")
            state = merge(state, factory_state.current(self.tmp, self.locks), trusted=[],
                          replaced=[], failed=[], pruned=[],
                          shared=factory_state.shared_entry(self.tmp))
        self.assertEqual(len(state["shared"]), factory_state.SHARED_HISTORY)
        self.assertEqual(state["shared"][0], factory_state.shared_entry(self.tmp))

    def test_the_shared_history_survives_the_label(self) -> None:
        labels = {LABEL: json.dumps(self.state)}
        self.assertEqual(parse_labels(labels)["shared"], [factory_state.shared_entry(self.tmp)])


if __name__ == "__main__":
    unittest.main()
