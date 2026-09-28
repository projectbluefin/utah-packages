---
name: gnome-build-meta-audit
description: >-
  Evidence-backed audit of GNOME RPM recipes against GNOME/gnome-build-meta.
  Load before interpreting a difference between a factory GNOME source version,
  patch set, feature option, or dependency edge and the upstream BuildStream
  intent, and before regenerating the audit for a newer GNOME release.
metadata:
  type: reference
---

# GNOME recipes vs gnome-build-meta audit

This factory inherits Fedora RPM recipes, but the GNOME release integration is
defined upstream in [GNOME/gnome-build-meta](https://gitlab.gnome.org/GNOME/gnome-build-meta)
(BuildStream). The audit tool makes the delta explicit and classified:

`tools/audit_gnome_build_meta.py`

It is an **audit, not a rewrite**: Fedora integration, Hummingbird constraints,
RPM subpackages and downstream policy can all justify a difference. The goal is
a maintained, evidence-backed delta, not a mechanical replacement of Fedora
packaging and not a one-time spreadsheet.

## Pinned input

`config/gnome-build-meta.json` records the authoritative GNOME input:

- `source.release_tag` and `source.release_commit` — the pinned release. We pin
  a **full commit**, never mutable `master`, and record the corresponding tag.
- `mapping` — the explicit source-name mapping for names that cannot be inferred
  safely, e.g. `gnome-desktop3 -> core/gnome-desktop.bst`, `gtk4 -> sdk/gtk.bst`,
  `gtk3 -> sdk/gtk+-3.bst`, `gdk-pixbuf2 -> sdk/gdk-pixbuf.bst`,
  `librsvg2 -> sdk/librsvg.bst`, and the GVfs split
  `gvfs* -> sdk-deps/gvfs.bst|sdk/gvfs-client.bst|core/gvfs-daemon.bst`.
- `factory_alias` — subpackages/renames that resolve to a real factory source
  registry name (`gvfs-client`, `gvfs-daemon` -> `gvfs`).
- `classification_overrides` — reviewer decisions on `needs_review` entries
  (see [Classification](#classification)), so a human judgement is not reset by
  the next re-run.
- `unmapped` — GNOME-owned or GNOME-tangential factory sources deliberately
  out of scope, each with the reason it is not mapped. Every GNOME-owned
  factory source must be either mapped or listed here: the report's
  `unaccounted_gnome_sources` lists any that are in neither list (a gnome.org
  url in the factory lock, or a matching gbm element that builds the module
  from gnome.org), so a forgotten source is visible rather than silent.

## Command

```sh
# A checkout of gnome-build-meta at the pinned commit; the tool verifies HEAD
# is source.release_commit and the working tree is clean, unless --no-verify.
git clone https://gitlab.gnome.org/GNOME/gnome-build-meta.git /tmp/gbm
git -C /tmp/gbm checkout <source.release_commit>

python3 tools/audit_gnome_build_meta.py --gbm-dir /tmp/gbm
# writes reports/audit-gnome-build-meta.json and reports/audit-gnome-build-meta.md
# --json-out / --markdown-out override the output paths
# --no-verify audits an exported snapshot (a tarball/exported dir, not a git repo)
```

## What it compares

For every mapped GNOME-owned factory source the audit reports:

- **source identity**: GNOME module + release/ref in gbm vs the factory source
  lock version/filename.
- **release line**: GNOME single-number cycles (>= 40) vs library `major.minor`
  lines are compared with `release_line()`; a same-line dev/rawhide bump is
  informational, a true line mismatch is `needs_review`. The gbm version comes
  from the tar url, or from a `git_repo` element's `git describe` `ref`
  (`1.18.4-0-g4541e0c` -> `1.18.4`); when no version can be read the reason
  says the release line was **NOT compared** instead of reporting alignment.
- **patches**: gbm `kind: patch` sources vs Fedora spec `Patch:`/`PatchN:`
  references.
- **feature flags**: gbm `variables` (e.g. `meson-local: "-Dprofiler=false"`)
  are parsed into `-D` options and diffed against the spec's `-D...` options.
  `feature_comparison` per entry reports the options only one side passes and
  the options both sides pass with a **different value** (`gtk3`'s
  `-Dprofiler=false` in gbm vs `true` in the spec); `true`/`enabled` and
  `false`/`disabled` are normalized so a spelling difference is not reported as
  a conflict. A conflicting option is drift evidence and makes the entry
  `needs_review`.
- **dependency categories**: gbm `build-depends` / `runtime-depends` /
  `depends` are compared against the spec's `BuildRequires:` / `Requires:`
  edges by normalized name (`pkgconfig(glib-2.0)` and `glib2-devel` both
  normalize to the gbm element `glib`). The trailing API version is kept
  separately rather than discarded, so split-API libraries are not collapsed:
  a `gtk3` edge does not match a spec that only requires `gtk4`. An API stated
  on only one side still matches (Fedora's `gnome-desktop3` vs the gbm element
  `gnome-desktop`). `dependency_comparison` reports which gbm edges
  matched a factory edge and which did not. Only that direction is reported:
  an RPM spec also carries Fedora toolchain/packaging edges that have no gbm
  element by design. Both raw lists stay in the report, because a gbm element
  path and an RPM name are not fully mechanically comparable — the judgement is
  the reviewer's, and this narrows what they have to read.
- **component membership**: whether the gbm element exists and is a core/sdk/
  core-deps component, and whether the factory source is tracked at all.

BuildStream `(@)` includes are resolved deliberately (see the `Loader`), and
unresolved merge operators (`(>)`, `(<)`, ...) are recorded per element. The
resolved-include set is reset per element, so a shared include
(`include/gcc-for-recc.yml`) is reported for every element that pulls it in.

## Classification

Every difference is labelled, never treated as an automatic defect:

- `aligned` — source identity and release line match gbm.
- `intentional_fedora` / `intentional_hummingbird` — a reviewer-confirmed
  Fedora/RPM or Hummingbird/downstream justification.
- `actionable_drift` — a real divergence worth a focused follow-up issue/PR.
- `needs_review` — the tool found evidence it cannot attribute to intent; a
  human re-classifies it into one of the above.
- `unmapped` — no gbm element (or no factory registry entry) for the name.

The classifier is conservative: it flags any material drift as `needs_review`
so the default behaviour is human confirmation, not silent acceptance.

### Recording a review decision

`aligned`, `needs_review` and `unmapped` are the tool's own verdicts. The three
human classifications are recorded in `classification_overrides` in
`config/gnome-build-meta.json`, which is what makes them survive a re-run (the
weekly workflow included):

```json
"classification_overrides": {
  "gtk3": {
    "classification": "intentional_fedora",
    "reason": "Fedora builds gtk3 with -Dprofiler=true for sysprof support; reviewed <date>/<PR>."
  }
}
```

Rules the tool enforces (a malformed override is a hard error, never ignored
silently, because an override hides an entry from review):

- `classification` must be `intentional_fedora`, `intentional_hummingbird` or
  `actionable_drift`, and `reason` must be non-empty.
- the key must exist in `mapping`.
- the override applies **only** while the tool still classifies the entry
  `needs_review`. If the evidence changes (a bump realigns the entry, or new
  drift appears), the override is reported as ignored in the entry's `notes`
  and the entry returns to the tool's classification — a stale decision cannot
  mask new drift.

The JSON report keeps both verdicts per entry: `auto_classification` /
`auto_reason` (the tool) and `classification` / `classification_override` (the
recorded decision).

## Update procedure for a newer GNOME release

No tool changes are required to audit a newer release:

1. In `config/gnome-build-meta.json`, bump `source.release_tag` and
   `source.release_commit` to the new pinned tag/commit.
2. `git clone`/`git checkout` gnome-build-meta at that commit.
3. Re-run the command above. Then work the report:
   - fix any entry whose `notes` say the mapped element was **not found in
     gnome-build-meta** (an element renamed or moved in the new release) by
     updating its `mapping` entry;
   - add a `mapping` or `unmapped` entry for anything listed under
     `unaccounted_gnome_sources`;
   - re-check every `needs_review` entry and record the decision in
     `classification_overrides` (see above). Overrides whose entry is no longer
     `needs_review` are reported as ignored in that entry's `notes` — remove
     them.
4. Do **not** follow mutable `master`; always pin a concrete tag + full commit.

File focused follow-up issues or small PRs for `actionable_drift`, and never
fold unrelated package changes into one bulk rewrite.

## Tests

```sh
python3 -m pytest tests/test_audit_gnome_build_meta.py -q
```

`just check` / `just test` gate the change in CI (factory contract + full suite).

Tests that build a throwaway gnome-build-meta checkout must commit with
`git commit --no-verify` and `check=True`. A contributor's global
`core.hooksPath` (for example a Conventional Commits `commit-msg` hook) rejects
messages like `init`, and an unchecked commit fails later as a confusing
`rev-parse HEAD` error instead of at the commit.
