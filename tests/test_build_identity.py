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


if __name__ == "__main__":
    unittest.main()
