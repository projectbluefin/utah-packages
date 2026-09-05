# Wire the pinned Packit container into a real build step (pilot import)

Status: **implemented and locally verified**. The scoping decision below
(pilot over 49 packages, not a full 193-package migration) was made without
interactive confirmation because the user was unavailable mid-session — see
"Assumption flagged for review". Implementation proceeded per autopilot
instructions to keep moving rather than block; the user should still review
the scope call after the fact and redirect if it's wrong.

Follow-up: the pilot now covers all 54 packages that carry an inherited
`.packit.yaml`. The factory's verified-source pipeline stages the locked
upstream archive and Fedora lookaside files beside each spec, and
`packit srpm --preserve-spec` keeps Packit on that locked version. This closes
the five-package gap described below without expanding the pilot to the other
packages in the repository.

## Context

- PRs #36–#40 already decided the Packit question for this repo: don't build
  `containers/packit-sdk/` ourselves; pin
  `quay.io/packit/packit@sha256:...` (upstream-published, rebuilt daily) and
  use only `packit srpm` / `packit build in-mock`, never the mutable
  `packit/actions/*@main` GitHub Actions. This is recorded in
  `docs/architecture.md` and `docs/packit-reuse-research.md` §7.
- Issue #35 closed as COMPLETED, but two of its acceptance criteria were
  never checked off:
  - "At least one existing or new job in this repo consumes the image ...
    to run `packit srpm` and/or `packit build in-mock` against a real
    package, as proof it works end-to-end."
  - "`docs/architecture.md` or `docs/contributing.md` gets a short pointer
    to the new image once it's wired into a real build step."
- Today, **nothing** in CI invokes `packit`. All 193 packages under
  `packages/*/` build via a hand-rolled shell block, duplicated identically
  across five sharded matrix jobs (`rebuild0`..`rebuild4`) in
  `.github/workflows/rebuild-rpms.yml`: `dnf builddep` the spec, stage
  sources, `rpmbuild -br` (retry loop for `%generate_buildrequires`), then
  `rpmbuild -ba`. This runs directly in a plain Fedora container — not even
  through Mock — despite mock being installed.
- 54 of the 193 package directories carry a genuine `.packit.yaml` (and a few more only a
  `README.packit`) inherited unmodified from the original Fedora dist-git
  import. They are dead weight today: no workflow reads them.

## Assumption flagged for review

The request was "import the existing packages in this repo to the new
system, leave the old artifacts in place." Two readings are both
defensible:

1. **Pilot** — wire `packit srpm` in as an *additive*, opt-in path for the
   54 packages that already carry a `.packit.yaml` (49 of which actually
   produce a valid SRPM -- see "Results of local verification"), without
   touching the
   existing `rpmbuild -ba` build/publish flow for any package.
2. **Full migration** — convert SRPM generation for all 193 packages to go
   through `packit`, writing new `.packit.yaml` files for the 117 that lack
   one.

**This spec picks (1), the pilot**, and treats (2) as explicit future scope
gated on the pilot succeeding. Reasons:

- It is the option `docs/packit-reuse-research.md` §7 actually recommends:
  pin the CLI, use it narrowly, don't restructure the whole factory around
  it in one pass.
- It directly closes the two unchecked boxes on issue #35 with the smallest
  possible blast radius, consistent with how #36→#37→#38→#40 were landed as
  a sequence of small, reviewable PRs rather than one large change.
- It literally satisfies "leave the old artifacts in place": the 117
  packages without `.packit.yaml`, and the entire current build/publish
  path for all 193 packages, are untouched.
- A full migration is a ~200-line-per-package-class risk across a
  1570-line workflow already carrying hard-won, package-specific
  workarounds (dbus daemon for Fish, `USER` env for `just`, retry loop for
  Rust `%generate_buildrequires`, etc.) documented inline. Replacing that in
  one shot for 193 packages, sight unseen, is not something to do without
  the user confirming they actually want the existing path replaced instead
  of supplemented.

If the user meant (2) or something else, they should say so when they
review this spec; the plan step is cheap to redo, the workflow rewrite is
not.

## Goal

Add one new, isolated CI job — `packit-srpm-pilot` — that:

1. Runs in the pinned `ghcr`-independent, digest-pinned
   `quay.io/packit/packit` container (resolve and record the current digest
   at implementation time; re-verify it matches the `packit`/`mock`/
   `createrepo_c` versions PR #40's evidence showed).
2. Matrixes over the 49 packages (of 54 candidates) confirmed to produce a
   valid SRPM -- see "Results of local verification".
3. Runs `packit srpm` against each package's existing spec + `.packit.yaml`
   from a full git checkout (tags included, per the research doc's
   requirement that `packit srpm` needs real Git history/tags, not a
   shallow checkout).
4. Uploads the resulting SRPM as a build artifact and asserts it is
   non-empty and `rpm -qp`-parseable (mirrors the existing
   "a build that produced no RPM must fail here" pattern already used in
   `rebuild-rpms.yml`).
5. Does **not** feed that SRPM into Mock, the RPM overlay, or the published
   repository. This job is a proof-of-concept/verification lane only,
   parallel to and independent of `rebuild0`..`rebuild4`. Nothing about the
   existing rebuild/publish pipeline changes.
6. Runs on `workflow_dispatch` and `pull_request` (validation only, matching
   the existing convention that "pull requests validate configuration but
   cannot publish"), not on the `schedule` trigger — this is a
   verification job, not a new package source of truth yet.

## Non-goals (this pilot)

- Replacing `rpmbuild -ba`/`-br` in `rebuild0`..`rebuild4`.
- Writing `.packit.yaml` for the 117 packages that lack one.
- Using `packit build in-mock` (needs a privileged Mock root + this repo's
  Hummingbird buildroot config mounted in — real, but a separate follow-up
  once `packit srpm` is proven).
- Any change to publishing, signing, or the RPM overlay/Pages/GHCR paths.
- Deleting or modifying any existing `.packit.yaml`/`README.packit` file —
  they are read, not written, by the new job.

## Design

### New workflow job

Add a `packit-srpm-pilot` job, either as a new job appended to
`rebuild-rpms.yml` (reuses its existing `prepare` job's package-listing
logic) or as a new standalone workflow
`.github/workflows/packit-srpm-pilot.yml` if keeping it fully decoupled
from the rebuild pipeline's `needs:`/`if:` graph is cleaner. Decide during
planning by checking whether `prepare`'s outputs are easy to filter down to
"packages with `.packit.yaml`" or whether a fresh, simpler job is less
code.

```yaml
packit-srpm-pilot:
  if: ${{ !cancelled() }}
  strategy:
    fail-fast: false
    matrix:
      package: [<49 verified names, computed once and pinned as a
                 literal list or generated by `prepare` the same way stage
                 lists are today>]
  container:
    image: quay.io/packit/packit@sha256:<pinned digest>
  steps:
    - uses: actions/checkout@<pinned-sha>
      with:
        fetch-depth: 0        # packit srpm needs tags/history
        fetch-tags: true
    - name: packit srpm
      working-directory: packages/${{ matrix.package }}
      run: packit srpm
    - name: verify SRPM was produced
      run: |
        srpm=$(find . -maxdepth 1 -name '*.src.rpm' -print -quit)
        test -n "$srpm"
        rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}\n' "$srpm"
    - uses: actions/upload-artifact@<pinned-sha>
      with:
        name: packit-srpm-${{ matrix.package }}
        path: packages/${{ matrix.package }}/*.src.rpm
        if-no-files-found: error
```

(Illustrative — exact structure finalized during implementation planning,
including how `fail-fast: false` interacts with the existing convention
of per-package jobs failing independently.)

### Docs

- `docs/architecture.md`: add a short note, next to the existing Packit
  pointer, that a `packit-srpm-pilot` job proves `packit srpm` end-to-end
  against real packages, and link to this spec for the scope decision.
- `docs/contributing.md`: no change needed yet — this pilot doesn't change
  how a contributor adds a package.

### Error handling

- Matches the existing convention: fail loudly and specifically (test for
  a produced artifact, not just exit code 0) rather than letting an empty
  upload silently succeed — this repo already had to special-case exactly
  that failure mode in `rebuild-rpms.yml`.
- A package whose `.packit.yaml` is stale/wrong (plausible, since these are
  unmodified Fedora imports) should fail only that matrix entry, not the
  whole job — `fail-fast: false`.

### Testing / validation

- `actions/lint` equivalents already run in `validate.yml`; confirm the new
  workflow (or job) passes `actionlint`/whatever this repo already uses in
  `validate.yml` before merging.
- Manual proof: trigger `workflow_dispatch` once implemented and confirm at
  least one real package (recommend starting with a small, low-risk one
  from the 49 — e.g. `fzf` or `zenity` rather than `gnome-shell`) produces
  a valid SRPM artifact.

## Results of local verification

Before wiring this into CI, the exact `packit srpm` invocation was run
locally (`podman run` against the pinned digest) for all 54 packages that
carry a leftover `.packit.yaml`. Findings that changed the plan above:

1. **Packit's monorepo config schema needed a real top-level `packages:`
   map**, not the per-package `.packit.yaml` files as they exist today (they
   are hosted-service configs — `pull_from_upstream`/`koji_build`/
   `bodhi_update` jobs — and error with `KeyError('downstream_package_name')`
   if pointed at directly). A new root-level `.packit.yaml` was added with
   `specfile_path`/`upstream_package_name`/`downstream_package_name`/`paths`
   per package, read only by the new CI job. The 54 per-package
   `.packit.yaml`/`README.packit` files are untouched and still unused.
2. **49 of the 54 packages produce a valid SRPM as-is.** 5 do not:
   `adw-gtk3-theme`, `bootc`, `igt-gpu-tools`, `mesa`, `runc`. All 5 fail
   identically: their specs declare `SourceN`/`PatchN` entries (vendor
   tarballs, upstream README/LICENSE mirrors, a license-clarification email)
   that this factory's own verified-source pipeline stages into `_sourcedir`
   only at actual `rpmbuild` time (`rebuild-rpms.yml`'s
   `staged=/work/staged/$PACKAGE` step, combining the recipe directory with
   `/work/sources/$PACKAGE`). `packit srpm` has no equivalent staging step
   and fails with `Bad file: ... No such file or directory` for each missing
   source. This is a real, load-bearing architectural difference between
   Packit's "clone-and-build" model and this factory's "verify-then-stage"
   model, not a bug in either. **These 5 packages are excluded from the pilot
   matrix and `.packit.yaml`**, with a comment explaining why. Feeding staged
   sources into `packit srpm` (so all 193 could eventually be covered) is
   explicit future work, not this pilot.
3. `packit srpm` calls out to `release-monitoring.org` for some packages
   (non-fatal; it falls back to the spec's `%version` when unreachable) and,
   by default, rewrites the spec's `Release` field and repository state
   in-place (`--update-release` is on by default). Run against a real git
   checkout this only touches the ephemeral CI runner's working copy, which
   is discarded at job end — nothing is written back to the repository.
4. The container's `PATH_OR_URL` resolution for a package's git root is
   strict: it must match a `paths:` entry relative to the config's own
   location, not just any ancestor directory containing `.git`. This is why
   the config lives at the repository root (`PATH_OR_URL` defaults to `cwd`)
   rather than being run from inside each package directory.

## Out of scope / future work (not this spec)

- Full migration of every package's SRPM generation to `packit srpm`.
- `packit build in-mock` wired to the real Hummingbird buildroot.
- Adding Packit configuration for the remaining packages if migration
  proceeds.
- Removing the hand-rolled `rpmbuild -br`/`-ba` block from
  `rebuild0`..`rebuild4` — explicitly *not* touched by this pilot ("leave
  the old artifacts in place").
