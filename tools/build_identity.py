#!/usr/bin/env python3
"""Calculate the immutable identity of a factory package build.

A package result is reusable only when its own inputs are unchanged: the
source lock, the recipe tree, and the Hummingbird base every build root
starts from. Nothing else is hashed. Build scripts, workflows, the runtime
contract and the rest of the manifest are how the factory works, not what a
package is built from, and folding them in meant a one-line change anywhere
rebuilt every package.

What a package is built *against* is recorded instead of hashed. At the end
of a build, the factory packages installed in the build root are listed and
each is stored with the build key it carried at the time (``build_deps``).
The rebuild planner then re-runs a package when any recorded dependency has a
different key now or is itself being rebuilt, transitively -- the same rule a
maintainer applies by hand after a soname bump, applied automatically.

The identity is metadata for CI reuse; RPM contents and the final repository
gates remain the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path, PurePosixPath

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


def identity(
    package: str,
    root: Path = Path("."),
    rpm_dir: Path | None = None,
    deps_file: Path | None = None,
    prior_dir: Path | None = None,
) -> dict[str, object]:
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
        "recipe_sha256": file_digest(root / "packages" / recipe.recipe_name(entry)),
        "base_image": base,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    result = {"package": package, "build_key": "sha256:" + hashlib.sha256(encoded).hexdigest(), **payload}
    # Absent and empty mean different things downstream: empty is "this build
    # looked and installed no factory RPM", absent is "nobody looked". Only a
    # real build with a dependency listing sets the field.
    if deps_file is not None and deps_file.is_file():
        result["build_deps"] = record_build_deps(package, deps_file, prior_dir)
    outputs = []
    if rpm_dir is not None and rpm_dir.is_dir():
        for rpm in sorted(rpm_dir.rglob("*.rpm")):
            outputs.append({
                "file": rpm.relative_to(rpm_dir).as_posix(),
                "sha256": hashlib.sha256(rpm.read_bytes()).hexdigest(),
            })
    result["outputs"] = outputs
    return result


def prior_outputs(prior_dir: Path | None) -> dict[str, tuple[str, str]]:
    """Map every RPM an earlier build produced to the entry that produced it.

    Keyed by RPM basename, which is exactly what ``rpm -qa`` can print for an
    installed package, so the build root's contents map back to manifest
    entries with no name guessing at all.

    Source names cannot do this job. Two entries share one recipe -- the
    ``webkitgtk`` and ``webkit2gtk4.1`` shards, ``malcontent`` and
    ``malcontent-bootstrap`` -- and each pair collapses to a single
    ``%{SOURCERPM}`` name, so a source-name lookup answers with whichever of
    the two it happens to find. Their binaries never collide
    (``javascriptcoregtk6.0`` against ``javascriptcoregtk4.1``,
    ``0.14.0-1`` against ``0.14.0-0.bootstrap``), so the recorded outputs
    are exact where the source name is ambiguous.

    Earlier lanes of the same run arrive as ``<name>.build-key.json`` files
    and win over the accumulator's manifest, since theirs is the copy the
    build root actually installed.
    """
    found: dict[str, tuple[str, str]] = {}
    if prior_dir is None or not prior_dir.is_dir():
        return found

    def record(package: object, build_key: object, outputs: object) -> None:
        if not isinstance(package, str) or not isinstance(build_key, str):
            return
        if not isinstance(outputs, list):
            return
        for output in outputs:
            if isinstance(output, dict) and isinstance(output.get("file"), str):
                found[PurePosixPath(output["file"]).name] = (package, build_key)

    manifest = prior_dir / "factory-build-manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text())
            for name, value in data.get("packages", {}).items():
                if isinstance(value, dict):
                    record(name, value.get("build_key"), value.get("outputs"))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    for path in sorted(prior_dir.rglob("*.build-key.json")):
        try:
            item = json.loads(path.read_text())
            record(item.get("package"), item.get("build_key"), item.get("outputs"))
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return found


def record_build_deps(
    package: str, deps_file: Path | None, prior_dir: Path | None
) -> dict[str, str]:
    """Map each factory package installed in the build root to its build key.

    ``deps_file`` holds the RPM basenames the build script read out of the
    build root, one per line. A basename no recorded output claims is
    counted and ignored: the lane already purges artifacts the manifest no
    longer promises, so one appearing here is an accumulator left-over
    rather than a dependency this build can be held to.
    """
    known = prior_outputs(prior_dir)
    deps: dict[str, str] = {}
    unmapped = 0
    for line in deps_file.read_text().splitlines():
        basename = line.strip()
        if not basename:
            continue
        match = known.get(basename)
        if match is None:
            unmapped += 1
            continue
        name, build_key = match
        if name != package:
            deps[name] = build_key
    if unmapped:
        print(
            f"{unmapped} installed factory RPMs matched no recorded build; "
            "not recorded as dependencies",
            file=sys.stderr,
        )
    return dict(sorted(deps.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--key-only", action="store_true")
    parser.add_argument("--rpm-dir", type=Path)
    parser.add_argument("--deps-file", type=Path, help="factory source names installed in the build root")
    parser.add_argument("--prior-dir", type=Path, help="where earlier lanes' keys and the accumulator manifest are")
    args = parser.parse_args()
    result = identity(args.package, args.root, args.rpm_dir, args.deps_file, args.prior_dir)
    if args.key_only:
        print(result["build_key"])
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
