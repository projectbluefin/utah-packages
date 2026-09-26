#!/usr/bin/env python3
"""Coverage for tools/check_suppressed_tests.py, run by tools/validate.py.

The gate exists because one `%global tests_nonfatal 1` would have closed
issue #132 by shipping a PipeWire with a hanging test in it. These tests fix
both halves of that: a new definition fails, and the one inherited exception
cannot outlive the recipe that earned it -- nor grow past the number of
definitions that recipe was imported with.
"""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import check_suppressed_tests
from tools.check_suppressed_tests import INHERITED, drifted, main, offenders


# The shape every Fedora audio %check uses. The guard reads tests_nonfatal;
# it never defines it, so it must not be mistaken for one.
GUARDED_CHECK = (
    "%check\n"
    "%meson_test || TESTS_ERROR=$?\n"
    'if [ "${TESTS_ERROR}" != "" ]; then\n'
    'echo "test failed"\n'
    "%{!?tests_nonfatal:exit $TESTS_ERROR}\n"
    "fi\n"
)


class SuppressedTestsTests(unittest.TestCase):
    def recipe(self, root: Path, package: str, body: str) -> Path:
        directory = root / "packages" / package
        directory.mkdir(parents=True)
        path = directory / f"{package}.spec"
        path.write_text(body)
        return path

    def test_guard_alone_is_not_a_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pipewire", GUARDED_CHECK)
            self.assertEqual(offenders(root), [])

    def test_global_and_define_both_caught(self) -> None:
        for macro in ("%global", "%define"):
            with self.subTest(macro=macro):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    self.recipe(
                        root,
                        "pipewire",
                        f"{macro} tests_nonfatal 1\n" + GUARDED_CHECK,
                    )
                    found = offenders(root)
                    self.assertEqual(
                        [(package, number) for package, number, _ in found],
                        [("pipewire", 1)],
                    )

    def test_indented_definition_is_caught(self) -> None:
        # Fedora indents these inside %if blocks; leading space must not hide
        # the definition from the gate.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(
                root,
                "pipewire",
                "%ifarch %{ix86}\n  %global tests_nonfatal 1\n%endif\n",
            )
            self.assertEqual([p for p, _, _ in offenders(root)], ["pipewire"])

    def test_inherited_package_is_exempt_up_to_its_recorded_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pulseaudio", "%global tests_nonfatal 1\n" * 2)
            self.assertEqual(offenders(root), [])
            self.assertEqual(drifted(root), [])

    def test_a_definition_beyond_the_recorded_count_is_drift(self) -> None:
        # The bug this closes: exempting the whole package would let a Fedora
        # import bump add a third, unconditional definition to pulseaudio and
        # pass the gate, because offenders() never scans an allowlisted recipe.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pulseaudio", "%global tests_nonfatal 1\n" * 3)
            (report,) = drifted(root)
            self.assertIn("defines tests_nonfatal 3 time(s)", report)
            self.assertIn("allowlist records 2", report)
            self.assertIn("packages/pulseaudio/pulseaudio.spec:3", report)
            self.assertEqual(main(root), 1)

    def test_fewer_definitions_than_recorded_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pulseaudio", "%global tests_nonfatal 1\n")
            (report,) = drifted(root)
            self.assertIn("allowlist records 2", report)
            self.assertIn("lower the count", report)
            self.assertEqual(main(root), 1)

    def test_inherited_entry_that_no_longer_applies_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pulseaudio", GUARDED_CHECK)
            self.assertEqual(
                drifted(root),
                ["pulseaudio: no longer defines tests_nonfatal; drop the entry"],
            )

    def test_an_absent_recipe_is_not_drift(self) -> None:
        # validate.py runs against synthetic trees, so "the allowlisted recipe
        # is not here" must not be an error. Deletion is caught by
        # test_every_inherited_entry_still_exists instead.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages").mkdir()
            self.assertEqual(drifted(root), [])
            self.assertEqual(main(root), 0)

    def test_every_inherited_entry_still_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        for package in INHERITED:
            with self.subTest(package=package):
                self.assertTrue(
                    sorted((root / "packages" / package).glob("*.spec")),
                    f"{package} is allowlisted but has no recipe; drop the entry",
                )

    def test_recorded_counts_match_the_real_tree(self) -> None:
        # drifted() is what enforces this at gate time; asserting it here too
        # names the recipe in the failure, so a bumped import says which
        # allowlist entry to revisit.
        root = Path(__file__).resolve().parent.parent
        for package, (expected, _reason) in INHERITED.items():
            with self.subTest(package=package):
                found = [
                    number
                    for spec in sorted((root / "packages" / package).glob("*.spec"))
                    for number, _line in check_suppressed_tests.definitions(spec)
                ]
                self.assertEqual(
                    len(found),
                    expected,
                    f"{package} defines tests_nonfatal at lines {found}; "
                    f"INHERITED records {expected}",
                )

    def test_main_fails_on_a_new_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # pulseaudio at its recorded count, so only pipewire is the failure.
            self.recipe(root, "pulseaudio", "%global tests_nonfatal 1\n" * 2)
            self.recipe(root, "pipewire", "%global tests_nonfatal 1\n")
            self.assertEqual(drifted(root), [])
            self.assertEqual(main(root), 1)

    def test_main_fails_on_a_drifted_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pulseaudio", GUARDED_CHECK)
            self.assertEqual(main(root), 1)

    def test_main_passes_a_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.recipe(root, "pipewire", GUARDED_CHECK)
            with mock.patch.dict(check_suppressed_tests.INHERITED, clear=True):
                self.assertEqual(main(root), 0)

    def test_the_real_tree_passes_and_pulseaudio_is_why_the_list_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(main(root), 0)
        self.assertIn("pulseaudio", INHERITED)


if __name__ == "__main__":
    unittest.main()
