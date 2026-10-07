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
5. Exactly one spec, same file name, on both commits.
6. `sources`, `Name:`, `Epoch:` and `Version:` unchanged, so the SHA-512 lock
   in `config/upstream-sources.json` still describes the payload. Version
   moves stay with `tools/upstream_bump.py`: Fedora is a recipe feed, not a
   source-update feed.
7. No added `BuildRequires` item (literal, unexpanded; a tightened version
   constraint counts as added) and no newly added `%generate_buildrequires`.

Rules 3, 4 and 6 are what make the plymouth failure
([`repeated-mistakes.md` §23](repeated-mistakes.md#23-an-import-pull-request-is-a-recipe-not-a-package))
impossible here: a re-import never changes the recipe set, the lock or the
Packit block, so no count moves. `--apply` re-renders `.packit.yaml` and
exits non-zero if it changed, and the workflow diffs `.packit.yaml` and
`config/upstream-sources.json` after running the unit tests and
`tools/validate.py`.

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
