#!/usr/bin/env python3
"""config/upstream-sources.json stays in name order, and only order changes."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.bootstrap_upstream_sources import merge_candidates
from tools.source_lock_order import FIX_COMMAND, in_lock_order, main, sort_lock
from tools.validate import check_source_lock_order


def entry(name: str, **fields) -> dict:
    return {"name": name, "version": "1", "sha512": "0" * 128, **fields}


def render(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


class LockFixture(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "config").mkdir()
        self.lock = self.root / "config" / "upstream-sources.json"

    def write(self, packages: list[dict]) -> None:
        self.lock.write_text(render({"schema": 1, "packages": packages}))

    def names(self) -> list[str]:
        return [package["name"] for package in json.loads(self.lock.read_text())["packages"]]


class ValidatorTests(LockFixture):
    def test_an_unsorted_lock_fails_with_the_pair_and_the_fix_command(self) -> None:
        self.write([entry("alpha"), entry("gamma"), entry("beta")])
        with self.assertRaises(SystemExit) as raised:
            check_source_lock_order(self.root)
        message = str(raised.exception)
        self.assertIn("'gamma' is listed before 'beta'", message)
        self.assertIn(FIX_COMMAND, message)

    def test_a_sorted_lock_passes(self) -> None:
        self.write([entry("ModemManager"), entry("alpha"), entry("libICE"), entry("libacl")])
        check_source_lock_order(self.root)

    def test_the_order_is_case_sensitive(self) -> None:
        # Code-point order, not casefolded: a lock sorted case-insensitively fails.
        self.write([entry("alpha"), entry("ModemManager")])
        with self.assertRaises(SystemExit):
            check_source_lock_order(self.root)

    def test_a_nameless_entry_is_an_invalid_lock_not_a_traceback(self) -> None:
        self.write([entry("alpha"), {"version": "1"}])
        with self.assertRaisesRegex(SystemExit, "invalid source lock"):
            check_source_lock_order(self.root)

    def test_check_flag_exits_nonzero_without_rewriting(self) -> None:
        self.write([entry("beta"), entry("alpha")])
        before = self.lock.read_bytes()
        self.assertEqual(main(["--root", str(self.root), "--check"]), 1)
        self.assertEqual(self.lock.read_bytes(), before)


class SortTests(LockFixture):
    def test_sorting_moves_whole_entries_without_editing_any(self) -> None:
        packages = [
            entry("zenity", fallback_urls=["https://example.org/z"], stage=2),
            entry("NetworkManager-ssh", build_lane="container", build_lane_reason="why"),
            entry("libacl", dist_bump={"count": 1, "baseline": "1"}),
            entry("libICE"),
        ]
        self.write(packages)
        before = {package["name"]: json.dumps(package) for package in packages}
        self.assertTrue(sort_lock(self.lock))
        after = json.loads(self.lock.read_text())
        self.assertEqual(self.names(), ["NetworkManager-ssh", "libICE", "libacl", "zenity"])
        # Same entry set, each object byte-identical including its key order.
        self.assertEqual({package["name"]: json.dumps(package) for package in after["packages"]}, before)
        self.assertEqual(after["schema"], 1)

    def test_sorting_a_sorted_lock_leaves_the_file_untouched(self) -> None:
        self.write([entry("beta"), entry("alpha")])
        sort_lock(self.lock)
        sorted_bytes = self.lock.read_bytes()
        self.assertFalse(sort_lock(self.lock))
        self.assertEqual(self.lock.read_bytes(), sorted_bytes)


class InsertionTests(unittest.TestCase):
    def test_a_merged_candidate_lands_between_its_neighbours(self) -> None:
        existing = {"schema": 1, "packages": [entry("alpha"), entry("gamma"), entry("omega")]}
        merged = merge_candidates(existing, [entry("zeta"), entry("beta")])
        self.assertEqual(
            [package["name"] for package in merged["packages"]],
            ["alpha", "beta", "gamma", "omega", "zeta"],
        )

    def test_merging_keeps_every_existing_object_untouched(self) -> None:
        packages = [entry("alpha", stage=3), entry("gamma", fallback_urls=["https://example.org/g"])]
        snapshot = json.dumps(packages)
        merged = merge_candidates({"schema": 1, "packages": packages}, [entry("beta")])
        by_name = {package["name"]: package for package in merged["packages"]}
        self.assertIs(by_name["alpha"], packages[0])
        self.assertIs(by_name["gamma"], packages[1])
        self.assertEqual(json.dumps(packages), snapshot)

    def test_two_imports_from_one_base_merge_without_conflict(self) -> None:
        # The conflict this order exists to prevent: two import branches cut
        # from the same base used to both append after the last entry.
        base = {"schema": 1, "packages": [entry("alpha"), entry("mid"), entry("omega")]}
        with tempfile.TemporaryDirectory() as directory:
            ours, common, theirs = (Path(directory) / name for name in ("ours", "base", "theirs"))
            common.write_text(render(base))
            ours.write_text(render(merge_candidates(base, [entry("beta")])))
            theirs.write_text(render(merge_candidates(base, [entry("zeta")])))
            merged = subprocess.run(
                ["git", "merge-file", "-p", str(ours), str(common), str(theirs)],
                capture_output=True, text=True,
            )
        self.assertEqual(merged.returncode, 0, merged.stdout)
        self.assertEqual(merged.stdout, render(merge_candidates(base, [entry("beta"), entry("zeta")])))

    def test_in_lock_order_returns_the_same_objects(self) -> None:
        packages = [entry("b"), entry("a")]
        ordered = in_lock_order(packages)
        self.assertIs(ordered[0], packages[1])
        self.assertIs(ordered[1], packages[0])


if __name__ == "__main__":
    unittest.main()
