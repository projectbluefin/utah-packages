---
name: queue-observability
description: Measure CI queue wait for issue #304, and the boundary of what this repository can change about runner saturation.
metadata:
  type: procedure
---

# CI queue-observability

Issue #304 tracks chronic CI runner saturation on the factory. Most of the
mitigations it lists are **maintainer decisions** this repository cannot make
alone: a merge queue or batch window on `main` (#1), a priority lane for
fix-forward rebuilds (#2), dedicated runners for long-pole C++ builds like
`webkitgtk` (#3), staggering the rebuild/bump/verify crons (#4), and capping
`update-branch` churn (#5). Do not open a PR trying to implement those — they
are policy/infra decisions, and per `AGENTS.md` autonomy repairs known failures
but does not manufacture approval.

What this repository *can* ship is mitigation #6, queue-time observability, and
that is what `tools/queue_wait.py` + `.github/workflows/queue-observability.yml`
do.

## The metric

"Queue wait" is the earliest actual job `started_at` minus the run attempt's
`run_started_at` (falling back to `created_at` when the run record carries none) — the
wall-clock time a run sat pending before its first job ran. That is the
saturation #304 is about. The numbers come from the GitHub Actions API
(`GET .../actions/workflows/{id}/runs` and `.../runs/{id}/jobs`), never from
anything a workflow prints.

The report also carries a **per-job** view (`per_job`): each started job's own
`started_at` minus its `created_at` (when the job was queued), with overall
p50/p90/max and a `by_runner_pool` breakdown keyed by the job's sorted
`runs-on` labels (falling back to its runner group, then `unknown`). Runner ids
are ephemeral on hosted runners, so pools — not runners — are the unit. The
step summary (rendered by `tools/queue_wait.py --render-summary`) prints the
per-job percentiles and names the pool with the longest single wait.

**Coverage boundary:** the daily job measures `rebuild-rpms.yml` runs that were
triggered directly (schedule, dispatch, push). Canary calls `rebuild-rpms.yml`
via `workflow_call`, and the Actions API attributes those runs to `canary.yml`,
so canary-driven rebuilds are not in the report. Pass `--workflow canary.yml`
too if they need measuring.

Semantics worth pinning (they are unit-tested in `tests/test_queue_wait.py`):

- Only jobs that actually ran count. GitHub can populate `started_at` and
  `created_at` even for skipped jobs; filter `conclusion=skipped` explicitly
  from both run and per-job measurements. Missing timestamps remain gaps.
- A run that never started a job (cancelled before start, or whose jobs could
  not be read) is a **measurement gap** reported as `wait_seconds: null`, never
  a zero wait. `runs_observed` counts it; `runs_measured` does not.
- Percentiles use linear interpolation (numpy `linear`), so p50/p90 mean the
  same as any dashboard.

## Boundary of autonomy

- The job is **read-only**: `permissions: actions: read`. It lists runs and
  jobs and changes nothing about scheduling.
- The **metric is always produced** (`reports/queue-wait.json`); the **alert is
  opt-in** via the `QUEUE_WAIT_THRESHOLD` repo variable. The agreed threshold
  is a maintainer decision (#304 "Done when"), so the workflow does not hardcode
  one. The tool exits 1 when p50 exceeds the threshold, which is how the
  daily job alerts — it goes red. Any Actions API failure (auth, permissions,
  rate limit, 5xx) or missing token exits 2, so it is never mistaken for the
  alert.
- Splitting long poles, priority lanes and merge-queue batching are out of scope
  for a contributable PR. When a task asks for one of those, the shippable part
  is the measurement that would prove it works; the policy change stays a
  maintainer decision.

## Validating a change here

- `just check` (factory contract + workflow quoting + runtime contract + tests)
  and `just test` before every commit.
- `actionlint` on any workflow touched — CI runs it.
- Action references stay SHA-pinned; floating tags fail pre-commit.
