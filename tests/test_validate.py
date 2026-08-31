#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path


def _setup_factory(tmpdir: str) -> Path:
    """Create a minimal factory config + packages dir for testing."""
    root = Path(tmpdir)
    config = root / "config"
    packages = root / "packages"
    config.mkdir(parents=True, exist_ok=True)
    packages.mkdir(parents=True, exist_ok=True)
    return root


class BootstrapValidationTests(unittest.TestCase):
    def test_valid_bootstrap_passes(self) -> None:
        from tools.validate import validate_bootstrap_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text(
                "# header\nfuse\nntfs-3g\nudisks2\n"
            )
            result = validate_bootstrap_packages(root / "config")
            self.assertEqual(result, ["fuse", "ntfs-3g", "udisks2"])

    def test_empty_bootstrap_rejected(self) -> None:
        from tools.validate import validate_bootstrap_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text("# only comments\n")
            with self.assertRaises(SystemExit) as ctx:
                validate_bootstrap_packages(root / "config")
            self.assertIn("empty", str(ctx.exception))

    def test_duplicate_bootstrap_rejected(self) -> None:
        from tools.validate import validate_bootstrap_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text("fuse\nfuse\n")
            with self.assertRaises(SystemExit) as ctx:
                validate_bootstrap_packages(root / "config")
            self.assertIn("duplicates", str(ctx.exception))

    def test_invalid_names_rejected(self) -> None:
        from tools.validate import validate_bootstrap_packages
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text("bad name\n")
            with self.assertRaises(SystemExit) as ctx:
                validate_bootstrap_packages(root / "config")
            self.assertIn("source RPM names", str(ctx.exception))


class HummingbirdUpstreamTests(unittest.TestCase):
    def test_valid_rawhide_import(self) -> None:
        from tools.validate import validate_hummingbird_upstream
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / ".hummingbird-upstream.json").write_text(json.dumps({
                "package": "test", "branch": "rawhide", "remote": "https://example.com",
                "commit": "abc123", "tree": "def456", "imported_at": "2026-01-01T00:00:00Z",
            }))
            # Should not raise
            validate_hummingbird_upstream(pkg)

    def test_valid_upstream_import(self) -> None:
        from tools.validate import validate_hummingbird_upstream
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / ".hummingbird-upstream.json").write_text(json.dumps({
                "package": "test", "branch": "upstream", "remote": "https://example.com",
                "commit": "", "tree": "", "imported_at": "2026-01-01T00:00:00Z",
            }))
            validate_hummingbird_upstream(pkg)

    def test_rawhide_import_requires_commit_and_tree(self) -> None:
        from tools.validate import validate_hummingbird_upstream
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / ".hummingbird-upstream.json").write_text(json.dumps({
                "package": "test", "branch": "rawhide", "remote": "https://example.com",
                "commit": "", "tree": "def456", "imported_at": "2026-01-01T00:00:00Z",
            }))
            with self.assertRaises(SystemExit) as ctx:
                validate_hummingbird_upstream(pkg)
            self.assertIn("rawhide import must carry", str(ctx.exception))


class BuildrootLockTests(unittest.TestCase):
    def test_valid_lock_passes(self) -> None:
        from tools.validate import validate_buildroot_lock
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config"
            config.mkdir()
            (config / "buildroot-lock.json").write_text(json.dumps({
                "schema": 1,
                "image": {"pinned": "quay.io/fedora/fedora:44@sha256:" + "a" * 64},
            }))
            validate_buildroot_lock(config)

    def test_missing_lock_rejected(self) -> None:
        from tools.validate import validate_buildroot_lock
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config"
            config.mkdir()
            with self.assertRaises(SystemExit) as ctx:
                validate_buildroot_lock(config)
            self.assertIn("not found", str(ctx.exception))

    def test_wrong_schema_rejected(self) -> None:
        from tools.validate import validate_buildroot_lock
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config"
            config.mkdir()
            (config / "buildroot-lock.json").write_text(json.dumps({
                "schema": 2,
                "image": {"pinned": "sha256:" + "a" * 64},
            }))
            with self.assertRaises(SystemExit) as ctx:
                validate_buildroot_lock(config)
            self.assertIn("schema", str(ctx.exception))

    def test_invalid_digest_rejected(self) -> None:
        from tools.validate import validate_buildroot_lock
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "config"
            config.mkdir()
            (config / "buildroot-lock.json").write_text(json.dumps({
                "schema": 1,
                "image": {"pinned": "quay.io/fedora/fedora:44@sha256:" + "b" * 63},
            }))
            with self.assertRaises(SystemExit) as ctx:
                validate_buildroot_lock(config)
            self.assertIn("SHA-256", str(ctx.exception))


class EndToEndProvenanceTests(unittest.TestCase):
    def test_package_without_provenance_fails(self) -> None:
        from tools.validate import validate_all
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text("fuse\n")
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": []})
            )
            (root / "config" / "hummingbird-provided-sources.json").write_text(
                json.dumps({"sources": []})
            )
            (root / "config" / "buildroot-lock.json").write_text(json.dumps({
                "schema": 1,
                "image": {"pinned": "sha256:" + "c" * 64},
            }))
            pkg = root / "packages" / "no-provenance"
            pkg.mkdir()
            with self.assertRaises(SystemExit) as ctx:
                validate_all(root / "config", root / "packages")
            self.assertIn("missing provenance", str(ctx.exception))

    def test_hummingbird_provided_excluded_from_provenance(self) -> None:
        from tools.validate import validate_all
        with tempfile.TemporaryDirectory() as tmpdir:
            root = _setup_factory(tmpdir)
            (root / "config" / "bootstrap-packages.txt").write_text("fuse\n")
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": []})
            )
            (root / "config" / "hummingbird-provided-sources.json").write_text(
                json.dumps({"sources": ["provided-pkg"]})
            )
            (root / "config" / "buildroot-lock.json").write_text(json.dumps({
                "schema": 1,
                "image": {"pinned": "sha256:" + "d" * 64},
            }))
            pkg = root / "packages" / "provided-pkg"
            pkg.mkdir()
            validate_all(root / "config", root / "packages")


if __name__ == "__main__":
    unittest.main()
