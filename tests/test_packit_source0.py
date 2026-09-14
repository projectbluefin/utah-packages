#!/usr/bin/env python3

import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools.packit_source0 import verified_source0


class PackitSource0Tests(unittest.TestCase):
    def test_returns_locked_archive_relative_to_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            (package_dir / "demo.spec").write_text("Name: demo\n")
            (package_dir / "demo-1.0.tar.gz").write_bytes(b"verified source")
            config = root / "config" / "upstream-sources.json"
            config.parent.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo",
                                "filename": "demo-1.0.tar.gz",
                                "sha512": "0" * 128,
                            }
                        ]
                    }
                )
            )

            with patch.dict(
                os.environ,
                {"PACKIT_SPECFILE_PATH": "demo.spec"},
                clear=True,
            ):
                self.assertEqual(
                    verified_source0(root, package_dir),
                    "demo-1.0.tar.gz",
                )

    def test_synthesizes_a_placeholder_for_a_recipe_with_no_upstream_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "nosource"
            package_dir.mkdir(parents=True)
            (package_dir / "nosource.spec").write_text("Name: nosource\nVersion: 1\n")
            config = root / "config" / "upstream-sources.json"
            config.parent.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "nosource",
                                "version": "1",
                                "no_upstream_source": True,
                            }
                        ]
                    }
                )
            )

            with patch.dict(
                os.environ,
                {"PACKIT_SPECFILE_PATH": "nosource.spec"},
                clear=True,
            ):
                first = verified_source0(root, package_dir)
                self.assertEqual(first, "nosource-1.tar.gz")
                # Packit requires a path to a file that exists, in the spec
                # directory so it has nothing to symlink.
                archive = package_dir / first
                self.assertTrue(archive.is_file())
                self.assertEqual(
                    tarfile.open(archive).getnames(),
                    [],
                    "the placeholder carries no members",
                )
                # Byte-reproducible across runs: no name, no timestamp.
                recorded = archive.read_bytes()
                archive.unlink()
                self.assertEqual(verified_source0(root, package_dir), first)
                self.assertEqual(archive.read_bytes(), recorded)


if __name__ == "__main__":
    unittest.main()
