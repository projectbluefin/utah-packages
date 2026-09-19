#!/usr/bin/env python3
"""Unit coverage for ``tools/scan_rawhide_state.py``.

The ``detect-rawhide-updates`` workflow runs this tool to build
``config/rawhide-state.json`` and ``reports/rawhide-changed-sources.txt``.
``tools/rawhide_sources.py`` was already covered, but the querying, state-diff,
and output-emission logic that makes up *this* module was not exercised by
``just test`` -- so a regression in JSON structure, changed-source detection,
or output paths would only surface on a scheduled GitHub Actions run.

These tests pin that logic: ``dnf repoquery`` is mocked, and the state-diff and
report-writing paths are driven with temp files so no network or real config is
touched.
"""

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tomllib
from unittest.mock import MagicMock, patch

from tools import scan_rawhide_state as srs
from tools.rawhide_sources import source_name

ROOT = Path(__file__).resolve().parent.parent

REPOQUERY_LINE = (
    "ModemManager\t1.24.0-1.fc44\tx86_64\tModemManager-1.24.0-1.fc44.src.rpm"
)


def _repoquery_result(stdout):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = 0
    return result


class QueryTests(unittest.TestCase):
    def test_query_parses_repoquery_output(self):
        cmd = ["dnf", "repoquery", "--latest-limit=1",
               "--qf", "%{name}\\t%{evr}\\t%{arch}\\t%{sourcerpm}", "ModemManager"]
        with patch("subprocess.run", return_value=_repoquery_result(REPOQUERY_LINE + "\n")) as run:
            value = srs.query("ModemManager")

        self.assertEqual(
            value,
            {"name": "ModemManager", "evr": "1.24.0-1.fc44",
             "arch": "x86_64", "sourcerpm": "ModemManager-1.24.0-1.fc44.src.rpm"},
        )
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], cmd)

    def test_query_returns_none_when_repoquery_has_no_lines(self):
        with patch("subprocess.run", return_value=_repoquery_result("")):
            self.assertIsNone(srs.query("nothing-shipped"))

    def test_query_filters_blank_and_none_lines(self):
        stdout = "\n".join(["", REPOQUERY_LINE, "(none)", ""]) + "\n"
        with patch("subprocess.run", return_value=_repoquery_result(stdout)):
            value = srs.query("ModemManager")

        self.assertEqual(value["name"], "ModemManager")

    def test_query_none_line_yields_no_result(self):
        with patch("subprocess.run", return_value=_repoquery_result("(none)\n")):
            self.assertIsNone(srs.query("ModemManager"))

    def test_query_skips_malformed_lines_and_picks_first_valid(self):
        stdout = "Repository 'rawhide' is missing name(s)\n" + REPOQUERY_LINE + "\n"
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(stdout)), \
             redirect_stderr(stderr):
            value = srs.query("ModemManager")

        self.assertEqual(
            value,
            {"name": "ModemManager", "evr": "1.24.0-1.fc44",
             "arch": "x86_64", "sourcerpm": "ModemManager-1.24.0-1.fc44.src.rpm"},
        )
        self.assertIn("discarding malformed repoquery line for ModemManager", stderr.getvalue())
        self.assertIn("Repository 'rawhide' is missing name(s)", stderr.getvalue())

    def test_query_returns_none_when_all_lines_are_malformed(self):
        stdout = "Repository 'rawhide' is missing name(s)\nSome unexpected text\n"
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(stdout)), \
             redirect_stderr(stderr):
            value = srs.query("ModemManager")

        self.assertIsNone(value)
        self.assertIn("discarding malformed repoquery line for ModemManager", stderr.getvalue())

    def test_query_skips_partially_tabbed_lines(self):
        stdout = "only\ttwo\tparts\n"
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(stdout)), \
             redirect_stderr(stderr):
            value = srs.query("ModemManager")

        self.assertIsNone(value)
        self.assertIn("discarding malformed repoquery line for ModemManager", stderr.getvalue())


class MainTests(unittest.TestCase):
    def _write_manifest(self, tmp):
        # import_binaries is patched in these tests, so the manifest only has to
        # be parseable by tomllib; an empty table is enough.
        path = Path(tmp) / "manifest.toml"
        path.write_text("[fedora]\n")
        return path

    def _run_main(self, tmp, binaries, states, previous):
        state_path = Path(tmp) / "nested" / "rawhide-state.json"
        changed_path = Path(tmp) / "nested" / "rawhide-changed-sources.txt"
        manifest_path = self._write_manifest(tmp)
        if previous is not None:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(previous))
        stdout = StringIO()
        argv = ["scan_rawhide_state.py", "--manifest", str(manifest_path),
                "--state", str(state_path), "--changed", str(changed_path)]
        with patch("tools.scan_rawhide_state.import_binaries", return_value=sorted(binaries)), \
             patch("tools.scan_rawhide_state.query", side_effect=lambda p: states[p]), \
             patch.object(sys, "argv", argv), \
             redirect_stdout(stdout):
            rc = srs.main()
        return rc, stdout.getvalue(), state_path, changed_path

    def test_detects_changed_source_and_writes_outputs(self):
        binaries = ["alpha", "beta", "gamma"]
        states = {
            "alpha": {"name": "alpha", "evr": "1.0-1.fc44", "arch": "x86_64",
                      "sourcerpm": "alpha-1.0-1.fc44.src.rpm"},
            "beta": {"name": "beta", "evr": "1.0-1.fc44", "arch": "x86_64",
                     "sourcerpm": "beta-1.0-1.fc44.src.rpm"},
            "gamma": {"name": "gamma", "evr": "2.0-1.fc44", "arch": "x86_64",
                      "sourcerpm": "gamma-2.0-1.fc44.src.rpm"},
        }
        # alpha and beta are unchanged; gamma is new (no previous entry).
        previous = {"alpha": states["alpha"], "beta": states["beta"]}

        with tempfile.TemporaryDirectory() as tmp:
            rc, out, state_path, changed_path = self._run_main(
                tmp, binaries, states, previous)
            self.assertEqual(rc, 0)
            self.assertIn("observed 3 Rawhide packages; queued 1 source rebuilds", out)
            # parent directories were created for both output files
            self.assertTrue(state_path.exists())
            self.assertTrue(changed_path.exists())
            written = json.loads(state_path.read_text())
            self.assertEqual(set(written), set(binaries))
            # only the changed package queues a rebuild, as its source name
            self.assertEqual(changed_path.read_text().splitlines(), ["gamma"])

    def test_no_changes_writes_empty_changed_file(self):
        binaries = ["alpha", "beta"]
        states = {
            "alpha": {"name": "alpha", "evr": "1.0-1.fc44", "arch": "x86_64",
                      "sourcerpm": "alpha-1.0-1.fc44.src.rpm"},
            "beta": {"name": "beta", "evr": "1.0-1.fc44", "arch": "x86_64",
                     "sourcerpm": "beta-1.0-1.fc44.src.rpm"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _, changed_path = self._run_main(tmp, binaries, states, dict(states))
            self.assertEqual(rc, 0)
            self.assertIn("queued 0 source rebuilds", out)
            # empty changed list writes a trailing-newline-free empty file
            self.assertEqual(changed_path.read_text(), "")

    def test_missing_previous_state_treats_everything_as_changed(self):
        binaries = ["alpha", "beta"]
        states = {
            "alpha": {"name": "alpha", "evr": "1.0-1.fc44", "arch": "x86_64",
                      "sourcerpm": "alpha-1.0-1.fc44.src.rpm"},
            "beta": {"name": "beta", "evr": "1.0-1.fc44", "arch": "x86_64",
                     "sourcerpm": "beta-1.0-1.fc44.src.rpm"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            rc, _, _, changed_path = self._run_main(tmp, binaries, states, None)
            self.assertEqual(rc, 0)
            # sorted, de-duplicated source names across all queried packages
            self.assertEqual(changed_path.read_text().splitlines(), ["alpha", "beta"])

    def test_query_none_packages_are_dropped_before_diffing(self):
        binaries = ["alpha", "beta"]
        states = {
            "alpha": {"name": "alpha", "evr": "1.0-1.fc44", "arch": "x86_64",
                      "sourcerpm": "alpha-1.0-1.fc44.src.rpm"},
            "beta": None,
        }
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, state_path, _ = self._run_main(tmp, binaries, states, None)
            self.assertEqual(rc, 0)
            self.assertIn("observed 1 Rawhide packages", out)
            written = json.loads(state_path.read_text())
            self.assertEqual(set(written), {"alpha"})


class EndToEndManifestTests(unittest.TestCase):
    def test_real_manifest_resolves_and_emits(self):
        # Exercises the real import_binaries wiring end to end: the committed
        # manifest must resolve, and every resolved binary must be queried.
        manifest = tomllib.loads((ROOT / "config" / "bluefin-packages.toml").read_text())
        binaries = srs.import_binaries(manifest)
        self.assertTrue(binaries)
        sample = binaries[0]
        value = {"name": sample, "evr": "1.0-1.fc44", "arch": "x86_64",
                 "sourcerpm": f"{sample}-1.0-1.fc44.src.rpm"}
        expected_source = source_name(value["sourcerpm"])

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "rawhide-state.json"
            changed_path = Path(tmp) / "rawhide-changed-sources.txt"
            with patch("tools.scan_rawhide_state.query", return_value=value):
                with patch.object(sys, "argv", ["scan_rawhide_state.py",
                        "--manifest", str(ROOT / "config" / "bluefin-packages.toml"),
                        "--state", str(state_path), "--changed", str(changed_path)]):
                    rc = srs.main()
                written = json.loads(state_path.read_text())
                self.assertEqual(rc, 0)
                self.assertEqual(set(written), set(binaries))
                self.assertEqual(changed_path.read_text().splitlines(), [expected_source])


if __name__ == "__main__":
    unittest.main()
