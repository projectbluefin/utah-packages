#!/usr/bin/env python3
"""Waves solved from BuildRequires, and the cycle config breaks on purpose."""

from pathlib import Path
import tempfile
import unittest

from tools.build_graph import (
    Recipe,
    capabilities,
    dependents,
    graph,
    read_rows,
    waves,
)


def recipe(name, buildrequires=(), provides=()):
    return Recipe(name=name, buildrequires=list(buildrequires), provides={name, *provides})


class CapabilityTests(unittest.TestCase):
    def test_versions_and_operators_are_dropped(self) -> None:
        self.assertEqual(capabilities("pkgconfig(gtk4) >= 4.10"), ["pkgconfig(gtk4)"])
        self.assertEqual(capabilities("vulkan-headers = 1.4.350.0"), ["vulkan-headers"])
        self.assertEqual(capabilities("libtalloc-devel"), ["libtalloc-devel"])
        self.assertEqual(capabilities("  "), [])

    def test_a_rich_dependency_names_every_alternative(self) -> None:
        self.assertEqual(
            capabilities("(python3dist(foo) >= 1 with python3dist(foo) < 2)"),
            ["python3dist(foo)", "python3dist(foo)"],
        )
        self.assertEqual(
            capabilities("(pkgconfig(a) or pkgconfig(b))"), ["pkgconfig(a)", "pkgconfig(b)"]
        )


class GraphTests(unittest.TestCase):
    def test_subpackage_and_explicit_provides_become_edges(self) -> None:
        recipes = {
            "vulkan-headers": recipe("vulkan-headers"),
            "vulkan-loader": recipe("vulkan-loader", ["vulkan-headers"], ["vulkan-loader-devel"]),
            "mesa": recipe("mesa", ["pkgconfig(vulkan)"]),
        }
        # pkgconfig(vulkan) is generated at build time, so only the published
        # repository knows vulkan-loader provides it.
        edges = graph(recipes, {"vulkan-loader": {"pkgconfig(vulkan)", "libvulkan.so.1()(64bit)"}})
        self.assertEqual(edges["vulkan-loader"], {"vulkan-headers"})
        self.assertEqual(edges["mesa"], {"vulkan-loader"})
        self.assertEqual(dependents(edges)["vulkan-headers"], {"vulkan-loader"})

    def test_a_self_edge_and_a_foreign_provider_are_ignored(self) -> None:
        recipes = {"gtk4": recipe("gtk4", ["gtk4-devel", "glib2-devel"], ["gtk4-devel"])}
        self.assertEqual(graph(recipes, {"glib2": {"glib2-devel"}})["gtk4"], set())


class WaveTests(unittest.TestCase):
    EDGES = {
        "libcupsfilters": set(),
        "libppd": {"libcupsfilters"},
        "cups-browsed": {"libcupsfilters", "libppd"},
        "unrelated": set(),
    }

    def test_longest_path_orders_the_set(self) -> None:
        self.assertEqual(
            waves(self.EDGES, self.EDGES, {}),
            {"libcupsfilters": 0, "libppd": 1, "cups-browsed": 2, "unrelated": 0},
        )

    def test_only_edges_inside_the_build_set_count(self) -> None:
        # libcupsfilters is not being rebuilt; its published build serves.
        self.assertEqual(
            waves({"libppd", "cups-browsed"}, self.EDGES, {}),
            {"libppd": 0, "cups-browsed": 1},
        )

    def test_config_stage_breaks_a_cycle_it_was_written_for(self) -> None:
        edges = {
            # flatpak needs libmalcontent; malcontent needs flatpak; the
            # bootstrap build provides libmalcontent without flatpak.
            "malcontent-bootstrap": set(),
            "flatpak": {"malcontent", "malcontent-bootstrap"},
            "malcontent": {"flatpak"},
        }
        stages = {"malcontent-bootstrap": 8, "flatpak": 9, "malcontent": 10}
        self.assertEqual(
            waves(edges, edges, stages),
            {"malcontent-bootstrap": 0, "flatpak": 1, "malcontent": 2},
        )

    def test_a_cycle_config_does_not_break_builds_side_by_side_and_is_named(self) -> None:
        edges = {"a": {"b"}, "b": {"a"}, "c": {"a"}}
        unordered: list[set[str]] = []
        self.assertEqual(waves(edges, edges, {}, unordered), {"a": 0, "b": 0, "c": 1})
        self.assertEqual(unordered, [{"a", "b"}])

    def test_stage_outside_a_cycle_does_not_move_a_package(self) -> None:
        # A hand stage is an override for cycle-breakers only; a package
        # with nothing to wait for goes in the first wave whatever it says.
        self.assertEqual(waves({"gnome-shell"}, {"gnome-shell": set()}, {"gnome-shell": 10}),
                         {"gnome-shell": 0})


class ReadRowsTests(unittest.TestCase):
    def test_reads_the_extraction_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            row = Path(directory) / "vulkan-loader"
            row.mkdir()
            (row / "br").write_text("gcc\nvulkan-headers = 1.4.350.0\n(a or b)\n")
            (row / "names").write_text("vulkan-loader\nvulkan-loader-devel\n")
            (row / "provides").write_text("vulkan = 1.4.350.0-1\nvulkan-devel(x86-64) = 1\n")
            (row / "rc").write_text("0\n0\n0\n")
            (row / "err").write_text("warning: bogus date\n")
            broken = Path(directory) / "broken"
            broken.mkdir()
            (broken / "rc").write_text("1\n1\n1\n")
            (broken / "err").write_text("error: line 3: unknown tag\n")
            recipes = read_rows(Path(directory))
        loader = recipes["vulkan-loader"]
        self.assertEqual(loader.buildrequires, ["gcc", "vulkan-headers", "a", "b"])
        self.assertIn("vulkan-loader-devel", loader.provides)
        self.assertIn("vulkan", loader.provides)
        self.assertTrue(loader.parsed)
        self.assertEqual(loader.error, "")
        self.assertFalse(recipes["broken"].parsed)
        self.assertIn("unknown tag", recipes["broken"].error)


if __name__ == "__main__":
    unittest.main()
