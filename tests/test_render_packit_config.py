#!/usr/bin/env python3

from pathlib import Path
import unittest

from tools.render_packit_config import render
from tools.package_inventory import inventory

ROOT = Path(__file__).resolve().parent.parent


class RenderPackitConfigTests(unittest.TestCase):
    def test_rendered_config_matches_repository_file(self):
        self.assertEqual(render(ROOT), (ROOT / ".packit.yaml").read_text())
        self.assertEqual(render(ROOT).count("    specfile_path:"), len(inventory(ROOT)))


if __name__ == "__main__":
    unittest.main()
