#!/usr/bin/env python3
"""A failed %check is retried once, in both build lanes, and only %check.

One flaky test (fish) used to hold back a whole factory run. build-stage.yml
now reruns a package build once when rpmbuild reports a bad exit status from
%check, and reports the retry. Repeated mistake 11: the container lane and the
mock lane must agree, so both are asserted here.
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parent.parent
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"
CHECK_FAILURE = re.compile(r'grep -qE "Bad exit status from \.\*\\\(%check\\\)" (\S+)')


def step(name: str) -> dict:
    workflow = yaml.safe_load(BUILD_STAGE.read_text())
    return next(
        s for s in workflow["jobs"]["build"]["steps"] if s.get("name") == name
    )


LANES = {
    "container": "Build the verified source with its RPM recipe",
    "mock": "Build the verified source in a mock root",
}


class CheckRetryTests(unittest.TestCase):
    def test_both_lanes_retry_only_a_check_failure(self) -> None:
        for lane, name in LANES.items():
            with self.subTest(lane=lane):
                script = step(name)["run"]
                self.assertRegex(script, CHECK_FAILURE, "retry must key on a %check failure")
                self.assertIn("title=flaky %check retry::", script)
                self.assertIn("title=flaky %check::", script)
                self.assertIn("/work/reports/flaky-check", script)

    def test_each_lane_retries_exactly_once(self) -> None:
        # One retry, not a loop: a %check that fails twice is a real failure.
        for lane, name in LANES.items():
            with self.subTest(lane=lane):
                script = step(name)["run"]
                build = "build_ba" if lane == "container" else "mock_rebuild"
                calls = re.findall(rf"^\s*{build} \|\| status=\$\?$", script, re.MULTILINE)
                self.assertEqual(len(calls), 2, f"{lane}: first attempt plus one retry")
                self.assertNotRegex(script, rf"for .* in .*\n\s*{build}")

    def test_the_failure_status_is_still_what_fails_the_job(self) -> None:
        container = step(LANES["container"])["run"]
        self.assertIn('exit "$status"', container)
        mock = step(LANES["mock"])["run"]
        self.assertIn('test "$status" -eq 0', mock)

    def test_the_retry_reaches_the_job_summary(self) -> None:
        report = step("Report a %check that passed only on its retry")
        self.assertEqual(report.get("if"), "always()")
        self.assertIn("work/reports/flaky-check", report["run"])
        self.assertIn("GITHUB_STEP_SUMMARY", report["run"])

    def test_the_pattern_matches_what_rpmbuild_prints(self) -> None:
        """The grep in the workflow, run against real rpmbuild output."""
        pattern = CHECK_FAILURE.search(step(LANES["container"])["run"])
        self.assertIsNotNone(pattern)
        regex = re.search(r'grep -qE "([^"]+)"', pattern.group(0)).group(1)
        samples = {
            "error: Bad exit status from /var/tmp/rpm-tmp.Ab12Cd (%check)\n": True,
            "RPM build errors:\n    Bad exit status from /var/tmp/rpm-tmp.x (%check)\n": True,
            "error: Bad exit status from /var/tmp/rpm-tmp.Ab12Cd (%build)\n": False,
            "error: Bad exit status from /var/tmp/rpm-tmp.Ab12Cd (%install)\n": False,
        }
        for text, expected in samples.items():
            with self.subTest(text=text.strip()), tempfile.NamedTemporaryFile("w") as log:
                log.write(text)
                log.flush()
                found = subprocess.run(["grep", "-qE", regex, log.name]).returncode == 0
                self.assertEqual(found, expected)


if __name__ == "__main__":
    unittest.main()


class CanaryFlakyCheckTests(unittest.TestCase):
    """The canary proves the retry by failing a %check once on purpose."""

    def test_the_injection_is_canary_only_and_edits_the_staged_copy(self) -> None:
        script = step(LANES["container"])["run"]
        self.assertIn('if [ -n "${FLAKY_CHECK:-}" ]; then', script)
        self.assertIn('spec="$staged/$(basename "$spec")"', script)
        workflow = yaml.safe_load(BUILD_STAGE.read_text())
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(triggers["workflow_call"]["inputs"]["flaky_check"]["default"], "")

    def test_the_injected_line_fails_once_then_passes(self) -> None:
        """Run the workflow's own sed on a spec, then the %check line twice."""
        script = step(LANES["container"])["run"]
        sed = re.search(r'sed -i ("0,/\^%check/[^"]+") "\$spec"', script).group(1)
        with tempfile.TemporaryDirectory() as directory:
            spec = Path(directory) / "demo.spec"
            spec.write_text("Name: demo\n%build\ntrue\n%check\nmake check\n")
            marker = Path(directory) / "marker"
            program = sed.replace("\\/tmp\\/canary-flaky-check", str(marker).replace("/", "\\/"))
            subprocess.run(["bash", "-c", f'sed -i {program} "$0"', str(spec)], check=True)
            injected = spec.read_text().splitlines()[4]
            self.assertIn("exit 1", injected)
            first = subprocess.run(["bash", "-c", injected])
            second = subprocess.run(["bash", "-c", injected])
        self.assertEqual((first.returncode, second.returncode), (1, 0))

    def test_a_flaky_package_never_restores_from_the_cache(self) -> None:
        text = BUILD_STAGE.read_text()
        self.assertEqual(
            text.count("!contains(fromJSON(inputs.flaky_check || '[]'), matrix.package)"), 3
        )
