#!/usr/bin/env python3
"""Resolve and verify buildroot container image digests.

The factory builds inside a Fedora 44 container.  Using a mutable tag such as
``quay.io/fedora/fedora:44`` means a silent image update can change the
compiler, libraries, and macro set from one run to the next without anything
in the repository noticing.  This tool pins that reference to an immutable
digest stored in ``config/buildroot-lock.json`` and can verify that a given
image reference matches the lock.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_DIGEST_PATTERN = re.compile(
    r"^([^:]+(?:[:.][^:/]+)*)/([^:]+):([^@]+)@sha256:([0-9a-f]{64})$"
)


def resolve(image: str) -> str:
    """Resolve a (mutable) image tag to a full digest-pinned reference.

    Returns ``repo:tag@sha256:digest`` so the tag is preserved alongside the
    digest.  Uses ``podman inspect`` which is available on the GitHub-hosted
    runners (Ubuntu 24.04 ships podman).  Falls back to ``docker`` if podman
    is absent.
    """
    for tool in ("podman", "docker"):
        digest = _inspect_for_digest(tool, image)
        if digest is not None:
            repo_part = digest.split("@")[0]
            hash_part = digest[len(repo_part) + 1:]
            tag = image.rsplit(":", 1)[-1]
            return f"{repo_part}:{tag}@{hash_part}"
    raise RuntimeError(f"could not resolve image digest for {image}: install podman or docker")


def _inspect_for_digest(tool: str, image: str) -> str | None:
    """Inspect *tool* for *image*, returning a single repo digest string."""
    inspect = subprocess.run([tool, "inspect", image], capture_output=True, text=True, check=False)
    if inspect.returncode != 0 or not inspect.stdout.strip():
        pull = subprocess.run([tool, "pull", image], capture_output=True, check=False)
        if pull.returncode != 0:
            return None
        inspect = subprocess.run([tool, "inspect", image], capture_output=True, text=True, check=False)
    if inspect.returncode == 0 and inspect.stdout.strip():
        data = json.loads(inspect.stdout)
        if data and "RepoDigests" in data[0]:
            return _pick_digest(data[0]["RepoDigests"])
    return None


def _pick_digest(digests: list[str]) -> str:
    """Prefer the quay.io / registry.fedoraproject.org digest over others."""
    for digest in digests:
        if not digest.startswith("registry.fedoraproject.org/"):
            return digest
    return digests[0]


def split_pinned(pinned: str) -> str:
    """Return the ``repo/name:tag`` portion of a digest-pinned reference."""
    match = REPO_DIGEST_PATTERN.match(pinned)
    if not match:
        raise ValueError(f"not a digest-pinned reference: {pinned}")
    repo, name, tag = match.group(1), match.group(2), match.group(3)
    return f"{repo}/{name}:{tag}"


def load_lock(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"buildroot lock file not found: {path}")
    data = json.loads(path.read_text())
    if data.get("schema") != 1:
        raise ValueError(f"unsupported buildroot lock schema: {data.get('schema')}")
    if "image" not in data or "pinned" not in data["image"]:
        raise ValueError("buildroot lock missing image.pinned")
    return data


def _read_repositories(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data.get("repositories", {})
    except (json.JSONDecodeError, KeyError):
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=Path("config/buildroot-lock.json"))
    parser.add_argument("--resolve", action="store_true",
                        help="resolve the reference tag to a digest and write the lock")
    parser.add_argument("--check", action="store_true",
                        help="verify a runtime image reference matches the pinned digest")
    parser.add_argument("--image", default="quay.io/fedora/fedora:44",
                        help="image reference to resolve or verify")
    args = parser.parse_args()

    if args.resolve:
        pinned = resolve(args.image)
        reference = split_pinned(pinned)
        lock = {
            "schema": 1,
            "image": {"reference": reference, "pinned": pinned},
            "release": reference.split(":")[-1],
            "repositories": _read_repositories(args.lock),
        }
        args.lock.parent.mkdir(parents=True, exist_ok=True)
        args.lock.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(f"resolved {reference} -> {pinned}")
        return 0

    if args.check:
        lock = load_lock(args.lock)
        runtime_pinned = resolve(args.image)
        expected = lock["image"]["pinned"]
        if runtime_pinned != expected:
            print(f"MISMATCH: buildroot image {args.image} resolves to {runtime_pinned}, "
                  f"but lock file pins {expected}", file=sys.stderr)
            return 1
        print(f"buildroot image matches lock: {expected}")
        return 0

    # Default: print the pinned reference for use in CI.
    lock = load_lock(args.lock)
    print(lock["image"]["pinned"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
