"""Untrusted import artifacts must never replace trusted tools or existing locks."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.import_proposal import restore


class ImportProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "root"
        self.incoming = Path(self.tmp.name) / "incoming"
        (self.root / "config").mkdir(parents=True)
        (self.root / "packages").mkdir()
        self.lock = self.root / "config/upstream-sources.json"
        self.existing = {"schema": 1, "packages": [{"name": "existing", "version": "1"}]}
        self.lock.write_text(json.dumps(self.existing))
        self.recipe = self.incoming / "packages/demo"
        self.recipe.mkdir(parents=True)
        (self.recipe / "demo.spec").write_text("Name: demo\nVersion: 1\n")
        (self.recipe / ".hummingbird-upstream.json").write_text(json.dumps({"package": "demo"}))
        self.candidate = self.incoming / "candidate.json"
        self.candidate.write_text(json.dumps({"schema": 1, "packages": [{"name": "demo", "version": "1"}]}))
        (self.incoming / "report.json").write_text(json.dumps({"accepted": 1, "rejected": []}))

    def test_accepts_one_new_recipe_without_changing_existing_locks(self):
        restore(self.root, self.incoming, "demo")
        self.assertEqual(json.loads(self.lock.read_text())["packages"][0], self.existing["packages"][0])
        self.assertTrue((self.root / "packages/demo/demo.spec").is_file())

    def test_rejects_host_script_in_artifact(self):
        (self.incoming / "tools").mkdir()
        with self.assertRaises(ValueError):
            restore(self.root, self.incoming, "demo")
        self.assertFalse((self.root / "packages/demo").exists())

    def test_rejects_recipe_symlink_before_any_write(self):
        (self.recipe / "escape").symlink_to(self.lock)
        with self.assertRaises(ValueError):
            restore(self.root, self.incoming, "demo")
        self.assertEqual(json.loads(self.lock.read_text()), self.existing)

    def test_rejects_candidate_for_another_package(self):
        self.candidate.write_text(json.dumps(self.existing))
        with self.assertRaises(ValueError):
            restore(self.root, self.incoming, "demo")

    def test_rejects_replacing_an_existing_recipe(self):
        (self.root / "packages/demo").mkdir()
        with self.assertRaises(ValueError):
            restore(self.root, self.incoming, "demo")
        self.assertEqual(json.loads(self.lock.read_text()), self.existing)
