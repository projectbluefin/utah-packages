#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

from tools.rebuild_plan import (
    changed_entries,
    dependents_from_primary,
    expected_release,
    format_build_plan,
    is_global_change,
    is_published,
    merge_dependents,
    overflow,
    plan,
    provides_from_primary,
    published_from_primary,
    reverse_closure,
    spec_dependents,
    stage_outputs,
    stale_from_primary,
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
    """The runtime soname edge: a rebuilt library drags what links against it."""

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
        self.assertEqual([e["name"] for e in build], ["mutter", "gnome-shell", "gse-x"])

    def test_a_dependent_with_no_recipe_is_ignored(self) -> None:
        config = {"packages": [{"name": "mutter", "version": "1.0"}]}
        build = plan(
            config, Path("/nonexistent"), published={}, changed={"mutter"},
            full=False, factory_repo="", dependents={"mutter": {"ghost"}},
        )
        self.assertEqual([e["name"] for e in build], ["mutter"])


class SpecDependentsTests(unittest.TestCase):
    """Build-time dependency edges parsed from specs."""

    def test_spec_dependents_finds_buildrequires_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages_dir = root / "packages"

            # libfoo provides libfoo, libfoo-devel, pkgconfig(libfoo)
            p_foo = packages_dir / "libfoo"
            p_foo.mkdir(parents=True)
            (p_foo / "libfoo.spec").write_text(
                "Name: libfoo\nVersion: 1.0\nRelease: 1%{?dist}\n"
                "%package devel\nSummary: devel\n"
            )

            # bar BuildRequires: libfoo-devel
            p_bar = packages_dir / "bar"
            p_bar.mkdir(parents=True)
            (p_bar / "bar.spec").write_text(
                "Name: bar\nVersion: 1.0\nRelease: 1%{?dist}\n"
                "BuildRequires: libfoo-devel\n"
            )

            deps = spec_dependents(root, {"libfoo", "bar"})
            self.assertIn("bar", deps.get("libfoo", set()))

    def test_pkgconfig_symbols_map_to_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages_dir = root / "packages"

            p_cam = packages_dir / "libcamera"
            p_cam.mkdir(parents=True)
            (p_cam / "libcamera.spec").write_text(
                "Name: libcamera\nVersion: 1.0\nRelease: 1%{?dist}\n"
                "Provides: pkgconfig(libcamera)\n"
            )

            p_pw = packages_dir / "pipewire"
            p_pw.mkdir(parents=True)
            (p_pw / "pipewire.spec").write_text(
                "Name: pipewire\nVersion: 1.0\nRelease: 1%{?dist}\n"
                "BuildRequires: pkgconfig(libcamera)\n"
            )

            deps = spec_dependents(root, {"libcamera", "pipewire"})
            self.assertIn("pipewire", deps.get("libcamera", set()))

    def test_merge_dependents_combines_multiple_maps(self) -> None:
        m1 = {"a": {"b"}}
        m2 = {"a": {"c"}, "d": {"e"}}
        merged = merge_dependents(m1, m2)
        self.assertEqual(merged, {"a": {"b", "c"}, "d": {"e"}})


class GlobalChangeTests(unittest.TestCase):
    def test_global_workflow_changes_trigger_full_rebuild(self) -> None:
        is_global, triggers = is_global_change([".github/workflows/rebuild-rpms.yml"])
        self.assertTrue(is_global)
        self.assertIn(".github/workflows/rebuild-rpms.yml", triggers)

        is_global, triggers = is_global_change([".github/workflows/build-stage.yml"])
        self.assertTrue(is_global)

    def test_global_tooling_changes_trigger_full_rebuild(self) -> None:
        is_global, triggers = is_global_change(["tools/mock_config.py"])
        self.assertTrue(is_global)
        self.assertIn("tools/mock_config.py", triggers)

        # Test and planning tool changes do not force full rebuilds
        is_global, _ = is_global_change(["tools/rebuild_plan.py", "tests/test_rebuild_plan.py"])
        self.assertFalse(is_global)

    def test_global_config_changes_trigger_full_rebuild(self) -> None:
        is_global, triggers = is_global_change(["config/hummingbird.repo"])
        self.assertTrue(is_global)
        self.assertIn("config/hummingbird.repo", triggers)

        # upstream-sources.json alone is an inventory change, not global rebuild
        is_global, _ = is_global_change(["config/upstream-sources.json"])
        self.assertFalse(is_global)

    def test_ignored_paths_do_not_trigger_rebuild(self) -> None:
        is_global, _ = is_global_change([
            "docs/architecture.md",
            "AGENTS.md",
            "README.md",
            ".agents/skills/build-failure-triage/SKILL.md",
        ])
        self.assertFalse(is_global)


class StaleTests(unittest.TestCase):
    """A published binary asking for what nothing provides any more rebuilds."""

    PRIMARY = full_primary(
        ("libheif", "libheif", ["libheif.so.1()(64bit)"], ["libavcodec.so.62()(64bit)", "libX11.so.6()(64bit)"]),
        ("libavcodec-free", "ffmpeg-free", ["libavcodec.so.63()(64bit)"], ["libc.so.6"]),
        ("gnome-shell", "gnome-shell", ["gnome-shell"], ["libheif.so.1()(64bit)", "rpmlib(PayloadIsZstd)", "(foo or bar)", "/usr/bin/python3"]),
    )
    EXTERNAL = {"libc.so.6"}

    def test_provides_include_shipped_files(self) -> None:
        primary = full_primary(("a", "a", ["cap"], [])).replace(
            b"</format>", b"</format><file>/usr/bin/a</file>", 1
        )
        self.assertEqual(provides_from_primary(primary), {"cap", "/usr/bin/a"})

    def test_an_unsatisfied_soname_marks_its_source_stale(self) -> None:
        stale = stale_from_primary(self.PRIMARY, self.EXTERNAL)
        self.assertEqual(stale, {"libheif": {"libavcodec.so.62()(64bit)"}})

    def test_unsatisfied_base_buildroot_sonames_do_not_flag_stale(self) -> None:
        # libX11.so.6()(64bit) is unsatisfied in PRIMARY and absent from EXTERNAL,
        # but libX11.so is not provided by the factory, so it must not mark libheif stale.
        stale = stale_from_primary(self.PRIMARY, {"libavcodec.so.62()(64bit)"})
        self.assertEqual(stale, {})

    def test_external_provides_count_as_satisfied(self) -> None:
        stale = stale_from_primary(self.PRIMARY, {"libavcodec.so.62()(64bit)"})
        self.assertNotIn("libheif", stale)

    def test_rpmlib_rich_and_file_requires_are_not_judged(self) -> None:
        stale = stale_from_primary(self.PRIMARY, self.EXTERNAL)
        self.assertNotIn("gnome-shell", stale)

    def test_a_stale_package_rebuilds_and_drags_its_dependents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("libheif", "ffmpeg-free", "gnome-shell"):
                recipe(root, name, "1")
            config = {"packages": [
                {"name": "ffmpeg-free", "version": "1.0", "stage": 0},
                {"name": "libheif", "version": "1.0", "stage": 1},
                {"name": "gnome-shell", "version": "1.0", "stage": 2},
            ]}
            published = published_from_primary(self.PRIMARY)
            stale = set(stale_from_primary(self.PRIMARY, self.EXTERNAL))
            names = [
                entry["name"]
                for entry in plan(
                    config, root, published=published, changed=set(), full=False,
                    factory_repo="file:///work/factory",
                    dependents=dependents_from_primary(self.PRIMARY), stale=stale,
                )
            ]
            self.assertEqual(names, ["libheif", "gnome-shell"])


class BuildPlanFormattingTests(unittest.TestCase):
    def test_format_build_plan_markdown_and_json(self) -> None:
        build = [{"name": "demo", "stage": 0}, {"name": "sub", "stage": 1}]
        reasons = {
            "demo": ["recipe edit"],
            "sub": ["reverse dependency of demo"],
        }
        md, plan_json = format_build_plan(
            build,
            reasons,
            full=False,
            direct_changes={"demo"},
            reverse_deps={"sub"},
            total_inventory=10,
        )
        self.assertIn("# Factory Build Plan", md)
        self.assertIn("**Build Mode:** Incremental", md)
        self.assertIn("`demo`", md)
        self.assertIn("`sub`", md)
        self.assertEqual(plan_json["mode"], "incremental")
        self.assertEqual(plan_json["total_selected"], 2)
        self.assertEqual(plan_json["total_inventory"], 10)
        self.assertEqual(plan_json["stages"]["stage0"], ["demo"])
        self.assertEqual(plan_json["stages"]["stage1"], ["sub"])

    def test_format_build_plan_full_rebuild(self) -> None:
        build = [{"name": "demo", "stage": 0}]
        reasons = {"demo": ["global trigger (tools/rebuild_plan.py)"]}
        md, plan_json = format_build_plan(
            build,
            reasons,
            full=True,
            global_triggers=["tools/rebuild_plan.py"],
            total_inventory=1,
        )
        self.assertIn("**Build Mode:** Full Rebuild", md)
        self.assertIn("tools/rebuild_plan.py", md)
        self.assertEqual(plan_json["mode"], "full")
        self.assertEqual(plan_json["global_triggers"], ["tools/rebuild_plan.py"])


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
