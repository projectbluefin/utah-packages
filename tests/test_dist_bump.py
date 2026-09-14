#!/usr/bin/env python3

import unittest

from tools.dist_bump import BumpError, spec_release, suffix


class SpecReleaseTests(unittest.TestCase):
    def test_strips_the_dist_macro(self) -> None:
        self.assertEqual(spec_release("Name: x\nRelease: 3%{?dist}\n"), "3")
        self.assertEqual(spec_release("Release: 0.1%{dist}\n"), "0.1")

    def test_keeps_a_release_with_no_dist_macro(self) -> None:
        self.assertEqual(spec_release("Release: 7\n"), "7")

    def test_extracts_the_leading_release_from_sub_macros(self) -> None:
        # The literal release before the first macro is stable across rebuilds,
        # so it is what a baseline compares against; trailing optional macros
        # (gitdate, pre_tag) are ignored rather than treated as uncomparable.
        self.assertEqual(
            spec_release(
                "Release: 5%{?gitdate:.%{gitdate}git%{gitversion}}%{?dist}\n"
            ),
            "5",
        )
        self.assertEqual(spec_release("Release: 1%{?pre_tag}%{?dist}\n"), "1")

    def test_returns_no_release_for_a_purely_macro_release(self) -> None:
        # %autorelease, %{baserelease}, krb5's %{krb5_release}: no literal
        # segment to compare, so the bump is skipped (""), not crashed on.
        for release in (
            "Release: %{krb5_release}%{?dist}\n",
            "Release: %{autorelease}\n",
            "Release:        %autorelease -b3\n",
            "Release: %{baserelease}%{?snapdate:.%{snapdate}git%{shortcommit}}%{?dist}\n",
        ):
            self.assertEqual(spec_release(release), "")

    def test_reports_a_spec_with_no_release(self) -> None:
        with self.assertRaises(BumpError):
            spec_release("Name: x\nVersion: 1\n")


class SuffixTests(unittest.TestCase):
    def test_no_bump_means_no_suffix(self) -> None:
        self.assertEqual(suffix({"name": "x"}, "3"), "")

    def test_applies_the_count_while_the_baseline_holds(self) -> None:
        entry = {"dist_bump": {"count": 1, "baseline": "3"}}
        self.assertEqual(suffix(entry, "3"), ".1")

    def test_retires_the_count_once_fedora_moves(self) -> None:
        # The whole point of the baseline. Release 4 already outranks anything
        # published as 3.bfin.1, so claiming .1 again would assert a rebuild
        # that never happened.
        entry = {"dist_bump": {"count": 1, "baseline": "3"}}
        self.assertEqual(suffix(entry, "4"), "")

    def test_compares_a_numeric_baseline_as_written(self) -> None:
        entry = {"dist_bump": {"count": 2, "baseline": 3}}
        self.assertEqual(suffix(entry, "3"), ".2")

    def test_a_multi_segment_release_is_still_just_a_string(self) -> None:
        entry = {"dist_bump": {"count": 1, "baseline": "0.1"}}
        self.assertEqual(suffix(entry, "0.1"), ".1")
        self.assertEqual(suffix(entry, "0.2"), "")

    def test_rejects_the_bare_integer_shape(self) -> None:
        # The shape this file used to accept. It cannot say what release it
        # was counted against, which is the bug.
        with self.assertRaises(BumpError):
            suffix({"dist_bump": 1}, "3")

    def test_rejects_a_bump_missing_its_baseline(self) -> None:
        with self.assertRaises(BumpError):
            suffix({"dist_bump": {"count": 1}}, "3")


if __name__ == "__main__":
    unittest.main()
