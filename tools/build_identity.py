#!/usr/bin/env python3
"""Calculate the immutable identity of a factory package build.

A package result is reusable only when its source lock, recipe tree, factory
configuration, and Hummingbird base identity are unchanged.  The identity is
metadata for CI reuse; RPM contents and the final repository gates remain the
source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recipe  # noqa: E402


def package_entry(config: dict, package: str) -> dict:
    return recipe.entry(package, config)


def file_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        raise ValueError(f"package recipe directory does not exist: {root}")
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def identity(package: str, root: Path = Path("."), rpm_dir: Path | None = None) -> dict[str, object]:
    config_path = root / "config" / "upstream-sources.json"
    policy_path = root / "config" / "runtime-contract.toml"
    config = json.loads(config_path.read_text())
    entry = package_entry(config, package)
    policy = tomllib.loads(policy_path.read_text())
    base = policy.get("base", {}).get("image", "")
    if not isinstance(base, str) or "@sha256:" not in base:
        raise ValueError("runtime contract base image is not digest-pinned")

    payload = {
        "package": package,
        "source": entry,
        # An entry may build a recipe directory of another name (see
        # tools/recipe.py); the entry itself, defines included, is already in
        # the payload above, so two shards of one recipe get distinct keys.
        "recipe_sha256": file_digest(root / "packages" / recipe.recipe_name(entry)),
        "base_image": base,
        "factory_files": {
            "hummingbird_repo": hashlib.sha256((root / "config" / "hummingbird.repo").read_bytes()).hexdigest(),
            "runtime_contract": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
            # Until the dependency planner emits per-consumer provider
            # fingerprints, include the complete source manifest. This is
            # conservative: changing one provider invalidates every cached
            # result instead of risking reuse against a changed closure.
            "source_manifest": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "build_workflow": hashlib.sha256((root / ".github" / "workflows" / "rebuild-lane.yml").read_bytes()).hexdigest(),
            # The compiler cache action is deliberately absent. Every entry it
            # can serve is addressed by the hash of the preprocessed source and
            # the compiler flags, so it cannot change what a build produces --
            # only how long it takes. Hashing it meant that tuning the cache
            # invalidated all 178 packages and rebuilt the factory from
            # scratch, which is the opposite of what a cache is for.
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    result = {"package": package, "build_key": "sha256:" + hashlib.sha256(encoded).hexdigest(), **payload}
    outputs = []
    if rpm_dir is not None and rpm_dir.is_dir():
        for rpm in sorted(rpm_dir.rglob("*.rpm")):
            outputs.append({
                "file": rpm.relative_to(rpm_dir).as_posix(),
                "sha256": hashlib.sha256(rpm.read_bytes()).hexdigest(),
            })
    result["outputs"] = outputs
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--key-only", action="store_true")
    parser.add_argument("--rpm-dir", type=Path)
    args = parser.parse_args()
    result = identity(args.package, args.root, args.rpm_dir)
    if args.key_only:
        print(result["build_key"])
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
