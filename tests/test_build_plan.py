#!/usr/bin/env python3
"""Tests for factory build plan and reverse dependency computation."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.build_plan import (
    BuildPlan,
    compute_build_plan,
    compute_reverse_dependency_closure,
    normalize_version,
    parse_spec_symbols,
)

ROOT = Path(__file__).resolve().parent.parent


class BuildPlanTests(unittest.TestCase):
    def setUp(self):
        config_path = ROOT / "config" / "upstream-sources.json"
        config = json.loads(config_path.read_text())
        self.factory_pkgs = {p["name"] for p in config["packages"]}
        self.symbol_to_pkg, self.forward_deps = parse_spec_symbols(ROOT, self.factory_pkgs)

    def test_parse_spec_symbols_covers_known_packages(self):
        self.assertIn("pango", self.symbol_to_pkg)
        self.assertIn("gtk4", self.symbol_to_pkg)
        self.assertIn("libadwaita", self.symbol_to_pkg)
        self.assertIn("pkgconfig(pango)", self.symbol_to_pkg)
        self.assertIn("pkgconfig(gtk4)", self.symbol_to_pkg)
        self.assertIn("pkgconfig(libadwaita-1)", self.symbol_to_pkg)

    def test_direct_reverse_dependency_selection(self):
        # pango is an upstream library for gtk4, gtk3, etc.
        closure, reverse_deps = compute_reverse_dependency_closure(["pango"], self.forward_deps, self.factory_pkgs)
        self.assertIn("pango", closure)
        self.assertIn("gtk4", closure)
        self.assertIn("gtk3", closure)
        self.assertIn("gtk4", reverse_deps["pango"])

    def test_transitive_reverse_dependency_closure(self):
        # Editing gtk4 should select its dependents: libadwaita, mutter, gnome-shell, etc.
        closure, reverse_deps = compute_reverse_dependency_closure(["gtk4"], self.forward_deps, self.factory_pkgs)
        self.assertIn("gtk4", closure)
        self.assertIn("libadwaita", closure)
        self.assertIn("mutter", closure)
        self.assertIn("gnome-shell", closure)
        self.assertIn("xdg-desktop-portal-gnome", closure)

    def test_build_plan_direct_edit_and_reverse_deps(self):
        # Changing only pango recipe should compute plan with pango and downstream closure
        # When published versions match config exactly:
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        published = {p["name"]: p.get("version", "") for p in config["packages"]}
        plan = compute_build_plan(
            root_dir=ROOT,
            changed_files=["packages/pango/pango.spec"],
            published_packages=published,
            full_rebuild=False,
        )
        self.assertFalse(plan.is_full_rebuild)
        self.assertEqual(plan.direct_changes, {"pango"})
        self.assertIn("gtk4", plan.reverse_deps)
        self.assertIn("libadwaita", plan.reverse_deps)
        self.assertIn("pango", plan.packages)
        self.assertIn("gtk4", plan.packages)

    def test_build_plan_global_trigger(self):
        # Modifying global workflow or config triggers a full rebuild
        plan_workflow = compute_build_plan(
            root_dir=ROOT,
            changed_files=[".github/workflows/rebuild-rpms.yml"],
            full_rebuild=False,
        )
        self.assertTrue(plan_workflow.is_full_rebuild)
        self.assertEqual(len(plan_workflow.packages), len(self.factory_pkgs))

        plan_config = compute_build_plan(
            root_dir=ROOT,
            changed_files=["config/runtime-contract.toml"],
            full_rebuild=False,
        )
        self.assertTrue(plan_config.is_full_rebuild)
        self.assertEqual(len(plan_config.packages), len(self.factory_pkgs))

    def test_build_plan_non_code_changes_ignored(self):
        # Documentation or agent changes should not trigger builds
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        published = {p["name"]: p.get("version", "") for p in config["packages"]}
        plan = compute_build_plan(
            root_dir=ROOT,
            changed_files=["README.md", "docs/architecture.md", ".agents/skills/build.md"],
            published_packages=published,
            full_rebuild=False,
        )
        self.assertFalse(plan.is_full_rebuild)
        self.assertEqual(plan.packages, [])

    def test_build_plan_version_change_detection(self):
        # Changing published version triggers rebuild of that package and its reverse deps
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        published = {p["name"]: p.get("version", "") for p in config["packages"]}

        # Now simulate pango version changed in config compared to published
        published["pango"] = "1.50.0"  # different from current 1.58.2
        plan = compute_build_plan(
            root_dir=ROOT,
            changed_files=[],
            published_packages=published,
            full_rebuild=False,
        )
        self.assertIn("pango", plan.direct_changes)
        self.assertIn("gtk4", plan.reverse_deps)
        self.assertIn("pango", plan.packages)

    def test_build_plan_new_package_detection(self):
        # Package missing from published repo must be built along with reverse deps
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        published = {p["name"]: p.get("version", "") for p in config["packages"]}

        # Remove libadwaita from published
        del published["libadwaita"]
        plan = compute_build_plan(
            root_dir=ROOT,
            changed_files=[],
            published_packages=published,
            full_rebuild=False,
        )
        self.assertIn("libadwaita", plan.direct_changes)
        self.assertIn("libadwaita", plan.packages)
        # Downstream of libadwaita like gnome-shell/gnome-control-center should be in reverse deps
        self.assertIn("gnome-control-center", plan.reverse_deps)

    def test_summary_markdown_generation(self):
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        published = {p["name"]: p.get("version", "") for p in config["packages"]}
        plan = compute_build_plan(
            root_dir=ROOT,
            changed_files=["packages/pango/pango.spec"],
            published_packages=published,
            full_rebuild=False,
        )
        md = plan.summary_markdown()
        self.assertIn("# Factory Build Plan", md)
        self.assertIn("pango", md)
        self.assertIn("gtk4", md)
        self.assertIn("## Build Waves", md)
        self.assertIn("## Package Impact Matrix", md)


if __name__ == "__main__":
    unittest.main()
