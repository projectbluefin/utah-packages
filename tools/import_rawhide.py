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
    # Fedora package names may contain dots (vid.stab), so allow '.' but never
    # a leading one or '..', which would let the name escape packages/.
    if (
        not name
        or not name.replace("-", "").replace("_", "").replace(".", "").isalnum()
        or name[0] in "-."
        or ".." in name
    ):
        raise ValueError(
            "package name must contain only letters, numbers, '_', '-' or '.', "
            "cannot start with '-' or '.', and cannot contain '..'"
        )


def validate_branch(branch: str) -> None:
    if not branch or not all(c.isalnum() or c in "-_./" for c in branch) or branch.startswith("-") or ".." in branch:
        raise ValueError("branch name contains invalid characters")


def validate_ref(ref: str) -> None:
    # A re-import pins the exact commit Koji built, so only a full object name
    # is accepted: a short or symbolic ref could resolve differently later.
    if len(ref) != 40 or any(c not in "0123456789abcdef" for c in ref):
        raise ValueError("ref must be a full 40-character lowercase commit id")


def clone(remote: str, branch: str, destination: Path) -> None:
    """Blob-less clone of one dist-git branch; blobs arrive on demand."""
    subprocess.run(
        ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout",
         "--branch", branch, remote, str(destination)],
        check=True,
    )


def extract(repository: Path, ref: str, destination: Path) -> None:
    """Write the tree at ``ref`` into ``destination``, exactly as git archive does."""
    destination.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(["git", "archive", ref], cwd=repository, stdout=subprocess.PIPE)
    try:
        subprocess.run(["tar", "-x", "-C", str(destination)], stdin=archive.stdout, check=True)
    finally:
        if archive.stdout:
            archive.stdout.close()
        archive.wait()
    if archive.returncode:
        raise subprocess.CalledProcessError(archive.returncode, ["git", "archive", ref])


def provenance(package: str, branch: str, remote: str, commit: str, tree: str) -> dict:
    return {
        "package": package,
        "branch": branch,
        "remote": remote,
        "commit": commit,
        "tree": tree,
        "imported_at": datetime.now(UTC).isoformat(),
    }


def import_snapshot(repository: Path, package: str, branch: str, remote: str,
                    ref: str, destination: Path, *, replace: bool = False) -> dict:
    """Copy the recipe at ``ref`` into ``destination`` and record its provenance.

    ``replace`` swaps an existing recipe for the snapshot wholesale: files the
    new commit no longer carries are removed rather than left behind, so the
    result is the Fedora tree and nothing else, the same as a first import.
    """
    commit = run("git", "rev-parse", f"{ref}^{{commit}}", cwd=repository)
    tree = run("git", "rev-parse", f"{commit}^{{tree}}", cwd=repository)
    if destination.exists():
        if not replace:
            raise SystemExit(f"destination already exists: {destination}")
        shutil.rmtree(destination)
    extract(repository, commit, destination)
    record = provenance(package, branch, remote, commit, tree)
    (destination / ".hummingbird-upstream.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", help="Fedora dist-git package name")
    parser.add_argument("--branch", default="rawhide")
    parser.add_argument("--ref", help="exact commit to import (default: the branch head); must be on the branch")
    parser.add_argument("--replace", action="store_true",
                        help="re-import over an existing recipe instead of refusing")
    parser.add_argument("--remote-template", default="https://src.fedoraproject.org/rpms/{package}.git")
    parser.add_argument("--destination", type=Path, default=Path("packages"))
    args = parser.parse_args()

    try:
        validate_package(args.package)
        validate_branch(args.branch)
        if args.ref is not None:
            validate_ref(args.ref)
    except ValueError as exc:
        raise SystemExit(str(exc))

    remote = args.remote_template.format(package=args.package)
    destination = args.destination / args.package
    if destination.exists() and not args.replace:
        raise SystemExit(f"destination already exists: {destination}")

    with tempfile.TemporaryDirectory(prefix="rawhide-import-") as temporary:
        repository = Path(temporary) / "dist-git"
        clone(remote, args.branch, repository)
        ref = args.ref or "HEAD"
        if args.ref is not None:
            on_branch = subprocess.run(
                ["git", "merge-base", "--is-ancestor", args.ref, "HEAD"], cwd=repository, check=False,
            )
            if on_branch.returncode != 0:
                raise SystemExit(f"{args.ref} is not on {args.branch}")
        record = import_snapshot(repository, args.package, args.branch, remote, ref,
                                 destination, replace=args.replace)

    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
