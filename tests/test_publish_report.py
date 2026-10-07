#!/usr/bin/env python3
"""Coverage for the run-report path of tools/publish_gate.py.

rebuild-rpms.yml turns a factory run into two human-readable artefacts: the
job summary the ``assemble`` step prints, and the tracking-issue body the
``report`` subcommand writes. Both say, per package, what a consumer actually
gets when a build did not publish -- the previous build, the previous build it
lost precedence to, or nothing at all. Getting that wrong is silent: the
workflow still succeeds and the wrong sentence is what a maintainer reads.

``summary`` had no test at all, ``render_report`` was exercised for two of its
four publication outcomes, and ``main``'s ``report``/``marker``/``pattern``
dispatch was never driven. These cases cover the rendering decisions and the
command line the workflow calls, using no RPMs and no rpm(8): every function
here is pure apart from the files ``report`` writes.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools.publish_gate import (
    Assembly,
    artifact_pattern,
    failed_marker,
    main,
    render_report,
    summary,
)


class SummaryTests(unittest.TestCase):
    """``summary`` -- the job summary the assemble step prints."""

    def test_names_every_replaced_source_when_the_list_is_short(self) -> None:
        text = summary(Assembly(replaced=["fish", "gtk4"]))
        self.assertIn("Replaced 2 source package(s): `fish`, `gtk4`", text)

    def test_counts_without_naming_when_more_than_forty_were_replaced(self) -> None:
        names = [f"pkg{n:03d}" for n in range(41)]
        text = summary(Assembly(replaced=names))
        self.assertIn("Replaced 41 source package(s).", text)
        self.assertNotIn("pkg000", text)

    def test_says_nothing_about_failures_when_every_package_built(self) -> None:
        text = summary(Assembly(replaced=["fish"]))
        self.assertNotIn("failed and were not replaced", text)
        self.assertNotIn("| package |", text)

    def test_reports_zero_replacements_without_a_name_list(self) -> None:
        text = summary(Assembly())
        self.assertIn("Replaced 0 source package(s).", text)

    def test_tells_a_reader_what_consumers_get_for_each_failed_package(self) -> None:
        text = summary(
            Assembly(
                replaced=["gtk4"],
                failed=["fish", "libbar", "wayland"],
                kept_previous=["fish"],
                absent=["libbar"],
                losers=["wayland"],
            )
        )
        self.assertIn("**3 package(s) failed and were not replaced:**", text)
        self.assertIn("| `fish` | previous build |", text)
        self.assertIn("| `libbar` | nothing: never published |", text)
        self.assertIn(
            "| `wayland` | previous build (this build lost precedence) |", text
        )

    def test_precedence_wins_over_kept_previous_for_the_same_package(self) -> None:
        """A loser that also has a previous build is named as a loser.

        Both are true of it; only the precedence sentence explains why a
        package that *built* is not in the repository.
        """
        text = summary(
            Assembly(failed=["wayland"], kept_previous=["wayland"], losers=["wayland"])
        )
        self.assertIn(
            "| `wayland` | previous build (this build lost precedence) |", text
        )
        self.assertNotIn("| `wayland` | previous build |", text)

    def test_ends_with_a_newline_so_it_appends_cleanly_to_the_job_summary(self) -> None:
        self.assertTrue(summary(Assembly(replaced=["fish"])).endswith("\n"))


class RenderReportTests(unittest.TestCase):
    """``render_report`` -- the tracking-issue body, one per run."""

    def render(self, **kwargs) -> str:
        defaults = {
            "failed": [],
            "publish_result": "success",
            "publish_report": None,
            "digest": "",
            "run_url": "https://github.com/projectbluefin/utah-packages/actions/runs/1",
        }
        return render_report(**{**defaults, **kwargs})

    def test_says_the_tag_moved_and_how_many_sources_it_carried(self) -> None:
        body = self.render(
            digest="sha256:" + "a" * 64,
            publish_report={"replaced": ["fish", "gtk4"]},
        )
        self.assertIn(f"Published `sha256:{'a' * 64}`, replacing 2 source package(s).", body)

    def test_reports_a_successful_run_that_had_nothing_to_publish(self) -> None:
        body = self.render(publish_result="success")
        self.assertIn("Nothing new to publish; the published image is unchanged.", body)

    def test_reports_a_blocked_transaction_as_holding_back_everything(self) -> None:
        body = self.render(publish_result="failure")
        self.assertIn("**Not published.**", body)
        self.assertIn("Hummingbird-only consumer transaction", body)

    def test_names_the_publish_job_outcome_when_it_neither_passed_nor_failed(self) -> None:
        body = self.render(publish_result="cancelled")
        self.assertIn("**Not published** (publish job: cancelled).", body)

    def test_says_the_publish_job_did_not_run_when_it_has_no_outcome(self) -> None:
        body = self.render(publish_result="")
        self.assertIn("**Not published** (publish job: did not run).", body)

    def test_a_digest_is_reported_even_when_the_publish_result_is_empty(self) -> None:
        """The digest is the fact; the job outcome string is not.

        publish-repository.yml is a reusable workflow, so the caller can see a
        digest output without the ``result`` the report job reads.
        """
        body = self.render(digest="sha256:" + "b" * 64, publish_result="")
        self.assertIn("Published `sha256:", body)
        self.assertNotIn("did not run", body)

    def test_states_what_consumers_get_for_each_failed_package(self) -> None:
        body = self.render(
            failed=["fish", "libbar", "wayland"],
            publish_result="failure",
            publish_report={
                "kept_previous": ["fish"],
                "absent": ["libbar"],
                "precedence_losers": ["wayland"],
            },
        )
        self.assertIn("**3 package(s) failed this run:**", body)
        self.assertIn("| `fish` | previous build |", body)
        self.assertIn("| `libbar` | nothing: never published |", body)
        self.assertIn(
            "| `wayland` | previous build (this build lost precedence) |", body
        )

    def test_hedges_when_no_publish_report_says_whether_a_build_was_published(self) -> None:
        """With no publish report the run cannot know, and must not claim."""
        body = self.render(failed=["fish"], publish_result="failure")
        self.assertIn("| `fish` | previous build, if one was published |", body)

    def test_says_so_plainly_when_every_selected_package_built(self) -> None:
        body = self.render(failed=[], digest="sha256:" + "c" * 64,
                           publish_report={"replaced": ["fish"]})
        self.assertIn("Every selected package built.", body)
        self.assertNotIn("| package |", body)

    def test_carries_the_run_url_so_the_issue_links_back(self) -> None:
        body = self.render(run_url="https://example.invalid/run/7")
        self.assertIn("Run: https://example.invalid/run/7", body)


class FailedMarkerTests(unittest.TestCase):
    """``failed_marker`` -- what the previous report recorded, re-read."""

    def test_round_trips_the_failed_list_a_report_embedded(self) -> None:
        body = render_report(
            failed=["fish", "gtk4"], publish_result="failure", publish_report=None,
            digest="", run_url="",
        )
        self.assertEqual(failed_marker(body), ["fish", "gtk4"])

    def test_round_trips_an_empty_failed_list_rather_than_reporting_none(self) -> None:
        """``[]`` and "no marker" are different states and must stay different."""
        body = render_report(
            failed=[], publish_result="success", publish_report=None,
            digest="", run_url="",
        )
        self.assertEqual(failed_marker(body), [])

    def test_returns_none_for_a_body_with_no_marker(self) -> None:
        self.assertIsNone(failed_marker("an issue somebody edited by hand"))

    def test_returns_none_for_an_empty_or_absent_body(self) -> None:
        self.assertIsNone(failed_marker(""))
        self.assertIsNone(failed_marker(None))

    def test_reads_the_marker_out_of_surrounding_prose(self) -> None:
        body = 'intro\n<!-- failed: ["fish"] -->\ntrailing comment\n'
        self.assertEqual(failed_marker(body), ["fish"])


class ArtifactPatternTests(unittest.TestCase):
    """``artifact_pattern`` -- the download-artifact glob per wave."""

    def test_an_empty_wave_downloads_every_rpm_artifact(self) -> None:
        self.assertEqual(artifact_pattern("", "utah-"), "utah-rpm-*")

    def test_wave_zero_is_spelled_out_because_brace_alternation_needs_two(self) -> None:
        self.assertEqual(artifact_pattern("0", ""), "rpm-s0-*")

    def test_a_later_wave_expands_to_every_wave_up_to_and_including_it(self) -> None:
        self.assertEqual(artifact_pattern("3", ""), "rpm-s{0,1,2,3}-*")


class CommandLineTests(unittest.TestCase):
    """``main`` -- the subcommands rebuild-rpms.yml actually runs."""

    def test_pattern_prints_a_github_output_assignment(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["pattern", "--wave", "2", "--prefix", "utah-"]), 0)
        self.assertEqual(out.getvalue(), "pattern=utah-rpm-s{0,1,2}-*\n")

    def test_marker_prints_the_failed_list_as_compact_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = Path(tmp) / "body.md"
            body.write_text('<!-- failed: ["fish", "gtk4"] -->\n')
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["marker", str(body)]), 0)
        self.assertEqual(out.getvalue(), '["fish","gtk4"]\n')

    def test_marker_prints_null_for_a_body_that_carries_no_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = Path(tmp) / "body.md"
            body.write_text("hand-written\n")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["marker", str(body)]), 0)
        self.assertEqual(out.getvalue(), "null\n")

    def test_failures_prints_the_selected_packages_with_no_rpm_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts.json"
            artifacts.write_text(json.dumps(["utah-rpm-s0-fish", "utah-log-s0-gtk4"]))
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(
                    main([
                        "failures",
                        "--build-list", json.dumps(["fish", "gtk4"]),
                        "--artifacts", str(artifacts),
                        "--prefix", "utah-",
                    ]),
                    0,
                )
        self.assertEqual(json.loads(out.getvalue()), ["gtk4"])

    def test_failures_counts_a_precedence_loser_that_did_upload_an_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts.json"
            artifacts.write_text(json.dumps(["rpm-s0-fish", "rpm-s0-wayland"]))
            out = io.StringIO()
            with redirect_stdout(out):
                main([
                    "failures",
                    "--build-list", json.dumps(["fish", "wayland"]),
                    "--artifacts", str(artifacts),
                    "--losers", json.dumps(["wayland"]),
                ])
        self.assertEqual(json.loads(out.getvalue()), ["wayland"])

    def run_report(self, tmp: Path, **overrides) -> tuple[str, list[str]]:
        artifacts = tmp / "artifacts.json"
        artifacts.write_text(json.dumps(overrides.pop("artifacts", ["rpm-s0-fish"])))
        output = tmp / "report.md"
        failed_output = tmp / "failed.json"
        argv = [
            "report",
            "--build-list", json.dumps(overrides.pop("build_list", ["fish", "gtk4"])),
            "--artifacts", str(artifacts),
            "--output", str(output),
            "--failed-output", str(failed_output),
            "--run-url", "https://example.invalid/run/9",
        ]
        for flag, value in overrides.items():
            argv += [f"--{flag.replace('_', '-')}", value]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(argv), 0)
        return output.read_text(), json.loads(failed_output.read_text())

    def test_report_writes_the_issue_body_and_the_failed_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body, failed = self.run_report(Path(tmp), publish_result="failure")
        self.assertEqual(failed, ["gtk4"])
        self.assertIn("**1 package(s) failed this run:**", body)
        self.assertIn("Run: https://example.invalid/run/9", body)
        self.assertEqual(failed_marker(body), ["gtk4"])

    def test_report_uses_the_publish_report_to_say_what_consumers_get(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body, _ = self.run_report(
                Path(tmp),
                publish_result="success",
                digest="sha256:" + "d" * 64,
                publish_report=json.dumps(
                    {"replaced": ["fish"], "absent": ["gtk4"]}
                ),
            )
        self.assertIn("Published `sha256:", body)
        self.assertIn("| `gtk4` | nothing: never published |", body)

    def test_report_records_an_empty_failed_list_when_everything_built(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body, failed = self.run_report(
                Path(tmp),
                artifacts=["rpm-s0-fish", "rpm-s0-gtk4"],
                publish_result="success",
                digest="sha256:" + "e" * 64,
            )
        self.assertEqual(failed, [])
        self.assertIn("Every selected package built.", body)


if __name__ == "__main__":
    unittest.main()
