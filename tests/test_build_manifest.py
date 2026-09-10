import json
import tempfile
import unittest
from pathlib import Path

from tools.build_manifest import update


class BuildManifestTests(unittest.TestCase):
    def test_merges_only_complete_package_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "old.build-key.json").write_text(
                json.dumps({"package": "old", "build_key": "sha256:old", "outputs": [{"file": "old.rpm"}]})
            )
            (root / "incomplete.build-key.json").write_text(
                json.dumps({"package": "bad", "build_key": "sha256:bad", "outputs": []})
            )
            (root / "linked.build-key.json").write_text(
                json.dumps({"package": "linked", "build_key": "sha256:linked",
                            "outputs": [{"file": "linked.rpm"}],
                            "build_deps": {"old": "sha256:old"}})
            )
            path = update(root)
            data = json.loads(path.read_text())
            self.assertIn("old", data["packages"])
            self.assertNotIn("bad", data["packages"])
            # The dependency record survives the merge; an old record without
            # one reads as having none rather than as malformed.
            self.assertEqual(data["packages"]["linked"]["build_deps"], {"old": "sha256:old"})
            # Absent stays absent: an old record must not be read as a
            # package that checked and found nothing upstream.
            self.assertNotIn("build_deps", data["packages"]["old"])


if __name__ == "__main__":
    unittest.main()
