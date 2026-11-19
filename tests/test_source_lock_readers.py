"""Read-only consumers of the source locks go through package_inventory.

``tools/package_inventory.py`` is the one parse of
``config/upstream-sources.json``: a duplicated package name, an unknown stage
or an unknown build lane is a contract violation for every reader. A tool that
re-parses the file with its own ``{entry["name"]: entry ...}`` comprehension
silently lets the last duplicate win instead. Each test here feeds a reader a
lock file with a duplicated name and expects the shared refusal.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import audit_dakota, audit_gnome_build_meta, package_index, rawhide_reimport

DUPLICATE = {
    "schema": 1,
    "packages": [
        {"name": "jpegxl", "version": "0.11", "url": "https://u/jxl-0.11.tar.gz"},
        {"name": "jpegxl", "version": "0.12", "url": "https://u/jxl-0.12.tar.gz"},
    ],
}


class DuplicateLockRefusedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "config").mkdir()
        self.lock = self.root / "config" / "upstream-sources.json"
        self.lock.write_text(json.dumps(DUPLICATE))
        (self.root / "packages").mkdir()

    def test_package_index_group(self) -> None:
        rpm = {
            "name": "jpegxl", "arch": "x86_64", "epoch": "0", "version": "0.11",
            "release": "1", "sourcerpm": "jpegxl-0.11-1.src.rpm", "summary": "",
            "description": "", "url": "", "license": "", "buildtime": 0,
            "size": 0, "installed": 0,
        }
        with self.assertRaisesRegex(ValueError, "duplicate source lock: jpegxl"):
            package_index.group([rpm], self.root, set())

    def test_rawhide_reimport_main(self) -> None:
        argv = ["rawhide_reimport.py", "--root", str(self.root)]
        with mock.patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "duplicate source lock: jpegxl"):
                rawhide_reimport.main()

    def test_audit_gnome_build_meta_main(self) -> None:
        gbm = self.root / "gbm"
        gbm.mkdir()
        argv = [
            "--gbm-dir", str(gbm), "--no-verify", "--sources", str(self.lock),
            "--packages-dir", str(self.root / "packages"),
            "--json-out", str(self.root / "out.json"),
            "--markdown-out", str(self.root / "out.md"),
        ]
        with mock.patch.object(audit_gnome_build_meta, "_aliases", return_value={}):
            with self.assertRaisesRegex(ValueError, "duplicate source lock: jpegxl"):
                audit_gnome_build_meta.main(argv)

    def test_audit_dakota_main(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        argv = [
            "--pin", str(repo / "config" / "dakota.json"),
            "--snapshot", str(repo / "config" / "dakota-elements.tsv"),
            "--sources", str(self.lock),
            "--packages-dir", str(self.root / "packages"),
            "--json-out", str(self.root / "out.json"),
            "--markdown-out", str(self.root / "out.md"),
        ]
        with self.assertRaisesRegex(ValueError, "duplicate source lock: jpegxl"):
            audit_dakota.main(argv)


if __name__ == "__main__":
    unittest.main()
