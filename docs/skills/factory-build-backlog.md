---
name: factory-build-backlog
description: Track the factory build backlog from projectbluefin/utah-packages#308 — the catalog, the auditor, and the per-area rollup.  Live totals are computed, never committed; do not hard-code them.
---

# Factory build backlog

The Bluefin-vs-Utah bare-metal audit on 2026-09-30 found a set of names
in neither the pinned factory repo nor the Hummingbird supply (the
audit's original total — 551 — is the starting point; live totals are
computed by the auditor and shift every time a gap closes or a recipe
lands). Each name is a candidate factory build
or an explicit wontfix. The backlog catalog
(`config/factory-build-backlog.toml`) is the source of truth: every name
lives in exactly one of the ten issue-aligned areas, and leaving the
backlog requires a matching `[resolved]` or `[wontfix]` entry.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `config/factory-build-backlog.toml` | The catalog: names grouped by area (the auditor prints the live count) |
| `tools/factory_build_backlog.py` | Auditor: classifies each name against the live repo state and prints a Markdown summary; `--output <path>` writes the full JSON report |
| `Justfile` `factory-build-backlog` recipe | Runs `--check` against the working tree (wired into read-only `check`) |
| `.github/workflows/validate.yml` *Factory build backlog* job | Runs the same `--check`, then publishes the summary to the job summary and the JSON report as the `factory-build-backlog` artifact |

The report is derived and **not committed**. It used to be
(`reports/factory-build-backlog.json`, compared byte-for-byte by `--check`),
and since every recipe import moves its totals, each merge to `main`
re-conflicted most open import PRs. Do not reintroduce a tracked report,
rollup, or count: read totals from `just factory-build-backlog` locally or
from the CI job summary or artifact. The report carries no wall-clock field,
so two runs over the same tree produce identical JSON.

`--check` exits 1 when:

- a name repeats inside an area, appears in two areas, or sits in two of
  area / `[resolved]` / `[wontfix]`;
- `[meta].audit_names_sha256` is missing, or the sorted names across areas,
  `[resolved]` and `[wontfix]` do not hash to it (every audited name is
  accounted for exactly once);
- a backlog name has its own recipe directory but no source lock
  (`inconsistent_recipe_state`: a half-imported name).

Closing a gap is therefore a catalog edit only; there is nothing to
regenerate for the backlog. `just regenerate-inventory` refreshes the
generated Packit configuration after combining `main` and PR source changes.

Not wired yet — follow-up work, do not go looking for it:
`.github/workflows/recalculate-factory-build-backlog.yml` (periodic recalc).

## Partitions

The auditor classifies each catalog name into exactly one state:

| State | Meaning |
| --- | --- |
| `already_recipe` | A directory exists under `packages/<name>/`, or the name is an unconditionally built `%package` subpackage of such a spec |
| `already_locked` | `config/upstream-sources.json` has a lock entry |
| `already_packit` | `.packit.yaml` has a package block |
| `manifest_wants` | `config/bluefin-packages.toml` lists the name |
| `pending` | None of the above; a factory build is owed |

Wontfixed names are not a state: leaving the backlog removes the name from
every area, and the auditor rejects a catalog where an area name is also in
`[wontfix]`. `[wontfix]` shows up in `totals`, never in `states`.

Order is significant: the strongest signal wins. Reordering the
`_classify` function silently changes counts and is a contract break.

## Sections

This skill is split by section so concurrent edits do not collide. Edit the file that owns the section.

- [Closing a backlog gap](factory-build-backlog/closing-a-backlog-gap.md#closing-a-backlog-gap)
- [Diagnosing drift](factory-build-backlog/diagnosing-drift.md#diagnosing-drift)
- [Boot-screen output reconciliation](factory-build-backlog/diagnosing-drift.md#boot-screen-output-reconciliation)
- [Firewall connection monitor acceptance](factory-build-backlog/package-notes.md#firewall-connection-monitor-acceptance)
- [Hand-locking an import without `rpmspec`](factory-build-backlog/package-notes.md#hand-locking-an-import-without-rpmspec)
- [IP set package family](factory-build-backlog/package-notes.md#ip-set-package-family)
- [JBIG2 decoder library](factory-build-backlog/package-notes.md#jbig2-decoder-library)
- [Checkpoint/restore package family](factory-build-backlog/package-notes.md#checkpointrestore-package-family)
- [Windows domain enrollment (adcli)](factory-build-backlog/package-notes.md#windows-domain-enrollment-adcli)
- [Serd source verification](factory-build-backlog/package-notes.md#serd-source-verification)
- [HFS+ filesystem tools](factory-build-backlog/package-notes.md#hfs-filesystem-tools)
- [Libev event loop library](factory-build-backlog/package-notes.md#libev-event-loop-library)
- [uvg266 VVC encoder library](factory-build-backlog/package-notes.md#uvg266-vvc-encoder-library)
- [davs2 AVS2 decoder library](factory-build-backlog/package-notes.md#davs2-avs2-decoder-library)
