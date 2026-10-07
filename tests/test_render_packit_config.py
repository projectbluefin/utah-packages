#!/usr/bin/env python3

from pathlib import Path
import unittest

from tools.render_packit_config import render

ROOT = Path(__file__).resolve().parent.parent


class RenderPackitConfigTests(unittest.TestCase):
    def test_rendered_config_matches_repository_file(self):
        rendered = render(ROOT)
        # The line count matches the package count by construction: one entry
        # per record the inventory returns, which the agreement gate keeps
        # in sync with the source lock.
        expected = rendered.count("    specfile_path:")
        self.assertEqual(rendered, (ROOT / ".packit.yaml").read_text())
        self.assertEqual(
            sum(1 for path in (ROOT / "packages").iterdir() if path.is_dir()),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
