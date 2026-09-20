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
job as an artifact. `BUILDROOT_IMAGE` records the expected digest and a
mismatch warns. `tests/test_buildroot_sharing.py` fails any workflow that
pulls the build root from a registry per job. Do not add a per-job pull, and
do not "fix" an exit 125 `manifest unknown` on the build root by editing a
digest.

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
- [ ] Is there a run, on this head, that reached the gate this fix claims to
      satisfy?
