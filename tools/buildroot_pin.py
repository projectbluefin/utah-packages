#!/usr/bin/env python3
"""Read or move the factory build-root pin (config/buildroot-image).

The pin names the factory's own mirror, ghcr.io/projectbluefin/utah-buildroot,
by tag and digest. refresh-buildroot.yml moves it; prepare in rebuild-rpms.yml
reads it and pulls it by digest. A mirror pin is the only kind that can be
pulled by digest safely: quay.io garbage-collects fedora:44 digests within
hours, and nothing prunes the mirror (docs/skills/repeated-mistakes.md
section 7).

It lives in config/, not in the workflow, because the workflow token cannot
push changes to workflow files: the first refresh (run 36167595383) mirrored
the image and then had its pull request refused with "refusing to allow a
GitHub App to create or update workflow ... without workflows permission".

`set` also moves config/buildroot-lock.json, which names the same root by
digest for the provenance manifest (tools/buildroot_lock.py,
docs/skills/supply-chain-provenance.md). tools/validate.py fails when the
lock names anything but this pin, and the refresh job runs only `set`, so a
lock left behind would fail every refresh pull request.

    buildroot_pin.py get
    buildroot_pin.py set ghcr.io/projectbluefin/utah-buildroot:<tag>@sha256:<64 hex>
"""

from __future__ import annotations

from pathlib import Path
import json
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
PIN_FILE = ROOT / "config" / "buildroot-image"
LOCK_NAME = "buildroot-lock.json"
MIRROR = "ghcr.io/projectbluefin/utah-buildroot"

MIRROR_PIN = re.compile(
    rf"^{re.escape(MIRROR)}:[A-Za-z0-9_][A-Za-z0-9._-]{{0,127}}@sha256:[0-9a-f]{{64}}$"
)
LEGACY_PIN = re.compile(r"^quay\.io/fedora/fedora:[0-9]+@sha256:[0-9a-f]{64}$")


def is_mirror_pin(value: str) -> bool:
    return bool(MIRROR_PIN.match(value))


def parse(text: str) -> str:
    """The single pin a pin file holds; comments and blank lines are ignored."""
    values = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(values) != 1:
        raise ValueError(f"expected exactly one pin in {PIN_FILE.name}, found {len(values)}")
    value = values[0]
    if not (is_mirror_pin(value) or LEGACY_PIN.match(value)):
        raise ValueError(f"not a build-root pin: {value}")
    return value


def get(path: Path = PIN_FILE) -> str:
    return parse(path.read_text())


def set_pin(value: str, path: Path = PIN_FILE) -> None:
    """Move the pin, and the buildroot lock beside it when there is one.

    The lock is read before anything is written, so a lock that cannot be
    parsed fails the move instead of leaving the pin moved without it. Only
    each locked root's ``image`` moves. A locked ``packages`` list is left as
    it was: it described the old root, and ``buildroot_lock.py snapshot
    --strict`` should report that divergence rather than have the list
    silently emptied.
    """
    if not is_mirror_pin(value):
        raise ValueError(f"not a {MIRROR}:<tag>@sha256:<digest> pin: {value}")
    lock_path = path.with_name(LOCK_NAME)
    lock = json.loads(lock_path.read_text()) if lock_path.is_file() else None
    if lock is not None:
        roots = lock.get("buildroots")
        if not isinstance(roots, dict) or not all(isinstance(r, dict) for r in roots.values()):
            raise ValueError(f"invalid buildroot lock: {lock_path}")
        for root in roots.values():
            root["image"] = value
    path.write_text(value + "\n")
    if lock is not None:
        lock_path.write_text(json.dumps(lock, indent=2) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "get":
        print(get())
        return 0
    if len(argv) == 3 and argv[1] == "set":
        set_pin(argv[2])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
