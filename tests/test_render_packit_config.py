#!/usr/bin/env python3

from pathlib import Path
import unittest

from tools.render_packit_config import render

ROOT = Path(__file__).resolve().parent.parent


class RenderPackitConfigTests(unittest.TestCase):
    def test_rendered_config_matches_repository_file(self):
        self.assertEqual(render(ROOT), (ROOT / ".packit.yaml").read_text())
        self.assertEqual(render(ROOT).count("    specfile_path:"), 195)


if __name__ == "__main__":
    unittest.main()
