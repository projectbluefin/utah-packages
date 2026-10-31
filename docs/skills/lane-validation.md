---
name: lane-validation
description: Validate wave recipes with dispatched Canary lane runs — lane_packages scoping, per-ref inventory, fork limits, and what a green run actually proves.
---

# Validating recipe waves with lane runs

A Canary run without package selection builds only the default canary set
(`libical`, `vulkan-headers`, `vulkan-loader`). A green run that did not name
your recipes proves nothing about them — this mistake has been made and
merged on, so treat every unattributed green with suspicion.

## Dispatching a lane

```bash
gh workflow run canary.yml -R projectbluefin/utah-packages --ref <branch> \
  -f lane_packages='["pkg-a","pkg-b"]'
```

- `lane_packages` is a JSON array of **source** package names (recipe
  directory names).
- Names resolve against the **dispatched ref's** inventory. Unmerged recipes
  are unknown on `main` — dispatch wave branches for unmerged content, `main`
  only for what is already merged there.
- The lane builds the named set `skip_publish`-style against the published
  factory for BuildRequires it does not build itself. A recipe whose
  dependencies are themselves unmerged and unpublished fails here by design;
  land dependencies first, then retry the dependent.
- `lane_backend` selects the pass6 backend. The dispatch default is
  `container` (`canary.yml`), while production builds `hermetic`
  (`rebuild-rpms.yml` default; AGENTS.md). A green lane therefore proves the
  container lane only — pass `-f lane_backend=hermetic` when the claim needs
  the production backend.
- API-opened PRs currently produce no `pull_request` workflow runs in this
  repository, so a dispatched lane is the working validation path and the
  required-check display needs admin interpretation at merge time.

## Reading a lane result

- Per-package `rebuild` jobs are the verdict. `plan` succeeding while `build`
  fails usually means dependency resolution (`builddep` conflicts, missing
  `crate()` providers, excluded ICU-era libraries).
- Common failure shapes and where they point:
  - `nothing provides libicuuc.so.77`-class conflicts → the dependency needs
    a factory build against the current ICU, not the Fedora-linked one.
  - `nothing provides crate(...)` → the Rust crate stack has no provider;
    needs a vendoring-vs-packaging decision, not a retry.
  - `Bad file` on dist-git extras (PPDs, scripts) → Fedora `.gitignore`
    patterns (`*.gz`, bare script names) left them untracked at import;
    force-add and re-run.
  - `%prep` patch hunks failing under RPM's `--fuzz=0` → write the patch
    against the post-predecessor tree (replay the spec's patch order
    locally), or use a scripted `sed` next to the spec's existing
    workarounds for backslash-continued lines unified diff cannot touch.
- A lane that fails only on recipes outside your wave is someone else's
  signal — do not re-run the whole lane to chase it; narrow `lane_packages`.

## Fork limits

Fork dispatches run the same workflow but publish to the fork registry, where
the first publish of a canary tag fails (`manifest unknown`) and the run goes
red after otherwise successful builds. Use forks for parallel signal only;
merge decisions cite upstream runs.

## Fork pull requests and the required Canary (#369)

Most pull requests never need this: a pull request that only adds recipes and new
inventory entries passes `Canary` at once, with nothing built, for forks and
in-repository branches alike. `config/upstream-sources.json`,
`config/factory-build-backlog.toml` and `config/fedora-primary-sources.txt` are
recipe inventory, not pipeline, and count only when a change reaches an entry
that already existed, names a canary package, or leaves them unreadable
(`pipeline_relevant` in `tools/canary.py`; the lock is compared with the pull
request's merge base, so a branch that is merely behind `main` is not a change).
Everything else under `tools/`, `.github/`, `config/` and `Containerfile` still
counts. The rest of this section is for those pull requests.

The required `Canary` check cannot pass from a fork pull request that touches a
pipeline path: its token has no `packages: write`, so `canary.yml` fails it with
"a fork pull request cannot publish the canary image". The author cannot fix
that, and neither can an agent working from a fork; do not ask them to.

Changing an existing source-lock entry, including only its primary URL or
fallback URLs with an unchanged digest, needs this proof even when it changes
no workflow or build tool. Adding only new non-canary entries does not:
`pipeline_relevant` applies the inventory exceptions described above. If
configuration validation passed, the build jobs were skipped, and Canary's
`Decide` step reports missing maintainer-run proof, classify the failure as a
review prerequisite, not a failed package build. Keep the intended source
changes and the gate intact; removing either does not validate the change.

A repair request naming a generic failed check can refer to this prerequisite.
Read the failed job before changing code. Do not push an empty commit or
rerun the fork job without proof: neither supplies the missing build evidence,
and any new head invalidates proof for the previous commit. Finish necessary
changes first, then give the maintainer the final full head SHA for review and
dispatch. The default Canary set still does not build the imported recipe;
that recipe needs its own scoped build and runtime acceptance evidence.

A maintainer who has reviewed the diff runs **Canary for a fork pull request**
(Actions tab, `canary-fork-pr.yml`) with the pull request number and the full
head commit they reviewed. It copies exactly that commit to `canary/pr-<N>`
and dispatches `canary.yml` there, so the `Canary` check is created on the
pull request's own head commit. It refuses when the head moved since review,
when the pull request is not open against `main`, when it changes 3000 or
more files (GitHub's file list stops there), and when it changes
`.github/` (workflow changes never run with this repository's credentials from
a fork; push those by hand). A new push to the pull request needs a new
review and a new run.

The canary run builds the fork's code with `packages: write`, so the review is
the security boundary, exactly as it was when a maintainer pushed the branch by
hand.

The pull request does not count the dispatched run's own `Canary` check: it
lives in the check suite of `canary/pr-<N>`, and the pull request rolls up only
its own branch's suite (observed on #622: the dispatched run passed on the head
commit while the pull request kept the fork run's red `Canary` and stayed
`BLOCKED`). So the fork's own `Canary` job passes on proof instead: a
`workflow_dispatch` run of `canary.yml` on `canary/pr-<N>` that completed with
success at exactly the pull request's head (`tools/fork_canary.py proof`). When
such a run finishes, the `refresh` job of the same workflow (it waits for the
run it dispatched, executes nothing from the pull request, and holds the write
permissions the re-run needs) re-runs the pull request's own `Canary`. A run
that began before `canary.yml` could read the proof reuses its old workflow
file and fails again, so the job then closes and reopens the pull request once
to start a fresh run on the same commit. A maintainer-run Canary that does not
pass is reported on the pull request and the check stays red. The press holds a
runner for as long as that run takes (about half an hour). A push after review
changes the head, so the old proof no longer applies.
