#!/usr/bin/env python3
"""Regression test: `publish_gate.py assemble`, as publish-repository.yml runs it.

``test_incremental_publish.py`` proves the pure ``assemble`` and ``apply``
decisions. The publish job never calls those directly: it runs

    python3 tools/publish_gate.py assemble --seed repository --built built \\
        --build-list "$BUILD_LIST" --losers "$LOSERS" --report work/publish-report.json

and reads ``.replaced`` from the report to decide whether to publish. This
suite drives that command end to end, with a stand-in ``rpm`` on ``PATH``
whose ``%{SOURCERPM}`` answer is the first line of each fake RPM file, so it
proves what the command itself adds:

* the source package is read from the RPM header, not the file name;
* a ``-bootstrap`` recipe that built is reported as ``bootstrapped`` -- not
  as a failure -- and its ``0.bootstrap`` RPMs never enter the repository;
* the losers JSON reaches the decision, and the report and summary are
  written where the workflow reads them;
* ``source_names`` queries ``rpm`` in chunks, skips source RPMs, and fails
  closed when ``rpm`` answers for fewer files than it was given or a header
  carries no source RPM.
"""
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.publish_gate import main, source_names

FAKE_RPM = """#!/bin/sh
# Stand-in for `rpm -qp --nosignature --qf '%{SOURCERPM}\\n' FILE...`.
printf '%s\\n' "$#" >> "$FAKE_RPM_CALLS"
shift 4
if [ -n "$FAKE_RPM_DROP_LAST" ]; then
    count=$#
    for file; do
        count=$((count - 1))
        [ "$count" -eq 0 ] && break
        head -n 1 "$file"
    done
    exit 0
fi
for file; do
    head -n 1 "$file"
done
"""


class FakeRpmCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        rpm = bin_dir / "rpm"
        rpm.write_text(FAKE_RPM)
        rpm.chmod(0o755)
        self.calls = self.root / "rpm-calls"
        self.calls.write_text("")
        environment = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_RPM_CALLS": str(self.calls),
        }
        patcher = mock.patch.dict(os.environ, environment)
        patcher.start()
        self.addCleanup(patcher.stop)

    def rpm_file(self, relative: str, sourcerpm: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sourcerpm + "\n")
        return path

    def rpm_invocations(self) -> list[int]:
        """Argument count of every `rpm` invocation, in order."""
        return [int(line) for line in self.calls.read_text().split()]


class AssembleCommandTests(FakeRpmCase):
    def setUp(self):
        super().setUp()
        # Seeded repository: the previous publication.
        self.rpm_file("repository/result/x86_64/mutter-50.0-1.hum1.bfin.x86_64.rpm",
                      "mutter-50.0-1.hum1.bfin.src.rpm")
        self.rpm_file("repository/result/x86_64/mutter-common-50.0-1.hum1.bfin.x86_64.rpm",
                      "mutter-50.0-1.hum1.bfin.src.rpm")
        self.rpm_file("repository/result/x86_64/fish-4.0-1.hum1.bfin.x86_64.rpm",
                      "fish-4.0-1.hum1.bfin.src.rpm")
        self.rpm_file("repository/result/x86_64/libwayland-client-1.23-1.hum1.bfin.x86_64.rpm",
                      "wayland-1.23-1.hum1.bfin.src.rpm")
        self.rpm_file("repository/result/x86_64/malcontent-libs-0.13-1.hum1.bfin.x86_64.rpm",
                      "malcontent-0.13-1.hum1.bfin.src.rpm")
        self.rpm_file("repository/result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm",
                      "gtk4-4.20-1.hum1.bfin.src.rpm")
        # This run's builds. The source RPM is never published as a binary.
        self.rpm_file("built/result/x86_64/mutter-50.1-1.hum1.bfin.x86_64.rpm",
                      "mutter-50.1-1.hum1.bfin.src.rpm")
        self.rpm_file("built/result/mutter-50.1-1.hum1.bfin.src.rpm",
                      "unused: source RPMs are never queried")
        # wayland's binaries are named libwayland-*: only the header names it.
        self.rpm_file("built/result/x86_64/libwayland-client-1.24-1.hum1.bfin.x86_64.rpm",
                      "wayland-1.24-1.hum1.bfin.src.rpm")
        # malcontent-bootstrap builds the SRPM "malcontent" at 0.bootstrap.
        self.rpm_file("built/result/x86_64/malcontent-libs-0.13-0.bootstrap.hum1.bfin.x86_64.rpm",
                      "malcontent-0.13-0.bootstrap.hum1.bfin.src.rpm")
        self.rpm_file("built/result/x86_64/gtk4-4.21-1.hum1.bfin.x86_64.rpm",
                      "gtk4-4.21-1.hum1.bfin.src.rpm")
        self.report_path = self.root / "work" / "nested" / "publish-report.json"

    def run_assemble(self, build_list, losers=None, withheld=None):
        argv = [
            "assemble",
            "--seed", str(self.root / "repository"),
            "--built", str(self.root / "built"),
            "--build-list", json.dumps(build_list),
            "--report", str(self.report_path),
        ]
        if losers is not None:
            argv += ["--losers", json.dumps(losers)]
        if withheld is not None:
            path = self.root / "work" / "withheld.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"withheld": withheld}))
            argv += ["--withheld", str(path)]
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(argv)
        self.assertEqual(status, 0)
        return json.loads(self.report_path.read_text()), stdout.getvalue(), stderr.getvalue()

    def published(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.root / "repository"))
            for path in (self.root / "repository").rglob("*.rpm")
        )

    def test_the_command_replaces_by_header_source_and_writes_the_report(self):
        report, stdout, stderr = self.run_assemble(
            ["mutter", "fish", "wayland", "malcontent-bootstrap", "gtk4", "libbar"],
            losers=["gtk4"],
        )

        self.assertEqual(report, {
            "replaced": ["mutter", "wayland"],
            "failed": ["fish", "gtk4", "libbar"],
            "kept_previous": ["fish", "gtk4"],
            "absent": ["libbar"],
            "precedence_losers": ["gtk4"],
            "withheld": [],
            "withheld_reasons": {},
            "bootstrapped": ["malcontent-bootstrap"],
        })
        self.assertEqual(self.published(), [
            "result/x86_64/fish-4.0-1.hum1.bfin.x86_64.rpm",
            "result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm",
            "result/x86_64/libwayland-client-1.24-1.hum1.bfin.x86_64.rpm",
            "result/x86_64/malcontent-libs-0.13-1.hum1.bfin.x86_64.rpm",
            "result/x86_64/mutter-50.1-1.hum1.bfin.x86_64.rpm",
        ])
        self.assertIn("### Incremental publish", stdout)
        self.assertIn("Replaced 2 source package(s): `mutter`, `wayland`", stdout)
        self.assertIn("| `gtk4` | previous build (this build lost precedence) |", stdout)
        self.assertIn("| `libbar` | nothing: never published |", stdout)
        self.assertIn("removed 3 seed RPMs, added 2 built RPMs", stderr)

    def test_a_held_back_build_keeps_its_previous_build_and_is_not_a_failure(self):
        # publish_holdback.py held mutter back: a published consumer still
        # needs what mutter 50.0 provides. The rest of the run publishes.
        self.keep_only_built("mutter-", "libwayland-")
        report, stdout, stderr = self.run_assemble(
            ["mutter", "wayland"],
            withheld={"mutter": ["gnome-shell needs libmutter-17.so.0, which the new mutter no longer provides"]},
        )

        self.assertEqual(report["replaced"], ["wayland"])
        self.assertEqual(report["withheld"], ["mutter"])
        self.assertEqual(report["failed"], [])
        self.assertIn("libmutter-17.so.0", report["withheld_reasons"]["mutter"][0])
        self.assertIn("result/x86_64/mutter-50.0-1.hum1.bfin.x86_64.rpm", self.published())
        self.assertIn("result/x86_64/mutter-common-50.0-1.hum1.bfin.x86_64.rpm", self.published())
        self.assertNotIn("result/x86_64/mutter-50.1-1.hum1.bfin.x86_64.rpm", self.published())
        self.assertIn("held back", stdout)
        self.assertIn("removed 1 seed RPMs, added 1 built RPMs", stderr)

    def test_a_built_bootstrap_recipe_is_not_reported_as_failed(self):
        report, stdout, _ = self.run_assemble(["malcontent-bootstrap"])

        self.assertEqual(report["bootstrapped"], ["malcontent-bootstrap"])
        self.assertNotIn("malcontent-bootstrap", report["failed"])
        self.assertNotIn("failed and were not replaced", stdout)
        # The real malcontent stays published; the bootstrap copy never lands.
        self.assertIn("result/x86_64/malcontent-libs-0.13-1.hum1.bfin.x86_64.rpm",
                      self.published())
        self.assertFalse(any("bootstrap" in path for path in self.published()))

    def test_a_bootstrap_recipe_that_did_not_build_is_a_failure(self):
        (self.root / "built/result/x86_64/"
         "malcontent-libs-0.13-0.bootstrap.hum1.bfin.x86_64.rpm").unlink()

        report, _, _ = self.run_assemble(["malcontent-bootstrap"])

        self.assertEqual(report["bootstrapped"], [])
        self.assertEqual(report["failed"], ["malcontent-bootstrap"])
        self.assertEqual(report["absent"], ["malcontent-bootstrap"])

    def keep_only_built(self, *names: str) -> None:
        """Leave only these binary RPMs in built/, as one wave's download would."""
        for path in (self.root / "built").rglob("*.rpm"):
            if not path.name.startswith(names):
                path.unlink()

    def test_losers_default_to_none(self):
        self.keep_only_built("gtk4-")

        report, _, _ = self.run_assemble(["gtk4"])

        self.assertEqual(report["replaced"], ["gtk4"])
        self.assertEqual(report["precedence_losers"], [])
        self.assertIn("result/x86_64/gtk4-4.21-1.hum1.bfin.x86_64.rpm", self.published())
        self.assertNotIn("result/x86_64/gtk4-4.20-1.hum1.bfin.x86_64.rpm", self.published())

    def test_a_run_that_built_nothing_reports_nothing_replaced(self):
        self.keep_only_built()
        before = self.published()
        report, _, stderr = self.run_assemble(["libbar"])

        # publish-repository.yml skips the image when `.replaced` is empty.
        self.assertEqual(report["replaced"], [])
        self.assertEqual(self.published(), before)
        self.assertIn("removed 0 seed RPMs, added 0 built RPMs", stderr)


    def assemble_with_artifacts(self, build_list, artifacts, wave=""):
        path = self.root / "work" / "run-artifacts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifacts))
        argv = ["assemble", "--seed", str(self.root / "repository"),
                "--built", str(self.root / "built"),
                "--build-list", json.dumps(build_list),
                "--report", str(self.report_path),
                "--artifacts", str(path), "--prefix", "", "--wave", wave]
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            status = main(argv)
        return status, stderr.getvalue()

    def test_a_download_cut_short_fails_instead_of_publishing_builds_as_failures(self):
        # gtk4 built and uploaded its artifact, but the download stopped short.
        self.keep_only_built("mutter-", "libwayland-")
        before = self.published()
        status, stderr = self.assemble_with_artifacts(
            ["mutter", "wayland", "gtk4"],
            ["rpm-s0-mutter", "rpm-s0-wayland", "rpm-s1-gtk4", "build-graph"])

        self.assertEqual(status, 1)
        self.assertIn("gtk4", stderr)
        self.assertEqual(self.published(), before)
        self.assertFalse(self.report_path.exists())

    def test_a_complete_download_passes_the_check(self):
        status, _ = self.assemble_with_artifacts(
            ["mutter", "wayland", "gtk4", "malcontent-bootstrap", "libbar"],
            ["rpm-s0-mutter", "rpm-s0-wayland", "rpm-s1-gtk4",
             "rpm-s0-malcontent-bootstrap", "build-graph"])
        self.assertEqual(status, 0)

    def test_artifacts_of_later_waves_are_not_expected_in_an_early_publication(self):
        self.keep_only_built("mutter-", "libwayland-")
        status, _ = self.assemble_with_artifacts(
            ["mutter", "wayland", "gtk4"],
            ["rpm-s0-mutter", "rpm-s0-wayland", "rpm-s1-gtk4"], wave="0")
        self.assertEqual(status, 0)

class SourceNamesTests(FakeRpmCase):
    def test_source_rpms_are_skipped_and_never_queried(self):
        binary = self.rpm_file("r/foo-1-1.x86_64.rpm", "foo-1-1.src.rpm")
        source = self.rpm_file("r/foo-1-1.src.rpm", "not read")
        other = self.rpm_file("r/notes.txt", "not read")

        self.assertEqual(source_names([binary, source, other]), {str(binary): "foo"})
        # -qp --nosignature --qf FORMAT plus the one binary RPM.
        self.assertEqual(self.rpm_invocations(), [5])

    def test_rpm_is_never_run_without_binary_rpms(self):
        self.assertEqual(source_names([]), {})
        self.assertEqual(self.rpm_invocations(), [])

    def test_large_repositories_are_queried_in_chunks_of_200(self):
        paths = [
            self.rpm_file(f"r/pkg{index:03d}-1-1.x86_64.rpm", f"pkg{index:03d}-1-1.src.rpm")
            for index in range(450)
        ]

        names = source_names(paths)

        self.assertEqual(len(names), 450)
        self.assertEqual(names[str(paths[0])], "pkg000")
        self.assertEqual(names[str(paths[449])], "pkg449")
        self.assertEqual(self.rpm_invocations(), [4 + 200, 4 + 200, 4 + 50])

    def test_fewer_headers_than_files_fails_closed(self):
        paths = [
            self.rpm_file("r/a-1-1.x86_64.rpm", "a-1-1.src.rpm"),
            self.rpm_file("r/b-1-1.x86_64.rpm", "b-1-1.src.rpm"),
        ]
        with mock.patch.dict(os.environ, {"FAKE_RPM_DROP_LAST": "1"}):
            with self.assertRaisesRegex(RuntimeError, "rpm reported 1 headers for 2 files"):
                source_names(paths)

    def test_a_header_without_a_source_rpm_fails_closed(self):
        path = self.rpm_file("r/orphan-1-1.x86_64.rpm", "(none)")

        with self.assertRaisesRegex(RuntimeError, "orphan-1-1.x86_64.rpm: no source RPM"):
            source_names([path])


if __name__ == "__main__":
    unittest.main()
