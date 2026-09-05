import json
import unittest
from pathlib import Path

from tools import recipe


ROOT = Path(__file__).parents[1]


class RecipeTests(unittest.TestCase):
    def test_plain_entry_builds_its_own_directory(self):
        item = {"name": "demo"}
        self.assertEqual(recipe.recipe_name(item), "demo")
        self.assertEqual(recipe.rpm_defines(item), [])

    def test_shard_builds_the_shared_recipe_with_its_defines(self):
        item = {"name": "demo-shard", "recipe": "demo", "rpm_defines": ["_without_gtk4 1"]}
        self.assertEqual(recipe.recipe_name(item), "demo")
        self.assertEqual(recipe.rpm_defines(item), ["_without_gtk4 1"])

    def test_defines_must_be_macro_value_pairs(self):
        with self.assertRaises(ValueError):
            recipe.rpm_defines({"name": "demo", "rpm_defines": ["_without_gtk4"]})
        with self.assertRaises(ValueError):
            recipe.rpm_defines({"name": "demo", "rpm_defines": "_without_gtk4 1"})

    def test_webkitgtk_shards_share_the_recipe_and_source(self):
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        gtk4 = recipe.entry("webkitgtk", manifest)
        gtk3 = recipe.entry("webkit2gtk4.1", manifest)
        self.assertEqual(recipe.recipe_name(gtk4), "webkitgtk")
        self.assertEqual(recipe.recipe_name(gtk3), "webkitgtk")
        self.assertEqual(gtk4["sha512"], gtk3["sha512"])
        self.assertEqual(gtk4["version"], gtk3["version"])
        self.assertEqual(gtk4.get("stage"), gtk3.get("stage"))
        # Each shard disables exactly the port the other builds.
        self.assertEqual(recipe.rpm_defines(gtk4), ["_without_gtk3 1"])
        self.assertEqual(recipe.rpm_defines(gtk3), ["_without_gtk4 1"])

    def test_compiler_cache_is_opt_in_and_boolean(self):
        self.assertFalse(recipe.compiler_cache({"name": "demo"}))
        self.assertTrue(recipe.compiler_cache({"name": "demo", "compiler_cache": True}))
        with self.assertRaises(ValueError):
            recipe.compiler_cache({"name": "demo", "compiler_cache": "yes"})

    def test_only_the_long_compiles_keep_a_compiler_cache(self):
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        opted = {
            item["name"]
            for item in manifest["packages"]
            if recipe.compiler_cache(item)
        }
        self.assertEqual(opted, {"webkitgtk", "webkit2gtk4.1", "mozjs140"})

    def test_every_cached_recipe_reads_the_cache_environment(self):
        """The flag mounts the client; the recipe still has to use it.

        This exists as a rule rather than three assertions because opting a
        package in and leaving its %build alone gives a silently uncached
        build, which on a WebKit-scale compile is the difference between
        fitting the runner and not. It caught exactly that on firefox, which
        the tree no longer carries.
        """
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        for item in manifest["packages"]:
            if not recipe.compiler_cache(item):
                continue
            directory = ROOT / "packages" / recipe.recipe_name(item)
            specs = sorted(directory.glob("*.spec"))
            self.assertTrue(specs, item["name"])
            for spec in specs:
                self.assertIn(
                    ". /work/tools/sccache.env", spec.read_text(), str(spec)
                )

    def test_webkitgtk_recipe_reads_the_cache_environment(self):
        spec = (ROOT / "packages/webkitgtk/webkitgtk.spec").read_text()
        # Without this the cache lands inside the container and is discarded.
        self.assertIn(". /work/tools/sccache.env", spec)

    def test_webkitgtk_recipe_gates_both_ports(self):
        spec = (ROOT / "packages/webkitgtk/webkitgtk.spec").read_text()
        self.assertIn("%bcond_without gtk4", spec)
        self.assertIn("%bcond_without gtk3", spec)
        # The debug packages are named after the source package, so the shards
        # must not share one: two webkitgtk-debuginfo RPMs of the same NEVR and
        # different contents cannot both survive in one repository.
        self.assertIn("Name:           webkitgtk4.1", spec)
        self.assertIn("Name:           webkitgtk\n", spec)
        # ...and the shard name must not collide with a subpackage either.
        self.assertNotIn("Name:           webkit2gtk4.1", spec)


if __name__ == "__main__":
    unittest.main()
