#!/usr/bin/env python3
"""Create a deterministic Rawhide availability report.

This is observability only. Rawhide metadata must not trigger a package update:
Fedora dist-git snapshots are accepted by dist_git.py only after their NVR has
passed the Koji gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.rawhide_sources import SRPM_NAME, import_binaries, source_name


def query(package: str) -> dict[str, str] | None:
    command = [
        "dnf", "repoquery", "--latest-limit=1",
        "--qf", "%{name}\t%{evr}\t%{arch}\t%{sourcerpm}\n", package,
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    lines = [line for line in result.stdout.splitlines() if line and "(none)" not in line]
    # dnf5 expands only \n in --qf, not \t (libdnf5-cli copies the two-char
    # sequence through verbatim), so the format must carry real tabs and a
    # trailing newline. A literal "\t" is copied through as backslash-t and the
    # i686 and x86_64 records glue into one line, which is the "expected 4, got
    # 1" that #99's dnf4-style format produced (#172): query() then returns None
    # for every package and main() writes an empty report that exits green,
    # hiding the crash instead of closing it. Prefer x86_64 then noarch over
    # lines[0], which is i686 (arch sorts first); the source package is
    # arch-independent but a fixed arch keeps the report deterministic. Skip any
    # line that is not four real-tab fields (dnf5 can still emit warnings into
    # stdout) rather than crashing (#172). Every discarded line and every
    # package that survives parsing but has no selectable arch is logged to
    # stderr, so a systematically malformed query or an arch-filtered package is
    # visible instead of silently vanishing from the report.
    records: dict[str, dict[str, str]] = {}
    for line in lines:
        parts = line.split("\t", 3)
        if len(parts) != 4:
            sys.stderr.write(
                f"scan_rawhide_state: skipping line that is not four "
                f"tab-separated fields for {package!r}: {line!r}\n"
            )
            continue
        name, evr, line_arch, sourcerpm = parts
        if not SRPM_NAME.match(sourcerpm):
            sys.stderr.write(
                f"scan_rawhide_state: skipping line with non-SRPM "
                f"sourcerpm for {package!r}: {line!r}\n"
            )
            continue
        records.setdefault(
            line_arch,
            {"name": name, "evr": evr, "arch": line_arch, "sourcerpm": sourcerpm},
        )
    for arch in ("x86_64", "noarch"):
        if arch in records:
            return records[arch]
    if records:
        sys.stderr.write(
            f"scan_rawhide_state: no x86_64 or noarch record for {package!r}; "
            f"dropping it from the report (arches seen: "
            f"{', '.join(sorted(records))})\n"
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("config/bluefin-packages.toml"))
    parser.add_argument("--state", type=Path, default=Path("config/rawhide-state.json"))
    parser.add_argument("--changed", type=Path, default=Path("reports/rawhide-changed-sources.txt"))
    args = parser.parse_args()

    manifest = tomllib.loads(args.manifest.read_text())
    binaries = import_binaries(manifest)
    state = {package: query(package) for package in binaries}
    state = {package: value for package, value in state.items() if value}
    previous = json.loads(args.state.read_text()) if args.state.exists() else {}
    changed = sorted({
        source_name(value["sourcerpm"])
        for package, value in state.items()
        if previous.get(package) != value
    })

    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.changed.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    args.changed.write_text("\n".join(changed) + ("\n" if changed else ""))
    print(f"observed {len(state)} Rawhide packages; queued {len(changed)} source rebuilds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
