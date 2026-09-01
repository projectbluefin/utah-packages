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
            path = update(root)
            data = json.loads(path.read_text())
            self.assertIn("old", data["packages"])
            self.assertNotIn("bad", data["packages"])


if __name__ == "__main__":
    unittest.main()
