#!/usr/bin/env python3

import json
from pathlib import Path
import tomllib
import unittest

from tools.validate_multimedia_closure import validate


ROOT = Path(__file__).resolve().parent.parent


class MultimediaClosureTests(unittest.TestCase):
    def setUp(self):
        self.manifest = tomllib.loads((ROOT / "config" / "bluefin-packages.toml").read_text())
        self.locks = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        self.report = json.loads((ROOT / "reports" / "bluefin-multimedia-closure.json").read_text())

    def test_committed_report_matches_factory_contract(self):
        self.assertEqual(validate(self.manifest, self.locks, self.report), [])

    def test_missing_requirement_is_rejected(self):
        report = json.loads(json.dumps(self.report))
        report["requirements"].pop()
        errors = validate(self.manifest, self.locks, report)
        self.assertTrue(any("do not match multimedia_overrides" in error for error in errors))

    def test_unlocked_source_is_rejected(self):
        report = json.loads(json.dumps(self.report))
        report["requirements"][0]["factory_source"] = "not-locked"
        errors = validate(self.manifest, self.locks, report)
        self.assertTrue(any("unlocked factory source" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
