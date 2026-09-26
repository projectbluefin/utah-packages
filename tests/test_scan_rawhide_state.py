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
               "--qf", "%{name}\t%{evr}\t%{arch}\t%{sourcerpm}\n", "ModemManager"]
        with patch("subprocess.run", return_value=_repoquery_result(REPOQUERY_LINE + "\n")) as run:
            value = srs.query("ModemManager")

        self.assertEqual(
            value,
            {"name": "ModemManager", "evr": "1.24.0-1.fc44",
             "arch": "x86_64", "sourcerpm": "ModemManager-1.24.0-1.fc44.src.rpm"},
        )
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], cmd)

    def test_query_uses_real_tabs_and_trailing_newline(self):
        # dnf5 expands only \n in --qf, not \t, so the format must carry real tabs
        # and a trailing newline. A literal "\t" glues the per-arch records into
        # one line and the scan silently reports nothing (#172, #99's lesson). Pin
        # the real tab so that regressing to a dnf4-style escape cannot happen
        # unseen.
        with patch("subprocess.run", return_value=_repoquery_result(REPOQUERY_LINE + "\n")) as run:
            srs.query("ModemManager")
        qf = run.call_args.args[0][4]
        self.assertIn("\t", qf)
        self.assertNotIn("\\t", qf)
        self.assertTrue(qf.endswith("\n"))

    def test_query_prefers_x86_64_over_i686(self):
        # dnf5 emits one record per arch on its own line. i686 sorts first, so
        # lines[0] would be i686; the source package is arch-independent but the
        # report must pick a fixed arch. Prefer x86_64, then noarch (#172).
        stdout = (
            "ModemManager\t1.24.0-1.fc44\ti686\tModemManager-1.24.0-1.fc44.src.rpm\n"
            "ModemManager\t1.24.0-1.fc44\tx86_64\tModemManager-1.24.0-1.fc44.src.rpm\n"
        )
        with patch("subprocess.run", return_value=_repoquery_result(stdout)):
            value = srs.query("ModemManager")
        self.assertEqual(value["arch"], "x86_64")

    def test_query_falls_back_to_noarch_when_no_x86_64(self):
        stdout = (
            "ModemManager\t1.24.0-1.fc44\ti686\tModemManager-1.24.0-1.fc44.src.rpm\n"
            "ModemManager\t1.24.0-1.fc44\tnoarch\tModemManager-1.24.0-1.fc44.src.rpm\n"
        )
        with patch("subprocess.run", return_value=_repoquery_result(stdout)):
            value = srs.query("ModemManager")
        self.assertEqual(value["arch"], "noarch")

    def test_query_returns_none_when_records_are_glued(self):
        # If dnf5 ever emits a literal backslash-t with no newline, the i686 and
        # x86_64 records glue into one line that splits to a single field; the
        # guard skips it and query() returns None rather than storing garbage
        # (#172). This pins that the glued shape is swallowed, not parsed.
        glued = (
            "ModemManager\\t1.24.0-1.fc44\\ti686\\tModemManager-1.24.0-1.fc44.src.rpm"
            "ModemManager\\t1.24.0-1.fc44\\tx86_64\\tModemManager-1.24.0-1.fc44.src.rpm"
        )
        with patch("subprocess.run", return_value=_repoquery_result(glued + "\n")):
            self.assertIsNone(srs.query("ModemManager"))

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

    def test_query_skips_warning_line_and_uses_good_one(self):
        # A dnf5 warning mixed before the real repoquery line must not crash the
        # scan; the warning is skipped and the well-formed line is parsed. (issue #172)
        stdout = "Warning: some progress line\n" + REPOQUERY_LINE + "\n"
        with patch("subprocess.run", return_value=_repoquery_result(stdout)) as run:
            value = srs.query("ModemManager")

        self.assertEqual(value["name"], "ModemManager")
        run.assert_called_once()

    def test_query_skips_malformed_lines_until_a_four_field_one(self):
        stdout = "\n".join(["garbage", "a\tb", REPOQUERY_LINE]) + "\n"
        with patch("subprocess.run", return_value=_repoquery_result(stdout)) as run:
            value = srs.query("ModemManager")

        self.assertEqual(value["name"], "ModemManager")

    def test_query_skips_four_field_line_with_non_srpm_sourcerpm(self):
        # A warning/progress line can carry 3+ tabs and pass the field count;
        # validate the sourcerpm against SRPM_NAME so garbage never reaches
        # source_name(), which would raise (issue #172 follow-up).
        bad = "ModemManager\t1.24.0-1.fc44\tx86_64\tnot-a-source-rpm.txt"
        stdout = "Warning: some\tprogress\tline\n" + bad + "\n"
        with patch("subprocess.run", return_value=_repoquery_result(stdout)) as run:
            value = srs.query("ModemManager")

        self.assertIsNone(value)
        run.assert_called_once()

    def test_query_skips_srpm_suffixed_line_source_name_cannot_parse(self):
        # ``.src.rpm`` alone is a weaker grammar than SRPM_NAME: this line would
        # pass a suffix check, be stored in state, and then crash main() inside
        # source_name(). The guard must use the same grammar source_name() does.
        # The arch is x86_64 so the arch preference cannot reject the line
        # first -- the SRPM_NAME guard is what must do the rejecting.
        bad = "foo\t1.0-1.fc44\tx86_64\tqux.src.rpm"
        with self.assertRaises(ValueError):
            source_name("qux.src.rpm")
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(bad + "\n")), \
             redirect_stderr(stderr):
            self.assertIsNone(srs.query("foo"))
        self.assertIn("non-SRPM sourcerpm", stderr.getvalue())

    def test_query_logs_lines_that_are_not_four_fields(self):
        # Rule 16 promises every discarded line is visible on stderr, not just
        # the ones that fail the SRPM_NAME guard, so a systematically malformed
        # query is noticed instead of silently returning None.
        stdout = "Warning: some progress line\n" + REPOQUERY_LINE + "\n"
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(stdout)), \
             redirect_stderr(stderr):
            value = srs.query("ModemManager")

        self.assertEqual(value["name"], "ModemManager")
        self.assertIn("not four tab-separated fields", stderr.getvalue())
        self.assertIn("Warning: some progress line", stderr.getvalue())

    def test_query_logs_when_only_unsupported_arches_are_present(self):
        # A package whose records are all e.g. i686 is dropped from the report
        # by the arch preference. That drop must be logged, otherwise the
        # package vanishes from state with no trace.
        stdout = (
            "ModemManager\t1.24.0-1.fc44\ti686\tModemManager-1.24.0-1.fc44.src.rpm\n"
            "ModemManager\t1.24.0-1.fc44\taarch64\tModemManager-1.24.0-1.fc44.src.rpm\n"
        )
        stderr = StringIO()
        with patch("subprocess.run", return_value=_repoquery_result(stdout)), \
             redirect_stderr(stderr):
            self.assertIsNone(srs.query("ModemManager"))

        message = stderr.getvalue()
        self.assertIn("no x86_64 or noarch record", message)
        self.assertIn("aarch64, i686", message)

    def test_query_accepts_sourcerpm_source_name_can_parse(self):
        # The guard must not reject well-formed source RPMs, including names
        # that contain '-'.
        line = ("gtk4-devel\t4.20.1-1.fc44\tx86_64\t"
                "gtk4-4.20.1-1.fc44.src.rpm")
        with patch("subprocess.run", return_value=_repoquery_result(line + "\n")):
            value = srs.query("gtk4-devel")

        self.assertIsNotNone(value)
        self.assertEqual(source_name(value["sourcerpm"]), "gtk4")

    def test_query_returns_none_when_no_line_has_four_fields(self):
        stdout = "\n".join(["just a warning", "one\ttwo\n"])
        with patch("subprocess.run", return_value=_repoquery_result(stdout)):
            self.assertIsNone(srs.query("ModemManager"))


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
