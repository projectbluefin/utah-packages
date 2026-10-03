#!/usr/bin/env python3
"""Measure the factory build backlog against the current repository state.

Issue ``projectbluefin/utah-packages#308`` records the 551 Bluefin names that
Utah's bare-metal audit (2026-09-30) found in neither the pinned factory repo
nor the Hummingbird supply. Each entry is a candidate factory build or an
explicit wontfix; tracking its real state is what this tool exists to do.

The tool takes ``config/factory-build-backlog.toml`` as the source of truth
(so adding a name is one PR), partitions every entry by where it stands in
the factory today, and emits ``reports/factory-build-backlog.json`` as a
deterministic snapshot: the report carries no wall-clock field, so a run
that changes nothing rewrites the file byte-for-byte. ``--check`` exits 1
if the snapshot is stale or if the catalog itself is malformed, so the
snapshot stays trustworthy in CI.

Partitions:

- ``already_recipe``   — a directory exists under ``packages/<name>/``, or
  the name is a ``%package`` subpackage of such a spec (explicit
  ``%package -n NAME`` or implicit ``%package SUFFIX``, which names
  ``<spec>-SUFFIX``): the factory build that ships the parent also ships
  it. A ``%package`` guarded by an ``%if`` that is off or undecidable for
  the default build does not count -- it is not built, so the name is
  still owed.
- ``already_locked``   — ``config/upstream-sources.json`` has a lock entry
- ``already_packit``   — ``.packit.yaml`` has a package block
- ``manifest_wants``   — ``config/bluefin-packages.toml`` lists the name
- ``pending``          — none of the above; a factory build is still owed

Names in ``[wontfix]`` have left the backlog, so they are never report
entries: the catalog contract forbids a name from being in an area and in
``[wontfix]`` at once, and ``--check`` rejects a catalog that does it.
``[wontfix]`` is counted in ``totals``, not partitioned.

The report records every name once with the partition it falls into and a
per-area rollup. Counts always reconcile: ``total = already_recipe + (else
already_locked + (else already_packit + (else manifest_wants + (else
pending))))`` -- because each check is strictly weaker than the previous,
the most-specific state wins.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory, load_source_locks
from tools.packit_workflow import package_names


CATALOG_PATH = Path("config/factory-build-backlog.toml")
REPORT_PATH = Path("reports/factory-build-backlog.json")
PACKIT_PATH = Path(".packit.yaml")
UPSTREAM_PATH = Path("config/upstream-sources.json")
MANIFEST_PATH = Path("config/bluefin-packages.toml")


def _load_catalog(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _packit_names(path: Path) -> set[str]:
    """Package names declared in the root ``.packit.yaml`` ``packages:`` block.

    Delegates to ``tools.packit_workflow.package_names`` so the audit reads
    the Packit config through the same primitive the rest of the codebase
    already trusts.
    """
    if not path.is_file():
        return set()
    return set(package_names(path))


def _lock_names(path: Path) -> set[str]:
    """Package names pinned in ``config/upstream-sources.json``.

    Goes through :func:`tools.package_inventory.load_source_locks`, which the
    factory documents as the only parse of that file: a duplicate lock or an
    unknown stage must fail here exactly as it fails for every other reader.
    """
    if not path.is_file():
        return set()
    return set(load_source_locks(path).keys())


def _manifest_names(path: Path) -> set[str]:
    """Every package listed in any section of the Bluefin manifest."""
    if not path.is_file():
        return set()
    data = tomllib.loads(path.read_text())
    names: set[str] = set()
    for section, values in data.items():
        if section == "excluded" or not isinstance(values, dict):
            continue
        names.update(values.get("packages", []))
    return names


def _recipe_names(root: Path) -> set[str]:
    """Names with a recipe directory under ``packages/``."""
    packages = root / "packages"
    if not packages.is_dir():
        return set()
    return {d.name for d in packages.iterdir() if d.is_dir()}


# Macros the auditor resolves when expanding ``%package -n`` lines. These
# are the conditional suffixes Fedora-style specs use to namespace the
# free-world rebuild of a package (``-free``) and the no-suffix default
# (empty string). Other ``%{?...}`` conditionals are intentionally not
# resolved: if a name is conditionally declared, the auditor stays
# conservative and treats it as not yet shipped -- the operator can
# always add the name to ``[resolved]`` to close it explicitly.
_RECIPE_SUFFIX_RESOLUTIONS = {
    "pkg_suffix": "",
    "basepkg_suffix": "",
}


def _expand_recipe_macro(value: str) -> str:
    """Resolve the auditor's known ``%{name}`` and ``%{?...}`` forms.

    ``%{name}`` and ``%{pkg_name}`` use the spec's own ``Name:`` tag
    (which the auditor does not parse), so they are left alone and
    produce names with the macro in place -- which is a conservative
    miss, not a false positive. ``%{?pkg_suffix}`` / ``%{?basepkg_suffix}``
    expand to the empty string for the no-suffix build (which is the
    common case). Anything else is left untouched.
    """
    if "%{?pkg_suffix}" in value:
        value = value.replace("%{?pkg_suffix}", _RECIPE_SUFFIX_RESOLUTIONS["pkg_suffix"])
    if "%{?basepkg_suffix}" in value:
        value = value.replace("%{?basepkg_suffix}", _RECIPE_SUFFIX_RESOLUTIONS["basepkg_suffix"])
    return value


def _bcond_state(line: str, bconds: dict[str, bool]) -> None:
    """Record a ``%bcond*`` declaration in ``bconds``.

    Three shapes exist: ``%bcond_with NAME`` (feature off by default),
    ``%bcond_without NAME`` (on by default) and the modern
    ``%bcond NAME DEFAULT`` where ``DEFAULT`` is ``0`` or ``1``. A later
    declaration wins, which matches RPM's own last-definition-wins
    behaviour when a spec redefines a bcond under an ``%if``.
    """
    tokens = line.split()
    if len(tokens) < 2:
        return
    directive = tokens[0]
    if directive == "%bcond_with":
        bconds[tokens[1]] = False
    elif directive == "%bcond_without":
        bconds[tokens[1]] = True
    elif directive == "%bcond" and len(tokens) >= 3:
        try:
            bconds[tokens[1]] = bool(int(tokens[2]))
        except ValueError:
            bconds.pop(tokens[1], None)


_WITH_RE = re.compile(r"^(?P<negate>!\s*)?%\{(?P<kind>with|without)\s+(?P<name>[A-Za-z0-9_]+)\}$")


def _eval_condition(expression: str, bconds: dict[str, bool]) -> bool | None:
    """Truth of an ``%if`` expression, or ``None`` when it is not decidable.

    Only the bcond forms the auditor can resolve are evaluated --
    ``%{with X}``, ``%{without X}`` and their ``!`` negation. Everything
    else (``0%{?fedora}``, ``%ifarch``, arithmetic comparisons) is
    undecidable without a build target, and the auditor says so rather
    than guessing a distro.
    """
    match = _WITH_RE.match(" ".join(expression.split()))
    if match is None:
        return None
    value = bconds.get(match.group("name"))
    if value is None:
        return None
    if match.group("kind") == "without":
        value = not value
    if match.group("negate"):
        value = not value
    return value


def _subpackage_names(root: Path) -> set[str]:
    """Names declared by ``%package`` lines in every spec under ``packages/``.

    A spec may declare multiple binary subpackages in addition to the
    recipe directory itself. There are two ``%package`` shapes:

    - ``%package -n NAME`` — explicit name; the subpackage is built and
      named whatever ``NAME`` says (e.g. ``%package -n libavcodec`` in
      ``packages/ffmpeg/ffmpeg.spec`` ships ``libavcodec``).
    - ``%package SUFFIX`` — implicit; the subpackage is named
      ``{spec_name}-{SUFFIX}`` because RPM tacks the suffix onto the
      spec's own ``Name:``.

    A ``%package`` line only counts when every enclosing ``%if`` is known
    to be taken for this factory's default build. ``%package qt6`` in
    ``packages/gstreamer1-plugins-good/`` sits under ``%if %{with qt6}``
    with ``%bcond_with qt6`` and nothing in the factory passing
    ``--with qt6``, so that subpackage is never built and the name stays
    in the backlog; ``packages/ffmpeg/`` declares its ``libav*``
    subpackages under ``%if ! %{with freeworld_lavc}``, which is true by
    default, so those do ship. Conditions the auditor cannot decide
    (``%ifarch``, ``0%{?fedora}``) are treated as not taken: a missed
    name shows up as ``pending`` work, while a false ``already_recipe``
    would hide a real gap.

    Without parsing both shapes, the auditor counts the unguarded
    implicit-suffix names as ``pending`` even though the factory build
    already ships them, inflating the "pending" total and forcing the
    operator to close every such name by hand.
    """
    packages = root / "packages"
    if not packages.is_dir():
        return set()
    names: set[str] = set()
    for spec in packages.glob("*/[!.]*.spec"):
        spec_name = spec.parent.name
        bconds: dict[str, bool] = {}
        # One frame per open ``%if``: ``True`` taken, ``False`` not taken,
        # ``None`` undecidable. A ``%package`` counts only when every frame
        # is ``True``.
        stack: list[bool | None] = []
        for line in spec.read_text().splitlines():
            line = line.strip()
            if line.startswith("%bcond"):
                _bcond_state(line, bconds)
                continue
            if line.startswith("%if"):
                directive, _, rest = line.partition(" ")
                if directive == "%if":
                    stack.append(_eval_condition(rest, bconds))
                else:
                    # ``%ifarch``/``%ifnarch``/``%ifos``: target-dependent.
                    stack.append(None)
                continue
            if line.startswith("%elif"):
                if stack:
                    stack[-1] = None
                continue
            if line == "%else" or line.startswith("%else "):
                if stack:
                    current = stack[-1]
                    stack[-1] = None if current is None else not current
                continue
            if line.startswith("%endif"):
                if stack:
                    stack.pop()
                continue
            if not line.startswith("%package"):
                continue
            if any(frame is not True for frame in stack):
                continue
            tokens = line.split(None, 3)
            if len(tokens) < 2:
                continue
            if tokens[1] == "-n":
                # Explicit form: ``%package -n NAME`` — the subpackage's
                # own name, which may differ entirely from the spec's.
                if len(tokens) < 3:
                    continue
                candidate = _expand_recipe_macro(tokens[2]).strip()
            else:
                # Implicit form: ``%package SUFFIX`` — RPM tacks the
                # suffix onto the spec's ``Name:`` tag, which the auditor
                # does not parse. The directory name is used as an
                # approximation of that tag (``_spec_per_package`` only
                # enforces one spec per directory, not that the two
                # agree), so a directory that renames the package yields
                # a name that matches nothing -- a conservative miss.
                suffix = tokens[1].strip()
                candidate = f"{spec_name}-{suffix}"
            # ``-devel`` and other in-spec splits share the recipe's
            # provenance; classifying them under ``already_recipe`` is
            # the right signal -- the factory build that ships the
            # parent package also ships its -devel sibling.
            if candidate and not candidate.startswith("-"):
                names.add(candidate)
    return names


def _classify(
    name: str,
    *,
    recipes: set[str],
    subpackages: set[str],
    locks: set[str],
    packit: set[str],
    manifest: set[str],
) -> str:
    """Pick the most-specific partition a name falls into.

    Order is significant: the first match wins. ``already_recipe`` is the
    strongest signal (a full spec + provenance + sources file is present
    for the package itself, OR the name is a ``%package -n`` subpackage of
    an existing recipe -- in which case the factory build that ships the
    parent recipe also ships the subpackage), then ``already_locked``
    (source URL is SHA-512 pinned), then ``already_packit`` (Packit block
    declared), then ``manifest_wants`` (consumer asks for it), then
    ``pending`` (a factory build is still owed). Reordering this list
    silently changes counts.

    Wontfixed names are not classified: leaving the backlog removes the name
    from every area, and ``_report`` rejects a catalog where an area name is
    also in ``[wontfix]``.
    """
    if name in recipes or name in subpackages:
        return "already_recipe"
    if name in locks:
        return "already_locked"
    if name in packit:
        return "already_packit"
    if name in manifest:
        return "manifest_wants"
    return "pending"


def _catalog_totals(catalog: dict) -> tuple[set[str], dict[str, list[str]], set[str], set[str]]:
    """Pull the catalog's three name sets: backlog, wontfix, resolved.

    The per-area value is a ``list``, not a ``set``: de-duplicating here
    would hide a name repeated inside a single area's ``packages`` list,
    and the catalog contract is that a backlog name appears exactly once
    across the whole catalog. ``_report`` counts occurrences and rejects
    any repeat, within an area or across two of them.
    """
    backlog: dict[str, list[str]] = {}
    for area, info in catalog.get("areas", {}).items():
        backlog[area] = list(info.get("packages", []))
    resolved = {entry["name"] for entry in catalog.get("resolved", {}).get("packages", [])}
    wontfix = {entry["name"] for entry in catalog.get("wontfix", {}).get("packages", [])}
    all_backlog: set[str] = set()
    for names in backlog.values():
        all_backlog.update(names)
    return all_backlog, backlog, wontfix, resolved


def _report(root: Path, catalog_path: Path) -> dict:
    catalog = _load_catalog(catalog_path)
    meta = catalog.get("meta", {})

    recipes = _recipe_names(root)
    subpackages = _subpackage_names(root)
    locks = _lock_names(root / UPSTREAM_PATH.relative_to("."))
    packit = _packit_names(root / PACKIT_PATH.relative_to("."))
    manifest = _manifest_names(root / MANIFEST_PATH.relative_to("."))

    all_backlog, by_area, wontfix_set, resolved_set = _catalog_totals(catalog)

    # The catalog is the contract: any name in the backlog appears exactly
    # once -- not twice in one area's list, and not once in each of two areas.
    seen: dict[str, int] = {}
    for area, names in by_area.items():
        for name in names:
            seen[name] = seen.get(name, 0) + 1
    duplicates = sorted(name for name, count in seen.items() if count != 1)
    if duplicates:
        raise SystemExit(
            "catalog lists these names more than once (repeated within an area "
            f"or present in more than one area): {duplicates}"
        )
    # A name that has moved out of the backlog (``[resolved]`` or ``[wontfix]``)
    # MUST NOT also appear in any area: the documented closing contract is a
    # two-edit (drop the entry, record the decision). An overlap here means
    # the next import run would silently keep counting the closed gap as
    # ``pending``.
    overlap_backlog_resolved = sorted(all_backlog & resolved_set)
    overlap_backlog_wontfix = sorted(all_backlog & wontfix_set)
    if overlap_backlog_resolved:
        raise SystemExit(
            f"catalog lists these names in both an area and [resolved]: {overlap_backlog_resolved}"
        )
    if overlap_backlog_wontfix:
        raise SystemExit(
            f"catalog lists these names in both an area and [wontfix]: {overlap_backlog_wontfix}"
        )
    # A name that has been wontfixed is, by definition, not a future build
    # candidate; it does not need a recipe and it does not need a manifest
    # decision. Marking it as both would mean we kept the door open after we
    # decided to close it.
    overlap_resolved_wontfix = sorted(resolved_set & wontfix_set)
    if overlap_resolved_wontfix:
        raise SystemExit(
            f"catalog lists these names in both [resolved] and [wontfix]: {overlap_resolved_wontfix}"
        )

    partition_counts: dict[str, int] = {}
    entries: list[dict] = []
    for area in sorted(by_area):
        for name in sorted(by_area[area]):
            state = _classify(
                name,
                recipes=recipes,
                subpackages=subpackages,
                locks=locks,
                packit=packit,
                manifest=manifest,
            )
            partition_counts[state] = partition_counts.get(state, 0) + 1
            entries.append(
                {
                    "name": name,
                    "area": area,
                    "state": state,
                }
            )

    area_rollup: dict[str, dict[str, int]] = {}
    for area in sorted(by_area):
        rollup = {}
        for entry in entries:
            if entry["area"] != area:
                continue
            rollup[entry["state"]] = rollup.get(entry["state"], 0) + 1
        rollup["total"] = len(by_area[area])
        area_rollup[area] = dict(sorted(rollup.items()))

    report = {
        "issue": meta.get("issue", ""),
        "audit_source": meta.get("audit_source", ""),
        "audit_measured_at": meta.get("audit_measured_at", ""),
        "audit_digest_bluefin": meta.get("audit_digest_bluefin", ""),
        "audit_digest_utah": meta.get("audit_digest_utah", ""),
        "audit_digest_factory": meta.get("audit_digest_factory", ""),
        "totals": {
            "backlog": len(all_backlog),
            "resolved": len(resolved_set),
            "wontfix": len(wontfix_set),
        },
        "states": dict(sorted(partition_counts.items())),
        "areas": area_rollup,
        "entries": entries,
    }
    # Inventory spot-check: every name with its own recipe (not a
    # subpackage of one) must also be in the inventory's source-locked set,
    # not just in packages/. Mismatches here mean a recipe was added
    # without updating upstream-sources.json; this is what catches a
    # half-imported name that the backlog would otherwise call resolved.
    # Subpackages (libavcodec, libavutil, ...) are deliberately skipped:
    # they share the recipe's provenance, and the inventory tracks the
    # parent recipe, not the per-binary outputs.
    locked_records = {record.name for record in inventory(root) if record.source_locked}
    inconsistent = []
    for entry in entries:
        if entry["state"] == "already_recipe" and entry["name"] in recipes and entry["name"] not in locked_records:
            inconsistent.append(entry["name"])
    if inconsistent:
        report["inconsistent_recipe_state"] = sorted(inconsistent)
    return report


def _check(report: dict, path: Path) -> int:
    """Verify the committed snapshot still matches the live repository state.

    ``--check`` is the gate. The report carries no wall-clock field, so the
    live report and the committed snapshot must be equal byte-for-byte;
    anything else is drift. The messages below name the drifting section
    (meta, totals, states, areas, entries, recipe consistency) so a failure
    says what moved instead of dumping two large dicts.
    """
    if not path.is_file():
        print(f"missing snapshot at {path}; run without --check to regenerate")
        return 1

    on_disk = json.loads(path.read_text())
    errors = []
    # ``[meta]`` (issue, audit_source, the three digest pins, audit_measured_at)
    # is sourced from the catalog, so a stale snapshot would not catch a
    # metadata-only edit. Compare the whole ``meta`` block byte-for-byte.
    if report.get("issue") != on_disk.get("issue"):
        errors.append(f"issue drift: live {report.get('issue')!r} vs snapshot {on_disk.get('issue')!r}")
    if report.get("audit_source") != on_disk.get("audit_source"):
        errors.append(
            f"audit_source drift: live {report.get('audit_source')!r} vs "
            f"snapshot {on_disk.get('audit_source')!r}"
        )
    for digest in ("audit_digest_bluefin", "audit_digest_utah", "audit_digest_factory"):
        if report.get(digest) != on_disk.get(digest):
            errors.append(
                f"{digest} drift: live {report.get(digest)!r} vs snapshot {on_disk.get(digest)!r}"
            )
    if report.get("audit_measured_at") != on_disk.get("audit_measured_at"):
        errors.append(
            f"audit_measured_at drift: live {report.get('audit_measured_at')!r} vs "
            f"snapshot {on_disk.get('audit_measured_at')!r}"
        )
    if report["totals"] != on_disk.get("totals"):
        errors.append(f"totals drift: live {report['totals']} vs snapshot {on_disk.get('totals')}")
    if report["states"] != on_disk.get("states"):
        errors.append(f"states drift: live {report['states']} vs snapshot {on_disk.get('states')}")
    # Totals and states are blind to a name moving between areas or two names
    # of the same state swapping places, so compare the rollup and the entry
    # list themselves. ``report["entries"]`` always has exactly
    # ``totals["backlog"]`` items (``_report``'s per-area classification loop
    # emits one entry per backlog name) so an entries-vs-backlog count check
    # is unreachable and is not duplicated here.
    backlog = report["totals"]["backlog"]
    if report["areas"] != on_disk.get("areas"):
        moved = sorted(
            area
            for area in set(report["areas"]) | set(on_disk.get("areas", {}))
            if report["areas"].get(area) != on_disk.get("areas", {}).get(area)
        )
        errors.append(f"areas drift: {moved}")
    if report["entries"] != on_disk.get("entries"):
        live_entries = {entry["name"]: entry for entry in report["entries"]}
        disk_entries = {entry["name"]: entry for entry in on_disk.get("entries", [])}
        changed = sorted(
            name
            for name in set(live_entries) | set(disk_entries)
            if live_entries.get(name) != disk_entries.get(name)
        )
        errors.append(f"entries drift: {changed}")
    if report.get("inconsistent_recipe_state") != on_disk.get("inconsistent_recipe_state"):
        errors.append(
            "inconsistent_recipe_state drift: live "
            f"{report.get('inconsistent_recipe_state')} vs snapshot "
            f"{on_disk.get('inconsistent_recipe_state')}"
        )
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"factory-build-backlog snapshot consistent ({backlog} entries, {report['states'].get('pending', 0)} pending)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when the committed snapshot is stale")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    catalog_path = (root / args.catalog).resolve() if not args.catalog.is_absolute() else args.catalog
    output_path = (root / args.output).resolve() if not args.output.is_absolute() else args.output

    report = _report(root, catalog_path)

    if args.check:
        return _check(report, output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    # Stable stdout summary: per-state counts, then per-area pending counts
    # so the user can see which area is the biggest gap.
    summary = {"states": report["states"], "totals": report["totals"]}
    pending_per_area = {
        area: rollup.get("pending", 0)
        for area, rollup in sorted(report["areas"].items())
    }
    summary["pending_per_area"] = pending_per_area
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
