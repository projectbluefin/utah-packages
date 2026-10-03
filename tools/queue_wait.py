#!/usr/bin/env python3
"""Measure CI queue wait, so runner saturation stops being anecdotal.

Issue #304 reports chronic queue saturation on the factory: a single
``webkitgtk`` build holding runners for hours with everything queued behind
it, and fix-forward rebuilds sitting pending for over an hour behind a bulk
wave. The evidence was captured by hand while shepherding a bump; the point
of this tool is to make it a number we can watch instead of a story we tell
after the fact.

"Queue wait" is the time between a run being created and its first job
actually starting to run -- the ``created_at`` of the run minus the earliest
``started_at`` among its jobs. That is the wall-clock time a contributor
spent waiting, which is exactly the saturation this issue is about.

The GitHub Actions API is the source of truth for both timestamps, so this
tool reads runs and their jobs rather than trusting anything a workflow prints.
The network calls live in :func:`measure`; the parsing, percentile and
threshold logic is pure and unit-tested here.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OWNER = "projectbluefin"
DEFAULT_REPO = "utah-packages"

# GitHub pages a run list at 100 items; a rebuild wave rarely has more than a
# handful of runs per day, so this is enough for a daily job without a second
# request. Kept as a constant so tests can assert the request shape.
PER_PAGE = 100


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 API timestamp into an aware UTC datetime.

    The API always sends UTC (a trailing ``Z``), but ``datetime.fromisoformat``
    chokes on that ``Z`` before Python 3.11. Normalise it and attach UTC so
    every subtraction happens in one timezone. A missing value (a job that was
    never scheduled) parses to ``None`` and is skipped by callers.
    """
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def first_started_at(jobs: list[dict]) -> datetime | None:
    """Earliest ``started_at`` across a run's jobs.

    A run's jobs include ones that were skipped or never queued; those have no
    ``started_at``. The queue wait ends when the first job *runs*, so only
    jobs that actually started count. Returns ``None`` when nothing started,
    which means the run was cancelled or rejected before it could queue work.
    """
    started = [
        ts
        for job in jobs
        if (ts := parse_timestamp(job.get("started_at"))) is not None
    ]
    return min(started) if started else None


def queue_wait_seconds(run: dict, jobs: list[dict] | None) -> float | None:
    """Queue wait in seconds for one run, or ``None`` if it cannot be measured.

    ``jobs`` is ``None`` when the jobs endpoint could not be read for this run;
    that is a measurement gap, not a zero wait, so it returns ``None`` rather
    than a misleadingly small number.
    """
    created = parse_timestamp(run.get("run_started_at") or run.get("created_at"))
    if created is None:
        return None
    started = first_started_at(jobs or [])
    if started is None:
        return None
    return (started - created).total_seconds()


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (the ``'linear'`` method).

    Matches numpy's default so the numbers mean the same thing a contributor
    would expect from any dashboard. An empty input is ``0.0`` so a workflow
    with no runs still produces a report instead of crashing.
    """
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _bucket(waits: list[dict], threshold_seconds: float | None) -> dict:
    seconds = [w["wait_seconds"] for w in waits if w["wait_seconds"] is not None]
    summary = {
        "runs_measured": len(seconds),
        "p50_seconds": percentile(seconds, 50),
        "p90_seconds": percentile(seconds, 90),
        "max_seconds": max(seconds) if seconds else 0.0,
        "min_seconds": min(seconds) if seconds else 0.0,
        "threshold_seconds": threshold_seconds,
        "threshold_exceeded": bool(
            threshold_seconds is not None and seconds and percentile(seconds, 50) > threshold_seconds
        ),
    }
    # The single worst offender is the signal worth naming, not just its
    # duration. It is what a contributor was waiting on.
    worst = max(
        (w for w in waits if w["wait_seconds"] is not None),
        key=lambda w: w["wait_seconds"],
        default=None,
    )
    if worst is not None:
        summary["worst"] = {
            "run_number": worst["run_number"],
            "head_branch": worst["head_branch"],
            "conclusion": worst["conclusion"],
            "wait_seconds": worst["wait_seconds"],
        }
    return summary


def summarize(waits: list[dict], threshold_seconds: float | None = None) -> dict:
    """Summarise per-run queue waits into an overall and per-workflow report.

    Each entry in ``waits`` is a dict with at least ``workflow``, ``run_number``,
    ``head_branch``, ``conclusion`` and ``wait_seconds``. ``wait_seconds`` may be
    ``None`` when the run never started a job; those are counted as observed but
    excluded from the percentile math.
    """
    measured = [w for w in waits if w["wait_seconds"] is not None]
    per_workflow: dict[str, list[dict]] = {}
    for wait in waits:
        per_workflow.setdefault(wait["workflow"], []).append(wait)

    overall_summary = _bucket(measured, threshold_seconds)
    workflows_summary = {name: _bucket(waits, threshold_seconds) for name, waits in per_workflow.items()}

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "runs_observed": len(waits),
        "runs_measured": len(measured),
        "threshold_seconds": threshold_seconds,
        "overall": overall_summary,
        "workflows": workflows_summary,
        "threshold_exceeded": overall_summary["threshold_exceeded"],
    }


def _coerce_seconds(value: str) -> float:
    text = value.strip().lower()
    multipliers = {
        "s": 1, "sec": 1, "second": 1, "seconds": 1,
        "m": 60, "min": 60, "minute": 60, "minutes": 60,
        "h": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
    }
    if text.isdigit():
        return float(text)
    for suffix, factor in multipliers.items():
        if text.endswith(suffix):
            number = text[: -len(suffix)].strip()
            if number.isdigit():
                return float(number) * factor
    raise argparse.ArgumentTypeError(f"could not parse duration '{value}'")


def _http_get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def fetch_runs(token: str, owner: str, repo: str, workflow_id: str) -> list[dict]:
    """Fetch the most recent completed runs of one workflow from the Actions API."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/workflows/{workflow_id}/runs?per_page={PER_PAGE}&status=completed"
    )
    payload = _http_get_json(url, token)
    # The runs list endpoint returns its array under "workflow_runs"; reading
    # "runs" silently returned [] and the job reported zero runs measured.
    return payload.get("workflow_runs", [])


def fetch_jobs(token: str, owner: str, repo: str, run_id: int) -> list[dict]:
    """Fetch the jobs of one run. Empty list if the run has none."""
    url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/runs/{run_id}/jobs?per_page={PER_PAGE}"
    )
    try:
        payload = _http_get_json(url, token)
    except urllib.error.HTTPError as error:
        # A run that finished before its jobs were retained, or a run the token
        # cannot read, yields no jobs. Treat that as an unmeasurable run, not a
        # fatal error, so one bad run does not sink the whole report.
        if error.code == 404:
            return []
        raise
    return payload.get("jobs", [])


def measure(
    token: str,
    owner: str,
    repo: str,
    workflow_ids: list[str],
    runs_per_workflow: int = 50,
) -> list[dict]:
    """Return one wait record per completed run across the given workflows.

    ``workflow_ids`` may be workflow filenames (``rebuild-rpms.yml``) or numeric
    IDs; the API accepts both. Each record carries the fields :func:`summarize`
    needs plus the raw ``wait_seconds`` so callers can re-bucket however they like.
    """
    records: list[dict] = []
    for workflow_id in workflow_ids:
        runs = fetch_runs(token, owner, repo, workflow_id)
        for run in runs[:runs_per_workflow]:
            jobs = fetch_jobs(token, owner, repo, run["id"])
            wait = queue_wait_seconds(run, jobs)
            records.append({
                "workflow": workflow_id,
                "run_number": run.get("run_number"),
                "head_branch": run.get("head_branch"),
                "conclusion": run.get("conclusion"),
                "wait_seconds": wait,
            })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--owner", default=os.environ.get("GH_OWNER", DEFAULT_OWNER))
    parser.add_argument("--repo", default=os.environ.get("GH_REPO", DEFAULT_REPO))
    parser.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="Workflow filename or ID to measure (repeatable). Defaults to rebuild-rpms.yml.",
    )
    parser.add_argument("--limit", type=int, default=50, help="Runs to inspect per workflow (default 50).")
    parser.add_argument(
        "--threshold",
        type=_coerce_seconds,
        default=None,
        help="Alert when p50 queue wait exceeds this. Accepts plain seconds or a duration like 30m/2h.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write the JSON report here in addition to stdout.")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub token with actions: read.")
    args = parser.parse_args()

    workflows = args.workflow or ["rebuild-rpms.yml"]
    if not args.token:
        print("GITHUB_TOKEN is not set; the Actions API needs it to list runs", file=sys.stderr)
        return 2

    try:
        waits = measure(args.token, args.owner, args.repo, workflows, runs_per_workflow=args.limit)
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            print(
                f"Actions API request failed ({error.code}): this job needs the "
                "'actions: read' permission",
                file=sys.stderr,
            )
            return 2
        raise
    except urllib.error.URLError as error:
        print(f"could not reach the Actions API: {error}", file=sys.stderr)
        return 2

    report = summarize(waits, threshold_seconds=args.threshold)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    # The JSON report is the durable record. This is what the workflow step
    # summary turns into the alert, and what a failing exit code surfaces.
    print(json.dumps(report["overall"], indent=2, sort_keys=True))
    if report["threshold_exceeded"]:
        print(
            f"\nQueue wait p50 exceeds the {args.threshold}s threshold "
            f"(see reports/queue-wait.json). This is issue #304 firing.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
