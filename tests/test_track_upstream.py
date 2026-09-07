import unittest

from tools import track_upstream


SHA = "ab56199345fdc385e62e414ec200c10777c985fb2bde767f9c76e049f47bc6d2ae83ed12d60dc1ebe0e66f22f7a7e554c13ab13837fb8cb2fbd5481149b07654"
OTHER = "0" * 128


class ParseSourcesTests(unittest.TestCase):
    def test_reads_filename_and_digest(self):
        text = f"SHA512 (wireguard-tools-1.0.20260223.tar.xz) = {SHA}\n"
        self.assertEqual(
            track_upstream.parse_sources(text),
            [("wireguard-tools-1.0.20260223.tar.xz", SHA)],
        )

    def test_ignores_other_lines_and_algorithms(self):
        text = f"MD5 (x.tar.gz) = {'0'*32}\n\n# comment\nSHA512 (y.tar.xz) = {OTHER}\n"
        self.assertEqual(track_upstream.parse_sources(text), [("y.tar.xz", OTHER)])


class ClassifyTests(unittest.TestCase):
    FILENAME = "wireguard-tools-1.0.20260223.tar.xz"

    def state(self, version="1.0.20260223", sources=None):
        return {
            "package": "wireguard-tools",
            "version": version,
            "nvr": f"wireguard-tools-{version}-2.fc45",
            "sources": sources if sources is not None else [(self.FILENAME, SHA)],
        }

    def entry(self, **overrides):
        base = {
            "name": "wireguard-tools",
            "version": "1.0.20260223",
            "filename": self.FILENAME,
            "sha512": SHA,
            "url": track_upstream.lookaside_url("wireguard-tools", self.FILENAME, SHA),
        }
        base.update(overrides)
        return base

    def test_entry_already_tracking_the_lookaside_is_not_flagged(self):
        self.assertIsNone(classify_or_none := track_upstream.classify(self.entry(), self.state()))

    def test_upstream_host_is_flagged_as_location_drift(self):
        # The real wireguard-tools case: right version, right bytes, but fetched
        # from a snapshot endpoint that 404s once the tag moves.
        entry = self.entry(url="https://git.zx2c4.com/wireguard-tools/snapshot/"
                               + self.FILENAME)
        found = track_upstream.classify(entry, self.state())
        self.assertIsNotNone(found)
        self.assertIn("source is not the Fedora lookaside", found["reasons"])
        self.assertNotIn("version", " ".join(found["reasons"]))
        self.assertEqual(found["proposed"]["sha512"], SHA)
        self.assertTrue(found["proposed"]["url"].startswith(
            "https://src.fedoraproject.org/repo/pkgs/rpms/wireguard-tools/"))

    def test_version_drift_is_flagged(self):
        entry = self.entry(version="1.0.20250101")
        found = track_upstream.classify(entry, self.state())
        self.assertTrue(any(r.startswith("version ") for r in found["reasons"]))

    def test_a_shard_uses_its_dist_git_name_for_the_lookaside(self):
        entry = self.entry(name="webkit2gtk4.1", dist_git_name="webkitgtk",
                           url="https://example.invalid/x.tar.xz")
        found = track_upstream.classify(entry, self.state())
        self.assertEqual(found["dist_git"], "webkitgtk")
        self.assertIn("/rpms/webkitgtk/", found["proposed"]["url"])

    def test_no_matching_source_returns_nothing(self):
        found = track_upstream.classify(
            self.entry(filename="unrelated.tar.gz"),
            self.state(sources=[("a.tar.gz", SHA), ("b.tar.gz", OTHER)]),
        )
        self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()
