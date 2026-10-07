---
name: factory-build-backlog
description: Track the factory build backlog from projectbluefin/utah-packages#308 — the catalog, the auditor, and the per-area rollup.  Live totals live in the report; do not hard-code them.
---

# Factory build backlog

The Bluefin-vs-Utah bare-metal audit on 2026-09-30 found a set of names
in neither the pinned factory repo nor the Hummingbird supply (the
audit's original total — 551 — is the starting point; live totals
live in `reports/factory-build-backlog.json` and shift every time a
gap closes or a recipe lands). Each name is a candidate factory build
or an explicit wontfix. The backlog catalog
(`config/factory-build-backlog.toml`) is the source of truth: every name
lives in exactly one of the ten issue-aligned areas, and leaving the
backlog requires a matching `[resolved]` or `[wontfix]` entry.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `config/factory-build-backlog.toml` | The catalog: names grouped by area (see the report for the live count) |
| `tools/factory_build_backlog.py` | Auditor: classifies each name against the live repo state |
| `reports/factory-build-backlog.json` | Committed snapshot; live totals (backlog / pending / already_recipe / manifest_wants / resolved / wontfix) — regenerate with a plain run of the auditor |
| `Justfile` `factory-build-backlog` recipe | Runs `--check` against the working tree (wired into `check` so every PR that drifts the report fails before merge) |

The snapshot is deterministic: the report carries no wall-clock field, so a
run that changes nothing rewrites the file byte-for-byte and leaves the tree
clean.

`--check` also runs as a gate in `.github/workflows/validate.yml`.

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

## Closing a backlog gap

Two edits — never one, never none:

- Remove the entry from `[areas.<area>].packages`.
- Add the entry to either:
  - `[resolved].packages` (`{ name = "<n>", commit = "<sha>", pr = <n> }`) —
    a recipe was imported. `commit` and `pr` are both informational; the
    closing record is the import PR (the one this two-edit move ships in)
    and `tools/factory_build_backlog.py:356-357` only reads `entry["name"]`.
    Do not pre-fill `commit` with a SHA from a future commit that does not
    exist yet at PR-open time, and do not let a rebase or squash-merge
    invalidate it. The `pr` field links the entry to its closing PR for
    cross-referencing.
  - `[wontfix].packages` (`{ name = "<n>", reason = "..." }`) — Utah decided
    not to carry it, with a link to the decision issue. `reason` is also
    informational and not validated.

`[resolved]` is the only closing record. A recipe import PR makes this
two-edit move in the same PR; `already_recipe` is the auditor's observation
of an area name whose move is still owed (for example a recipe that landed
before the name was catalogued), not an alternative way to close it, and the
next PR that touches the name sweeps it into `[resolved]`.

The catalog test (`tests/test_factory_build_backlog.py::CatalogConsistencyTests`)
pins the count and sorted-name SHA-256 against the original audit. The auditor
checks that same digest across area, resolved and wontfix entries. A one-for-one
substitution fails even when all counts remain unchanged; moving an existing
name to a closing record preserves the digest. The baseline was verified
against the pinned gist's `nowhere-551.txt`; changing it requires a new audit. The auditor
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
  false `already_recipe` hides a gap. A `%bcond` declared inside such a
  branch is likewise not applied: under an untaken branch it is ignored,
  under an undecidable one (`%if 0%{?fedora} %bcond_without X %else
  %bcond_with X %endif`) the bcond is left unknown, so any `%if %{with X}`
  it guards is undecidable too.

After a recipe PR lands, regenerate `reports/factory-build-backlog.json`; the inventory-driven gate deliberately rejects a snapshot made before that import. Refresh it together with recipe and Packit inventory changes when preparing concurrent PRs.
