import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class BuildLaneTests(unittest.TestCase):
    def test_lane_overrides_are_disjoint_and_configured(self):
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        names = {item["name"] for item in manifest["packages"]}
        lanes = tomllib.loads((ROOT / "config/build-lanes.toml").read_text())
        listed = [name for lane in lanes.values() for name in lane["packages"]]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertTrue(set(listed) <= names)

    def test_late_closures_have_their_required_internal_inputs(self):
        requirements = {}
        for spec in (ROOT / "packages").glob("*/*.spec"):
            text = spec.read_text(errors="replace")
            requirements[spec.parent.name] = set(
                re.findall(r"^BuildRequires:\s+(?:pkgconfig\()?([a-zA-Z0-9_.+-]+)", text, re.MULTILINE)
            )
        self.assertIn("mozjs-140", requirements["gjs"])
        self.assertIn("gtk4", requirements["webkitgtk"])
        self.assertIn("webkit2gtk-4.1", requirements["evolution-data-server"])
        self.assertIn("gjs-1.0", requirements["gnome-shell"])
        self.assertIn("libedataserver-1.2", requirements["gnome-shell"])


if __name__ == "__main__":
    unittest.main()
