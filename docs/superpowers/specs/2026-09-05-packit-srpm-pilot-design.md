# Wire the pinned Packit container into a real build step (pilot import)

Status: drafted autonomously; **user has not yet reviewed or approved this
spec**. The scoping decision below was made without interactive confirmation
because the user was unavailable mid-session — see "Assumption flagged for
review" before this is acted on.

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
- 76 of the 193 package directories carry a `.packit.yaml` (and some a
  `README.packit`) inherited unmodified from the original Fedora dist-git
  import. They are dead weight today: no workflow reads them.

## Assumption flagged for review

The request was "import the existing packages in this repo to the new
system, leave the old artifacts in place." Two readings are both
defensible:

1. **Pilot** — wire `packit srpm` in as an *additive*, opt-in path for the
   76 packages that already carry a `.packit.yaml`, without touching the
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
2. Matrixes over the 76 packages that already have a `.packit.yaml`.
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
      package: [<76 names with .packit.yaml, computed once and pinned as a
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
  from the 76 — e.g. `fzf` or `zenity` rather than `gnome-shell`) produces
  a valid SRPM artifact.

## Out of scope / future work (not this spec)

- Full migration of all 193 packages' SRPM generation to `packit srpm`.
- `packit build in-mock` wired to the real Hummingbird buildroot.
- Retiring the 117 packages' need for hand-authored `.packit.yaml` if/when
  migration proceeds.
- Removing the hand-rolled `rpmbuild -br`/`-ba` block from
  `rebuild0`..`rebuild4` — explicitly *not* touched by this pilot ("leave
  the old artifacts in place").
