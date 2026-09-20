"""A cache hit must be indistinguishable from a build, or it is not safe.

The factory used to rebuild most of its 342 packages every run because its only skip
mechanism is the atomically-published consumer repository, whose witness has
been frozen at 67 packages since 2026-08-30 (issue #177). webkitgtk alone built
20 times on 19 September at 182 minutes a build, with byte-identical inputs.

tools/package_cache_key.py is the key for a per-package cache that answers "have
we already built this exact thing", kept separate from "is the repository
coherent enough to install from". The danger it has to avoid is serving an RPM
built under inputs that differ from this run's -- which is the same incoherence
the publish gate exists to catch, arriving by a route that bypasses it. So these
tests are mostly about what must *change* the key.
"""
import hashlib
import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/package_cache_key.py"

spec = importlib.util.spec_from_file_location("package_cache_key", SCRIPT)
pck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pck)

BASE = dict(
    package="webkitgtk",
    recipe="recipe-digest",
    buildroot_digest="sha256:buildroot",
    factory_digest="sha256:factory",
    resolved_root=["gcc-15.2.1-1.fc44.x86_64", "glibc-2.42-1.fc44.x86_64"],
    disttag=".hum1.bfin",
)


class KeySensitivityTests(unittest.TestCase):
    def test_identical_inputs_give_an_identical_key(self):
        self.assertEqual(pck.cache_key(**BASE), pck.cache_key(**BASE))

    def test_the_resolved_root_order_does_not_matter(self):
        """dnf reports installs in transaction order, which varies harmlessly."""
        reversed_root = dict(BASE, resolved_root=list(reversed(BASE["resolved_root"])))
        self.assertEqual(pck.cache_key(**BASE), pck.cache_key(**reversed_root))

    def test_a_duplicate_in_the_root_does_not_change_the_key(self):
        doubled = dict(BASE, resolved_root=BASE["resolved_root"] + BASE["resolved_root"])
        self.assertEqual(pck.cache_key(**BASE), pck.cache_key(**doubled))

    def test_every_input_changes_the_key(self):
        """The whole safety argument. A missed input serves a wrong RPM."""
        variants = {
            "package": dict(BASE, package="bluez"),
            "recipe": dict(BASE, recipe="other-digest"),
            "buildroot": dict(BASE, buildroot_digest="sha256:other"),
            "factory": dict(BASE, factory_digest="sha256:other"),
            "disttag": dict(BASE, disttag=".hum1.bfin.2"),
            "resolved_root": dict(
                BASE, resolved_root=["gcc-15.2.2-1.fc44.x86_64",
                                     "glibc-2.42-1.fc44.x86_64"]
            ),
        }
        base = pck.cache_key(**BASE)
        for field, variant in variants.items():
            with self.subTest(field=field):
                self.assertNotEqual(
                    base, pck.cache_key(**variant),
                    f"changing {field} must change the key, or a cache hit can "
                    f"serve an RPM built under different inputs",
                )

    def test_the_schema_is_part_of_the_key(self):
        """An entry computed under older rules must not look current."""
        base = pck.cache_key(**BASE)
        original = pck.SCHEMA
        try:
            pck.SCHEMA = original + "-next"
            self.assertNotEqual(base, pck.cache_key(**BASE))
        finally:
            pck.SCHEMA = original


class RecipeDigestTests(unittest.TestCase):
    def recipe(self, files: dict[str, bytes]) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            return pck.recipe_digest(root)

    def test_the_changelog_is_part_of_the_recipe(self):
        """%autorelease reads it, so it decides the Release and the NEVR.

        Many specs use %autorelease. A digest that ignored the changelog
        would treat two different releases as the same build.
        """
        a = self.recipe({"p.spec": b"spec", "changelog": b"* one\n"})
        b = self.recipe({"p.spec": b"spec", "changelog": b"* one\n* two\n"})
        self.assertNotEqual(a, b)

    def test_patches_and_sources_count(self):
        a = self.recipe({"p.spec": b"spec", "fix.patch": b"--- a\n"})
        b = self.recipe({"p.spec": b"spec", "fix.patch": b"--- b\n"})
        self.assertNotEqual(a, b)

    def test_a_rename_is_a_change(self):
        """Paths are hashed with contents, so moving a patch is not invisible."""
        a = self.recipe({"p.spec": b"spec", "one.patch": b"x"})
        b = self.recipe({"p.spec": b"spec", "two.patch": b"x"})
        self.assertNotEqual(a, b)

    def test_an_added_file_changes_it(self):
        a = self.recipe({"p.spec": b"spec"})
        b = self.recipe({"p.spec": b"spec", "extra.gpg": b"key"})
        self.assertNotEqual(a, b)

    def test_an_empty_recipe_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                pck.recipe_digest(Path(tmp))

    def test_the_real_webkitgtk_recipe_hashes(self):
        digest = pck.recipe_digest(ROOT / "packages/webkitgtk")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        # And is stable across calls, which is the property the cache needs.
        self.assertEqual(digest, pck.recipe_digest(ROOT / "packages/webkitgtk"))


class CommandLineTests(unittest.TestCase):
    def run_script(self, package="webkitgtk", root_lines="gcc-1\nglibc-1\n", extra=()):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write(root_lines)
            path = handle.name
        try:
            return subprocess.run(
                ["python3", str(SCRIPT), package,
                 "--buildroot-digest", "sha256:aaa",
                 "--factory-digest", "sha256:bbb",
                 "--disttag", ".hum1.bfin",
                 "--resolved-root", path, *extra],
                capture_output=True, text=True, cwd=ROOT,
            )
        finally:
            Path(path).unlink()

    def test_it_prints_a_single_key(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^[0-9a-f]{32}$")
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_an_empty_resolved_root_is_refused_rather_than_keyed(self):
        """A key over nothing would collide across genuinely different roots."""
        result = self.run_script(root_lines="\n  \n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to compute a cache key", result.stderr)

    def test_an_unknown_package_fails(self):
        result = self.run_script(package="does-not-exist")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no recipe at", result.stderr)


class CacheableSelectionTests(unittest.TestCase):
    """The cache must not decide what to rebuild, only how to obtain it."""

    @classmethod
    def setUpClass(cls):
        import importlib
        cls.rp = importlib.import_module("tools.rebuild_plan")

    def build(self, *names):
        return [{"name": n} for n in names]

    def test_it_never_widens_or_narrows_what_plan_selected(self):
        selected = self.build("a", "b", "c")
        allowed = self.rp.cacheable(selected, set(), set())
        self.assertEqual(allowed, ["a", "b", "c"])

    def test_a_changed_recipe_is_not_served_from_cache(self):
        """The author of an edit is owed a real build."""
        allowed = self.rp.cacheable(self.build("a", "b"), {"b"}, set())
        self.assertEqual(allowed, ["a"])

    def test_a_stale_package_is_not_served_from_cache(self):
        """Its recipe may not have moved, so its key can hit.

        A stale published package requires a soname nothing provides any more.
        Serving it from cache hands back the broken build and defeats the repair
        the run exists to perform -- the one case where a hit is worse than a
        miss.
        """
        allowed = self.rp.cacheable(self.build("a", "b"), set(), {"b"})
        self.assertEqual(allowed, ["a"])

    def test_both_exclusions_apply_together(self):
        allowed = self.rp.cacheable(self.build("a", "b", "c"), {"b"}, {"c"})
        self.assertEqual(allowed, ["a"])

    def test_it_returns_names_in_inventory_order(self):
        # The build list is in inventory order and stays that way, so the
        # workflow can zip it against the stage lists without re-sorting.
        selected = self.build("zeta", "alpha", "mu")
        self.assertEqual(
            self.rp.cacheable(selected, set(), set()), ["zeta", "alpha", "mu"]
        )

class TagIsTheKeyTests(unittest.TestCase):
    """The tag is the key, which is why there is nothing to validate.

    An earlier revision prefixed the package name for legibility. It was removed:
    the prefix added no uniqueness (the name is inside the hash, asserted below)
    and introduced a failure mode the bare key cannot have -- RPM names are laxer
    than OCI tags, so `gtk+` would have produced a mangled tag and a permanent
    miss. A hex digest is unconditionally a valid tag.
    """

    OCI_TAG = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$")

    def test_a_key_is_always_a_valid_oci_tag(self):
        for i in range(2000):
            key = pck.cache_key(**dict(BASE, recipe=f"recipe-{i}"))
            with self.subTest(i=i):
                self.assertRegex(key, r"^[0-9a-f]{32}$")
                self.assertTrue(self.OCI_TAG.match(key))

    def test_the_hash_binds_the_package_so_no_prefix_is_needed(self):
        """The property the removed prefix was mistakenly credited with."""
        keys = {
            name: pck.cache_key(**dict(BASE, package=name))
            for name in ("nautilus", "webkitgtk", "gtk4", "bluez")
        }
        self.assertEqual(len(set(keys.values())), len(keys))

    def test_a_package_name_a_tag_could_not_carry_is_now_harmless(self):
        """gtk+ was the case the prefix would have broken on."""
        key = pck.cache_key(**dict(BASE, package="gtk+"))
        self.assertRegex(key, r"^[0-9a-f]{32}$")
        self.assertTrue(self.OCI_TAG.match(key))


if __name__ == "__main__":
    unittest.main()
