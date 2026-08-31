#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.capture_buildroot import nevra, query_rpms


class CaptureBuildrootTests(unittest.TestCase):
    def test_nevra_with_epoch(self) -> None:
        record = {"name": "openssl-libs", "epoch": "1", "version": "3.5.7", "release": "2.fc44", "arch": "x86_64"}
        self.assertEqual(nevra(record), "1:openssl-libs-3.5.7-2.fc44.x86_64")

    def test_nevra_without_epoch(self) -> None:
        record = {"name": "glibc", "epoch": "0", "version": "2.42", "release": "1.fc44", "arch": "x86_64"}
        self.assertEqual(nevra(record), "glibc-2.42-1.fc44.x86_64")

    def test_nevra_none_epoch(self) -> None:
        record = {"name": "bash", "epoch": "0", "version": "5.3", "release": "1.fc44", "arch": "x86_64"}
        self.assertEqual(nevra(record), "bash-5.3-1.fc44.x86_64")


class EmitManifestTests(unittest.TestCase):
    def test_collect_rpms_excludes_source_rpms(self) -> None:
        from tools.emit_manifest import collect_rpms
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg" / "foo-1.0-1.x86_64.rpm").write_bytes(b"")
            (root / "pkg" / "foo-1.0-1.src.rpm").write_bytes(b"")
            # Mock rpm -qp since we do not have real RPM files
            with patch("tools.emit_manifest.subprocess.check_output", return_value="foo-1.0-1.x86_64"):
                with patch("tools.emit_manifest.sha256_file", return_value="abc123"):
                    with patch.object(Path, "stat", lambda self: unittest.mock.Mock(st_size=0)):
                        result = collect_rpms(root)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["nevra"], "foo-1.0-1.x86_64")


if __name__ == "__main__":
    unittest.main()
