#!/usr/bin/env python3
"""Resolve Bluefin binary packages and import their Fedora Rawhide dist-git."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.rawhide_sources import import_binaries, source_name


def command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def factory_sources(destination: Path) -> set[str]:
    """Return package and binary names whose source is the factory itself (direct-upstream recipes)."""
    if not destination.is_dir():
        return set()
    names: set[str] = set()
    for directory in sorted(destination.iterdir()):
        if not directory.is_dir():
            continue
        provenance_path = directory / ".hummingbird-upstream.json"
        if not provenance_path.is_file():
            continue
        try:
            data = json.loads(provenance_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("branch") == "upstream":
            names.add(directory.name)
            if "package" in data and isinstance(data["package"], str):
                names.add(data["package"])
            for spec in sorted(directory.glob("*.spec")):
                main_name = directory.name
                try:
                    spec_content = spec.read_text(errors="replace")
                except OSError:
                    continue
                for line in spec_content.splitlines():
                    match_name = re.match(r"^Name:\s*(\S+)", line)
                    if match_name:
                        main_name = match_name.group(1)
                        names.add(main_name)
                    match_pkg_n = re.match(r"^%package\s+-n\s+(\S+)", line)
                    if match_pkg_n:
                        names.add(match_pkg_n.group(1))
                    else:
                        match_pkg = re.match(r"^%package\s+(\S+)", line)
                        if match_pkg:
                            names.add(f"{main_name}-{match_pkg.group(1)}")
    return names


def resolve_source(binary: str) -> tuple[str | None, str | None]:
    result = command("dnf", "repoquery", "--latest-limit=1", "--qf", "%{sourcerpm}", binary)
    candidates = sorted({line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip() != "(none)"})
    if not candidates:
        return None, result.stderr.strip() or "no Rawhide candidate"
    try:
        return source_name(candidates[0]), None
    except ValueError:
        return None, f"cannot derive source package from {candidates[0]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("config/bluefin-packages.toml"))
    parser.add_argument("--policy", type=Path, default=Path("config/runtime-contract.toml"))
    parser.add_argument("--destination", type=Path, default=Path("packages"))
    parser.add_argument("--report", type=Path, default=Path("reports/bluefin-rawhide-resolution.json"))
    args = parser.parse_args()

    manifest = tomllib.loads(args.manifest.read_text())
    binaries = import_binaries(manifest)
    if args.policy.exists():
        policy = tomllib.loads(args.policy.read_text())
        excluded = set(policy.get("unavailable", {}).get("packages", []))
        binaries = [binary for binary in binaries if binary not in excluded]

    factory = factory_sources(args.destination)
    binaries = [binary for binary in binaries if binary not in factory]

    resolved: dict[str, str] = {}
    unavailable: list[dict[str, str]] = []
    for binary in binaries:
        source, error = resolve_source(binary)
        if source:
            resolved[binary] = source
        else:
            unavailable.append({"binary": binary, "reason": error or "unknown resolver failure"})

    if not resolved:
        raise SystemExit("Rawhide resolver returned no source RPMs; refusing to open a flood of issues")

    imported: list[str] = []
    failures: list[dict[str, str]] = []
    for source in sorted(set(resolved.values())):
        destination = args.destination / source
        if destination.exists():
            imported.append(source)
            continue
        result = command(sys.executable, "tools/import_rawhide.py", source, "--destination", str(args.destination))
        if result.returncode == 0:
            imported.append(source)
        else:
            failures.append({"source": source, "reason": result.stderr.strip() or result.stdout.strip()})

    report = {
        "upstream_manifest": "https://github.com/projectbluefin/bluefin/blob/main/build_files/packages/base.toml",
        "binary_count": len(binaries),
        "resolved_binary_to_source": resolved,
        "imported_sources": imported,
        "unavailable": unavailable,
        "import_failures": failures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("binary_count", "imported_sources", "unavailable", "import_failures")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
