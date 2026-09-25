# Auditing GNOME recipes against gnome-build-meta

`tools/audit_gnome_build_meta.py` produces a deterministic, classified delta
between this factory's GNOME source RPMs and the upstream GNOME BuildStream
recipes. It is an audit, not a mechanism to replace Fedora packaging.

## Why

This factory inherits Fedora RPM recipes, but GNOME release integration is
defined upstream in
[GNOME/gnome-build-meta](https://gitlab.gnome.org/GNOME/gnome-build-meta).
Without a repeatable comparison, drift is invisible: source version/commit can
leave the intended GNOME release line, GNOME carries secondary sources / wraps /
patches the RPM recipe handles differently, Meson feature choices diverge,
dependency edges differ, and the package set can drift from GNOME core/sdk
membership.

## The pinned input

`config/gnome-build-meta.json` pins the authoritative GNOME input by full commit
(not mutable `master`) and records the corresponding release tag, the explicit
source-name mapping, subpackage/rename aliases, and deliberate exclusions. Every
GNOME-owned factory source is either mapped or listed under `unmapped` with a
reason; the report's `unaccounted_gnome_sources` names any that are in neither
list.

## Running

See the `gnome-build-meta-audit` skill
([`docs/skills/gnome-build-meta-audit.md`](skills/gnome-build-meta-audit.md)) for
the exact command, what the audit compares, the classification vocabulary, and
the update procedure for a newer GNOME release.

Quick start:

```sh
git clone https://gitlab.gnome.org/GNOME/gnome-build-meta.git /tmp/gbm
git -C /tmp/gbm checkout <source.release_commit>
python3 tools/audit_gnome_build_meta.py --gbm-dir /tmp/gbm
```

Outputs: `reports/audit-gnome-build-meta.json` (machine-readable) and
`reports/audit-gnome-build-meta.md` (reviewable Markdown). The report is
**non-gating** and safe to regenerate.
