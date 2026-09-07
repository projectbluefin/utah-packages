#!/usr/bin/env python3
"""Import a Fedora dist-git Rawhide snapshot into this package factory."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def validate_package(name: str) -> None:
    if not name or not name.replace("-", "").replace("_", "").isalnum() or name.startswith("-"):
        raise ValueError("package name must contain only letters, numbers, '_' or '-' and cannot start with '-'")


def validate_branch(branch: str) -> None:
    if not branch or not all(c.isalnum() or c in "-_./" for c in branch) or branch.startswith("-") or ".." in branch:
        raise ValueError("branch name contains invalid characters")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", help="Fedora dist-git package name")
    parser.add_argument("--branch", default="rawhide")
    parser.add_argument("--remote-template", default="https://src.fedoraproject.org/rpms/{package}.git")
    parser.add_argument("--destination", type=Path, default=Path("packages"))
    args = parser.parse_args()

    try:
        validate_package(args.package)
        validate_branch(args.branch)
    except ValueError as exc:
        raise SystemExit(str(exc))

    remote = args.remote_template.format(package=args.package)
    destination = args.destination / args.package
    if destination.exists():
        raise SystemExit(f"destination already exists: {destination}")

    with tempfile.TemporaryDirectory(prefix="rawhide-import-") as temporary:
        clone = Path(temporary) / "dist-git"
        subprocess.run(["git", "clone", "--filter=blob:none", "--branch", args.branch, remote, str(clone)], check=True)
        commit = run("git", "rev-parse", "HEAD", cwd=clone)
        tree = run("git", "rev-parse", "HEAD^{tree}", cwd=clone)
        destination.mkdir(parents=True)
        archive = subprocess.Popen(["git", "archive", args.branch], cwd=clone, stdout=subprocess.PIPE)
        try:
            subprocess.run(["tar", "-x", "-C", str(destination)], stdin=archive.stdout, check=True)
        finally:
            if archive.stdout:
                archive.stdout.close()
            archive.wait()

    provenance = {
        "package": args.package,
        "branch": args.branch,
        "remote": remote,
        "commit": commit,
        "tree": tree,
        "imported_at": datetime.now(UTC).isoformat(),
    }
    (destination / ".hummingbird-upstream.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
