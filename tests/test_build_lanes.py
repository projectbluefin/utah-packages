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

    def test_the_webrtc_chain_builds_one_wave_at_a_time(self):
        """abseil -> webrtc-audio-processing -> pipewire -> xdg-desktop-portal.

        Every link is a BuildRequires, and each one used to sit in the same
        wave as the thing it links, so it resolved against the build root's
        copy instead of the one the factory had just rebuilt.
        """
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        stages = {item["name"]: item.get("stage", 0) for item in manifest["packages"]}
        lanes = tomllib.loads((ROOT / "config/build-lanes.toml").read_text())
        late = lanes["stage0_late"]["packages"]

        # abseil-cpp is rebuilt in the stage-0 fast lane, so its one consumer
        # here has to be in the late lane rather than beside it.
        self.assertEqual(stages["abseil-cpp"], 0)
        self.assertNotIn("abseil-cpp", late)
        self.assertEqual(stages["webrtc-audio-processing"], 0)
        self.assertIn("webrtc-audio-processing", late)

        self.assertLess(stages["webrtc-audio-processing"], stages["pipewire"])
        self.assertLess(stages["pipewire"], stages["xdg-desktop-portal"])


if __name__ == "__main__":
    unittest.main()
