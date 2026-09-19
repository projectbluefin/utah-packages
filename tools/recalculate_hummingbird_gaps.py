#!/usr/bin/env python3
"""Measure Bluefin's package contract against a Hummingbird image and repo."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.runtime_contract import load_policy, package_section


def lines(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("config/bluefin-packages.toml"))
    parser.add_argument("--policy", type=Path, default=Path("config/runtime-contract.toml"))
    parser.add_argument("--image-packages", type=Path, required=True)
    parser.add_argument("--repo-packages", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/hummingbird-gap.json"))
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    manifest = tomllib.loads(args.manifest.read_text())
    # Version-specific lists are intentionally included: this is the full
    # Bluefin contract, independent of whichever Fedora release consumes it.
    contract = set()
    for section, values in manifest.items():
        if section != "excluded" and isinstance(values, dict):
            contract.update(values.get("packages", []))
    # Packages the runtime contract declares unavailable are debt Utah has
    # already decided not to carry, each with an issue-backed reason. Counting
    # them as missing would report parity Hummingbird is not expected to close.
    dropped = set(package_section(load_policy(args.policy), "unavailable")) & contract
    contract -= dropped
    image, repo = lines(args.image_packages), lines(args.repo_packages)
    available = image | repo
    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "image": args.image,
        "contract_binary_packages": sorted(contract),
        "excluded_as_unavailable": sorted(dropped),
        "available_from_image": sorted(contract & image),
        "available_from_repo_only": sorted((contract & repo) - image),
        "missing_from_hummingbird": sorted(contract - available),
        "counts": {
            "contract": len(contract),
            "excluded_as_unavailable": len(dropped),
            "image": len(contract & image),
            "repo_only": len((contract & repo) - image),
            "missing": len(contract - available),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
