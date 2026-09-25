---
name: repeated-mistakes
description: >-
  Mistakes this repository's history has already made at least twice, with
  the commits that made and unmade them. Load before changing the rebuild
  workflow, a stage assignment, a container pin, a spec's bconds, or before
  dropping a recipe, so the next fix does not repeat one of these.
metadata:
  type: reference
---

# Mistakes the history already made

`git log` on `main` is a record of fixes that undid earlier fixes. This file
lists the patterns that recurred, names the commits so the reasoning can be
read in full with `git show`, and states the rule each one settled. It is a
reference, not a changelog: add a pattern only when it has repeated, and keep
the rule, the evidence, and nothing else.

Read [`AGENTS.md`](../../AGENTS.md) first, then this file when the task
touches one of the areas below.

## 1. A recipe is not dead because nothing here consumes it today

**What happened.** `56b2973` dropped spirv-tools on the argument that nothing
in the runtime contract asked for it and mesa resolved it from the build
root. The first full publish run then failed the Hummingbird-only consumer
transaction on `nothing provides libSPIRV-Tools.so` for mesa-dri-drivers:
Hummingbird does not ship spirv-tools, so the runtime RPM had linked the
factory's own build and the factory had stopped producing it. `bf72d53`
restored it. The same shape closed `gcc` (`4bb0711`) and Firefox
(`20eae7a`) correctly, because Hummingbird ships gcc and Utah takes Firefox
as a Flatpak; the difference is whether the removed provider exists outside
the factory.

**Rule.** Before dropping a recipe, prove the provider exists in Hummingbird
(`repodata/primary.xml`, not a name search) or that no published binary
requires anything it provides. "Not in the contract" is about source names;
sonames are what the publish gate checks. `tools/rebuild_plan.py` now marks a
published build stale when its Requires are unsatisfied by factory plus
Hummingbird, which is the same check done early.

## 2. Two halves of one project cannot be pinned separately

**What happened.** spirv-tools built green on 2026-09-13 and failed a week
later with no change to the recipe, because `spirv-headers` comes from
outside the factory and moved. `3d2da97` switched off `-Werror`; the build
then died one layer down on a generated table naming an enum the pinned
spirv-tools did not know (`56b2973`). Relaxing the warning was treating a
version skew as a compiler setting.

**Rule.** When a package and its headers or grammar are released together
upstream, either build both here at matching versions or track the version
Fedora pairs them with. `bf72d53` moved spirv-tools to the release Rawhide
builds against Fedora 44's headers. A `-Werror` toggle is never the fix for a
missing symbol.

## 3. Same-stage siblings do not exist for each other

**What happened.** Four soname breaks in the first complete consumer
transaction were one mistake made four times (`33109b1`): gvfs and libnfs,
mozc and abseil-cpp, ntfs-3g and hwinfo, gnome-shell and
evolution-data-server were each in the same stage as their provider, so each
consumer linked whatever Hummingbird offered while the factory's newer build
won at install time and did not carry that soname. Before that, `8e8183f` and
`0bf1ee8` had to stop a stage from downloading its own siblings' artifacts,
because the ordering-dependent buildroot made the failing set move between
runs of one commit. libheif linked Fedora openjph 0.25 for the same reason
(`6940ae0`, `4d05fe0`).

**Rule.** A consumer of a library this factory rebuilds goes in a strictly
later stage than the provider. A failure naming a soname the factory used to
provide, or that Hummingbird provides at a different major, is a staging
question before it is a recipe question. The stage assignment lives in
`config/upstream-sources.json`.

## 4. A config change that alters a build has to invalidate the published copy

**What happened.** `33109b1` moved mozc and gnome-shell to later stages, and
the next run skipped both as already built: neither Version nor Release had
changed, so they matched the published listing and came back from the seeded
image as the very builds the move was meant to replace (`67cae1c`). The same
gap let stale libheif, gvfs, mozc and gnome-shell builds sit in the witness
for a week while their specs were already correct (`bf72d53`).

**Rule.** The plan trusts a published build only when nothing that produced it
changed: spec, patches, sources, stage, source URL, checksum, dist_bump
counter, and now the satisfiability of its Requires. Extending what the plan
considers "changed" is the fix; bumping Release by hand to force a rebuild is
not.

## 5. A global exclusion fights a local dependency

**What happened.** The ICU 77 versus 78 split was fought across fifteen
commits on `main` (`git log --grep=icu -i`). `012cb6a` removed a blanket libicu-77 exclusion because it broke
Fedora build-only dependencies. `47bf42a` put the exclusion in the publish
gate only. `49b3b56` put it back in every build root, which broke gvfs and
ffmpeg exactly as `012cb6a` had recorded. `57925d9` moved the requirement
into samba itself (`BuildRequires: libicu-devel >= 78`), and `65dec69` then
had to disable samba's Ceph VFS modules because libcephfs dragged ICU 77
back in, which `f8e7154` had already done once before the re-import undid it.

**Rule.** Express a version requirement in the one package that has it. A
build root legitimately carries both majors of a library when Fedora
build-only dependencies link one and the factory ships the other, so an
exclusion wide enough to remove the old major removes those dependencies
too. `GLOBAL_EXCLUDE` is for a stale duplicate of a Hummingbird package,
identified by exact release, never for a library at large.

## 6. A re-import silently reverts every local decision

**What happened.** samba's Ceph modules came back with the re-imported spec
(`65dec69`). The openjph bcond on libheif was added, retired, and added
again across `6940ae0`, `4d05fe0` and `4d2af41`. gstreamer-bad had
chromaprint declined, then onnx and opencv one run later because the first
had masked them (`718d4e4`); pipewire then hit the identical onnx conflict
(`fa7c3fc`).

**Rule.** After importing or re-importing a recipe, diff the new spec against
the previous one for `%bcond` lines and BuildRequires the factory had
changed, and check whether a sibling recipe already declined the same
feature for the same reason. When a feature is declined, decline every
feature that pulls the same unresolvable dependency in the same commit, not
one per run.

## 7. Repinning a digest that upstream garbage-collects is not a fix

**What happened.** `quay.io/fedora/fedora:44` and `quay.io/packit/packit`
publish only mutable tags and prune previous digests. `3a6e77a` pinned by
digest to satisfy the policy; the digests died within days and were repinned
by `abf267d`, `15a9dd5` and `3da8724`, each claiming to have settled it. The
third repin died four hours later, mid-run, killing thirty-seven jobs that
had started on a pin that was valid when the run began (`f1f1e4e`). One
commit claimed Renovate would track it; Renovate cannot run faster than the
rot.

**Rule.** The build root is pulled once, in `prepare`, and shared with every
job as an artifact. `config/buildroot-image` records the expected digest and a
mismatch warns. `tests/test_buildroot_sharing.py` fails any workflow that
pulls the build root from a registry per job. Do not add a per-job pull, and
do not "fix" an exit 125 `manifest unknown` on the build root by editing a
digest.

**Why the mirror exists.** Pulling the moving tag kept runs alive but let the
root change under the factory several times a day, and the package cache key
includes the root digest, so late stages never hit: webkitgtk built cold in
two consecutive runs because fedora:44 moved from `2cdfedd` to `94e175d`
between them. The fix is not pulling quay by digest (that is this section's
failure again) but owning the bytes: `refresh-buildroot.yml` copies fedora:44
weekly to `ghcr.io/projectbluefin/utah-buildroot` under a dated tag, which
nothing prunes, and opens a PR moving the pin in `config/buildroot-image`
(`tools/buildroot_pin.py`). A mirror pin is pulled by its digest, fatally,
because that digest cannot rot. Do not add a cleanup policy to that package.

## 8. A gate that has never run has never proved anything

**What happened.** The publish job's Hummingbird-only consumer transaction is
the one check that decides whether Utah can install what this factory ships.
It had never executed: a scratch image with no CMD failed `podman create`
(`33b820a`), the job had no checkout (`cafad84`), and it validated the first
five stages of an eleven-stage repository (`d5d733c`). Each fix exposed the
next, and the first real run found 27 problems. The `%check` evidence
capture likewise uploaded nothing for several runs because the container
wrote as root (`85ddb22`), and RPM artifacts were empty because of a
non-recursive glob while their upload step stayed green (triage skill,
Rule 4).

**Rule.** When a check is added or changed, find one run where it produced a
non-trivial result before trusting a green tick from it. A step that "passes"
on every run including the ones that should have failed is a step that is
not running. Read the artifact size and the upload's file count, not the
step's colour.

## 9. Re-triggering is not a fix

**What happened.** `ad11e3b` and `8a3a20c` are empty commits pushed to
re-run the matrix. Both times the underlying failure was real and returned.
`AGENTS.md` now bans this.

**Rule.** Re-run a job at most once, and only when it died before any test
body ran (exit 125 with a sub-kilobyte log, runner loss, artifact 403 at
finalisation). A failure that reproduces has a cause; find it. Never push an
empty commit, close and reopen a PR, or skip a test to get green.

## 10. Read the whole failure list, then fix the cause once

**What happened.** The stage matrix was pushed forward one failure at a time
for weeks: `10462ce` "clear the last three failures", then more failures
behind them. `60e6a6e` is the first commit written from a complete
eleven-stage traversal and it acted on all five failures at once. `1047aec`
noticed that two cycles had been lost to single-host source outages and gave
76 sources a lookaside fallback in one commit instead of one per outage.
`718d4e4` declined the second and third unresolvable feature in the same
commit as the first once it saw chromaprint had been masking them.

**Rule.** A run that reached the stage you care about is worth more than a
fast fix that supersedes it. When several failures share a shape (same
soname, same host, same exclusion), fix the shape. When one fix exposes the
next in a known chain, read ahead in the log or the dependency graph before
pushing.

## 11. A workaround for one lane has to be applied to both

**What happened.** `2d49b94` stopped uploading debuginfo, and `22acabd`
stopped building it with `debug_package %{nil}`. `7b35dbc` found that on the ten MinGW specs this
orphaned `.debug` files, because `%mingw_debug_package` sets
`__debug_package` itself and only `__debug_install_post %{nil}` stops
`find-debuginfo`. The fix had to land in both the container lane and the mock
lane, and `tests/test_factory_witness.py` asserts both defines appear in
both.

**Rule.** `build-stage.yml` has two build lanes that must agree. A `--define`
or environment fix goes in both, with a test that counts occurrences, or the
next run finds the lane you forgot.

## 12. Two tools reading one field have to agree on its empty value

**What happened.** `3b8d574` made `dist_bump.spec_release` return `""` for a
macro-only Release. `tools/rebuild_plan.py` read the same function and
treated `None` as "no comparable release", so a merge of the two branches
failed a test neither had failed alone (`c6a4b77`, carried as #138 because
the original PR was on a fork). `13c7410`'s zstandard pin had to be
re-applied by hand onto a rewritten prepare job for the same reason
(`bc1ce6a`).

**Rule.** A long-lived branch that touches `tools/` or the workflows has to
be merged with `main` and tested after the merge, not before it. A change
that alters what a shared helper returns names every caller in the commit.

## 13. Reporting a fix without a green job

**What happened.** `65dec69` opens with "I reported that 57925d9 made samba
link ICU 78. That was wrong: samba did not build at all." The failure one
stage later was read as progress on the ICU work when it was fallout from a
build the previous commit had broken. `56b2973` claimed spirv-tools could not
be fixed and was out of scope; both halves were wrong.

**Rule.** A fix is reported with the job that proves it, by run and stage.
When a later stage fails after a change, first check whether the package the
change touched actually built. The triage skill's verification checklist
applies to every claim, including claims about your own previous commit.

## 14. A serialized publish must validate its seed after it acquires the lock

**What happened.** The `publish` job serialized writes to the consumer tag, but
its seed came from the image `prepare` resolved before the build ran. Two
independent reviews of #133 caught the same lost-update window: a concurrent
`main` run could publish a newer image first, then an older run could acquire
the publish lock and replace it with artifacts built from the older witness.
Re-resolving the tag alone would make the seed newer while still allowing those
older artifacts to overwrite it.

**Rule.** A serialized writer must compare the current tag's digest with the
prepare-time witness inside the critical section. If they differ, refuse to
publish and rerun the newer commit. The lock protects the check and the copy
together; it does not make a stale build current.

## 15. Atomic publication must not discard successful build work

**What happened.** The published repository was the only witness and the only
reuse mechanism. When any late package or final gate failed, the repository
correctly stayed unchanged, but the next run recompiled every package absent
from that old witness. WebKitGTK alone compiled repeatedly for hours with
unchanged inputs. A cache-key helper was then merged without workflow wiring,
which documented the intended identity but preserved no work in practice.

**Rule.** Publish a successful package to its content-keyed cache immediately,
then restore it into the ordinary stage artifact on a later exact-key hit. The
cache never replaces rebuild selection or final repository gates, and stale or
directly changed packages never reuse it. Read
[`package-build-cache.md`](package-build-cache.md) before changing this path.

## 16. An observability tool that parses one line of external output crashes the whole run

**What happened.** `tools/scan_rawhide_state.py`'s `query()` unpacked the first
non-empty repoquery line into four tab-separated fields:
`name, evr, arch, sourcerpm = lines[0].split("\t", 3)`. dnf5 writes warnings and
progress to stdout under some conditions, and a package whose query returns
something unexpected does the same, so a single line that was not in that exact
shape raised `ValueError: not enough values to unpack` and took down the scan of
all ~300 packages on a scheduled run (issue #172, red nightly since at least
09-19). The existing unit tests only fed well-formed output, so the crash only
ever surfaced on the live workflow.

**Rule.** A scan or report tool that consumes the stdout of an external command
(dnf repoquery, rpm, a parser) must skip any line that is not the expected shape
and pick the first line that is, logging the discarded line to stderr rather
than crashing. Treat external command output as untrusted: one malformed line
must never lose the whole report, and the discarded line must be visible so a
systematically malformed query is noticed. When the skipped-line guard restates
a validation that another function already performs, validate with *that*
function's grammar (here `rawhide_sources.SRPM_NAME`), not a weaker stand-in
like a `.src.rpm` suffix check: a weaker guard lets garbage into state and moves
the crash downstream instead of removing it. A record that parses cleanly but is
then dropped by a *selection* rule (here the x86_64/noarch arch preference) must
be logged too — a silent drop is the same invisibility as a silent parse
failure. Cover the mixed-good/bad case in a
unit test that mocks the command — tests that only feed clean output let this
class of bug reach a scheduled run.

The lesson is not "dnf writes warnings to stdout". It is that #99 assumed dnf4
`--qf` semantics on dnf5: dnf5 expands only `\n`, not `\t`, in the query format,
so a `\t` is copied through as two characters and the per-arch records glue into
one line, making `query()` return `None` for every package and turning the red
nightly into a green nightly that reports nothing. The fix emits real tabs and a
trailing newline and prefers the x86_64/noarch record over `lines[0]` (i686
sorts first). Pin the real tab in a test so a return to a dnf4-style escape
cannot happen unseen.

## 17. CUPS 2.x and cups-filters 2.x package split

**What happened.** Historically, `cups-filters` contained all filters, PPD
helpers, braille printing, and `cups-browsed`. In upstream 2.x, this was
split across separate source repositories: `libcupsfilters`, `libppd`,
`cups-filters`, `cups-browsed`, and `braille-printer-app`. Fedora Rawhide
dist-git packages each independently. Attempting to build `cups-filters`
or `cups-browsed` without importing `libcupsfilters` and `libppd` fails build
dependency resolution (`pkgconfig(libcupsfilters)` and `pkgconfig(libppd)`).
Furthermore, `cups-filters` only weakly recommends `braille-printer-app`, which
carries heavy dependencies (`liblouis`, `ImageMagick`, etc.) not in the
Hummingbird base.

**Rule.** When importing cups-filters 2.x or cups-browsed into the factory,
import `libcupsfilters` (stage 0), `libppd` (stage 1, depends on
libcupsfilters), and `cups-filters` / `cups-browsed` (stage 2, depending on both
libraries). Do not pull `braille-printer-app` into the core printing closure
unless Braille printing is explicitly required.

## 18. Broad credential or tool exposure across build matrix jobs

**What happened.** `setup-sccache` ran unconditionally for every matrix package
in `build-stage.yml`, writing `ACTIONS_RUNTIME_TOKEN` and cache credentials into
`$GITHUB_WORKSPACE/work/tools/sccache.env`. Because `/work` is mounted into every
package's build container, untrusted upstream build code (`%build` / `%check`)
across all packages had access to the live Actions runtime token and cache service,
even though `mozjs140` was the sole consumer of sccache.

**Rule.** Gate any workflow tool setup that exposes credentials or sensitive
tokens to the specific matrix package that requires it
(`if: matrix.package == 'mozjs140'`). Never mount live Actions credentials or
compiler cache credentials into build environments for packages that do not
consume them.

## 19. A trusted seed must be verified, not just fresh

**What happened.** Entry 14 made the publish job's seed step compare the
resolved digest against the prepare-time witness, which stops an *older* run
from overwriting a newer one. It does nothing about a *bad* image being
current: the step still pulled `ghcr.io/<owner>/utah-packages:latest` (or the
branch tag) and copied every RPM out of it with no check that the image was
ever signed by this workflow. Anyone able to push to the GHCR package once --
a leaked token, a compromised workflow holding `packages: write`, or a
registry-side compromise -- could plant RPMs in the tag and have every
subsequent run copy them forward, sign `repomd.xml` over them, and publish a
new signed image containing them: freshness was being confused for trust.

**Rule.** Before creating a container or copying anything out of a seed
image, `cosign verify` the digest actually pulled -- never the mutable tag,
which can move again after the check -- against this same workflow's own
keyless OIDC identity. `latest` is only ever published from `refs/heads/main`;
a branch tag is only ever published by this workflow running on that branch.
Pin `--certificate-identity` to whichever ref actually matched, not a regex
wide enough to accept either -- a regex scoped to `main` alone breaks every
branch-tag seed, since those are signed under their own ref. `cosign verify`
reads `$DOCKER_CONFIG/config.json`, not podman's own auth file, so a
`podman login` without a matching `--authfile` is invisible to it (the
"Publish the repository" step hit the same split; see its comment on
`DOCKER_CONFIG`).

## 20. Bypassing the source-lock contract with direct JSON parsing

**What happened.** `prepare` originally ran an inline heredoc that parsed
`config/upstream-sources.json` directly (`#101`). When the rebuild plan logic
was extracted into `tools/rebuild_matrix.py`, `main()` continued parsing
`config/upstream-sources.json` via `json.loads` instead of using
`tools.package_inventory.source_locks`. Consequently, validation against
duplicate lock entries and out-of-range stage assignments was bypassed at matrix
planning time.

**Rule.** Every factory tool and workflow step must consume
`tools.package_inventory.source_locks` or `inventory` rather than parsing
`config/upstream-sources.json` directly from the working tree. (Historical reads
across git ranges, such as `git show ${base_sha}:...`, remain raw JSON.) The lock
file is parsed and validated in exactly one place.

## Quick checks before pushing a fix

- [ ] Does `git log --oneline -- <file>` show this file being fixed for the
      same reason before? Read that commit.
- [ ] Does the commit body of the change you are undoing say why it was
      made? Answer that reason explicitly.
- [ ] Is the provider you are removing available from Hummingbird by soname?
- [ ] Is every consumer of a rebuilt library in a later stage than it?
- [ ] Did a config change alter how a package is built without changing its
      NEVR? Then the plan has to know.
- [ ] Is the fix applied in both build lanes?
- [ ] Does a cache change preserve the invariants in
      [`package-build-cache.md`](package-build-cache.md)?
- [ ] Is there a run, on this head, that reached the gate this fix claims to
      satisfy?
