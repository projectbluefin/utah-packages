import json
import tempfile
import unittest
from pathlib import Path

from tools.build_identity import identity


class BuildIdentityTests(unittest.TestCase):
    def test_identity_is_stable_for_unchanged_inputs(self):
        first = identity("webrtc-audio-processing")
        second = identity("webrtc-audio-processing")
        self.assertEqual(first["build_key"], second["build_key"])
        self.assertTrue(str(first["build_key"]).startswith("sha256:"))

    def test_recipe_change_changes_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            (root / "tools").mkdir()
            (root / "tools" / "build-rpm.sh").write_text("build\n")
            (root / "tools" / "build-package.sh").write_text("driver\n")
            (root / "packages" / "demo").mkdir(parents=True)
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [{"name": "demo", "version": "1", "sha512": "a"}]})
            )
            (root / "config" / "runtime-contract.toml").write_text(
                '[base]\nimage = "example/os@sha256:' + "a" * 64 + '"\n'
            )
            (root / "config" / "hummingbird.repo").write_text("[hummingbird]\n")
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "actions" / "setup-sccache").mkdir(parents=True)
            (root / ".github" / "workflows" / "rebuild-lane.yml").write_text("lane\n")
            (root / ".github" / "actions" / "setup-sccache" / "action.yml").write_text("cache\n")
            recipe = root / "packages" / "demo" / "demo.spec"
            recipe.write_text("Version: 1\n")
            first = identity("demo", root)
            recipe.write_text("Version: 2\n")
            second = identity("demo", root)
            self.assertNotEqual(first["build_key"], second["build_key"])

    def test_factory_machinery_is_not_a_package_input(self):
        """A build script, workflow or manifest edit must not rebuild the world.

        Only the package's own source entry, its recipe tree and the base
        image are hashed. Everything else about how the factory builds is
        either irrelevant to the RPM or covered by `full`.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            (root / "tools").mkdir()
            (root / "tools" / "build-rpm.sh").write_text("build\n")
            (root / "packages" / "demo").mkdir(parents=True)
            (root / "packages" / "other").mkdir(parents=True)
            (root / "packages" / "demo" / "demo.spec").write_text("Version: 1\n")
            (root / "packages" / "other" / "other.spec").write_text("Version: 1\n")
            manifest = {"packages": [
                {"name": "demo", "version": "1", "sha512": "a"},
                {"name": "other", "version": "1", "sha512": "b"},
            ]}
            (root / "config" / "upstream-sources.json").write_text(json.dumps(manifest))
            (root / "config" / "runtime-contract.toml").write_text(
                '[base]\nimage = "example/os@sha256:' + "a" * 64 + '"\n'
            )
            first = identity("demo", root)
            (root / "tools" / "build-rpm.sh").write_text("changed build user\n")
            manifest["packages"][1]["stage"] = 3
            (root / "config" / "upstream-sources.json").write_text(json.dumps(manifest))
            second = identity("demo", root)
            self.assertEqual(first["build_key"], second["build_key"])
            manifest["packages"][0]["stage"] = 1
            (root / "config" / "upstream-sources.json").write_text(json.dumps(manifest))
            third = identity("demo", root)
            self.assertNotEqual(second["build_key"], third["build_key"], "own stage is an input")

    @staticmethod
    def _root(temporary):
        root = Path(temporary)
        (root / "config").mkdir()
        (root / "packages" / "demo").mkdir(parents=True)
        (root / "packages" / "demo" / "demo.spec").write_text("Version: 1\n")
        (root / "config" / "upstream-sources.json").write_text(
            json.dumps({"packages": [{"name": "demo", "version": "1", "sha512": "a"}]})
        )
        (root / "config" / "runtime-contract.toml").write_text(
            '[base]\nimage = "example/os@sha256:' + "a" * 64 + '"\n'
        )
        return root

    def test_a_build_with_no_listing_records_no_dependency_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            self.assertNotIn("build_deps", identity("demo", root))

    def test_an_empty_listing_records_an_empty_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            deps = root / "build-deps.txt"
            deps.write_text("")
            self.assertEqual(identity("demo", root, deps_file=deps)["build_deps"], {})

    def test_build_deps_map_installed_rpms_back_to_their_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            prior = root / "prior"
            prior.mkdir()
            (prior / "factory-build-manifest.json").write_text(json.dumps({"packages": {
                "libfoo": {"build_key": "sha256:old", "outputs": [
                    {"file": "x86_64/libfoo-1-1.hum1.bfin.x86_64.rpm"}]},
                "libbar": {"build_key": "sha256:bar", "outputs": [
                    {"file": "x86_64/libbar-2-1.hum1.bfin.x86_64.rpm"},
                    {"file": "x86_64/libbar-devel-2-1.hum1.bfin.x86_64.rpm"}]},
            }}))
            # An earlier lane of the same run supersedes the accumulator's copy.
            (prior / "libfoo.build-key.json").write_text(json.dumps({
                "package": "libfoo", "build_key": "sha256:new",
                "outputs": [{"file": "x86_64/libfoo-1-1.hum1.bfin.x86_64.rpm"}]}))
            deps = root / "build-deps.txt"
            deps.write_text(
                "libfoo-1-1.hum1.bfin.x86_64.rpm\n"
                "libbar-2-1.hum1.bfin.x86_64.rpm\n"
                "libbar-devel-2-1.hum1.bfin.x86_64.rpm\n"
                "stray-9-9.hum1.bfin.x86_64.rpm\n"
            )
            result = identity("demo", root, deps_file=deps, prior_dir=prior)
            # Two subpackages of libbar collapse to one entry; the unclaimed
            # basename is dropped rather than recorded as an uncomparable dep.
            self.assertEqual(
                result["build_deps"], {"libbar": "sha256:bar", "libfoo": "sha256:new"}
            )

    def test_shards_of_one_recipe_are_told_apart(self):
        """webkitgtk and webkit2gtk4.1 share a recipe and a %{SOURCERPM}.

        A source-name lookup answers with whichever it finds first, which is
        a wrong dependency record rather than a missing one. Their binaries
        never collide, so the recorded outputs separate them exactly.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            prior = root / "prior"
            prior.mkdir()
            (prior / "factory-build-manifest.json").write_text(json.dumps({"packages": {
                "webkitgtk": {"build_key": "sha256:gtk4", "outputs": [
                    {"file": "x86_64/javascriptcoregtk6.0-2.53.91-1.hum1.bfin.x86_64.rpm"}]},
                "webkit2gtk4.1": {"build_key": "sha256:gtk3", "outputs": [
                    {"file": "x86_64/javascriptcoregtk4.1-2.53.91-1.hum1.bfin.x86_64.rpm"}]},
                "malcontent": {"build_key": "sha256:full", "outputs": [
                    {"file": "x86_64/malcontent-0.14.0-1.hum1.bfin.x86_64.rpm"}]},
                "malcontent-bootstrap": {"build_key": "sha256:boot", "outputs": [
                    {"file": "x86_64/malcontent-0.14.0-0.bootstrap.hum1.bfin.x86_64.rpm"}]},
            }}))
            deps = root / "build-deps.txt"
            deps.write_text(
                "javascriptcoregtk4.1-2.53.91-1.hum1.bfin.x86_64.rpm\n"
                "malcontent-0.14.0-0.bootstrap.hum1.bfin.x86_64.rpm\n"
            )
            result = identity("demo", root, deps_file=deps, prior_dir=prior)
            self.assertEqual(result["build_deps"], {
                "malcontent-bootstrap": "sha256:boot",
                "webkit2gtk4.1": "sha256:gtk3",
            })


if __name__ == "__main__":
    unittest.main()
