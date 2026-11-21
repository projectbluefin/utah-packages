---
name: rawhide-recipe-reimports
description: >-
  How the daily bump/rawhide-imports pull request decides which carried
  recipes to re-import from Fedora Rawhide unattended, and what it leaves for
  a human. Load before changing tools/rawhide_reimport.py, its safety rules,
  or the bump job in detect-rawhide-updates.yml.
metadata:
  type: procedure
---

# Rawhide recipe re-imports

`detect-rawhide-updates.yml`'s `bump` job runs
`tools/rawhide_reimport.py --apply` daily and opens one pull request on
`bump/rawhide-imports`. Its outputs (`branch`, `pull-request-number`,
`pull-request-operation`, `pull-request-head-sha`) mirror what a
dispatch-based gate needs, because a `GITHUB_TOKEN` pull request triggers no
`pull_request` runs of its own.

## What counts as a move

Koji, not dist-git. For every recipe whose `.hummingbird-upstream.json` says
`branch: rawhide`, the tool asks Koji for the latest build tagged `rawhide`
and reads the dist-git commit it was built from (`getBuild().source`). The
branch head is never imported: Fedora's own build gate has to have passed.
A pin that is *ahead* of Koji (imported from an unbuilt head) is reported as
`behind_pin` and left alone; a move that touches only Fedora CI or monitoring
metadata is `metadata_only` and also left alone, because the provenance bump
alone changes the recipe digest and rebuilds the package and all its
dependants for no change in bytes.

## The safety rules (`classify`, all must hold)

1. Plain Fedora import: `branch: rawhide`, the standard `src.fedoraproject.org`
   remote, `package` equal to the directory.
2. Fast-forward: Koji's commit descends from the pinned commit.
3. The source lock carries only payload fields (`PLAIN_LOCK_KEYS`). A
   `dist_bump`, `rebuild_reason`, `generate`, `dist_git_name` or
   `buildroot_icu77` is a decision taken against the old recipe.
4. No Utah-local divergence: the recipe equals Fedora's tree at the pinned
   commit. Fedora metadata the build never reads (`INERT_FILES`, `.fmf/`,
   `plans/`, `tests/`) may be absent, unless the spec names it; a re-import
   keeps it absent so the diff shows only Fedora's real change. Local spec
   edits (including fixes for inherited upstream scriptlet typos) are
   divergence: the recipe stays out of automated re-imports until a human
   re-imports it by hand.
   A hand re-import has to carry the local deltas forward; for example
   `packages/flatpak` drops Fedora's `flatpak-add-fedora-repos.service`
   (Fedora OCI remotes; Utah uses Flathub) and bases `%autorelease` at 2
   ([`repeated-mistakes.md` §6](repeated-mistakes.md#6-a-re-import-silently-reverts-every-local-decision)).
5. Exactly one spec, same file name, on both commits.
6. `sources`, `Name:`, `Epoch:`, `Version:` and `Release:` unchanged, so the
   SHA-512 lock in `config/upstream-sources.json` still describes the payload.
   Version moves stay with `tools/upstream_bump.py`: Fedora is a recipe feed,
   not a source-update feed. A `Release:` change -- including the
   literal-`12%{?dist}` -> `%autorelease` swap that turned libnma into a
   1.10.6-12 -> 1.10.6-1 downgrade (issue #382, reverted on `main` by
   PR #383; see also issue #400) -- is left for a human: `%autorelease`
   resolves against the build target's tag, so a value of 14 in Koji
   becomes 1 here.
7. No added `BuildRequires` item (literal, unexpanded; a tightened version
   constraint counts as added) and no newly added `%generate_buildrequires`.

Rules 3, 4 and 6 are what make the plymouth failure
([`repeated-mistakes.md` §23](repeated-mistakes.md#23-an-import-pull-request-is-a-recipe-not-a-package))
impossible here: a re-import never changes the recipe set, the lock or the
Packit block, so no count moves. `--apply` re-renders `.packit.yaml` and
exits non-zero if it changed, and the workflow diffs `.packit.yaml` and
`config/upstream-sources.json` after running the unit tests and
`tools/validate.py`.

## Recipes that drift behind Rawhide BuildRequires

A `tools/upstream_bump.py` Version move rewrites only `Version:`, `sources`
and the lock; it keeps the old recipe's BuildRequires. When the new release
needs a new build tool, the bumped recipe fails and this tool cannot repair
it, even after Fedora ships the same version with the fix. libsecret
(issue #565) is the example: #535 moved it 0.21.7 -> 0.21.8.2 on Fedora's
0.21.7 recipe, and 0.21.8's `meson.build` needs `dbus-run-session` (via
`find_program`). The bump made the recipe diverge from the pin (rule 4,
"factory edited libsecret.spec, sources"). Rule 6 also fired: compared with
the pin, Fedora's catch-up commit changes `sources` and `Version:`. Rule 7
fired on the added `/usr/bin/dbus-run-session`, `python3-dbus` and
`python3-gobject`. Rule 4 alone keeps it out for good.

Fix it by hand. When Koji's Rawhide build has the same Version as the lock,
run `tools/import_rawhide.py <pkg> --ref <Koji commit> --replace`. Delete the
`INERT_FILES` the import adds, and confirm `sources` is byte-identical
(the lock then stays). That puts the recipe back to Fedora's tree, so later
moves are automated again. Check the `unsafe` lines of a report run for
`factory edited <pkg>.spec, sources` next to `adds BuildRequires`. That
pairing is how this drift shows up.

## Running it locally

```sh
python3 tools/rawhide_reimport.py                    # report only
python3 tools/rawhide_reimport.py --package libical  # one recipe
python3 tools/rawhide_reimport.py --apply            # rewrite packages/
```

It needs `git` and network access to Koji and src.fedoraproject.org, but no
`rpmspec`: nothing it does expands a spec. src.fedoraproject.org ignores
`--filter=blob:none`, so each moved package is a full clone; a full run
takes about two minutes, and a failed clone is reported as an error and
retried by the next day's run. On 2026-10-03 it saw 399 Rawhide recipes: 284
current, 14 pinned ahead of Koji, 10 metadata-only moves, 8 safe (appstream,
gdk-pixbuf2, ilbc, libei, libical, mobile-broadband-provider-info, re2,
wayland), 81 unsafe and 2 with no Koji Rawhide build (`linux-atm`,
`malcontent-bootstrap`). Most unsafe moves are Version moves (70) or recipes
carrying Utah-local edits (48).

## A %check failure Rawhide already patched: re-import, don't skip

When a carried recipe starts failing `%check` because the build root moved
under it, look at Rawhide's spec before touching the tests: Fedora has often
hit the same build root first. Hummingbird's libcurl 8.23.0 strips
credentials from the effective URL, so git 2.55.0 failed t5550.15/16/20 and
t5541.18 deterministically (issue #565). Rawhide's 2.56.0 recipe
(`4fe49145479f0f74c07b17e87e7c3fb12952ab80`, Koji `git-2.56.0-1.fc46`)
carries `git-2.56.0-http-strip-creds-effective-url.patch`. The fix was a hand
re-import, not a skip pattern:

```sh
python3 tools/rawhide_reimport.py --package git   # reports why it is unsafe
python3 tools/import_rawhide.py git --ref <koji-commit> --replace
```

Pick the Koji-built commit that carries the patch, diff the old recipe
against Fedora's tree at the old pin first to find Utah-local deltas (git had
none), and drop the `INERT_FILES` the import adds back (`.gitignore`,
`.mailmap`). A version move still means a hand lock update: version, URL,
filename and SHA-512 in `config/upstream-sources.json` from the upstream
tarball (download and verify; Fedora stays in `fallback_urls`), matching
`packages/<name>/sources`, and no `dist_bump` to carry because `Release`
resets with the new `Version`.

## A version re-import whose bytes are not Fedora's

`--replace` writes Fedora's `sources`, which pins Fedora's payload. When the
old recipe's `sources` differed from Fedora's tree at the old pin (the
old-pin diff shows it), the factory locks other bytes, so repin after the
import. Two cases from the #1051 drift batch:

- A generated Source0 (`generate` in the lock). intel-media-driver-free
  26.2.4 -> 26.3.5: add the tag archive's SHA-512 to
  `INTEL_MEDIA_INPUT_SHA512` in `tools/generated_sources_common.py`, run
  `python3 tools/generated_sources.py <pkg> packages/<pkg> <out>` twice (the
  digests must agree), and pin that digest in `sources` and the lock
  (`metadata_for()` gives the `version`, `filename` and `generate` fields).
  Unpack Fedora's lookaside copy and diff the trees; they matched.
- An upstream tarball the lookaside recompressed. nfs-utils 3.1.1 from
  kernel.org has Fedora's tree but other bytes, so `sources` pins the
  kernel.org SHA-512 and the lock keeps no lookaside `fallback_urls`.

## Changing the rules

Loosen a rule only with a test in `tests/test_rawhide_reimport.py` that shows
the new case is safe, and keep `classify` pure so the policy stays testable
offline. Widening rule 6 to version moves would make this workflow write
source locks, which needs the download-and-verify path `upstream_bump.py`
already owns; extend that tool rather than duplicating it here.

## Merging

The PR is opened with `GITHUB_TOKEN`, so it fires no `pull_request` CI. The
job then dispatches `bump-upstream-gate.yml` on `bump/rawhide-imports`, the
same gate the daily upstream bump uses (`docs/skills/upstream-version-bumps.md`):
it runs the required Canary check, builds exactly the re-imported recipes
without publishing, merges only at the commit that built, and dispatches the
factory on `main`. A failed build leaves the PR open with a comment naming the
packages. The gate accepts only these two branches, and only diffs confined to
the source lock and `packages/`.
