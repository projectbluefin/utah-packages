#!/usr/bin/env python3

from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.source_pipeline import fetch_with_fallbacks, main


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


class NoUpstreamSourceTests(unittest.TestCase):
    """An entry may declare that its recipe downloads nothing at all."""

    def run_pipeline(self, entry: dict, directory: str) -> dict:
        root = Path(directory)
        config = root / "sources.json"
        config.write_text(json.dumps({"packages": [entry]}))
        argv = [
            "source_pipeline.py", entry["name"],
            "--config", str(config),
            "--output", str(root / "out"),
            "--report-dir", str(root / "reports"),
        ]
        with patch.object(sys, "argv", argv), patch("tools.source_pipeline.fetch") as fetch:
            self.assertEqual(main(), 0)
        fetch.assert_not_called()
        return json.loads((root / "reports" / f"{entry['name']}.json").read_text())

    def test_a_sourceless_entry_fetches_nothing_and_still_stages_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_pipeline(
                {"name": "color-filesystem", "version": "1", "no_upstream_source": True}, directory
            )
            self.assertEqual(report["result"], "accepted")
            self.assertTrue(report["no_upstream_source"])
            # The build stages this directory unconditionally, so it must exist
            # even though nothing was downloaded into it.
            self.assertTrue((Path(directory) / "out" / "color-filesystem").is_dir())

    def test_a_sourceless_entry_may_not_also_claim_a_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                self.run_pipeline(
                    {
                        "name": "color-filesystem",
                        "version": "1",
                        "no_upstream_source": True,
                        "url": "https://example.invalid/color-filesystem-1.tar.xz",
                    },
                    directory,
                )


if __name__ == "__main__":
    unittest.main()
