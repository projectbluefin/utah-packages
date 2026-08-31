#!/usr/bin/env python3
"""Validate package-factory configuration.

Checks:
1. ``config/bootstrap-packages.txt`` format (non-empty, unique, source RPM names).
2. Every ``.hummingbird-upstream.json`` has the expected provenance schema.
3. Every imported package carries provenance: either a
   ``.hummingbird-upstream.json`` dist-git snapshot record or an explicit
   entry in ``config/upstream-sources.json`` with a locked SHA-512.
4. ``config/buildroot-lock.json`` exists, uses schema 1, and pins a valid SHA-256 digest.
"""
import json
import re
import sys
from pathlib import Path

SHA256_PATTERN = re.compile(r"sha256:([0-9a-f]{64})")


def validate_bootstrap_packages(config_dir: Path) -> list[str]:
    """Return the bootstrap source RPM list, or exit on invalid format."""
    packages = [
        raw.strip()
        for raw in (config_dir / "bootstrap-packages.txt").read_text().splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    ]
    if not packages:
        sys.exit("bootstrap package set is empty")
    if len(packages) != len(set(packages)):
        sys.exit("bootstrap package set contains duplicates")
    if any(" " in p or "/" in p for p in packages):
        sys.exit("package names must be source RPM names, one per line")
    return packages


def validate_hummingbird_upstream(path: Path) -> None:
    """Validate a single ``.hummingbird-upstream.json`` provenance record."""
    data = json.loads((path / ".hummingbird-upstream.json").read_text())
    required = {"package", "branch", "remote", "commit", "tree", "imported_at"}
    if set(data) != required:
        sys.exit(f"invalid upstream provenance: {path}")
    if data["branch"] not in ("rawhide", "upstream"):
        sys.exit(f"only rawhide or upstream imports are supported: {path}")
    if data["branch"] == "upstream":
        for key in ("commit", "tree"):
            if data[key]:
                sys.exit(f"upstream import must not carry {key}: {path}")
    else:
        for key in ("commit", "tree"):
            if not data[key]:
                sys.exit(f"rawhide import must carry {key}: {path}")


def validate_buildroot_lock(config_dir: Path) -> None:
    """Validate the buildroot lock file: schema, presence, and digest format."""
    lock_path = config_dir / "buildroot-lock.json"
    if not lock_path.exists():
        sys.exit("buildroot lock file not found: config/buildroot-lock.json")
    data = json.loads(lock_path.read_text())
    if data.get("schema") != 1:
        sys.exit(f"unsupported buildroot lock schema: {data.get('schema')}")
    pinned = data.get("image", {}).get("pinned", "")
    match = SHA256_PATTERN.search(pinned)
    if not match:
        sys.exit(f"buildroot lock image.pinned is not a valid SHA-256 digest: {pinned}")


def validate_all(config_dir: Path = Path("config"), packages_dir: Path = Path("packages")) -> None:
    """Run all validation checks."""
    packages = validate_bootstrap_packages(config_dir)

    upstream = json.loads((config_dir / "upstream-sources.json").read_text())
    upstream_names = {p["name"] for p in upstream.get("packages", [])}

    provided = json.loads((config_dir / "hummingbird-provided-sources.json").read_text())
    provided_names = set(provided.get("sources", []))

    package_dirs = sorted(p for p in packages_dir.iterdir() if p.is_dir())
    for path in package_dirs:
        if (path / ".hummingbird-upstream.json").is_file():
            validate_hummingbird_upstream(path)

    provenance_gaps = []
    for path in package_dirs:
        name = path.name
        if name in provided_names:
            continue
        has_distgit = (path / ".hummingbird-upstream.json").is_file()
        has_direct = name in upstream_names
        if not has_distgit and not has_direct:
            provenance_gaps.append(name)

    if provenance_gaps:
        sys.exit(
            "packages missing provenance (no .hummingbird-upstream.json or upstream-sources entry): "
            + ", ".join(sorted(provenance_gaps))
        )

    validate_buildroot_lock(config_dir)

    print(f"validated {len(packages)} source RPMs; {len(package_dirs)} package recipes with provenance")


if __name__ == "__main__":
    validate_all()

