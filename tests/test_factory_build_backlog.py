#!/usr/bin/env python3
"""Cover the factory build backlog catalog and its auditor.

The catalog (``config/factory-build-backlog.toml``) is the surface that
makes the 551-name backlog from projectbluefin/utah-packages#308
shrinkable: every name must appear in exactly one area, the area totals
must reconcile with the audit's 551, and removing a name requires it to
also land in ``[resolved]`` or ``[wontfix]`` so the count never silently
shrinks. The auditor (``tools/factory_build_backlog.py``) partitions
catalog names against the live repo state (``packages/``,
``config/upstream-sources.json``, ``.packit.yaml``, and
``config/bluefin-packages.toml``) so every import lands in
``already_*`` and reduces the ``pending`` total.

Tests construct a minimal tree on disk so the auditor and catalog can be
exercised without pulling or modifying the live repository.
"""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from tools import factory_build_backlog as backlog


def _toml(catalog_root: Path, areas: dict[str, list[str]], resolved: list[str] | None = None, wontfix: list[str] | None = None) -> Path:
    """Write a minimal ``config/factory-build-backlog.toml`` and return its path."""
    resolved = resolved or []
    wontfix = wontfix or []
    config_dir = catalog_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "factory-build-backlog.toml"
    lines = [
        "[meta]",
        'issue = "projectbluefin/utah-packages#308"',
        'audit_source = "https://example.test/gist"',
        'audit_digest_bluefin = "sha256:00"',
        'audit_digest_utah = "sha256:00"',
        'audit_digest_factory = "sha256:00"',
        'audit_measured_at = "2026-09-30T22:08:14Z"',
        "",
    ]
    for area, names in areas.items():
        lines.append(f"[areas.{area}]")
        lines.append('consumer_issue = "projectbluefin/utah#1"')
        lines.append("packages = [")
        for name in names:
            lines.append(f'    "{name}",')
        lines.append("]")
        lines.append("")
    lines.append("[resolved]")
    lines.append("packages = [")
    for entry in resolved:
        if isinstance(entry, dict):
            name = entry["name"]
            commit = entry.get("commit", "0" * 40)
            lines.append(f'    {{ name = "{name}", commit = "{commit}" }},')
        else:
            lines.append(f'    {{ name = "{entry}", commit = "{"0" * 40}" }},')
    lines.append("]")
    lines.append("")
    lines.append("[wontfix]")
    lines.append("packages = [")
    for entry in wontfix:
        if isinstance(entry, dict):
            name = entry["name"]
            reason = entry.get("reason", "wontfix")
            lines.append(f'    {{ name = "{name}", reason = "{reason}" }},')
        else:
            lines.append(f'    {{ name = "{entry}", reason = "wontfix" }},')
    lines.append("]")
    lines.append("")
    path.write_text("\n".join(lines))
    return path


def _populate(root: Path, *, recipes: list[str], locked: list[str], packit: list[str], manifest: list[str]) -> None:
    """Materialize the artifacts the auditor reads against."""
    packages_dir = root / "packages"
    packages_dir.mkdir(exist_ok=True)
    for name in recipes:
        (packages_dir / name).mkdir()
        (packages_dir / name / "sources").write_text("")
        # A spec file is what the live ``package_inventory`` expects; without
        # one the inventory raises and the auditor's snapshot-check guard
        # breaks for the wrong reason.
        (packages_dir / name / f"{name}.spec").write_text(f"Name: {name}\nVersion: 0\n")
        (packages_dir / name / ".hummingbird-upstream.json").write_text(
            json.dumps(
                {
                    "package": name,
                    "branch": "rawhide",
                    "remote": "https://example.test/rpms/" + name,
                    "commit": "0" * 40,
                    "tree": "0" * 40,
                    "imported_at": "2026-09-30T22:00:00Z",
                }
            )
        )
    (root / "config").mkdir(exist_ok=True)
    locks_data = {
        "schema": 1,
        "packages": [
            {"name": n, "url": f"https://example.test/{n}.tar.gz", "filename": f"{n}.tar.gz", "sha512": "0" * 128}
            for n in locked
        ],
    }
    (root / "config" / "upstream-sources.json").write_text(json.dumps(locks_data))
    packit_lines = ["packages:\n"]
    for name in packit:
        packit_lines.append(f"  {name}:\n    specfile_path: {name}.spec\n")
    (root / ".packit.yaml").write_text("".join(packit_lines))
    manifest_lines = ["[base]\n", 'packages = [']
    for name in manifest:
        manifest_lines.append(f'    "{name}",')
    manifest_lines.append("]\n")
    (root / "config" / "bluefin-packages.toml").write_text("".join(manifest_lines))


class CatalogTotalsTests(unittest.TestCase):
    def test_collects_one_list_per_area(self) -> None:
        catalog = tomllib.loads(
            '[areas.a]\npackages = ["x", "y"]\n'
            '[areas.b]\npackages = ["z"]\n'
            '[resolved]\npackages = []\n'
            '[wontfix]\npackages = []\n'
        )
        all_backlog, by_area, wontfix, resolved = backlog._catalog_totals(catalog)

        self.assertEqual(all_backlog, {"x", "y", "z"})
        self.assertEqual(by_area, {"a": ["x", "y"], "b": ["z"]})
        self.assertEqual(wontfix, set())
        self.assertEqual(resolved, set())

    def test_keeps_a_repeat_inside_one_area(self) -> None:
        """A within-area repeat must survive so ``_report`` can reject it."""
        catalog = tomllib.loads(
            '[areas.a]\npackages = ["x", "x"]\n'
            '[resolved]\npackages = []\n'
            '[wontfix]\npackages = []\n'
        )
        _, by_area, _, _ = backlog._catalog_totals(catalog)
        self.assertEqual(by_area, {"a": ["x", "x"]})


class ClassifyTests(unittest.TestCase):
    """The partition order is significant: the strongest signal wins."""

    def test_recipe_wins_over_lock(self) -> None:
        state = backlog._classify("fish", recipes={"fish"}, subpackages=set(), locks={"fish"}, packit={"fish"}, manifest={"fish"})
        self.assertEqual(state, "already_recipe")

    def test_lock_wins_over_packit(self) -> None:
        state = backlog._classify("fish", recipes=set(), subpackages=set(), locks={"fish"}, packit={"fish"}, manifest={"fish"})
        self.assertEqual(state, "already_locked")

    def test_packit_wins_over_manifest(self) -> None:
        state = backlog._classify("fish", recipes=set(), subpackages=set(), locks=set(), packit={"fish"}, manifest={"fish"})
        self.assertEqual(state, "already_packit")

    def test_manifest_wins_over_pending(self) -> None:
        state = backlog._classify("fish", recipes=set(), subpackages=set(), locks=set(), packit=set(), manifest={"fish"})
        self.assertEqual(state, "manifest_wants")

    def test_pending_when_no_signal(self) -> None:
        state = backlog._classify("fish", recipes=set(), subpackages=set(), locks=set(), packit=set(), manifest=set())
        self.assertEqual(state, "pending")

    def test_subpackage_wins_over_everything(self) -> None:
        # A name that is a ``%package -n`` subpackage of an existing recipe
        # is built by the factory even when no other signal is present --
        # a fresh spec with only ``%package -n libavcodec`` lines (no
        # packit, no lock, no manifest) still resolves to ``already_recipe``.
        state = backlog._classify("libavcodec", recipes=set(), subpackages={"libavcodec"}, locks=set(), packit=set(), manifest=set())
        self.assertEqual(state, "already_recipe")

    def test_subpackage_does_not_mask_recipe_partition(self) -> None:
        # If a name happens to match both ``recipes`` and ``subpackages``,
        # it still resolves to ``already_recipe`` (the same state). The
        # ``subpackages`` set only matters when ``recipes`` is empty --
        # which is the whole point of classifying subpackage names
        # without false-positiving on names that already have their own
        # recipe directory.
        state = backlog._classify("fish", recipes={"fish"}, subpackages={"fish"}, locks=set(), packit=set(), manifest=set())
        self.assertEqual(state, "already_recipe")


class SubpackageNameParserTests(unittest.TestCase):
    """``_subpackage_names`` reads every ``%package`` shape a spec may use.

    Two forms are equivalent to RPM:

    - ``%package -n NAME`` — explicit name. Common for library subpackages
      whose name does not share the spec's prefix
      (``%package -n libavcodec`` in ``ffmpeg.spec``).
    - ``%package SUFFIX`` — implicit name. RPM tacks the suffix onto the
      spec's ``Name:``. Fedora-style specs use this for split-out build
      outputs that share the parent's provenance
      (``%package qt6`` in ``gstreamer1-plugins-good.spec`` would ship
      ``gstreamer1-plugins-good-qt6`` -- in that spec it is guarded by an
      off-by-default bcond, so it does not).

    Guards matter as much as shapes: a ``%package`` only counts when every
    enclosing ``%if`` is known to be taken for the default build.

    Without parsing the second form, the auditor would count every
    implicit-suffix name as ``pending`` even though the factory build
    already ships it as part of the parent recipe. The test fixtures
    mirror those real shapes, not the abstract ones.
    """

    def _spec(self, root: Path, recipe: str, body: str) -> None:
        spec_dir = root / "packages" / recipe
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_path = spec_dir / f"{recipe}.spec"
        spec_path.write_text(f"Name: {recipe}\nVersion: 0\n\n{body}\n")

    def test_explicit_n_form_picks_the_explicit_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._spec(root, "ffmpeg", "%package -n libavcodec\nSummary: libavcodec\n")
            self.assertIn("libavcodec", backlog._subpackage_names(root))

    def test_implicit_suffix_form_picks_spec_name_dash_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._spec(root, "gstreamer1-plugins-good", "%package qt6\nSummary: qt6\n")
            self.assertIn("gstreamer1-plugins-good-qt6", backlog._subpackage_names(root))

    def test_both_shapes_in_one_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%package -n libavcodec\nSummary: libavcodec\n"
                "%package qt6\nSummary: qt6\n"
                "%package extras\nSummary: extras\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            names = backlog._subpackage_names(root)
            self.assertIn("libavcodec", names)
            self.assertIn("gstreamer1-plugins-good-qt6", names)
            self.assertIn("gstreamer1-plugins-good-extras", names)

    def test_disabled_bcond_guard_excludes_the_subpackage(self) -> None:
        """``%package`` under an off-by-default ``%bcond`` is not shipped.

        ``packages/gstreamer1-plugins-good/`` is the real shape: the spec
        sets ``%bcond_with qt6`` and guards ``%package qt6`` with ``%if
        %{with qt6}``. Nothing in this factory passes ``--with qt6``, so
        the subpackage is never built and the backlog name is still owed.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%bcond_with qt6\n"
                "%package gtk\nSummary: gtk\n"
                "%if %{with qt6}\n%package qt6\nSummary: qt6\n%endif\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            names = backlog._subpackage_names(root)
            self.assertIn("gstreamer1-plugins-good-gtk", names)
            self.assertNotIn("gstreamer1-plugins-good-qt6", names)

    def test_negated_off_bcond_guard_keeps_the_subpackage(self) -> None:
        """``%if ! %{with freeworld_lavc}`` is true, so ``libav*`` ships.

        This is ``packages/ffmpeg/``: the whole ``libav*`` block sits under
        a negated bcond that is off by default, so the default build does
        produce those subpackages.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%bcond freeworld_lavc 0\n"
                "%if ! %{with freeworld_lavc}\n"
                "%package -n libavcodec\nSummary: libavcodec\n"
                "%endif\n"
                "%if %{with freeworld_lavc}\n"
                "%package -n libavcodec-freeworld\nSummary: freeworld\n"
                "%endif\n"
            )
            self._spec(root, "ffmpeg", body)
            names = backlog._subpackage_names(root)
            self.assertIn("libavcodec", names)
            self.assertNotIn("libavcodec-freeworld", names)

    def test_bcond_without_defaults_the_feature_on(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = "%bcond_without qt5\n%if %{with qt5}\n%package qt\nSummary: qt\n%endif\n"
            self._spec(root, "gstreamer1-plugins-good", body)
            self.assertIn("gstreamer1-plugins-good-qt", backlog._subpackage_names(root))

    def test_else_branch_of_a_known_condition_flips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%bcond_with qt6\n"
                "%if %{with qt6}\n%package qt6\nSummary: qt6\n"
                "%else\n%package noqt\nSummary: noqt\n%endif\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            names = backlog._subpackage_names(root)
            self.assertNotIn("gstreamer1-plugins-good-qt6", names)
            self.assertIn("gstreamer1-plugins-good-noqt", names)

    def test_undecidable_guard_is_treated_as_not_built(self) -> None:
        """A distro/arch guard the auditor cannot evaluate stays ``pending``.

        The auditor has no build target, so ``%ifarch`` and ``0%{?fedora}``
        are unknowable. A missed name is visible work in the backlog; a
        false ``already_recipe`` would hide a real gap, which the tool's
        contract forbids.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%ifarch x86_64\n%package vpl\nSummary: vpl\n%endif\n"
                "%if 0%{?fedora}\n%package extras\nSummary: extras\n%endif\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            self.assertEqual(backlog._subpackage_names(root), set())

    def test_bcond_under_undecidable_guard_is_unknown(self) -> None:
        """The ``%if 0%{?fedora} ... %else ... %endif`` bcond idiom.

        ``packages/bluez/`` and ``packages/ffmpeg/`` declare bconds this
        way. RPM evaluates only one branch, and the auditor cannot tell
        which, so the bcond stays unknown instead of taking the ``%else``
        value -- otherwise a guarded ``%package`` would be reported as
        ``already_recipe`` when the real build may not ship it.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%if 0%{?fedora}\n%bcond_with jack\n"
                "%else\n%bcond_without jack\n%endif\n"
                "%if %{with jack}\n%package jack\nSummary: jack\n%endif\n"
            )
            self._spec(root, "pipewire", body)
            self.assertNotIn("pipewire-jack", backlog._subpackage_names(root))

    def test_bcond_under_untaken_guard_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%bcond_with qt6\n%bcond_with extras\n"
                "%if %{with qt6}\n%bcond_without extras\n%endif\n"
                "%if %{with extras}\n%package extras\nSummary: extras\n%endif\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            self.assertNotIn(
                "gstreamer1-plugins-good-extras", backlog._subpackage_names(root)
            )

    def test_nested_guards_require_every_frame_taken(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            body = (
                "%bcond_without extras\n%bcond_with qt6\n"
                "%if %{with extras}\n"
                "%package extras\nSummary: extras\n"
                "%if %{with qt6}\n%package qt6\nSummary: qt6\n%endif\n"
                "%package more\nSummary: more\n"
                "%endif\n"
            )
            self._spec(root, "gstreamer1-plugins-good", body)
            names = backlog._subpackage_names(root)
            self.assertIn("gstreamer1-plugins-good-extras", names)
            self.assertIn("gstreamer1-plugins-good-more", names)
            self.assertNotIn("gstreamer1-plugins-good-qt6", names)

    def test_no_package_lines_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._spec(root, "fish", "%description\nBuilt by the factory.\n")
            self.assertEqual(backlog._subpackage_names(root), set())

    def test_packages_directory_absent_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(backlog._subpackage_names(root), set())


class PackitAndLockTests(unittest.TestCase):
    def test_packit_names_returns_every_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".packit.yaml").write_text(
                "packages:\n"
                "  fish:\n    specfile_path: fish.spec\n"
                "  zsh:\n    specfile_path: zsh.spec\n"
            )
            self.assertEqual(backlog._packit_names(root / ".packit.yaml"), {"fish", "zsh"})

    def test_packit_names_handles_plus_and_dot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".packit.yaml").write_text(
                "packages:\n"
                "  python3-keyring+completion:\n    specfile_path: a.spec\n"
                "  vid.stab:\n    specfile_path: b.spec\n"
            )
            self.assertEqual(backlog._packit_names(root / ".packit.yaml"), {"python3-keyring+completion", "vid.stab"})

    def test_lock_names_reads_schema_1(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "packages": [
                            {"name": "fish"},
                            {"name": "zsh"},
                        ],
                    }
                )
            )
            self.assertEqual(backlog._lock_names(root / "upstream-sources.json"), {"fish", "zsh"})

    def test_manifest_names_collects_every_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bluefin-packages.toml").write_text(
                "[base]\npackages = [\"a\"]\n"
                "[fedora_v44]\npackages = [\"b\", \"c\"]\n"
                "[excluded]\npackages = [\"d\"]\n"
            )
            self.assertEqual(backlog._manifest_names(root / "bluefin-packages.toml"), {"a", "b", "c"})


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="backlog-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self) -> Path:
        catalog_path = _toml(
            self.root,
            areas={"codecs-media": ["ffmpeg", "x264-libs"], "power": ["tuned"]},
        )
        _populate(
            self.root,
            recipes=["ffmpeg"],
            locked=[],
            packit=[],
            manifest=[],
        )
        return catalog_path

    def test_partition_count_sums_match_catalog(self) -> None:
        report = backlog._report(self.root, self._write())
        states = report["states"]
        total = sum(states.values())
        self.assertEqual(total, report["totals"]["backlog"])
        self.assertEqual(report["totals"]["backlog"], 3)
        self.assertEqual(states["already_recipe"], 1)
        self.assertEqual(states["pending"], 2)

    def test_categorization_resolves_a_recipe_to_already_recipe(self) -> None:
        report = backlog._report(self.root, self._write())
        ffmpeg = next(entry for entry in report["entries"] if entry["name"] == "ffmpeg")
        self.assertEqual(ffmpeg["state"], "already_recipe")

    def test_pending_count_rolls_up_per_area(self) -> None:
        report = backlog._report(self.root, self._write())
        self.assertEqual(report["areas"]["codecs-media"]["pending"], 1)
        self.assertEqual(report["areas"]["codecs-media"]["already_recipe"], 1)
        self.assertEqual(report["areas"]["power"]["pending"], 1)

    def test_resolved_entries_drop_pending(self) -> None:
        # ``tuned`` is removed from the area and recorded in ``[resolved]``;
        # this is the documented contract for closing a backlog gap.
        catalog_path = _toml(
            self.root,
            areas={"power": []},
            resolved=[{"name": "tuned", "commit": "0" * 40}],
        )
        _populate(self.root, recipes=[], locked=[], packit=[], manifest=[])
        report = backlog._report(self.root, catalog_path)
        self.assertEqual(report["totals"]["backlog"], 0)
        self.assertEqual(report["totals"]["resolved"], 1)

    def test_wontfix_entries_count_as_resolved(self) -> None:
        # Same contract: dropping a name from the area must record the
        # decision in ``[wontfix]`` so the count never silently shrinks.
        catalog_path = _toml(
            self.root,
            areas={"power": []},
            wontfix=[{"name": "tuned", "reason": "wontfix"}],
        )
        _populate(self.root, recipes=[], locked=[], packit=[], manifest=[])
        report = backlog._report(self.root, catalog_path)
        self.assertEqual(report["totals"]["wontfix"], 1)
        self.assertEqual(report["totals"]["backlog"], 0)
        self.assertEqual(report["entries"], [])


class CatalogConsistencyTests(unittest.TestCase):
    """The catalog itself is a contract: 551 total, no duplicates across areas.

    The 551-name audit source is fixed; closing a gap moves a name out of
    an area into either ``[resolved]`` or ``[wontfix]`` (the two-edit
    closing contract documented in docs/skills/factory-build-backlog.md).
    That means the assertion is on the *sum* of the three tables, not on
    the backlog alone -- a PR that closes a gap without recording the
    decision would shrink the sum below 551, and a PR that closes a gap
    with a one-edit (drop only) would shrink the sum below 551 too.
    """

    CATALOG_TOTAL = 551

    def test_real_catalog_matches_the_audit_count(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        with (repo_root / "config" / "factory-build-backlog.toml").open("rb") as handle:
            catalog = tomllib.load(handle)
        all_backlog, by_area, wontfix, resolved = backlog._catalog_totals(catalog)
        digest = hashlib.sha256(
            ("\n".join(sorted(all_backlog | wontfix | resolved)) + "\n").encode()
        ).hexdigest()
        self.assertEqual(digest, "48210d268ba97da8da55f883529ee27f38bc48a4d8f3c4fad46913ef8614d07b")
        self.assertEqual(catalog["meta"]["audit_names_sha256"], digest)
        self.assertEqual(
            len(all_backlog) + len(resolved) + len(wontfix),
            self.CATALOG_TOTAL,
            f"factory-build-backlog.toml must record all {self.CATALOG_TOTAL} names "
            "(sum of areas + [resolved] + [wontfix]) from issue #308",
        )
        # Every name appears in exactly one area, once: a repeat inside an
        # area or across two areas would inflate the count above the area total.
        per_name = {}
        for area, names in by_area.items():
            for name in names:
                per_name[name] = per_name.get(name, 0) + 1
        duplicates = sorted(name for name, count in per_name.items() if count != 1)
        self.assertEqual(duplicates, [], f"catalog lists names more than once: {duplicates}")
        # Resolved and wontfix entries must not appear in any area: the catalog
        # design says once a name leaves the backlog it must land in one of
        # these two tables, and the next import must move it.
        removed = wontfix | resolved
        overlap = removed & all_backlog
        self.assertEqual(overlap, set(), f"these names are in both the backlog and a resolved table: {sorted(overlap)}")
        # A name may not be both resolved and wontfixed: the decision is one
        # of two, never both.
        both = resolved & wontfix
        self.assertEqual(both, set(), f"catalog lists names in both [resolved] and [wontfix]: {sorted(both)}")

    def test_real_report_matches_the_catalog_total(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        report = backlog._report(repo_root, repo_root / "config" / "factory-build-backlog.toml")
        # The report's totals are a partition of the catalog: backlog +
        # resolved + wontfix must equal the audit count. ``states`` only
        # covers backlog entries (every entry is classified once), so
        # ``sum(states) == backlog`` -- that's the correct shape, not a
        # regression against the audit count.
        totals = report["totals"]
        self.assertEqual(
            totals["backlog"] + totals["resolved"] + totals["wontfix"],
            self.CATALOG_TOTAL,
        )
        states_total = sum(report["states"].values())
        self.assertEqual(states_total, totals["backlog"])


class CatalogOverlapTests(unittest.TestCase):
    """The auditor must surface every catalog contract break, not silently pass."""

    def test_overlap_area_and_resolved_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned", "thermald"]},
                resolved=[{"name": "tuned", "commit": "0" * 40}],
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            with self.assertRaises(SystemExit) as caught:
                backlog._report(root, catalog_path)
            self.assertIn("tuned", str(caught.exception))
            self.assertIn("area and [resolved]", str(caught.exception))

    def test_overlap_area_and_wontfix_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned"]},
                wontfix=[{"name": "tuned", "reason": "wontfix"}],
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            with self.assertRaises(SystemExit) as caught:
                backlog._report(root, catalog_path)
            self.assertIn("tuned", str(caught.exception))
            self.assertIn("area and [wontfix]", str(caught.exception))

    def test_overlap_resolved_and_wontfix_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": []},
                resolved=[{"name": "tuned", "commit": "0" * 40}],
                wontfix=[{"name": "tuned", "reason": "wontfix"}],
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            with self.assertRaises(SystemExit) as caught:
                backlog._report(root, catalog_path)
            self.assertIn("tuned", str(caught.exception))
            self.assertIn("[resolved] and [wontfix]", str(caught.exception))

    def test_duplicate_across_areas_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned"], "codecs-media": ["tuned"]},
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            with self.assertRaises(SystemExit) as caught:
                backlog._report(root, catalog_path)
            self.assertIn("more than once", str(caught.exception))
            self.assertIn("tuned", str(caught.exception))

    def test_duplicate_within_one_area_exits(self) -> None:
        """A name repeated inside a single area breaks the same contract."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned", "tuned"]},
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            with self.assertRaises(SystemExit) as caught:
                backlog._report(root, catalog_path)
            self.assertIn("more than once", str(caught.exception))
            self.assertIn("tuned", str(caught.exception))


class CheckGateTests(unittest.TestCase):
    def test_check_passes_on_a_fresh_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned"], "codecs-media": ["ffmpeg"]},
            )
            _populate(root, recipes=["ffmpeg"], locked=[], packit=[], manifest=[])
            report = backlog._report(root, catalog_path)
            # Write the snapshot first so --check has a target.
            snapshot = root / "reports" / "factory-build-backlog.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            # Re-run the report generation and persist a comparable snapshot.
            snapshot.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            self.assertEqual(backlog._check(report, snapshot), 0)

    def test_check_fails_on_stale_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(root, areas={"power": ["tuned"]})
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            report = backlog._report(root, catalog_path)
            snapshot = root / "reports" / "factory-build-backlog.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            # Write a snapshot whose ``totals`` differ from ``report`` so the
            # check must surface the drift.
            stale = json.loads(json.dumps(report))
            stale["totals"]["backlog"] = 999
            snapshot.write_text(json.dumps(stale, indent=2, sort_keys=True) + "\n")
            self.assertEqual(backlog._check(report, snapshot), 1)

    def test_check_fails_on_missing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(root, areas={"power": ["tuned"]})
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            report = backlog._report(root, catalog_path)
            snapshot = root / "reports" / "factory-build-backlog.json"
            self.assertEqual(backlog._check(report, snapshot), 1)

    def test_check_fails_when_a_name_moved_between_areas(self) -> None:
        """Totals and states are blind to a move; areas and entries are not."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(
                root,
                areas={"power": ["tuned"], "codecs-media": ["ffmpeg"]},
            )
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            report = backlog._report(root, catalog_path)
            stale = json.loads(json.dumps(report))
            for entry in stale["entries"]:
                entry["area"] = "power" if entry["area"] == "codecs-media" else "codecs-media"
            stale["areas"] = {
                "power": report["areas"]["codecs-media"],
                "codecs-media": report["areas"]["power"],
            }
            self.assertEqual(stale["totals"], report["totals"])
            self.assertEqual(stale["states"], report["states"])
            snapshot = root / "reports" / "factory-build-backlog.json"
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_text(json.dumps(stale, indent=2, sort_keys=True) + "\n")
            self.assertEqual(backlog._check(report, snapshot), 1)

    def test_report_has_no_wall_clock_field(self) -> None:
        """Two runs of the same tree must produce identical bytes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = _toml(root, areas={"power": ["tuned"]})
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            first = backlog._report(root, catalog_path)
            second = backlog._report(root, catalog_path)
            self.assertNotIn("measured_at", first)
            self.assertEqual(
                json.dumps(first, indent=2, sort_keys=True),
                json.dumps(second, indent=2, sort_keys=True),
            )

    def test_check_resolves_paths_against_root_not_cwd(self) -> None:
        """``--root <tree> --check`` must work from any working directory."""
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(directory)
            _toml(root, areas={"power": ["tuned"]})
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            self.assertEqual(backlog.main(["--root", str(root)]), 0)
            cwd = os.getcwd()
            os.chdir(elsewhere)
            try:
                self.assertEqual(backlog.main(["--root", str(root), "--check"]), 0)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()


class AuditIdentityTests(unittest.TestCase):
    def test_equal_count_substitution_fails_but_closing_record_preserves_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _populate(root, recipes=[], locked=[], packit=[], manifest=[])
            digest = hashlib.sha256(b"x\ny\n").hexdigest()
            path = _toml(root, {"area": ["x", "y"]})
            path.write_text(path.read_text().replace("[meta]", f'[meta]\naudit_names_sha256 = "{digest}"'))
            self.assertEqual(backlog._report(root, path)["totals"]["backlog"], 2)
            path.write_text(path.read_text().replace('"y",', '"stray",'))
            with self.assertRaisesRegex(SystemExit, "catalog names differ"):
                backlog._report(root, path)
            path = _toml(root, {"area": ["x"]}, resolved=["y"])
            path.write_text(path.read_text().replace("[meta]", f'[meta]\naudit_names_sha256 = "{digest}"'))
            self.assertEqual(backlog._report(root, path)["totals"]["resolved"], 1)
