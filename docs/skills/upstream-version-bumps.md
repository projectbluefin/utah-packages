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

The `sources` manifest pins more than the primary tarball: bundled files
fetched from Fedora's lookaside by digest (`source_pipeline.py`
`bundled_sources`), such as `ppp-watch.tar.xz`, `krobelus.gpg`, a vendored Go
tree. `rewrite_sources()` replaces only the primary line, in place, and
keeps every other line verbatim, in either manifest form: the BSD
`ALGO (file) = hex` lines and the legacy md5sum `hex  file` lines ten carried
recipes still use (#326). Keeping only the BSD lines dropped those pins too.
Rewriting the manifest to the tarball alone dropped them, and in the first
gated bump (run 37129679613) adw-gtk3-theme, fish, gum and ppp all died in
`rpmbuild -bs`, reported as "lock resolve failed 3 times", before
anything compiled. `check_bumpable()` refuses, before fetching anything, two
recipes a bump cannot move on its own: a bundled entry whose name carries
the old version, in either its RPM or tarball spelling
(`gum-2.0.0-vendor.tar.bz2`, `fish-4.6.0.tar.xz.asc`,
`glycin-2.2.beta-vendor.tar.xz` for `2.2~beta`, whose successor someone has
to produce), and a `Version:` computed from macros that a `Source` line also
reads, directly or through another macro (alsa-sof-firmware's
`%{sof_ver_pkg}`, re2's `%{tag}`). A macro `Version:` whose sources read only
`%{version}` (pipewire, alsa-utils) is still overwritten with a literal. Both
refusals are skipped with a reason, like a failed download.

## When a bumped recipe fails

`--apply` moves the version only; the recipe can still need the change a new
release forces. Fix it on a `fix/recipe-<name>` branch that carries the bump
and the recipe change together, using Rawhide's spec at the same version as
the reference when Fedora has one. Seen so far:

- A new hard dependency in `configure`/`meson` needs its BuildRequires
  (ddcutil 2.2.7: `pkgconfig(libacl)`).
- The mobile-broadband stack (libqrtr-glib 1.4, libqmi 1.38) replaced
  gtk-doc with gi-docgen under the same `gtk_doc` meson option: BuildRequire
  `gi-docgen`, pass `-Dgtk_doc=true`, and ship `%{_docdir}/<lib>-1.0/`
  instead of `%{_datadir}/gtk-doc/html/<lib>/`.
- A tag is not a release: stixfonts tagged `v2.14` on an interim,
  source-only commit with no built fonts while its latest release stayed
  `v2.13b171`, and the daily bump proposed the tag. `forge_versions()` now
  reads a forge's releases API first (GitHub and GitLab, one extra request
  per tag feed) and polls tags only when the project publishes no stable,
  non-draft release at all. If a project's releases lag its real versions,
  give the lock an Anitya `feed` rather than reading tags again. Do not
  build an interim tag; leave the lock where it is.
- A suffixed lock is compared by its numeric prefix (`newer()`): a
  prerelease suffix (`rc`, `alpha`, `beta`, `pre`, `dev`) sits below it, any
  other suffix above. Without that, `version_key` read `2.13b171` (a build
  after 2.13) and `1.1.1^20251205git...` as older than every release sharing
  their major, and proposed 2.13 and 1.1.1 as "updates". `2.0b3`-style
  betas with a bare `b` read as post-releases; give such a lock a hold or
  a feed if it ever matters.
- A carried patch that stops applying was usually merged upstream. Check
  with `patch -p1 -R --dry-run` against the new tarball: a clean reverse apply
  means drop it, along with anything the spec marks as needed only for it
  (libgphoto2 2.5.34 dropped an `autoreconf`; libmtp 1.1.23 and libheif
  1.23.5 dropped theirs too).
- Rawhide at the same version has often already dropped, rebased or added a
  patch (libayatana-appindicator 0.6.0 needed Rawhide's gapi metadata patch
  for its mono bindings).

Verify a fix with `rebuild-rpms.yml` dispatched on the `fix/recipe-<name>`
ref with `packages=["<name>"]`; a non-main ref publishes only a
branch-named tag.

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
  `config/upstream-sources.json`, `config/bump-holds.json` and `packages/**`.
- Staleness: the gate works on `github.sha`, the branch head when it was
  dispatched, checks the pull request still points there, and merges with
  `gh pr merge --match-head-commit`. A newer bump's gate cancels an older
  one through the concurrency group.
- Partial failure holds instead of blocking. When the only problem is that
  some bumped packages failed (the build reached a verdict, both outputs
  are present, every bumped package was selected, every failure is a
  bumped package), `bump_gate.py holdable` names them and the gate's
  `Hold the failed packages and gate the rest` step runs `bump_gate.py
  trim`: their lock entries and `packages/<name>/` go back to the merge
  base exactly, and `config/bump-holds.json` records
  `{"holds": {"<name>": {"version", "run"}}}`. It commits that on top
  of the commit it built, pushes as a fast-forward (a moved branch refuses
  it), and dispatches itself on the new head. That run rebuilds only what
  is left, mostly from the package cache the first run pushed, and merges
  normally, holds included. If every bumped package failed, what is left
  is the holds file alone: `plan` reports `holds_only` (only the holds
  changed, lock content equal to base), the build is skipped, and it
  merges after Canary. Each round removes at least one package, so this
  converges. The dispatched run cancels the trimming run through the
  concurrency group, so the trimming run can show as cancelled.
- `upstream_bump.py` skips a proposal whose exact version is held and
  logs `held <name>`. A newer upstream release is proposed as usual, and
  applying it deletes the hold, which is why `bump-upstream-sources.yml`
  commits `config/bump-holds.json` with the lock and recipes. To retry a
  held version sooner, delete its entry, normally in the pull request that
  fixes the recipe. A hold set by a flaky build waits for the next release
  unless a human deletes it.
- Any other failed verdict leaves the pull request open with one comment per
  verdict per commit (marker `<!-- bump-gate: sha=... failed=[...] -->`).
  Other non-merge outcomes leave no comment: a refused diff or a failed or
  missing Canary fails the gate run (the Canary result is also the check on
  the head commit), and a moved head is a notice in the run. The next
  daily bump re-dispatches the gate even when nothing new moved, which
  retries a flaky build.
- A `target-cycle` (GNOME-next) run is never gated; it stays a human merge.
- GitHub does create `pull_request` runs for the bot-opened PR, parked in
  `action_required`; their pending `Canary` blocked the first gated merge
  ("the base branch policy prohibits the merge"). The merge job approves
  parked runs on the exact commit it built before waiting for Canary.
- A relock (a dispatched `--package` run that moves a primary off the Fedora
  lookaside) changes `config/fedora-primary-sources.txt`, which the gate
  refuses: moving a source's origin stays a human merge.

## Release feeds for lookaside locks (issue #134)

A lock whose primary is the Fedora lookaside names no feed in its own URLs.
It carries an explicit `feed` instead, which `parse_explicit_feed()` accepts
in three shapes:

- a git-forge Source0 URL (`github.com/<o>/<r>/archive|releases/...`, a
  `*gitlab*` host's `/-/archive/`), polled for tags or releases;
- `https://download.gnome.org/sources/<module>/...`, polled through the
  module's `cache.json` — needed whenever the module and the package differ
  (gtk3 → `gtk`, rest → `librest`), since the `--package` relock guess uses
  the package name;
- `https://release-monitoring.org/project/<id>` (Anitya), for upstreams that
  publish only a directory listing. Take the id from Fedora's own mapping,
  `GET /api/v2/packages/?distribution=Fedora&name=<pkg>`, then
  `/api/v2/projects/?name=<project>&ecosystem=<ecosystem>`.

Derive the feed from the spec's `Source0:` (expand it with `rpmspec -P` in a
Fedora container), and add it only when the feed lists the locked version in
the same spelling. Prefer a forge feed where its tags are clean — it is the
only kind that can be relocked — and fall back to Anitya when tags carry the
name (`libX11-1.8.12` strips to `11-1.8.12`), use another spelling
(`V3-6-0`), or include stray tags (`thin-provisioning-tools` has one that
reads as `2`).

What a feed on a lookaside lock can do:

- The **scheduled run only reports** it ("needs review"). It never applies,
  by design: the new bytes are not in the lookaside, and no unattended run
  moves a primary.
- A **`--package <name>` dispatch relocks** a GNOME or forge feed: the
  primary moves to the feed (the forge URL is the feed with the version
  substituted, so the feed must contain the locked version), the old lookaside
  URL becomes the fallback, the explicit `feed` is dropped, and the package is
  deleted from `config/fedora-primary-sources.txt`. Before that last step
  existed, every relock left a stale ratchet entry and failed
  `tools/validate.py`. The workflow's PR step commits the ratchet file too.
- An **Anitya feed never relocks**: it names versions, not a download URL.

The lookaside fallback is keyed by the Fedora package, not the GNOME module
(`rpms/gtk3/gtk-3.24.52.tar.xz/...`). `planned_entry()` used the module
until 2026-10-03, which left gtk4 and gnome-desktop3 with `rpms/gtk/` and
`rpms/gnome-desktop/` fallbacks that 404ed; both were corrected then.

Left without a feed on purpose (2026-10-03): git snapshots (aribb24),
sources with no upstream release (color-filesystem, kde-filesystem,
kde-settings, kf5), generated sources whose `generate.input` the tool does
not read (gpm, intel-media-driver-free, python-pydantic-core), a compat pin (protobuf3), a prerelease lock that the
feed spells differently (ibus 1.5.35~beta2, Xwayland 26.0.99.901), and
versions that cannot be compared with the lock's (enca's revival fork,
libappindicator's Ubuntu snapshot, libisoburn and libisofs `.pl02`, mozc,
spandsp date snapshots, fxload `2008_10_13`, and Vulkan headers/loader, whose
tags mix spec `v1.4.365` with SDK `vulkan-sdk-1.4.350.0`).
