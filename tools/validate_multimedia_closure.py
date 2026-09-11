#!/usr/bin/env python3
"""Validate the committed Bluefin multimedia closure contract."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


def _names(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{label} must be a list of strings")
        return []
    return value


def validate(manifest: dict[str, Any], locks: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """Return contract violations; an empty list means the report is valid."""
    errors: list[str] = []
    multimedia = manifest.get("multimedia_overrides")
    if not isinstance(multimedia, dict):
        return ["[multimedia_overrides] must be a table"]
    required = _names(multimedia.get("packages"), "multimedia_overrides.packages", errors)
    provided_section = manifest.get("hummingbird_provided", {})
    if not isinstance(provided_section, dict):
        errors.append("[hummingbird_provided] must be a table")
        provided = []
    else:
        provided = _names(provided_section.get("packages", []), "hummingbird_provided.packages", errors)

    lock_entries = locks.get("packages")
    if not isinstance(lock_entries, list):
        errors.append("config/upstream-sources.json packages must be a list")
        lock_names: set[str] = set()
    else:
        lock_names = {
            entry.get("name")
            for entry in lock_entries
            if isinstance(entry, dict) and isinstance(entry.get("name"), str)
        }

    source_section = manifest.get("multimedia_sources", {})
    source_map: dict[str, str] = {}
    if not isinstance(source_section, dict):
        errors.append("[multimedia_sources] must be a table")
    else:
        raw_map = source_section.get("source_by_binary", {})
        if not isinstance(raw_map, dict) or not all(
            isinstance(binary, str) and isinstance(source, str)
            for binary, source in raw_map.items()
        ):
            errors.append("multimedia_sources.source_by_binary must be a string map")
        else:
            source_map = raw_map
            unknown = sorted(set(source_map) - set(required))
            if unknown:
                errors.append(f"source map contains unlisted binaries: {', '.join(unknown)}")
            missing_sources = sorted(set(source_map.values()) - lock_names)
            if missing_sources:
                errors.append(f"source map names without locks: {', '.join(missing_sources)}")

    if len(required) != len(set(required)):
        errors.append("multimedia_overrides.packages contains duplicates")
    if len(provided) != len(set(provided)):
        errors.append("hummingbird_provided.packages contains duplicates")

    requirements = report.get("requirements")
    if not isinstance(requirements, list):
        errors.append("report.requirements must be a list")
        requirements = []
    report_by_name: dict[str, dict[str, Any]] = {}
    for entry in requirements:
        if not isinstance(entry, dict) or not isinstance(entry.get("requirement"), str):
            errors.append("every report requirement must have a string requirement")
            continue
        name = entry["requirement"]
        if name in report_by_name:
            errors.append(f"duplicate report requirement: {name}")
        report_by_name[name] = entry
        if entry.get("status") != "built":
            errors.append(f"{name} is not marked built")
        source = entry.get("factory_source")
        if not isinstance(source, str) or not source:
            errors.append(f"{name} has no factory source")
        elif source not in lock_names:
            errors.append(f"{name} uses an unlocked factory source: {source}")
        if not isinstance(entry.get("factory_binary"), str) or not entry["factory_binary"]:
            errors.append(f"{name} has no factory binary")
        if not isinstance(entry.get("binary_nevra"), str) or not entry["binary_nevra"]:
            errors.append(f"{name} has no binary NEVRA")

    if set(report_by_name) != set(required):
        errors.append(
            "report requirements do not match multimedia_overrides.packages "
            f"(missing={sorted(set(required) - set(report_by_name))}, "
            f"extra={sorted(set(report_by_name) - set(required))})"
        )
    for binary, source in source_map.items():
        entry = report_by_name.get(binary)
        if entry and entry.get("factory_source") != source:
            errors.append(f"{binary} source map says {source}, report says {entry.get('factory_source')}")

    provided_entries = report.get("provided_by_hummingbird")
    if not isinstance(provided_entries, list):
        errors.append("report.provided_by_hummingbird must be a list")
        provided_entries = []
    provided_by_name: dict[str, dict[str, Any]] = {}
    for entry in provided_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("requirement"), str):
            errors.append("every Hummingbird-provided entry must have a string requirement")
            continue
        name = entry["requirement"]
        if name in provided_by_name:
            errors.append(f"duplicate Hummingbird-provided requirement: {name}")
        provided_by_name[name] = entry
        if entry.get("status") != "provided":
            errors.append(f"{name} is not marked provided")
        if entry.get("factory_source") is not None:
            errors.append(f"{name} unexpectedly has a factory source")
        if not isinstance(entry.get("binary_nevra"), str) or not entry["binary_nevra"]:
            errors.append(f"{name} has no Hummingbird NEVRA")
    if set(provided_by_name) != set(provided):
        errors.append(
            "report Hummingbird-provided entries do not match manifest "
            f"(missing={sorted(set(provided) - set(provided_by_name))}, "
            f"extra={sorted(set(provided_by_name) - set(provided))})"
        )

    exceptions = report.get("documented_exceptions")
    if not isinstance(exceptions, list):
        errors.append("report.documented_exceptions must be a list")
    else:
        for entry in exceptions:
            if not isinstance(entry, dict):
                errors.append("every documented exception must be an object")
                continue
            if not isinstance(entry.get("requirement"), str) or not entry["requirement"]:
                errors.append("every documented exception needs a requirement")
            if not isinstance(entry.get("status"), str) or not entry["status"]:
                errors.append("every documented exception needs a status")
            if not isinstance(entry.get("reason"), str) or not entry["reason"]:
                errors.append("every documented exception needs a reason")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("config/bluefin-packages.toml"))
    parser.add_argument("--locks", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/bluefin-multimedia-closure.json"))
    args = parser.parse_args()

    errors = validate(
        tomllib.loads(args.manifest.read_text()),
        json.loads(args.locks.read_text()),
        json.loads(args.report.read_text()),
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    report = json.loads(args.report.read_text())
    print(f"validated multimedia closure: {len(report['requirements'])} built, "
          f"{len(report['provided_by_hummingbird'])} Hummingbird-provided")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
