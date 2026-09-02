#!/usr/bin/env python3
"""Assert a candidate repository contains every package the factory promises.

The publish gates prove that the packages built in this run outrank what
Fedora and Hummingbird offer, and that a consumer transaction resolves. Neither
proves the repository is complete, and it can be incomplete in a way nothing
else notices:

  * `prepare` skips a package it considers already published, and it reads that
    from the `:building` accumulator as well as from `:latest`. `publish` seeds
    the candidate from `:latest` alone. A package that only ever reached the
    accumulator is therefore skipped by the build and absent from the
    repository, and no later step looks for it.
  * The consumer transaction enables the Hummingbird repository beside the
    candidate, as it must -- the base OS legitimately supplies part of the
    closure. So a contract package the factory failed to provide can resolve
    from Hummingbird instead and the transaction still succeeds.

What the factory promises is exactly config/upstream-sources.json: every entry
there is a package it builds and publishes. The candidate records what it
actually has in factory-build-manifest.json, written by tools/build_manifest.py
from the per-package identity each lane uploads. This compares the two, and
checks that each file the manifest names is present with the contents it
recorded, so a truncated or half-merged download cannot pass either.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def expected_packages(config_path: Path) -> list[str]:
    config = json.loads(config_path.read_text())
    names = [item["name"] for item in config.get("packages", [])]
    if not names:
        raise ValueError("source manifest lists no packages")
    return names


def manifest_packages(repository: Path) -> dict[str, dict]:
    path = repository / "factory-build-manifest.json"
    if not path.is_file():
        raise ValueError(f"candidate has no build manifest at {path}")
    data = json.loads(path.read_text())
    packages = data.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("build manifest has no packages object")
    return packages


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def check(repository: Path, config_path: Path, verify_digests: bool = True) -> list[str]:
    """Return the reasons this repository may not be published, empty if none."""
    problems: list[str] = []
    packages = manifest_packages(repository)
    # One index of the tree, so a repository of thousands of RPMs is walked
    # once rather than once per recorded output.
    on_disk: dict[str, Path] = {}
    for path in repository.rglob("*.rpm"):
        if path.is_file():
            on_disk.setdefault(path.name, path)

    for name in expected_packages(config_path):
        record = packages.get(name)
        if not isinstance(record, dict):
            problems.append(f"{name}: the factory builds it, the candidate does not carry it")
            continue
        outputs = record.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            problems.append(f"{name}: recorded in the manifest with no RPM outputs")
            continue
        for output in outputs:
            if not isinstance(output, dict) or not isinstance(output.get("file"), str):
                problems.append(f"{name}: malformed output record")
                continue
            filename = Path(output["file"]).name
            found = on_disk.get(filename)
            if found is None:
                problems.append(f"{name}: {filename} is recorded but missing from the repository")
                continue
            expected_sha = output.get("sha256")
            if verify_digests and isinstance(expected_sha, str):
                if digest(found) != expected_sha:
                    problems.append(f"{name}: {filename} does not match its recorded checksum")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument(
        "--skip-digests",
        action="store_true",
        help="check that recorded files exist without reading them",
    )
    args = parser.parse_args()
    try:
        problems = check(args.repository, args.config, verify_digests=not args.skip_digests)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if problems:
        print(
            f"The candidate repository is missing {len(problems)} thing(s) the factory promises:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nPublishing it would ship a repository that does not contain what its\n"
            "manifest says it contains. Rebuild the named packages -- a full run\n"
            "(workflow_dispatch with full=true) rebuilds every one of them -- or\n"
            "correct config/upstream-sources.json if the factory no longer builds\n"
            "them.",
            file=sys.stderr,
        )
        return 1
    total = len(expected_packages(args.config))
    print(f"candidate repository carries all {total} packages the factory promises")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
