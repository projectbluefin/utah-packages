---
name: upstream-version-bumps
description: Preserve RPM release and rebuild-counter semantics when changing upstream versions, and how the daily bump gates and merges itself.
metadata:
  type: procedure
---

# Upstream version bumps

When changing `tools/upstream_bump.py`, keep the spec version, source lock,
and source manifest together. A changed `Version:` resets the numeric leading
literal of `Release:` to `1`; preserve following macros and comments. Leave
macro-only releases (`%autorelease`, `%{baserelease}`, `%{samba_release}`)
alone because their expanded value cannot be inferred from the recipe.
A no-op version rewrite must preserve the release.

Retire the package's `dist_bump` entry when applying a new upstream version,
for both GNOME and forge feeds. Its baseline records only the release, so a
reset from `1` to `1` cannot invalidate it automatically: without removal the
new version inherits a rebuild counter that belongs to the old sources.
Preserve counters on same-version applications.

Cover these cases in `tests/test_upstream_bump.py`, including an unchanged
numeric release across a version bump and both feed paths. Use fake downloads
and scratch trees so validation does not depend on live upstream releases.

A proposal's `module` key means two different things: a GNOME module for
`final`/`relock`, and the feed label (`github.com/<owner>/<repo>`) for a forge
`update`. `apply()` may take the module from the proposal only for a
`relock`; everything else reads it off the lock (`gnome_module(entry)`).
Reading a forge label as a GNOME module built
`download.gnome.org/sources/github.com/...` URLs that 404ed, and because one
failed download aborted the batch, every scheduled run from 2026-09-20 to
2026-10-02 applied nothing. `main()` now skips a bump whose bytes cannot be
fetched (as `plan()` already skips an unreachable feed) and fails only when
none applied. A CI log that names a package right before a traceback is not
evidence that package failed unless stdout is line buffered, which `main()`
now forces.

## The bump gate

The daily in-cycle pull request on `bump/upstream-sources` merges itself
through `.github/workflows/bump-upstream-gate.yml`, and only when every
bumped recipe builds. Decisions live in `tools/bump_gate.py` and are covered
by `tests/test_bump_gate.py`; the workflow only acts on them.

Constraints that shaped it, so they are not rediscovered:

- Everything here runs on `GITHUB_TOKEN`. A pull request it opens starts no
  `pull_request` workflow, and a merge it makes starts no `push` workflow;
  a `workflow_dispatch` it sends does start one. So the bump job dispatches
  the gate, the gate dispatches `canary.yml` with `pr=<number>` (the required
  `Canary` check is matched by name on the head commit, and a dispatch is the
  only way it lands there), and after merging it dispatches
  `rebuild-rpms.yml` on `main` to publish `latest`. Waiting for the 03:17
  schedule instead would leave a merged bump unpublished for up to a day.
- The build is `rebuild-rpms.yml` called as a job (`workflow_call`), not a
  dispatched run to find and poll: its `build_list` and `failed` outputs
  are job outputs, and no single job has to outlive a factory run.
  It runs with `packages` = the bumped recipes, `factory_tag: latest`,
  `skip_publish: true` and `artifact_prefix: gate-`, so it builds against
  what main would and publishes no tag at all. Restricting to the bumped set
  keeps a package already failing on main from blocking an unrelated bump;
  the cost is that reverse dependencies are first built by the post-merge
  run on main, where a failure keeps the previous build and opens the usual
  tracking issue.
- Fail closed: no named packages, a build that was skipped or cancelled, a
  missing output, a bumped package that was not selected, or any failure
  blocks the merge. The diff from main may touch only
  `config/upstream-sources.json` and `packages/**`.
- Staleness: the gate works on `github.sha`, the branch head when it was
  dispatched, checks the pull request still points there, and merges with
  `gh pr merge --match-head-commit`. A newer bump's gate cancels an older
  one through the concurrency group.
- A failed build verdict leaves the pull request open with one comment per
  verdict per commit (marker `<!-- bump-gate: sha=... failed=[...] -->`).
  Other non-merge outcomes leave no comment: a refused diff or a failed or
  missing Canary fails the gate run (the Canary result is also the check on
  the head commit), and a moved head is a notice in the run. The next
  daily bump re-dispatches the gate even when nothing new moved, which
  retries a flaky build.
- A `target-cycle` (GNOME-next) run is never gated; it stays a human merge.
