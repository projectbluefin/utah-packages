#!/usr/bin/env python3
"""Measure CI queue wait, so runner saturation stops being anecdotal.

Issue #304 reports chronic queue saturation on the factory: a single
``webkitgtk`` build holding runners for hours with everything queued behind
it, and fix-forward rebuilds sitting pending for over an hour behind a bulk
wave. The evidence was captured by hand while shepherding a bump; the point
of this tool is to make it a number we can watch instead of a story we tell
after the fact.

"Queue wait" is the time between a run (attempt) starting and its first job
actually running -- the earliest ``started_at`` among its jobs minus the run's
``run_started_at`` (falling back to ``created_at`` when the run record carries
none). ``run_started_at`` is used rather than ``created_at`` because the jobs
endpoint returns the latest attempt, so a re-run is measured from when that
attempt started. That is the wall-clock time a contributor spent waiting,
which is exactly the saturation this issue is about.

The GitHub Actions API is the source of truth for both timestamps, so this
tool reads runs and their jobs rather than trusting anything a workflow prints.
The network calls live in :func:`measure`; the parsing, percentile and
threshold logic is pure and unit-tested here.

Saturation also shows up per runner pool: one run can fan out across many jobs
that each wait their own stretch for a runner before starting.
:func:`job_wait_seconds` captures that per-job view, and :func:`measure` returns
it alongside the run-level record so :func:`summarize` can bucket it by runner
pool (the job's ``runs-on`` labels, falling back to its runner group).
GitHub-hosted runners are ephemeral -- nearly every job gets a fresh
``runner_id`` -- so bucketing by runner id would just restate each job.

A rebuild wave can exceed the Actions page size, so both :func:`fetch_runs` and
:func:`fetch_jobs` paginate instead of trusting a single page; a large rebuild
run has hundreds of jobs, and the later stages are where long poles queue.
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

# GitHub pages run and job lists at 100 items per page. Kept as a constant so
# the request shape is assertable; :func:`fetch_runs` and :func:`fetch_jobs`
# walk pages of this size.
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
        if job.get("conclusion") != "skipped"
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


def job_wait_seconds(job: dict) -> float | None:
    """Queue wait for one job: its own ``created_at`` to ``started_at``.

    A job's ``created_at`` is when its record was created and it was queued; its
    ``started_at`` is when a runner picked it up. The gap is how long that specific
    job waited for a runner -- the per-runner-pool view of saturation that a run-level
    number hides when one run fans out across many jobs. Returns ``None`` when
    either timestamp is missing (a job that never scheduled), which callers skip.
    """
    if job.get("conclusion") == "skipped":
        return None
    created = parse_timestamp(job.get("created_at"))
    started = parse_timestamp(job.get("started_at"))
    if created is None or started is None:
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


def summarize(
    waits: list[dict],
    threshold_seconds: float | None = None,
    per_job: list[dict] | None = None,
) -> dict:
    """Summarise per-run queue waits into an overall and per-workflow report.

    Each entry in ``waits`` is a dict with at least ``workflow``, ``run_number``,
    ``head_branch``, ``conclusion`` and ``wait_seconds``. ``wait_seconds`` may be
    ``None`` when the run never started a job; those are counted as observed but
    excluded from the percentile math. ``per_job`` is an optional list of
    per-job records (see :func:`measure`) bucketed by runner pool.
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
        "per_job": _per_job_summary(per_job or []),
        "threshold_exceeded": overall_summary["threshold_exceeded"],
    }


def render_step_summary(report: dict) -> str:
    """Render the workflow step-summary markdown for a :func:`summarize` report.

    Lives here rather than inline in the workflow so the keys it reads are
    unit-tested against the keys :func:`summarize` writes.
    """
    lines: list[str] = []
    overall = report["overall"]
    lines.append("## CI queue wait — " + report["measured_at"])
    lines.append("")
    lines.append(f"Runs measured: **{overall['runs_measured']}** / observed {report['runs_observed']}")
    lines.append(
        f"p50: **{overall['p50_seconds'] / 60:.1f} min**"
        f" · p90: **{overall['p90_seconds'] / 60:.1f} min**"
        f" · max: **{overall['max_seconds'] / 60:.1f} min**"
    )
    worst = overall.get("worst")
    if worst:
        lines.append(
            f"Worst: run #{worst['run_number']} ({worst['head_branch']}) — "
            f"{worst['wait_seconds'] / 60:.1f} min, {worst['conclusion']}"
        )
    per_job = report.get("per_job", {})
    if per_job.get("jobs_measured"):
        lines.append(
            f"Per-job (per runner pool): p50 **{per_job['p50_seconds'] / 60:.1f} min**"
            f" · p90 **{per_job['p90_seconds'] / 60:.1f} min** · max **{per_job['max_seconds'] / 60:.1f} min**"
        )
        # Name the runner pool (runs-on label set) that waited longest: the
        # saturation signal a run-level number hides when one run fans out.
        by_pool = per_job.get("by_runner_pool", {})
        if by_pool:
            pool, stats = max(by_pool.items(), key=lambda kv: kv[1]["max_seconds"])
            lines.append(
                f"Worst runner pool `{pool}`: {stats['jobs']} jobs, "
                f"max {stats['max_seconds'] / 60:.1f} min wait."
            )
    if overall.get("threshold_exceeded"):
        lines.append("")
        lines.append(
            ":rotating_light: p50 queue wait exceeds the "
            f"{overall['threshold_seconds'] / 60:.0f} min threshold (issue #304)."
        )
    else:
        threshold = overall.get("threshold_seconds")
        lines.append("")
        if threshold:
            lines.append(f"Within the {threshold / 60:.0f} min threshold.")
        else:
            lines.append("No threshold set (set QUEUE_WAIT_THRESHOLD to alert).")
    return "\n".join(lines) + "\n"


def runner_pool(job: dict) -> str:
    """Name the runner pool a job waited on: its ``runs-on`` labels, else its group.

    Runner ids are ephemeral on GitHub-hosted runners, so they cannot identify a
    saturated pool. The labels (``ubuntu-24.04``, ``self-hosted,x64``...) are what
    jobs actually compete for; the runner group is the fallback, then
    ``unknown`` for a job the API reports neither for.
    """
    labels = [str(label) for label in (job.get("labels") or []) if label]
    if labels:
        return ",".join(sorted(labels))
    return job.get("runner_group_name") or "unknown"


def _per_job_summary(per_job: list[dict]) -> dict:
    """Summarise per-job waits grouped by runner pool, so a saturated pool stands out.

    Each entry in ``per_job`` carries a ``runner_pool`` (see :func:`runner_pool`)
    and its own ``wait_seconds``. A run with no measured jobs yields an empty
    report rather than an error, so the scheduled job still produces output on
    quiet days.
    """
    seconds = [j["wait_seconds"] for j in per_job if j["wait_seconds"] is not None]
    by_pool: dict[str, list[float]] = {}
    for job in per_job:
        if job.get("wait_seconds") is not None:
            by_pool.setdefault(job.get("runner_pool") or "unknown", []).append(job["wait_seconds"])
    return {
        "jobs_measured": len(seconds),
        "p50_seconds": percentile(seconds, 50),
        "p90_seconds": percentile(seconds, 90),
        "max_seconds": max(seconds) if seconds else 0.0,
        "by_runner_pool": {
            pool: {
                "jobs": len(values),
                "p50_seconds": percentile(values, 50),
                "p90_seconds": percentile(values, 90),
                "max_seconds": max(values) if values else 0.0,
            }
            for pool, values in sorted(by_pool.items())
        },
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


def fetch_runs(
    token: str, owner: str, repo: str, workflow_id: str, limit: int = PER_PAGE
) -> list[dict]:
    """Fetch up to ``limit`` of the most recent completed runs of one workflow.

    Paginate the Actions run list (``PER_PAGE`` items per page) until ``limit``
    runs are collected or the API returns an empty page, so a rebuild wave
    larger than a single page is never silently truncated to the first page.
    """
    runs: list[dict] = []
    page = 1
    while len(runs) < limit:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/actions/workflows/{workflow_id}/runs?per_page={PER_PAGE}&page={page}&status=completed"
        )
        payload = _http_get_json(url, token)
        batch = payload.get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
        page += 1
    return runs[:limit]


def fetch_jobs(token: str, owner: str, repo: str, run_id: int) -> list[dict]:
    """Fetch every job of one run. Empty list if the run has none.

    A rebuild run can have hundreds of jobs, so paginate until ``total_count``
    jobs are collected (or the API returns an empty page) rather than silently
    keeping only the first page -- the later stages are where long poles queue.
    """
    jobs: list[dict] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}"
            f"/actions/runs/{run_id}/jobs?per_page={PER_PAGE}&page={page}"
        )
        try:
            payload = _http_get_json(url, token)
        except urllib.error.HTTPError as error:
            # A run that finished before its jobs were retained, or a run the
            # token cannot read, yields no jobs. Treat that as an unmeasurable
            # run, not a fatal error, so one bad run does not sink the report.
            if error.code == 404:
                return []
            raise
        batch = payload.get("jobs", [])
        if not batch:
            break
        jobs.extend(batch)
        total = payload.get("total_count")
        if total is None or len(jobs) >= total:
            break
        page += 1
    return jobs


def measure(
    token: str,
    owner: str,
    repo: str,
    workflow_ids: list[str],
    runs_per_workflow: int = 50,
) -> tuple[list[dict], list[dict]]:
    """Return run-level and per-job wait records across the given workflows.

    ``workflow_ids`` may be workflow filenames (``rebuild-rpms.yml``) or numeric
    IDs; the API accepts both. The first return value is one record per
    completed run with the fields :func:`summarize` needs. The second is one
    record per job that actually started, carrying its runner pool and its
    own queue wait, so saturation can be viewed per runner pool as well as per run.
    """
    records: list[dict] = []
    per_job: list[dict] = []
    for workflow_id in workflow_ids:
        runs = fetch_runs(token, owner, repo, workflow_id, limit=runs_per_workflow)
        for run in runs:
            jobs = fetch_jobs(token, owner, repo, run["id"])
            wait = queue_wait_seconds(run, jobs)
            records.append({
                "workflow": workflow_id,
                "run_number": run.get("run_number"),
                "head_branch": run.get("head_branch"),
                "conclusion": run.get("conclusion"),
                "wait_seconds": wait,
            })
            for job in jobs:
                jwait = job_wait_seconds(job)
                if jwait is not None:
                    per_job.append({
                        "runner_pool": runner_pool(job),
                        "runner_id": job.get("runner_id"),
                        "wait_seconds": jwait,
                        "job_name": job.get("name"),
                        "head_branch": run.get("head_branch"),
                        "conclusion": run.get("conclusion"),
                    })
    return records, per_job


def _describe_http_error(error: urllib.error.HTTPError) -> str:
    """Explain an Actions API failure without conflating rate limits and permissions."""
    headers = error.headers or {}
    rate_limited = error.code == 429 or (
        error.code == 403
        and (headers.get("X-RateLimit-Remaining") == "0" or headers.get("Retry-After"))
    )
    if rate_limited:
        return f"Actions API request was rate limited ({error.code}); retry later or lower --limit"
    if error.code in (401, 403, 404):
        return (
            f"Actions API request failed ({error.code}): check the token is valid "
            "and the job has the 'actions: read' permission"
        )
    return f"Actions API request failed ({error.code} {error.reason})"


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
    parser.add_argument(
        "--render-summary",
        type=Path,
        default=None,
        metavar="REPORT",
        help="Print the step-summary markdown for an existing JSON report and exit (no API calls).",
    )
    args = parser.parse_args()

    if args.render_summary:
        sys.stdout.write(render_step_summary(json.loads(args.render_summary.read_text())))
        return 0

    workflows = args.workflow or ["rebuild-rpms.yml"]
    if not args.token:
        print("GITHUB_TOKEN is not set; the Actions API needs it to list runs", file=sys.stderr)
        return 2

    try:
        waits, per_job = measure(args.token, args.owner, args.repo, workflows, runs_per_workflow=args.limit)
    except urllib.error.HTTPError as error:
        # Every API failure exits 2 so it is never mistaken for the threshold
        # alert (exit 1).
        print(_describe_http_error(error), file=sys.stderr)
        return 2
    except urllib.error.URLError as error:
        print(f"could not reach the Actions API: {error}", file=sys.stderr)
        return 2

    report = summarize(waits, threshold_seconds=args.threshold, per_job=per_job)

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
