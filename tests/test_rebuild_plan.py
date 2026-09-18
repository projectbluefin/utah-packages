#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

from tools.rebuild_plan import (
    changed_entries,
    dependents_from_primary,
    expected_release,
    is_published,
    overflow,
    plan,
    published_from_primary,
    reverse_closure,
    stage_outputs,
)


def primary(*entries: tuple[str, str, str]) -> bytes:
    """Minimal repodata primary.xml carrying only what the plan reads."""
    body = "".join(
        f"<package><name>{name}-libs</name>"
        f"<format><rpm:sourcerpm>{name}-{version}-{release}.src.rpm"
        f"</rpm:sourcerpm></format></package>"
        for name, version, release in entries
    )
    return f"<metadata>{body}</metadata>".encode()


def recipe(root: Path, name: str, release: str) -> None:
    package_dir = root / "packages" / name
    package_dir.mkdir(parents=True)
    (package_dir / f"{name}.spec").write_text(
        f"Name:           {name}\nVersion:        1.0\nRelease:        {release}%{{?dist}}\n"
    )


class PublishedParsingTests(unittest.TestCase):
    def test_keys_by_source_name_not_binary_name(self) -> None:
        # The binary in the fixture is demo-libs; the source is demo. Keying by
        # <name> would miss it entirely, which is how `wayland` could never be
        # matched: it ships no binary of that name.
        self.assertEqual(
            published_from_primary(primary(("demo", "1.0", "3.hum1.bfin"))),
            {"demo": ("1.0", "3.hum1.bfin")},
        )

    def test_ignores_entries_without_a_source_rpm(self) -> None:
        self.assertEqual(published_from_primary(b"<metadata></metadata>"), {})


class PublishedComparisonTests(unittest.TestCase):
    def test_matches_when_version_and_release_both_agree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            entry = {"name": "demo", "version": "1.0"}
            self.assertTrue(is_published(root, entry, {"demo": ("1.0", "3.hum1.bfin")}))

    def test_rebuilds_when_only_the_release_moved(self) -> None:
        # The gap this closes: a spec fix or an added patch bumps Release while
        # Version stands still. Comparing name+version alone skipped it, and on
        # the nightly schedule there is no diff range to catch it either.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "4")
            entry = {"name": "demo", "version": "1.0"}
            self.assertFalse(is_published(root, entry, {"demo": ("1.0", "3.hum1.bfin")}))

    def test_accepts_any_hummingbird_tag(self) -> None:
        # build-stage.yml reads the tag from the buildroot, so a move to hum2
        # must not invalidate every comparison.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            entry = {"name": "demo", "version": "1.0"}
            self.assertTrue(is_published(root, entry, {"demo": ("1.0", "3.hum2.bfin")}))

    def test_release_carries_the_dist_bump_counter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            entry = {
                "name": "demo",
                "version": "1.0",
                "dist_bump": {"count": 1, "baseline": "3"},
            }
            self.assertTrue(
                is_published(root, entry, {"demo": ("1.0", "3.hum1.bfin.1")})
            )
            # The counter is part of the identity: without it, this is a
            # different build and has to run.
            self.assertFalse(is_published(root, entry, {"demo": ("1.0", "3.hum1.bfin")}))

    def test_rejects_a_release_this_factory_did_not_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            entry = {"name": "demo", "version": "1.0"}
            self.assertFalse(is_published(root, entry, {"demo": ("1.0", "3.fc44")}))

    def test_normalizes_the_tilde_fedora_writes_into_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "1")
            entry = {"name": "demo", "version": "51.beta"}
            self.assertTrue(
                is_published(root, entry, {"demo": ("51~beta", "1.hum1.bfin")})
            )

    def test_an_autorelease_recipe_falls_back_to_the_version(self) -> None:
        # rpmautospec decides %autorelease at build time, so the release cannot
        # be predicted here. About half the inventory is in that shape, and
        # rebuilding all of it every run would be a real cost, so this matches
        # on version alone -- what the comparison did for every package before.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "%autorelease")
            entry = {"name": "demo", "version": "1.0"}
            self.assertIsNone(expected_release(root, entry))
            self.assertTrue(is_published(root, entry, {"demo": ("1.0", "3.hum1.bfin")}))
            # The version still has to agree.
            self.assertFalse(
                is_published(root, entry, {"demo": ("1.1", "3.hum1.bfin")})
            )


class ChangedEntryTests(unittest.TestCase):
    """A stage move has to force a rebuild.

    This is the gap that published a repository whose mozc and gnome-shell
    were the exact builds the stage move existed to replace: the move changed
    neither Version nor Release, so both matched the published listing and
    were skipped.
    """

    def _config(self, **overrides) -> dict:
        entry = {"name": "mozc", "version": "1.0", "stage": 0}
        entry.update(overrides)
        return {"packages": [entry, {"name": "quiet", "version": "2.0"}]}

    def test_a_stage_move_counts_as_changed(self) -> None:
        self.assertEqual(
            changed_entries(self._config(), self._config(stage=1)), {"mozc"}
        )

    def test_an_untouched_entry_does_not(self) -> None:
        self.assertEqual(changed_entries(self._config(), self._config()), set())

    def test_a_new_source_or_checksum_counts(self) -> None:
        self.assertEqual(
            changed_entries(self._config(), self._config(sha512="beef")), {"mozc"}
        )

    def test_a_new_entry_counts(self) -> None:
        after = self._config()
        after["packages"].append({"name": "fresh", "version": "1.0"})
        self.assertEqual(changed_entries(self._config(), after), {"fresh"})

    def test_a_removed_entry_is_not_reported(self) -> None:
        # There is nothing left to build, so it must not reach the matrix.
        before = self._config()
        after = {"packages": [before["packages"][1]]}
        self.assertEqual(changed_entries(before, after), set())


class PlanTests(unittest.TestCase):
    def _config(self) -> dict:
        return {"packages": [{"name": "demo", "version": "1.0"}]}

    def test_skips_a_published_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            self.assertEqual(
                plan(
                    self._config(),
                    root,
                    published={"demo": ("1.0", "3.hum1.bfin")},
                    changed=set(),
                    full=False,
                    factory_repo="https://example.invalid/repo/",
                ),
                [],
            )

    def test_skips_nothing_without_a_factory_repository(self) -> None:
        # The published listing is only a witness if the build root will really
        # have that repository. This is the pipewire-libs-extra failure: skipped
        # as published, then absent from the buildroot.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            self.assertEqual(
                [
                    entry["name"]
                    for entry in plan(
                        self._config(),
                        root,
                        published={"demo": ("1.0", "3.hum1.bfin")},
                        changed=set(),
                        full=False,
                        factory_repo="",
                    )
                ],
                ["demo"],
            )

    def test_a_changed_recipe_always_builds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            self.assertEqual(
                [
                    entry["name"]
                    for entry in plan(
                        self._config(),
                        root,
                        published={"demo": ("1.0", "3.hum1.bfin")},
                        changed={"demo"},
                        full=False,
                        factory_repo="https://example.invalid/repo/",
                    )
                ],
                ["demo"],
            )

    def test_full_ignores_what_is_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe(root, "demo", "3")
            self.assertEqual(
                len(
                    plan(
                        self._config(),
                        root,
                        published={"demo": ("1.0", "3.hum1.bfin")},
                        changed=set(),
                        full=True,
                        factory_repo="https://example.invalid/repo/",
                    )
                ),
                1,
            )


def full_primary(*packages: tuple[str, str, list[str], list[str]]) -> bytes:
    """A primary.xml with real namespaces, provides and requires.

    Each package is (binary name, source name, provides, requires); the source
    is always version 1.0 release 1.hum1.bfin.
    """
    body = ""
    for name, source, provides, requires in packages:
        body += (
            f"<package type=\"rpm\"><name>{name}</name><format>"
            f"<rpm:sourcerpm>{source}-1.0-1.hum1.bfin.src.rpm</rpm:sourcerpm>"
            "<rpm:provides>"
            + "".join(f"<rpm:entry name=\"{p}\"/>" for p in provides)
            + "</rpm:provides><rpm:requires>"
            + "".join(f"<rpm:entry name=\"{r}\"/>" for r in requires)
            + "</rpm:requires></format></package>"
        )
    return (
        "<metadata xmlns=\"http://linux.duke.edu/metadata/common\" "
        "xmlns:rpm=\"http://linux.duke.edu/metadata/rpm\">" + body + "</metadata>"
    ).encode()


class DependentsTests(unittest.TestCase):
    """The soname edge: a rebuilt library drags what links against it."""

    PRIMARY = full_primary(
        ("mutter-libs", "mutter", ["libmutter-17.so.0()(64bit)"], ["libc.so.6"]),
        ("gnome-shell", "gnome-shell", ["gnome-shell"], ["libmutter-17.so.0()(64bit)"]),
        ("gnome-shell-extension-x", "gse-x", [], ["gnome-shell"]),
        ("unrelated", "unrelated", [], ["libc.so.6"]),
    )

    def test_maps_a_provider_to_the_sources_that_require_it(self) -> None:
        self.assertEqual(
            dependents_from_primary(self.PRIMARY),
            {"mutter": {"gnome-shell"}, "gnome-shell": {"gse-x"}},
        )

    def test_a_package_requiring_its_own_subpackage_is_not_an_edge(self) -> None:
        primary = full_primary(
            ("demo", "demo", ["demo"], ["demo-libs"]),
            ("demo-libs", "demo", ["demo-libs"], []),
        )
        self.assertEqual(dependents_from_primary(primary), {})

    def test_closure_is_transitive_and_excludes_the_seed(self) -> None:
        dependents = dependents_from_primary(self.PRIMARY)
        self.assertEqual(reverse_closure({"mutter"}, dependents), {"gnome-shell", "gse-x"})

    def test_a_rebuilt_library_drags_its_published_dependents(self) -> None:
        # Every package is published at the version the inventory names, so
        # without the closure only the changed mutter would build -- and the
        # published gnome-shell would stay linked against the mutter this run
        # replaces.
        config = {
            "packages": [
                {"name": "mutter", "version": "1.0", "stage": 6},
                {"name": "gnome-shell", "version": "1.0", "stage": 10},
                {"name": "gse-x", "version": "1.0", "stage": 10},
                {"name": "unrelated", "version": "1.0"},
            ]
        }
        published = published_from_primary(self.PRIMARY)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("mutter", "gnome-shell", "gse-x", "unrelated"):
                recipe(root, name, "1")
            build = plan(
                config, root, published=published, changed={"mutter"},
                full=False, factory_repo="file:///repo",
                dependents=dependents_from_primary(self.PRIMARY),
            )
        # Inventory order is preserved so stages still come out in wave order.
        self.assertEqual([e["name"] for e in build], ["mutter", "gnome-shell", "gse-x"])

    def test_a_dependent_with_no_recipe_is_ignored(self) -> None:
        # Something the repository still carries from a recipe that was since
        # dropped cannot be rebuilt; the closure must not invent an entry.
        config = {"packages": [{"name": "mutter", "version": "1.0"}]}
        build = plan(
            config, Path("/nonexistent"), published={}, changed={"mutter"},
            full=False, factory_repo="", dependents={"mutter": {"ghost"}},
        )
        self.assertEqual([e["name"] for e in build], ["mutter"])


class StageOutputTests(unittest.TestCase):
    def test_chunks_a_stage_past_the_matrix_cap(self) -> None:
        build = [{"name": f"p{n}", "stage": 0} for n in range(266)]
        outputs = stage_outputs(build)
        chunks = [json.loads(chunk) for chunk in json.loads(outputs["stage0_chunks"])]
        self.assertEqual([len(chunk) for chunk in chunks], [250, 16])
        self.assertTrue(all(len(chunk) <= 256 for chunk in chunks))
        self.assertEqual(
            [name for chunk in chunks for name in chunk],
            [entry["name"] for entry in build],
        )

    def test_a_stage_with_no_packages_is_an_empty_list(self) -> None:
        outputs = stage_outputs([{"name": "demo", "stage": 0}])
        self.assertEqual(outputs["stage7"], "[]")
        self.assertEqual(outputs["stage7_chunks"], "[]")

    def test_reports_a_stage_that_has_no_job(self) -> None:
        self.assertEqual(
            overflow([{"name": "late", "stage": 11}, {"name": "fine", "stage": 10}]),
            ["late"],
        )


if __name__ == "__main__":
    unittest.main()
