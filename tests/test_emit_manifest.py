#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class CollectBuildrootLocksTests(unittest.TestCase):
    def test_collects_preflight_and_per_package_locks(self) -> None:
        from tools.emit_manifest import collect_buildroot_locks
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            (report_dir / "buildroot-lock-preflight.json").write_text(
                json.dumps({"image_ref": "preflight-image", "package_count": 10})
            )
            (report_dir / "buildroot-udev.json").write_text(
                json.dumps({"image_ref": "udev-image", "package_count": 20})
            )
            (report_dir / "buildroot-firefox.json").write_text(
                json.dumps({"image_ref": "firefox-image", "package_count": 30})
            )
            result = collect_buildroot_locks(report_dir)
            self.assertIn("preflight", result)
            self.assertIn("udev", result)
            self.assertIn("firefox", result)
            self.assertEqual(result["preflight"]["image_ref"], "preflight-image")

    def test_returns_empty_dict_when_no_locks(self) -> None:
        from tools.emit_manifest import collect_buildroot_locks
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_buildroot_locks(Path(tmpdir))
            self.assertEqual(result, {})


class CollectSourceReportsTests(unittest.TestCase):
    def test_collects_source_reports_excluding_special_files(self) -> None:
        from tools.emit_manifest import collect_source_reports
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            (report_dir / "udev.json").write_text(json.dumps({
                "package": "udev", "sha512": "abc", "resolved_url": "https://example.com/udev.tar.gz",
                "signature_verified": {"verified": True},
                "sha256_url": "https://example.com/SHA256",
            }))
            (report_dir / "firefox.json").write_text(json.dumps({
                "package": "firefox", "sha512": "def", "resolved_url": "https://example.com/firefox.tar.gz",
            }))
            (report_dir / "buildroot-udev.json").write_text(
                json.dumps({"should": "be skipped"})
            )
            (report_dir / "signature-report.json").write_text(
                json.dumps({"should": "be skipped"})
            )
            (report_dir / "manifest.json").write_text(
                json.dumps({"should": "be skipped"})
            )
            result = collect_source_reports(report_dir)
            self.assertEqual(len(result), 2)
            packages = {r["package"] for r in result}
            self.assertEqual(packages, {"udev", "firefox"})

    def test_skips_invalid_json(self) -> None:
        from tools.emit_manifest import collect_source_reports
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            (report_dir / "bad.json").write_text("not json{")
            (report_dir / "good.json").write_text(json.dumps({
                "package": "good", "sha512": "abc", "resolved_url": "https://example.com/good.tar.gz",
            }))
            result = collect_source_reports(report_dir)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["package"], "good")


class CollectSignatureReportTests(unittest.TestCase):
    def test_returns_none_when_report_missing(self) -> None:
        from tools.emit_manifest import collect_signature_report
        with tempfile.TemporaryDirectory() as tmpdir:
            result = collect_signature_report(Path(tmpdir))
            self.assertIsNone(result)

    def test_returns_report_when_present(self) -> None:
        from tools.emit_manifest import collect_signature_report
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            data = {"summary": "all verified", "packages": {}}
            (report_dir / "signature-report.json").write_text(json.dumps(data))
            result = collect_signature_report(report_dir)
            self.assertEqual(result, data)


class ManifestStructureTests(unittest.TestCase):
    def test_manifest_includes_all_sections(self) -> None:
        from tools.emit_manifest import main
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = root / "config"
            config.mkdir()
            (config / "buildroot-lock.json").write_text(json.dumps({
                "schema": 1,
                "image": {"pinned": "sha256:aaa"},
                "release": "44",
            }))
            report_dir = root / "reports"
            report_dir.mkdir()
            (report_dir / "udev.json").write_text(json.dumps({
                "package": "udev", "sha512": "abc", "resolved_url": "https://example.com/udev.tar.gz",
                "signature_verified": {"verified": True},
                "sha256_url": "https://example.com/SHA256",
            }))
            (report_dir / "buildroot-lock-preflight.json").write_text(
                json.dumps({"image_ref": "img1", "package_count": 10, "nevras": ["glibc-2.42-1.fc44.x86_64"]})
            )
            (report_dir / "signature-report.json").write_text(json.dumps({
                "summary": "verified", "packages": {}
            }))
            package_dir = root / "rpms"
            package_dir.mkdir()
            output = root / "manifest.json"
            with patch("sys.argv", [
                "emit_manifest.py",
                "--buildroot-lock", str(config / "buildroot-lock.json"),
                "--package-dir", str(package_dir),
                "--report-dir", str(report_dir),
                "--output", str(output),
                "--oci-digest", "sha256:digest123",
            ]):
                with patch("tools.emit_manifest.subprocess.check_output", return_value="udev-260-1.fc44.x86_64"):
                    with patch("tools.emit_manifest.sha256_file", return_value="deadbeef"):
                        with patch.object(Path, "stat", lambda self: type("MockStat", (), {"st_size": 1000})()):
                            ret = main()
            self.assertEqual(ret, 0)
            manifest = json.loads(output.read_text())
            self.assertEqual(manifest["schema"], 1)
            self.assertEqual(manifest["oci"]["digest"], "sha256:digest123")
            self.assertEqual(manifest["buildroot"]["release"], "44")
            self.assertIn("preflight", manifest["buildroot"]["neura_snapshots"])
            self.assertIn("udev", manifest["sources"])
            self.assertEqual(manifest["signature_provenance"]["summary"], "verified")
            self.assertEqual(manifest["packages"]["total"], 0)

    def test_manifest_handles_missing_buildroot_lock(self) -> None:
        from tools.emit_manifest import main
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_dir = root / "rpms"
            package_dir.mkdir()
            report_dir = root / "reports"
            report_dir.mkdir()
            output = root / "manifest.json"
            with patch("sys.argv", [
                "emit_manifest.py",
                "--buildroot-lock", str(root / "nonexistent-lock.json"),
                "--package-dir", str(package_dir),
                "--report-dir", str(report_dir),
                "--output", str(output),
            ]):
                ret = main()
            self.assertEqual(ret, 0)
            manifest = json.loads(output.read_text())
            self.assertEqual(manifest["buildroot"]["image"], {})


if __name__ == "__main__":
    unittest.main()
