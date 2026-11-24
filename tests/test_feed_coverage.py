#!/usr/bin/env python3
"""The daily bump can see releases for locks that had no feed (#1189).

A lock with no forge URL, no GNOME module and no explicit feed is skipped by
candidates(), so the daily scan cannot see an upstream release for it. This
batch gives such locks Anitya feeds from Fedora's own project mapping, kept
only where the project's current version equals the lock's version and the
lock has a primary URL to move.
"""

from pathlib import Path
import unittest

from tools import upstream_bump
from tools.package_inventory import source_locks

ROOT = Path(__file__).resolve().parent.parent

# Anitya projects whose version matched the lock when the feed was added.
FED = ('SDL3_net', 'adcli', 'argyllcms', 'b43-fwcutter', 'bc', 'bcache-tools', 'bindfs', 'bison', 'brltty', 'cifs-utils', 'davfs2', 'djvulibre', 'dnsmasq', 'dtc', 'erofs-utils', 'fcitx5-gtk', 'fxload', 'gnu-free-fonts', 'gutenprint', 'hdparm', 'ibus-chewing', 'ibus-libpinyin', 'ipset', 'iwd', 'kyotocabinet', 'lcms', 'libXScrnSaver', 'libXaw', 'libavc1394', 'libbsd', 'libcacard', 'libchewing', 'libdc1394', 'liberation-fonts', 'libev', 'libiec61883', 'libieee1284', 'libmd', 'libmpeg2', 'libntlm', 'libotf', 'libpfm', 'libpinyin', 'libraw1394', 'libssc', 'libudfread', 'libuser', 'libvirt', 'lilv', 'lzip', 'm17n-lib', 'mod_dnssd', 'nano', 'neon', 'nilfs-utils', 'oath-toolkit', 'ocl-icd', 'openconnect', 'opusfile', 'pam-u2f', 'pam_yubico', 'python-jaraco-classes', 'python-jaraco-functools', 'python-linux-procfs', 'python-llfuse', 'python-pskc', 'pyxdg', 'qemu', 'quota', 'realmd', 'rpcbind', 'sane-backends', 'serd', 'smartmontools', 'sord', 'speexdsp', 'spice', 'spice-protocol', 'spice-vdagent', 'sratom', 'strace', 'tiptop', 'trace-cmd', 'traceroute', 'uchardet', 'usbredir', 'usbutils', 'wget2', 'xcb-util-cursor')


class FeedCoverageTests(unittest.TestCase):
    def test_the_fed_locks_are_visible_to_the_daily_scan(self) -> None:
        tracked = {name for name, _, _ in upstream_bump.candidates(source_locks(ROOT))}
        for name in sorted(FED):
            with self.subTest(package=name):
                self.assertIn(name, tracked)

    def test_the_feeds_are_anitya_projects(self) -> None:
        locks = source_locks(ROOT)
        for name in sorted(FED):
            with self.subTest(package=name):
                feed = upstream_bump.parse_explicit_feed(locks[name]["feed"])
                self.assertEqual(feed, {"forge": "anitya", "id": feed["id"]})
                self.assertTrue(feed["id"].isdigit())


if __name__ == "__main__":
    unittest.main()
