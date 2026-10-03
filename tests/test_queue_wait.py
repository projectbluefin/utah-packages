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


class FetchJobsTests(unittest.TestCase):
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
