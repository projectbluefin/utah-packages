#!/usr/bin/env python3
"""Unit coverage for the queue-wait observability tool.

Issue #304 wants queue-wait to be a watched metric rather than an anecdote.
:mod:`tools.queue_wait` keeps its parsing, percentile and threshold logic pure
so it can be tested without hitting the Actions API; the network layer
(:func:`queue_wait.measure`) is exercised only by the scheduled workflow. These
tests pin the semantics that are easy to get wrong: which jobs count toward
queue wait, how percentiles behave on small samples, and that an unmeasurable
run is reported as a gap rather than a zero wait.
"""

import argparse
import json
import urllib.error
import unittest
from datetime import timedelta
from unittest.mock import patch

from tools import queue_wait as qw


class ParseTimestampTests(unittest.TestCase):
    def test_trailing_z_is_utc(self):
        value = qw.parse_timestamp("2026-09-28T12:00:00Z")
        self.assertEqual(value.minute, 0)
        self.assertEqual(value.tzinfo.utcoffset(value), timedelta(hours=0))

    def test_offset_is_normalised_to_utc(self):
        value = qw.parse_timestamp("2026-09-28T13:00:00+01:00")
        self.assertEqual(value.hour, 12)

    def test_missing_value_is_none(self):
        self.assertIsNone(qw.parse_timestamp(None))
        self.assertIsNone(qw.parse_timestamp(""))

    def test_zero_offset_equals_z(self):
        self.assertEqual(
            qw.parse_timestamp("2026-09-28T12:00:00Z"),
            qw.parse_timestamp("2026-09-28T12:00:00+00:00"),
        )


class FirstStartedAtTests(unittest.TestCase):
    def test_earliest_started_job_wins(self):
        jobs = [
            {"name": "prepare", "started_at": "2026-09-28T12:05:00Z"},
            {"name": "rebuild0", "started_at": "2026-09-28T12:07:00Z"},
        ]
        started = qw.first_started_at(jobs)
        self.assertEqual(started.hour, 12)
        self.assertEqual(started.minute, 5)

    def test_skipped_jobs_without_started_at_are_ignored(self):
        jobs = [
            {"name": "prepare", "started_at": "2026-09-28T12:05:00Z"},
            {"name": "skipped", "started_at": None},
            {"name": "never", "started_at": None},
        ]
        started = qw.first_started_at(jobs)
        self.assertEqual(started.minute, 5)

    def test_no_started_jobs_returns_none(self):
        self.assertIsNone(qw.first_started_at([]))
        self.assertIsNone(qw.first_started_at([{"started_at": None}]))

    def test_skipped_job_timestamps_do_not_end_the_queue_wait(self):
        skipped = {"conclusion": "skipped", "created_at": "2026-10-07T03:54:45Z",
                   "started_at": "2026-10-07T03:54:45Z"}
        actual = {"started_at": "2026-10-07T03:57:18Z"}
        self.assertEqual(qw.first_started_at([skipped, actual]).minute, 57)
        self.assertIsNone(qw.first_started_at([skipped]))
        self.assertIsNone(qw.job_wait_seconds(skipped))


class QueueWaitTests(unittest.TestCase):
    def test_wait_is_started_minus_created(self):
        run = {"created_at": "2026-09-28T12:00:00Z"}
        jobs = [{"started_at": "2026-09-28T12:30:00Z"}]
        self.assertEqual(qw.queue_wait_seconds(run, jobs), 1800.0)

    def test_run_without_created_is_unmeasurable(self):
        self.assertIsNone(qw.queue_wait_seconds({}, [{"started_at": "2026-09-28T12:30:00Z"}]))

    def test_run_that_never_started_is_unmeasurable_not_zero(self):
        # A cancelled-before-start run must read as a gap, not a fast queue.
        self.assertIsNone(qw.queue_wait_seconds({"created_at": "2026-09-28T12:00:00Z"}, []))

    def test_missing_jobs_is_a_gap_not_a_zero_wait(self):
        # jobs=None means the jobs endpoint could not be read for this run.
        self.assertIsNone(qw.queue_wait_seconds({"created_at": "2026-09-28T12:00:00Z"}, None))


class PercentileTests(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(qw.percentile([], 50), 0.0)

    def test_single_value(self):
        self.assertEqual(qw.percentile([42.0], 90), 42.0)

    def test_median_of_even_set_interpolates(self):
        # p50 of [1,2,3,4] is the mean of the two middle values.
        self.assertEqual(qw.percentile([1.0, 2.0, 3.0, 4.0], 50), 2.5)

    def test_p90_of_ten_values(self):
        values = [float(i) for i in range(10)]
        # rank = 0.9 * 9 = 8.1 -> value[8] + 0.1*(value[9]-value[8]) = 8.1
        self.assertAlmostEqual(qw.percentile(values, 90), 8.1)

    def test_sorted_input_is_not_required(self):
        self.assertEqual(qw.percentile([3.0, 1.0, 2.0], 50), 2.0)


class SummarizeTests(unittest.TestCase):
    def _records(self):
        return [
            {"workflow": "main", "run_number": 1, "head_branch": "main", "conclusion": "success", "wait_seconds": 600.0},
            {"workflow": "main", "run_number": 2, "head_branch": "main", "conclusion": "success", "wait_seconds": 1800.0},
            {"workflow": "main", "run_number": 3, "head_branch": "feature", "conclusion": None, "wait_seconds": None},
            {"workflow": "other", "run_number": 10, "head_branch": "main", "conclusion": "success", "wait_seconds": 300.0},
        ]

    def test_overall_excludes_unmeasurable_but_counts_them(self):
        report = qw.summarize(self._records())
        self.assertEqual(report["runs_observed"], 4)
        self.assertEqual(report["runs_measured"], 3)
        # p50 over the two measured main runs plus the one other run.
        self.assertEqual(report["overall"]["runs_measured"], 3)

    def test_per_workflow_breakdown(self):
        report = qw.summarize(self._records())
        self.assertIn("main", report["workflows"])
        self.assertIn("other", report["workflows"])
        self.assertEqual(report["workflows"]["other"]["runs_measured"], 1)

    def test_worst_offender_is_named(self):
        report = qw.summarize(self._records())
        worst = report["overall"]["worst"]
        self.assertEqual(worst["run_number"], 2)
        self.assertEqual(worst["wait_seconds"], 1800.0)

    def test_threshold_exceeded_flag(self):
        report = qw.summarize(self._records(), threshold_seconds=900)
        # p50 of [600, 1800, 300] is 600, below 900: not exceeded overall.
        self.assertFalse(report["threshold_exceeded"])

    def test_threshold_fires_when_p50_above(self):
        records = [
            {"workflow": "main", "run_number": i, "head_branch": "main", "conclusion": "success", "wait_seconds": float(sec)}
            for i, sec in enumerate([1200, 1800, 2400])
        ]
        report = qw.summarize(records, threshold_seconds=900)
        self.assertTrue(report["threshold_exceeded"])
        self.assertTrue(report["overall"]["threshold_exceeded"])

    def test_no_threshold_means_never_exceeded(self):
        report = qw.summarize(self._records(), threshold_seconds=None)
        self.assertIsNone(report["threshold_seconds"])
        self.assertFalse(report["threshold_exceeded"])


class CoerceSecondsTests(unittest.TestCase):
    def test_plain_seconds(self):
        self.assertEqual(qw._coerce_seconds("1800"), 1800.0)

    def test_minutes(self):
        self.assertEqual(qw._coerce_seconds("30m"), 1800.0)
        self.assertEqual(qw._coerce_seconds("90 minutes"), 5400.0)

    def test_hours(self):
        self.assertEqual(qw._coerce_seconds("2h"), 7200.0)

    def test_invalid_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            qw._coerce_seconds("nope")


class JobWaitTests(unittest.TestCase):
    def test_wait_is_started_minus_created(self):
        job = {"created_at": "2026-09-28T12:00:00Z", "started_at": "2026-09-28T12:05:00Z"}
        self.assertEqual(qw.job_wait_seconds(job), 300.0)

    def test_missing_created_is_none(self):
        self.assertIsNone(qw.job_wait_seconds({"started_at": "2026-09-28T12:05:00Z"}))

    def test_missing_started_is_none(self):
        self.assertIsNone(qw.job_wait_seconds({"created_at": "2026-09-28T12:00:00Z"}))


class FetchRunsPaginationTests(unittest.TestCase):
    def test_walks_pages_until_limit(self):
        # Each page returns one run; the third page is empty, so a request for
        # limit=2 must fetch pages 1 and 2 and confirm page 3 is empty.
        pages = {1: [1], 2: [2], 3: []}
        captured = []

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                params = dict(p.split("=") for p in captured[-1].split("?")[1].split("&"))
                page = int(params["page"])
                body = json.dumps({"workflow_runs": [{"id": i} for i in pages.get(page, [])]})
                return body.encode()

        def _capture(request, *_, **__):
            captured.append(request.get_full_url())
            return _Resp()

        with patch.object(qw.urllib.request, "urlopen", side_effect=_capture):
            runs = qw.fetch_runs("tok", "o", "r", "wf.yml", limit=2)
        self.assertEqual([r["id"] for r in runs], [1, 2])
        # Two runs came from two pages; the loop stops as soon as limit is met,
        # so it never fetches a confirming empty third page.
        self.assertEqual(len(captured), 2)
        self.assertIn("page=1", captured[0])
        self.assertIn("page=2", captured[1])

    def test_fetches_empty_confirming_page_then_stops(self):
        # limit larger than what exists: pages 1 and 2 return runs, page 3 is
        # empty, so the loop fetches page 3, sees nothing, and breaks.
        pages = {1: [1, 2], 2: [3], 3: []}
        captured = []

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                params = dict(p.split("=") for p in captured[-1].split("?")[1].split("&"))
                page = int(params["page"])
                return json.dumps({"workflow_runs": [{"id": i} for i in pages.get(page, [])]}).encode()

        def _capture(request, *_, **__):
            captured.append(request.get_full_url())
            return _Resp()

        with patch.object(qw.urllib.request, "urlopen", side_effect=_capture):
            runs = qw.fetch_runs("tok", "o", "r", "wf.yml", limit=5)
        self.assertEqual([r["id"] for r in runs], [1, 2, 3])
        self.assertEqual(len(captured), 3)
        self.assertIn("page=3", captured[2])

    def test_stops_at_limit_without_extra_request(self):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                return b'{"workflow_runs": [{"id": 1}, {"id": 2}]}'

        captured = []

        def _capture(request, *_, **__):
            captured.append(request.get_full_url())
            return _Resp()

        with patch.object(qw.urllib.request, "urlopen", side_effect=_capture):
            runs = qw.fetch_runs("tok", "o", "r", "wf.yml", limit=2)
        self.assertEqual(len(runs), 2)
        # One page of two satisfied the limit; no second request was made.
        self.assertEqual(len(captured), 1)


class PerJobSummaryTests(unittest.TestCase):
    def test_empty_per_job_is_zeroed(self):
        report = qw.summarize([], per_job=[])
        self.assertEqual(report["per_job"]["jobs_measured"], 0)
        self.assertEqual(report["per_job"]["by_runner_pool"], {})

    def test_buckets_by_runner_pool_not_ephemeral_runner_id(self):
        # Ephemeral hosted runners give every job a fresh runner_id; jobs that
        # share runs-on labels must still land in one pool bucket.
        per_job = [
            {"runner_pool": "ubuntu-24.04", "runner_id": 1, "wait_seconds": 100.0},
            {"runner_pool": "ubuntu-24.04", "runner_id": 2, "wait_seconds": 300.0},
            {"runner_pool": "ubuntu-24.04-arm", "runner_id": 3, "wait_seconds": 600.0},
        ]
        report = qw.summarize([], per_job=per_job)
        pj = report["per_job"]
        self.assertEqual(pj["jobs_measured"], 3)
        self.assertEqual(set(pj["by_runner_pool"]), {"ubuntu-24.04", "ubuntu-24.04-arm"})
        self.assertEqual(pj["by_runner_pool"]["ubuntu-24.04"]["jobs"], 2)
        self.assertEqual(pj["by_runner_pool"]["ubuntu-24.04-arm"]["max_seconds"], 600.0)

    def test_none_waits_are_excluded(self):
        per_job = [
            {"runner_pool": "ubuntu-24.04", "wait_seconds": 100.0},
            {"runner_pool": "ubuntu-24.04", "wait_seconds": None},
        ]
        report = qw.summarize([], per_job=per_job)
        self.assertEqual(report["per_job"]["jobs_measured"], 1)


class RenderStepSummaryTests(unittest.TestCase):
    def test_names_worst_runner_pool_from_summarize_output(self):
        # Pins the summary to the key summarize() actually writes
        # (by_runner_pool); a renamed key would silently drop this line.
        per_job = [
            {"runner_pool": "ubuntu-24.04", "wait_seconds": 60.0},
            {"runner_pool": "ubuntu-24.04", "wait_seconds": 120.0},
            {"runner_pool": "ubuntu-24.04-arm", "wait_seconds": 600.0},
        ]
        waits = [{"workflow": "wf.yml", "run_number": 7, "head_branch": "main",
                  "conclusion": "success", "wait_seconds": 300.0}]
        text = qw.render_step_summary(qw.summarize(waits, per_job=per_job))
        self.assertIn("Per-job (per runner pool)", text)
        self.assertIn("Worst runner pool `ubuntu-24.04-arm`: 1 jobs, max 10.0 min wait.", text)
        self.assertIn("Worst: run #7 (main)", text)
        self.assertIn("No threshold set", text)

    def test_no_jobs_omits_per_job_lines(self):
        text = qw.render_step_summary(qw.summarize([], per_job=[]))
        self.assertNotIn("Per-job", text)
        self.assertNotIn("Worst runner pool", text)

    def test_threshold_exceeded_alerts(self):
        waits = [{"workflow": "wf.yml", "run_number": 1, "head_branch": "main",
                  "conclusion": "success", "wait_seconds": 3600.0}]
        text = qw.render_step_summary(qw.summarize(waits, threshold_seconds=1800.0))
        self.assertIn(":rotating_light:", text)
        self.assertIn("30 min threshold", text)

    def test_cli_renders_without_token(self):
        import tempfile
        from pathlib import Path
        report = qw.summarize([], per_job=[{"runner_pool": "p", "wait_seconds": 60.0}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.json"
            path.write_text(json.dumps(report))
            with patch("sys.argv", ["queue_wait.py", "--render-summary", str(path)]), \
                 patch.dict("os.environ", {"GITHUB_TOKEN": ""}), \
                 patch("sys.stdout") as out:
                self.assertEqual(qw.main(), 0)
        written = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertIn("Worst runner pool `p`", written)



class MainHttpErrorTests(unittest.TestCase):
    """API failures exit 2 so they are never mistaken for the threshold alert (1)."""

    def _run(self, error):
        import io
        err = io.StringIO()
        with patch("sys.argv", ["queue_wait.py", "--token", "tok"]), \
             patch.object(qw, "measure", side_effect=error), \
             patch("sys.stderr", err):
            code = qw.main()
        return code, err.getvalue()

    def _error(self, code, headers=None):
        return urllib.error.HTTPError("url", code, "reason", headers or {}, None)

    def test_server_error_exits_2(self):
        code, msg = self._run(self._error(502))
        self.assertEqual(code, 2)
        self.assertIn("502", msg)

    def test_429_reports_rate_limit(self):
        code, msg = self._run(self._error(429))
        self.assertEqual(code, 2)
        self.assertIn("rate limited", msg)

    def test_403_secondary_rate_limit_is_not_a_permission_error(self):
        code, msg = self._run(self._error(403, {"Retry-After": "60"}))
        self.assertEqual(code, 2)
        self.assertIn("rate limited", msg)
        self.assertNotIn("actions: read", msg)

    def test_403_exhausted_quota_is_rate_limit(self):
        code, msg = self._run(self._error(403, {"X-RateLimit-Remaining": "0"}))
        self.assertIn("rate limited", msg)

    def test_403_without_rate_limit_headers_is_permissions(self):
        code, msg = self._run(self._error(403))
        self.assertEqual(code, 2)
        self.assertIn("actions: read", msg)

    def test_401_exits_2(self):
        code, msg = self._run(self._error(401))
        self.assertEqual(code, 2)
        self.assertIn("token", msg)


class RunnerPoolTests(unittest.TestCase):
    def test_labels_name_the_pool_order_independent(self):
        self.assertEqual(
            qw.runner_pool({"labels": ["x64", "self-hosted"], "runner_group_name": "Default"}),
            "self-hosted,x64",
        )

    def test_falls_back_to_group_then_unknown(self):
        self.assertEqual(qw.runner_pool({"labels": [], "runner_group_name": "GitHub Actions"}), "GitHub Actions")
        self.assertEqual(qw.runner_pool({}), "unknown")


class FetchJobsTests(unittest.TestCase):
    def _serve(self, pages, total):
        captured = []

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                params = dict(p.split("=") for p in captured[-1].split("?")[1].split("&"))
                ids = pages.get(int(params["page"]), [])
                return json.dumps({"total_count": total, "jobs": [{"id": i} for i in ids]}).encode()

        def _capture(request, *_, **__):
            captured.append(request.get_full_url())
            return _Resp()

        return captured, _capture

    def test_paginates_until_total_count(self):
        # A rebuild run with more jobs than one page: later pages must not be
        # silently dropped, and no request is made past total_count.
        pages = {1: list(range(100)), 2: list(range(100, 200)), 3: list(range(200, 234))}
        captured, side_effect = self._serve(pages, total=234)
        with patch.object(qw.urllib.request, "urlopen", side_effect=side_effect):
            jobs = qw.fetch_jobs("tok", "o", "r", 1)
        self.assertEqual(len(jobs), 234)
        self.assertEqual(len(captured), 3)
        self.assertIn("page=3", captured[2])

    def test_stops_on_empty_page_even_if_total_overstates(self):
        captured, side_effect = self._serve({1: [1, 2]}, total=5)
        with patch.object(qw.urllib.request, "urlopen", side_effect=side_effect):
            jobs = qw.fetch_jobs("tok", "o", "r", 1)
        self.assertEqual([j["id"] for j in jobs], [1, 2])
        self.assertEqual(len(captured), 2)

    def test_404_yields_no_jobs(self):
        def _raise(*_args, **_kwargs):
            raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)

        with patch.object(qw.urllib.request, "urlopen", side_effect=_raise):
            self.assertEqual(qw.fetch_jobs("tok", "o", "r", 1), [])

    def test_request_carries_the_per_page_shape(self):
        # PER_PAGE is a constant precisely so this request shape is assertable;
        # pin it so a refactor that hard-codes the page size cannot silently
        # drop the parameter and silently truncate the result.
        captured = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                return b'{"jobs": []}'

        def _capture(request, *_, **__):
            captured["url"] = request.get_full_url()
            return _Resp()

        with patch.object(qw.urllib.request, "urlopen", side_effect=_capture):
            self.assertEqual(qw.fetch_jobs("tok", "o", "r", 1), [])
        self.assertIn(f"per_page={qw.PER_PAGE}", captured["url"])


if __name__ == "__main__":
    unittest.main()
