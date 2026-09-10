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
        late = (
            lanes["stage0_late"]["packages"]
            + lanes["stage0_late_b"]["packages"]
            + lanes["stage0_late_c"]["packages"]
        )

        # abseil-cpp is rebuilt in the stage-0 fast lane, so its one consumer
        # here has to be in the late lane rather than beside it.
        self.assertEqual(stages["abseil-cpp"], 0)
        self.assertNotIn("abseil-cpp", late)
        self.assertEqual(stages["webrtc-audio-processing"], 0)
        self.assertIn("webrtc-audio-processing", late)
        self.assertIn("webrtc-audio-processing", lanes["stage0_late_b"]["packages"])
        self.assertIn("gstreamer1-plugins-good", lanes["stage0_late_c"]["packages"])

        self.assertLess(stages["webrtc-audio-processing"], stages["pipewire"])
        self.assertLess(stages["pipewire"], stages["xdg-desktop-portal"])

    def test_malcontent_cycle_builds_bootstrap_flatpak_then_full_malcontent(self):
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        stages = {item["name"]: item.get("stage", 0) for item in manifest["packages"]}
        lanes = tomllib.loads((ROOT / "config/build-lanes.toml").read_text())
        stage3_late = lanes["stage3_late"]["packages"]

        # The UI-less provider must be available to Flatpak, and Flatpak must
        # be available before the full malcontent build reaches stage 4.
        self.assertEqual(stages["malcontent-bootstrap"], 3)
        self.assertEqual(stages["flatpak"], 3)
        self.assertEqual(stages["malcontent"], 4)
        self.assertNotIn("malcontent-bootstrap", stage3_late)
        self.assertIn("flatpak", stage3_late)
        self.assertNotIn("malcontent", stage3_late)

    def test_every_late_lane_entry_names_why_it_is_late(self):
        """A late entry links something the fast lane rebuilds.

        The lane is not a scheduling preference: an entry here resolves a
        dependency the factory has just replaced, and the pairing is what
        makes it late. Pin each pair so removing the provider from stage 0
        does not quietly leave its consumer waiting for nothing.
        """
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        stages = {item["name"]: item.get("stage", 0) for item in manifest["packages"]}
        late = tomllib.loads((ROOT / "config/build-lanes.toml").read_text())
        first = late["stage0_late"]["packages"]
        second = late["stage0_late_b"]["packages"]
        third = late["stage0_late_c"]["packages"]
        late = first + second + third

        # consumer -> the stage-0 package whose rebuild it has to see. A
        # provider may itself be a late entry (libtevent, samba): then it
        # must sit in an earlier lane than its consumer, not merely stage 0.
        reasons = {
            "ffmpeg": ["libvpx", "openapv", "samba"],
            "gstreamer1-plugins-good": ["libvpx"],
            "libheif": ["openjph"],
            "liblrdf": ["raptor2"],
            "libtevent": ["libtalloc"],
            "samba": ["libtevent"],
            "webrtc-audio-processing": ["abseil-cpp"],
            "xorg-x11-server-Xwayland": ["wayland"],
        }
        self.assertEqual(sorted(late), sorted(reasons))
        self.assertEqual(sorted(first), ["libheif", "liblrdf", "libtevent"])
        self.assertEqual(sorted(second), ["samba", "webrtc-audio-processing"])
        self.assertIn("gstreamer1-plugins-good", third)
        lane_index = {name: 0 for name in first}
        lane_index.update({name: 1 for name in second})
        lane_index.update({name: 2 for name in third})
        for consumer, providers in reasons.items():
            for provider in providers:
                self.assertEqual(stages[provider], 0, provider)
                if provider in late:
                    self.assertLess(
                        lane_index[provider], lane_index[consumer],
                        f"{provider} must build in a lane before {consumer}",
                    )
                else:
                    self.assertNotIn(provider, late, f"{provider} must stay in the fast lane")

    def test_samba_precedes_every_smbclient_consumer(self):
        """Fedora's samba-core-libs links libicu 77, which no build root
        installs any more, so libsmbclient-devel can only come from here."""
        manifest = json.loads((ROOT / "config/upstream-sources.json").read_text())
        stages = {item["name"]: item.get("stage", 0) for item in manifest["packages"]}
        self.assertEqual(stages["samba"], 0)
        self.assertLess(stages["samba"], stages["gvfs"])
        self.assertLess(stages["samba"], stages["gnome-control-center"])


if __name__ == "__main__":
    unittest.main()
