---
name: factory-build-backlog
description: Track the 551-name factory build backlog from projectbluefin/utah-packages#308 — the catalog, the auditor, and the per-area rollup.
---

# Factory build backlog

The Bluefin-vs-Utah bare-metal audit on 2026-09-30 found 551 names in
neither the pinned factory repo nor the Hummingbird supply; each one is a
candidate factory build or an explicit wontfix. The backlog catalog
(`config/factory-build-backlog.toml`) is the source of truth: every name
lives in exactly one of the ten issue-aligned areas, and leaving the
backlog requires a matching `[resolved]` or `[wontfix]` entry.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `config/factory-build-backlog.toml` | The catalog: 551 names grouped by area |
| `tools/factory_build_backlog.py` | Auditor: classifies each name against the live repo state |
| `reports/factory-build-backlog.json` | Committed snapshot; regenerate with a plain run of the auditor |
| `Justfile` `factory-build-backlog` recipe | Runs `--check` against the working tree |

The snapshot is deterministic: the report carries no wall-clock field, so a
run that changes nothing rewrites the file byte-for-byte and leaves the tree
clean.

Not wired yet — follow-up work, do not go looking for these:

- `.github/workflows/recalculate-factory-build-backlog.yml` (periodic recalc).
- `--check` as a gate in `validate.yml`, and `factory-build-backlog` in
  `just check`.

Until that lands, run `just factory-build-backlog` by hand before pushing a
catalog or recipe change.

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

## Closing a backlog gap

Two edits — never one, never none:

- Remove the entry from `[areas.<area>].packages`.
- Add the entry to either:
  - `[resolved].packages` (`{ name = "<n>", commit = "<sha>" }`) — a recipe
    was imported, or
  - `[wontfix].packages` (`{ name = "<n>", reason = "..." }`) — Utah decided
    not to carry it, with a link to the decision issue.

The catalog test (`tests/test_factory_build_backlog.py::CatalogConsistencyTests`)
fails a PR that drops a name without recording the decision. The auditor
itself fails when the catalog totals do not reconcile with the report.

## Diagnosing drift

- `--check` compares the whole live report with the committed snapshot —
  totals, states, the per-area rollup and every entry — so a name moving
  between areas fails the gate even though the counts are unchanged.
- A `pending` count that grows means a name was added to the catalog
  without a recipe; re-run `tools/factory_build_backlog.py` and inspect
  `reports/factory-build-backlog.json`.
- A `pending` count that shrinks without a commit means someone dropped a
  name from the catalog without recording the decision; `git log -p
  config/factory-build-backlog.toml` is the fastest trace.
- `already_recipe` for a binary subpackage (`libavcodec`, `libavformat`,
  ...) means the source package's recipe declares it with a `%package`
  line: read the recipe, not the binary name. The auditor resolves both
  `%package -n NAME` and `%package SUFFIX` (which names `<spec>-SUFFIX`),
  and only when the `%package` is reached by the default build. A binary
  name no `%package` line declares — such as `ffmpeg-libs`, which RPM
  never builds under that name here — stays `pending` until the operator
  closes it in `[resolved]` or `[wontfix]`.
- A `%package` behind a disabled or undecidable `%if` does not count.
  `packages/gstreamer1-plugins-good/` declares `%package qt6` under `%if
  %{with qt6}` while the spec sets `%bcond_with qt6` and nothing in the
  factory passes `--with qt6`, so `gstreamer1-plugins-good-qt6` is
  `pending`: the factory build does not produce it. `packages/ffmpeg/`
  declares its `libav*` subpackages under `%if ! %{with freeworld_lavc}`,
  which is true by default, so those are `already_recipe`. Conditions the
  auditor cannot decide without a build target (`%ifarch`, `0%{?fedora}`)
  are treated as not taken — an extra `pending` name is visible work, a
  false `already_recipe` hides a gap.
