#!/usr/bin/env python3

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.source_pipeline import fetch_with_fallbacks


SOURCE_PIPELINE = Path(__file__).resolve().parent.parent / "tools" / "source_pipeline.py"


class SourcePipelineTests(unittest.TestCase):
    def test_uses_upstream_without_touching_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch("tools.source_pipeline.fetch") as fetch:
                chosen = fetch_with_fallbacks(["https://upstream.example/source", "https://mirror.example/source"], destination)
            self.assertEqual(chosen, "https://upstream.example/source")
            fetch.assert_called_once_with("https://upstream.example/source", destination)

    def test_uses_fallback_only_after_upstream_transport_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch(
                "tools.source_pipeline.fetch",
                side_effect=[RuntimeError("HTTP Error 418"), None],
            ) as fetch:
                chosen = fetch_with_fallbacks(["https://upstream.example/source", "https://mirror.example/source"], destination)
            self.assertEqual(chosen, "https://mirror.example/source")
            self.assertEqual(fetch.call_count, 2)

    def test_reports_every_failed_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch("tools.source_pipeline.fetch", side_effect=RuntimeError("offline")):
                with self.assertRaisesRegex(RuntimeError, "upstream.example.*mirror.example"):
                    fetch_with_fallbacks(["https://upstream.example/source", "https://mirror.example/source"], destination)

    def test_stages_verified_source_for_packit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "upstream.tar.xz"
            source.write_bytes(b"verified source")
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo",
                                "url": source.as_uri(),
                                "filename": source.name,
                                "sha512": hashlib.sha512(source.read_bytes()).hexdigest(),
                            }
                        ]
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SOURCE_PIPELINE),
                    "demo",
                    "--config",
                    str(config),
                    "--output",
                    str(root / "sources"),
                    "--report-dir",
                    str(root / "reports"),
                    "--stage-into",
                    str(root / "packages"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((package_dir / source.name).read_bytes(), b"verified source")


if __name__ == "__main__":
    unittest.main()
