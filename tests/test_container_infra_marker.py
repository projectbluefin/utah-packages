#!/usr/bin/env python3
"""The container lane marks a package-server outage for the bump gate (#1179).

with_backoff in tools/dnf_backoff.sh retries a dnf call that the Hummingbird
host refused. When the last attempt still fails on a download, it writes
infra-failure, so the bump gate does not hold a version that never got a
build. The marker lives in the shared helper, not in a copy local to
build_container.sh: a copy there was lost as soon as the script switched to
the shared helper (#1162), and these tests fail if that happens again.
"""

from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "tools" / "dnf_backoff.sh"
BUILD_CONTAINER = ROOT / "tools" / "build_container.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "build-stage.yml"


def run(output: str, failures: int) -> tuple[int, str | None, list[str]]:
    """Source the helper and run with_backoff on a command that prints
    `output` and fails `failures` times. Returns the exit code, the marker
    text (None when absent) and the waits it slept."""
    with tempfile.TemporaryDirectory() as directory:
        calls = Path(directory) / "calls"
        sleeps = Path(directory) / "sleeps"
        reports = Path(directory) / "reports"
        program = (
            f". {HELPER}\n"
            f'sleep() {{ echo "$1" >> {sleeps}; }}\n'
            "fake_dnf() {\n"
            f"  echo x >> {calls}\n"
            f"  printf '%s\\n' {shlex.quote(output)} >&2\n"
            f'  [ "$(wc -l < {calls})" -gt {failures} ] || return 7\n'
            "}\n"
            "with_backoff fake_dnf builddep foo.spec\n"
        )
        result = subprocess.run(
            ["bash", "-e", "-c", program],
            env={"REPORT_DIR": str(reports), "PATH": "/usr/bin:/bin"},
            capture_output=True, text=True,
        )
        marker = reports / "infra-failure"
        text = marker.read_text().strip() if marker.exists() else None
        waits = sleeps.read_text().split() if sleeps.exists() else []
    return result.returncode, text, waits


class ContainerInfraMarkerTests(unittest.TestCase):
    def test_an_outage_that_outlasts_the_retries_is_marked(self) -> None:
        code, marker, waits = run(
            "Status code: 503 for https://packages.redhat.com/x.rpm\n"
            "No more mirrors to try - All mirrors were already tried",
            failures=10,
        )
        self.assertEqual(code, 7)
        self.assertEqual(waits, ["5", "15", "45"])
        self.assertEqual(marker, "fake_dnf")

    def test_an_unsatisfiable_graph_is_not_marked(self) -> None:
        code, marker, _ = run("No match for argument: libfoo-devel", failures=10)
        self.assertEqual(code, 7)
        self.assertIsNone(marker)

    def test_recovered_transfer_errors_do_not_mask_a_dependency_failure(self) -> None:
        code, marker, _ = run(
            "Curl error (28): Timeout was reached\n"
            "Status code: 503 for https://example.test/package.rpm\n"
            "No match for argument: libfoo-devel",
            failures=10,
        )
        self.assertEqual(code, 7)
        self.assertIsNone(marker)

    def test_an_outage_that_clears_is_not_marked(self) -> None:
        code, marker, waits = run("Curl error (28): Timeout was reached", failures=2)
        self.assertEqual(code, 0)
        self.assertEqual(waits, ["5", "15"])
        self.assertIsNone(marker)

    def test_cache_key_dnf_failures_report_outages_not_dependency_errors(self) -> None:
        workflow = WORKFLOW.read_text()
        cache_step = workflow.split("      - name: Resolve the package cache key\n", 1)[1]
        container = cache_step.split("utah-buildroot:run bash -exc '\n", 1)[1].split(
            "\n            '\n", 1
        )[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work" / "cache").mkdir(parents=True)
            (root / "repos").mkdir()
            reports = root / "work" / "reports"
            calls = root / "calls"
            container = (
                container.replace("/work", str(root / "work"))
                .replace("/etc/yum.repos.d/", str(root / "repos") + "/")
                .replace("/tools/dnf_backoff.sh", str(HELPER))
            )
            program = """
set -e -o pipefail
sleep() { :; }
sed() { :; }
cp() { :; }
createrepo_c() { :; }
find() { case "$1" in */prior) [ "$PRIOR" = 1 ] && echo prior.rpm ;; *) echo package.spec ;; esac; return 0; }
rpm() { case "$1" in -qa) echo 1.hum1 ;; esac; return 0; }
dnf() {
  echo "$*" >> "$CALLS"
  case "$*" in *"$FAIL_ON"*) echo "$FAIL_MESSAGE" >&2; return 7 ;; esac
}
""" + container
            for target, prior in (("install createrepo_c", "1"),
                                  ("install dnf-plugins-core", "0"),
                                  ("upgrade libxml2", "0"),
                                  ("builddep -D", "0")):
                for message, expected_marker in (
                    ("Cannot download package.rpm: All mirrors were tried", True),
                    ("No match for argument: missing-devel", False),
                ):
                    with self.subTest(target=target, outage=expected_marker):
                        calls.unlink(missing_ok=True)
                        marker = reports / "infra-failure"
                        marker.unlink(missing_ok=True)
                        result = subprocess.run(
                            ["bash", "-c", program],
                            env={"PATH": "/usr/bin:/bin", "PACKAGE": "probe",
                                 "REPORT_DIR": str(reports), "CALLS": str(calls),
                                 "PRIOR": prior, "FAIL_ON": target, "FAIL_MESSAGE": message},
                            capture_output=True, text=True,
                        )
                        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
                        self.assertEqual(marker.exists(), expected_marker)
                        self.assertEqual(sum(target in line for line in calls.read_text().splitlines()), 4)

    def test_builddep_goes_through_the_shared_helper(self) -> None:
        script = BUILD_CONTAINER.read_text()
        self.assertIn(". /tools/dnf_backoff.sh", script)
        self.assertIsNone(
            re.search(r"^\s*with_backoff\(\)", script, re.M),
            "build_container.sh defines its own with_backoff; the outage marker lives in tools/dnf_backoff.sh",
        )
        self.assertRegex(script, r'(?m)^with_backoff builddep_attempt "\$spec"$')


if __name__ == "__main__":
    unittest.main()
