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
  registry name (`gvfs-client`, `gvfs-daemon` -> `gvfs`; `tinysparql` ->
  `localsearch`).
- `unmapped` — GNOME-tangential factory sources deliberately out of scope.

## Command

```sh
# A checkout of gnome-build-meta at the pinned commit; the tool verifies the
# working tree resolves to source.release_commit unless --no-verify is given.
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
  informational, a true line mismatch is `needs_review`.
- **patches**: gbm `kind: patch` sources vs Fedora spec `Patch:`/`PatchN:`
  references.
- **feature flags**: gbm `variables` (e.g. `meson-local`) vs spec `-D...`
  options.
- **dependency categories**: gbm `build-depends` / `runtime-depends` / `depends`
  are recorded alongside the spec's `BuildRequires:` and `Requires:` edges. Both
  sides are reported; the tool does not diff them, because a gbm element path
  and an RPM name are not mechanically comparable — the comparison is the
  reviewer's, and the report exists to put both lists in front of them.
- **component membership**: whether the gbm element exists and is a core/sdk/
  core-deps component, and whether the factory source is tracked at all.

BuildStream `(@)` includes are resolved deliberately (see the `Loader`), and
unresolved merge operators (`(>)`, `(<)`, ...) are recorded per element.

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

## Update procedure for a newer GNOME release

No tool changes are required to audit a newer release:

1. In `config/gnome-build-meta.json`, bump `source.release_tag` and
   `source.release_commit` to the new pinned tag/commit.
2. `git clone`/`git checkout` gnome-build-meta at that commit.
3. Re-run the command above. Fix any `name mapping:` (new module renames) and
   re-classify `needs_review` entries.
4. Do **not** follow mutable `master`; always pin a concrete tag + full commit.

File focused follow-up issues or small PRs for `actionable_drift`, and never
fold unrelated package changes into one bulk rewrite.

## Tests

```sh
python3 -m pytest tests/test_audit_gnome_build_meta.py -q
```

`just check` / `just test` gate the change in CI (factory contract + full suite).
