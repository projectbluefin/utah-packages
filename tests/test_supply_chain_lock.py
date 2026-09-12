#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path

from tools.buildroot_lock import compare, load_lock
from tools.factory_manifest import main as manifest_main


class BuildrootLockTests(unittest.TestCase):
    def test_compare_detects_missing_and_unexpected_packages(self):
        expected = [{"nevra": "glibc-2.41-1.fc44.x86_64"}, {"nevra": "openssl-libs-3.5.7-1.hum1.x86_64"}]
        actual = [{"nevra": "glibc-2.41-1.fc44.x86_64"}, {"nevra": "bash-5.2-1.fc44.x86_64"}]
        errors = compare(expected, actual)
        self.assertTrue(any("missing locked buildroot packages" in e for e in errors))
        self.assertTrue(any("unexpected buildroot packages" in e for e in errors))

    def test_load_lock_requires_digest_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps({
                "schema": 1,
                "buildroots": {
                    "bad": {"image": "quay.io/fedora/fedora:44", "packages": []}
                }
            }))
            with self.assertRaises(ValueError):
                load_lock(lock)


class FactoryManifestTests(unittest.TestCase):
    def test_manifest_aggregates_sources_buildroots_and_oci(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            (repo / "reports").mkdir(parents=True)
            (repo / "x86_64").mkdir(parents=True)
            (repo / "x86_64" / "demo-1.0-1.hum1.bfin.x86_64.rpm").write_bytes(b"rpm")
            (repo / "reports" / "demo.json").write_text(json.dumps({"package": "demo", "result": "accepted", "verification": "sha512", "checksum_only": True}))
            (repo / "reports" / "buildroot-demo.json").write_text(json.dumps({"name": "fedora-44", "packages": [{"nevra": "glibc-2.41.x86_64"}]}))
            lock = root / "lock.json"
            lock.write_text(json.dumps({"schema": 1, "buildroots": {"fedora-44": {"image": "quay.io/fedora/fedora:44@sha256:abc", "packages": []}}}))
            out = root / "manifest.json"
            rc = manifest_main([
                "--repository", str(repo),
                "--build-list", '["demo"]',
                "--buildroot-lock", str(lock),
                "--output", str(out),
                "--oci-ref", "ghcr.io/demo/utah-packages:latest",
                "--oci-digest", "sha256:123456",
            ])
            self.assertEqual(rc, 0)
            data = json.loads(out.read_text())
            self.assertEqual(data["schema"], 1)
            self.assertEqual(data["requested_packages"], ["demo"])
            self.assertEqual(data["packages"], ["x86_64/demo-1.0-1.hum1.bfin.x86_64.rpm"])
            self.assertEqual(data["oci"]["digest"], "sha256:123456")
            self.assertEqual(len(data["sources"]), 2)
            self.assertEqual(len(data["buildroots"]), 1)


if __name__ == "__main__":
    unittest.main()
