#!/usr/bin/env python3

import json
import os
from pathlib import Path
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
                    verified_source0(root),
                    "packages/demo/demo-1.0.tar.gz",
                )


if __name__ == "__main__":
    unittest.main()
