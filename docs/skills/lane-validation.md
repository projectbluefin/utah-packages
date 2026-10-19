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
