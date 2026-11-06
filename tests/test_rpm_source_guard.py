#!/usr/bin/env python3
"""Only the package a job built may leave it.

publish_gate.py replaces published RPMs by the source name in each uploaded
binary's %{SOURCERPM}, and %build runs as a user that can write into the
directory the lane uploads. tools/check_rpm_source.sh refuses a result
directory holding a binary that claims another source package, and both
lane scripts call it before anything is listed for upload. Repeated mistake
11: the lanes must agree, so both are asserted here.
"""

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tools" / "check_rpm_source.sh"
LANES = {
    "hermetic": ROOT / "tools" / "hermetic_build.sh",
    "container": ROOT / "tools" / "build_container.sh",
}
UPLOAD_LISTING = 'xargs -0 -r rpm -qp --qf "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\\n"'

# A stand-in rpm: the %{SOURCERPM} of each file is the file's own
# content, so a test writes the header it wants a binary to carry.
FAKE_RPM = """#!/bin/bash
set -euo pipefail
for arg in "$@"; do
  case "$arg" in
    -*|*%{*) continue ;;
  esac
  [ -f "$arg" ] || { echo "error: open of $arg failed" >&2; exit 1; }
  header=$(cat "$arg")
  [ -n "$header" ] || { echo "error: $arg: not an rpm package" >&2; exit 1; }
  echo "$header"
done
"""


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        self.tmp = Path(workdir.name)
        fake_bin = self.tmp / "bin"
        fake_bin.mkdir()
        rpm = fake_bin / "rpm"
        rpm.write_text(FAKE_RPM)
        rpm.chmod(rpm.stat().st_mode | stat.S_IXUSR)
        self.env = dict(os.environ, PATH=f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
        self.result = self.tmp / "result"
        (self.result / "nested").mkdir(parents=True)

    def rpm(self, name: str, sourcerpm: str) -> None:
        (self.result / name).write_text(sourcerpm + "\n")

    def run_guard(self, expected: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(GUARD), expected, str(self.result)],
            capture_output=True, text=True, env=self.env, check=False,
        )

    def test_binaries_of_the_built_source_pass(self) -> None:
        self.rpm("libwayland-client-1.24.0-1.hum1.bfin.x86_64.rpm", "wayland-1.24.0-1.hum1.bfin.src.rpm")
        self.rpm("nested/wayland-devel-1.24.0-1.hum1.bfin.x86_64.rpm", "wayland-1.24.0-1.hum1.bfin.src.rpm")
        # mock leaves the SRPM beside the binaries; it is not a binary.
        self.rpm("wayland-1.24.0-1.hum1.bfin.src.rpm", "(none)")
        result = self.run_guard("wayland")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("every binary RPM comes from source package wayland", result.stdout)

    def test_a_binary_claiming_another_source_fails(self) -> None:
        self.rpm("libwayland-client-1.24.0-1.hum1.bfin.x86_64.rpm", "wayland-1.24.0-1.hum1.bfin.src.rpm")
        self.rpm("gnome-shell-99.0-1.hum1.bfin.x86_64.rpm", "gnome-shell-99.0-1.hum1.bfin.src.rpm")
        result = self.run_guard("wayland")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error title=foreign RPM in build output::", result.stderr)
        self.assertIn("gnome-shell", result.stderr)

    def test_the_release_may_differ_but_the_name_may_not(self) -> None:
        # The hermetic lock SRPM carries the placeholder disttag, the build
        # the resolved one; and a dist_bump appends to the release. Only
        # the name is the key publish replaces by.
        self.rpm("fish-4.0.2-3.hum1.bfin.1.x86_64.rpm", "fish-4.0.2-3.hum1.bfin.1.src.rpm")
        self.assertEqual(self.run_guard("fish").returncode, 0)
        self.assertEqual(self.run_guard("fish-shell").returncode, 1)

    def test_an_unreadable_rpm_fails_closed(self) -> None:
        self.rpm("libwayland-client-1.24.0-1.hum1.bfin.x86_64.rpm", "wayland-1.24.0-1.hum1.bfin.src.rpm")
        (self.result / "planted-1.0-1.x86_64.rpm").write_text("")
        result = self.run_guard("wayland")
        self.assertNotEqual(result.returncode, 0)

    def test_an_empty_expected_name_is_refused(self) -> None:
        self.rpm("libwayland-client-1.24.0-1.hum1.bfin.x86_64.rpm", "wayland-1.24.0-1.hum1.bfin.src.rpm")
        self.assertNotEqual(self.run_guard("").returncode, 0)


class LaneTests(unittest.TestCase):
    def test_every_lane_guards_before_it_lists_for_upload(self) -> None:
        for lane, script in LANES.items():
            with self.subTest(lane=lane):
                text = script.read_text()
                guard = text.find("bash /tools/check_rpm_source.sh")
                listing = text.find(UPLOAD_LISTING)
                self.assertGreater(guard, -1, f"{lane} lane never runs the guard")
                self.assertGreater(listing, -1, f"{lane} lane never lists its output")
                self.assertLess(guard, listing, f"{lane} lane uploads before it checks")

    def test_each_lane_takes_its_expected_name_from_trusted_input(self) -> None:
        hermetic = LANES["hermetic"].read_text()
        self.assertIn('rpm -qp --nosignature --qf "%{NAME}" "$srpm"', hermetic)
        container = LANES["container"].read_text()
        self.assertIn('rpmspec -q --srpm --qf "%{NAME}\\n"', container)
        self.assertIn('bash /tools/check_rpm_source.sh "$expected_source" /work/result', container)

    def test_the_mock_lane_guards_before_it_lists_for_upload(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "build-stage.yml").read_text()
        start = workflow.index("- name: Build the verified source in a mock root")
        step = workflow[start : workflow.index("\n      - name:", start)]
        guard = step.find("bash /tools/check_rpm_source.sh")
        listing = step.find(UPLOAD_LISTING)
        self.assertGreater(guard, -1, "mock lane never runs the guard")
        self.assertGreater(listing, -1, "mock lane never lists its output")
        self.assertLess(guard, listing, "mock lane uploads before it checks")
        self.assertIn('/work/srpm/*.src.rpm', step[guard:listing])
        self.assertIn('"$PWD/tools:/tools:ro,Z"', step)


if __name__ == "__main__":
    unittest.main()
