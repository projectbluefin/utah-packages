#!/usr/bin/env python3
"""Executed coverage for ``tools/import_bluefin_rawhide.py``.

``tools/rawhide_sources.py`` (the grammar this tool consumes) is fully covered
by ``tests/test_rawhide_sources.py``, but the tool's own two functions --
``resolve_source`` and ``main`` -- had zero executed coverage. They carry the
decisions that matter operationally: which ``dnf repoquery`` answers count as a
resolution, the ``[unavailable] packages`` policy filter, the
"refuse to open a flood of issues" abort, the already-imported short circuit,
and the exact shape of ``reports/bluefin-rawhide-resolution.json``.

Every test stubs ``command`` so no ``dnf``/``git`` process is ever spawned.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import import_bluefin_rawhide as tool


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["stub"], returncode=returncode, stdout=stdout, stderr=stderr)


class ResolveSourceTests(unittest.TestCase):
    def test_resolves_source_name_from_sourcerpm(self) -> None:
        with mock.patch.object(tool, "command", return_value=completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n")) as run:
            self.assertEqual(tool.resolve_source("pipewire-alsa"), ("pipewire", None))
        run.assert_called_once_with(
            "dnf", "repoquery", "--latest-limit=1", "--qf", "%{sourcerpm}", "pipewire-alsa"
        )

    def test_deduplicates_and_takes_the_first_sorted_candidate(self) -> None:
        stdout = "zlib-1.3-1.fc44.src.rpm\nadw-gtk3-theme-5.7-1.fc44.src.rpm\nzlib-1.3-1.fc44.src.rpm\n"
        with mock.patch.object(tool, "command", return_value=completed(stdout=stdout)):
            self.assertEqual(tool.resolve_source("anything"), ("adw-gtk3-theme", None))

    def test_none_marker_is_not_a_candidate(self) -> None:
        with mock.patch.object(tool, "command", return_value=completed(stdout="(none)\n")):
            source, error = tool.resolve_source("ghost")
        self.assertIsNone(source)
        self.assertEqual(error, "no Rawhide candidate")

    def test_blank_output_reports_stderr_when_present(self) -> None:
        with mock.patch.object(tool, "command", return_value=completed(stdout="\n  \n", stderr="repo down\n")):
            source, error = tool.resolve_source("ghost")
        self.assertIsNone(source)
        self.assertEqual(error, "repo down")

    def test_unparseable_candidate_is_an_explicit_reason_not_a_crash(self) -> None:
        with mock.patch.object(tool, "command", return_value=completed(stdout="not-an-srpm\n")):
            source, error = tool.resolve_source("weird")
        self.assertIsNone(source)
        self.assertEqual(error, "cannot derive source package from not-an-srpm")


class FactorySourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.destination = Path(self._tmp.name) / "packages"

    def test_nonexistent_destination_returns_empty_set(self) -> None:
        self.assertEqual(tool.factory_sources(self.destination), set())

    def test_rawhide_branch_is_not_a_factory_source(self) -> None:
        pkg_dir = self.destination / "mesa"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / ".hummingbird-upstream.json").write_text(
            json.dumps({"package": "mesa", "branch": "rawhide"})
        )
        self.assertEqual(tool.factory_sources(self.destination), set())

    def test_upstream_branch_identifies_package_and_spec_names(self) -> None:
        pkg_dir = self.destination / "pipewire-libs-extra"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / ".hummingbird-upstream.json").write_text(
            json.dumps({"package": "pipewire-libs-extra", "branch": "upstream"})
        )
        spec = (
            "Name: pipewire-libs-extra\n"
            "%package -n libspa-extra\n"
            "%package subpkg\n"
            "%package plugin-nautilus\n"
        )
        (pkg_dir / "pipewire-libs-extra.spec").write_text(spec)
        expected = {
            "pipewire-libs-extra",
            "libspa-extra",
            "pipewire-libs-extra-subpkg",
            "pipewire-libs-extra-plugin-nautilus",
        }
        self.assertEqual(tool.factory_sources(self.destination), expected)

    def test_corrupt_or_missing_provenance_is_ignored(self) -> None:
        (self.destination / "corrupt").mkdir(parents=True)
        (self.destination / "corrupt" / ".hummingbird-upstream.json").write_text("invalid json")
        (self.destination / "no-provenance").mkdir(parents=True)
        self.assertEqual(tool.factory_sources(self.destination), set())

    def test_unreadable_spec_is_ignored(self) -> None:
        pkg_dir = self.destination / "unreadable-spec"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / ".hummingbird-upstream.json").write_text(
            json.dumps({"package": "unreadable-spec", "branch": "upstream"})
        )
        spec = pkg_dir / "unreadable-spec.spec"
        spec.write_text("Name: unreadable-spec\n")
        original_read_text = Path.read_text

        def mock_read_text(path_obj, *args, **kwargs):
            if path_obj == spec:
                raise OSError("Permission denied")
            return original_read_text(path_obj, *args, **kwargs)

        with mock.patch.object(Path, "read_text", side_effect=mock_read_text, autospec=True):
            self.assertEqual(tool.factory_sources(self.destination), {"unreadable-spec"})


class MainTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.manifest = self.root / "manifest.toml"
        self.policy = self.root / "policy.toml"
        self.destination = self.root / "packages"
        self.report = self.root / "reports" / "resolution.json"

    def write_manifest(self, fedora: list[str], multimedia: list[str] | None = None) -> None:
        body = [
            "[fedora]",
            f"packages = {json.dumps(fedora)}",
            "[multimedia_overrides]",
            f"packages = {json.dumps(multimedia or [])}",
        ]
        self.manifest.write_text("\n".join(body) + "\n")

    def run_main(self, responses):
        """Run ``main`` with ``command`` replaced by a scripted stub.

        ``responses`` maps the first meaningful argv token to a
        ``CompletedProcess``; repoquery calls key on the binary name and import
        calls key on the source package name.
        """
        calls: list[tuple[str, ...]] = []

        def fake_command(*args: str) -> subprocess.CompletedProcess:
            calls.append(args)
            key = args[-1] if args[0] == "dnf" else args[2]
            return responses[key]

        argv = [
            "import_bluefin_rawhide.py",
            "--manifest", str(self.manifest),
            "--policy", str(self.policy),
            "--destination", str(self.destination),
            "--report", str(self.report),
        ]
        with mock.patch.object(tool, "command", side_effect=fake_command), \
                mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(io.StringIO()):
            status = tool.main()
        return status, calls

    def read_report(self) -> dict:
        return json.loads(self.report.read_text())

    def test_happy_path_imports_and_writes_the_report(self) -> None:
        self.write_manifest(["pipewire-alsa"], ["gstreamer1-plugin-libav"])
        responses = {
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "gstreamer1-plugin-libav": completed(stdout="gstreamer1-plugins-libav-1.24-1.fc44.src.rpm\n"),
            "gstreamer1-plugins-libav": completed(),
            "pipewire": completed(),
        }
        status, calls = self.run_main(responses)

        self.assertEqual(status, 0)
        report = self.read_report()
        self.assertEqual(report["binary_count"], 2)
        self.assertEqual(
            report["resolved_binary_to_source"],
            {"pipewire-alsa": "pipewire", "gstreamer1-plugin-libav": "gstreamer1-plugins-libav"},
        )
        self.assertEqual(report["imported_sources"], ["gstreamer1-plugins-libav", "pipewire"])
        self.assertEqual(report["unavailable"], [])
        self.assertEqual(report["import_failures"], [])
        self.assertTrue(report["upstream_manifest"].startswith("https://github.com/projectbluefin/bluefin/"))

        import_calls = [call for call in calls if call[0] != "dnf"]
        self.assertEqual(
            import_calls[0],
            (sys.executable, "tools/import_rawhide.py", "gstreamer1-plugins-libav",
             "--destination", str(self.destination)),
        )

    def test_report_parent_directory_is_created(self) -> None:
        self.write_manifest(["pipewire-alsa"])
        self.assertFalse(self.report.parent.exists())
        self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(),
        })
        self.assertTrue(self.report.is_file())

    def test_policy_excluded_binaries_are_never_queried(self) -> None:
        self.write_manifest(["pipewire-alsa", "known-missing"])
        self.policy.write_text('[unavailable]\npackages = ["known-missing"]\n')
        status, calls = self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(),
        })
        self.assertEqual(status, 0)
        queried = [call[-1] for call in calls if call[0] == "dnf"]
        self.assertEqual(queried, ["pipewire-alsa"])
        self.assertEqual(self.read_report()["binary_count"], 1)

    def test_factory_sources_are_never_queried(self) -> None:
        self.write_manifest(["pipewire-alsa", "pipewire-libs-extra"])
        extra_dir = self.destination / "pipewire-libs-extra"
        extra_dir.mkdir(parents=True)
        (extra_dir / ".hummingbird-upstream.json").write_text(
            json.dumps({"package": "pipewire-libs-extra", "branch": "upstream"})
        )
        status, calls = self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(),
        })
        self.assertEqual(status, 0)
        queried = [call[-1] for call in calls if call[0] == "dnf"]
        self.assertEqual(queried, ["pipewire-alsa"])
        report = self.read_report()
        self.assertEqual(report["binary_count"], 1)
        self.assertEqual(report["unavailable"], [])

    def test_absent_policy_file_leaves_every_binary_in_scope(self) -> None:
        self.write_manifest(["pipewire-alsa", "zlib-devel"])
        self.assertFalse(self.policy.exists())
        self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "zlib-devel": completed(stdout="zlib-1.3-1.fc44.src.rpm\n"),
            "pipewire": completed(),
            "zlib": completed(),
        })
        self.assertEqual(self.read_report()["binary_count"], 2)

    def test_unresolved_binaries_are_recorded_with_their_reason(self) -> None:
        self.write_manifest(["pipewire-alsa", "ghost"])
        self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "ghost": completed(stdout="(none)\n", stderr="no match\n"),
            "pipewire": completed(),
        })
        self.assertEqual(
            self.read_report()["unavailable"],
            [{"binary": "ghost", "reason": "no match"}],
        )

    def test_total_resolution_failure_aborts_before_importing_anything(self) -> None:
        self.write_manifest(["ghost"])
        with self.assertRaises(SystemExit) as raised:
            self.run_main({"ghost": completed(stdout="(none)\n")})
        self.assertIn("refusing to open a flood of issues", str(raised.exception))
        self.assertFalse(self.report.exists())

    def test_existing_destination_short_circuits_the_import(self) -> None:
        self.write_manifest(["pipewire-alsa"])
        (self.destination / "pipewire").mkdir(parents=True)
        status, calls = self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
        })
        self.assertEqual(status, 0)
        self.assertEqual([call for call in calls if call[0] != "dnf"], [])
        self.assertEqual(self.read_report()["imported_sources"], ["pipewire"])

    def test_failed_import_is_reported_and_not_counted_as_imported(self) -> None:
        self.write_manifest(["pipewire-alsa"])
        self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(returncode=1, stderr="fedpkg clone failed\n"),
        })
        report = self.read_report()
        self.assertEqual(report["imported_sources"], [])
        self.assertEqual(report["import_failures"], [{"source": "pipewire", "reason": "fedpkg clone failed"}])

    def test_failed_import_falls_back_to_stdout_when_stderr_is_empty(self) -> None:
        self.write_manifest(["pipewire-alsa"])
        self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(returncode=1, stdout="branch rawhide missing\n"),
        })
        self.assertEqual(
            self.read_report()["import_failures"],
            [{"source": "pipewire", "reason": "branch rawhide missing"}],
        )

    def test_two_binaries_sharing_one_source_are_imported_once(self) -> None:
        self.write_manifest(["pipewire-alsa", "pipewire-pulseaudio"])
        status, calls = self.run_main({
            "pipewire-alsa": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire-pulseaudio": completed(stdout="pipewire-1.4.2-3.fc44.src.rpm\n"),
            "pipewire": completed(),
        })
        self.assertEqual(status, 0)
        self.assertEqual(len([call for call in calls if call[0] != "dnf"]), 1)
        self.assertEqual(self.read_report()["imported_sources"], ["pipewire"])


if __name__ == "__main__":
    unittest.main()
