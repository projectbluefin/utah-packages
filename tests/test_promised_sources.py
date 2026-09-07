"""The promised-source list decides what survives the accumulator purge.

A name missing from it means the lane deletes those RPMs from /work/prior, so
the interesting failures are all false negatives: a package the factory does
build whose source name this does not list. The checks below pin the four
spellings that have each been the real source name for something in the tree.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import promised_sources  # noqa: E402
import recipe  # noqa: E402


class PromisedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        self.names = set(promised_sources.promised(ROOT))

    def test_every_entry_and_recipe_is_promised(self):
        for item in self.config["packages"]:
            self.assertIn(item["name"], self.names)
            self.assertIn(recipe.recipe_name(item), self.names)
            self.assertIn(recipe.lookaside_name(item), self.names)

    def test_every_resolvable_spec_name_is_promised(self):
        """A recipe may set Name: per shard; both spellings must survive.

        webkitgtk is the live case -- the GTK3 shard renames the source package
        to webkitgtk4.1 so its debug RPMs stop colliding with the GTK4 shard --
        but this asserts the property for every recipe rather than that one.
        """
        for item in self.config["packages"]:
            directory = ROOT / "packages" / recipe.recipe_name(item)
            for spec in sorted(directory.glob("*.spec")):
                for name in re.findall(r"(?m)^Name:\s*(\S+)", spec.read_text()):
                    if "%" in name:
                        continue
                    self.assertIn(name, self.names, f"{spec} declares {name}")

    def test_webkitgtk_shards_are_both_promised(self):
        self.assertIn("webkitgtk", self.names)
        self.assertIn("webkitgtk4.1", self.names)

    def test_a_recipe_whose_name_is_a_macro_falls_back_to_its_directory(self):
        """Specs this cannot expand must still be covered, or the purge eats them."""
        unresolved = []
        for item in self.config["packages"]:
            directory = ROOT / "packages" / recipe.recipe_name(item)
            specs = sorted(directory.glob("*.spec"))
            if not specs:
                continue
            declared = re.findall(r"(?m)^Name:\s*(\S+)", specs[0].read_text())
            if not declared or all("%" in name for name in declared):
                unresolved.append(recipe.recipe_name(item))
        self.assertTrue(unresolved, "expected some specs to set Name: from a macro")
        for name in unresolved:
            self.assertIn(name, self.names)

    def test_a_removed_entry_is_not_promised(self):
        """The bug this exists for: libbluray came out and must stop excluding Fedora."""
        self.assertNotIn("libbluray", self.names)

    def test_the_script_prints_the_same_list(self):
        output = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "promised_sources.py")],
            capture_output=True, text=True, check=True, cwd=ROOT,
        ).stdout.split()
        self.assertEqual(sorted(output), sorted(self.names))

    def test_an_empty_manifest_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "upstream-sources.json").write_text('{"packages": []}')
            with self.assertRaises(ValueError):
                promised_sources.promised(root)


class SourceRpmNameTests(unittest.TestCase):
    """The lane strips %{SOURCERPM} back to a name with sed, so pin that shape.

    A source name can contain dashes and digits and dots, so the release and
    version have to come off the end rather than the name off the front.
    """

    @staticmethod
    def strip(source_rpm: str) -> str:
        return subprocess.run(
            ["sed", "s/\\.src\\.rpm$//; s/-[^-]*-[^-]*$//"],
            input=source_rpm, capture_output=True, text=True, check=True,
        ).stdout.strip()

    def test_names_with_dashes_and_dots_survive(self):
        cases = {
            "ffmpeg-9.0.1-1.hum1.bfin.src.rpm": "ffmpeg",
            "gstreamer1-plugins-base-1.28.0-1.hum1.bfin.src.rpm": "gstreamer1-plugins-base",
            "webkitgtk4.1-2.50.1-1.hum1.bfin.src.rpm": "webkitgtk4.1",
            "libbluray-1.5.0-1.hum1.bfin.src.rpm": "libbluray",
            "malcontent-0.14.0-0.bootstrap.1.hum1.bfin.src.rpm": "malcontent",
            "python-typing-inspection-0.4.4-1.hum1.bfin.src.rpm": "python-typing-inspection",
        }
        for source_rpm, expected in cases.items():
            self.assertEqual(self.strip(source_rpm), expected, source_rpm)

    def test_every_stripped_name_of_a_promised_build_stays_promised(self):
        """End to end: what the lane computes must match what the tool allows."""
        names = set(promised_sources.promised(ROOT))
        for name in sorted(names):
            self.assertEqual(self.strip(f"{name}-1.2.3-4.hum1.bfin.src.rpm"), name)


if __name__ == "__main__":
    unittest.main()
