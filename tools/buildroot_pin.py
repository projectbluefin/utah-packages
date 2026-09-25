#!/usr/bin/env python3
"""Read or move the factory build-root pin (BUILDROOT_IMAGE in rebuild-rpms.yml).

The pin names the factory's own mirror, ghcr.io/projectbluefin/utah-buildroot,
by tag and digest. refresh-buildroot.yml writes it; prepare pulls it by digest.
A mirror pin is the only kind that can be pulled by digest safely: quay.io
garbage-collects fedora:44 digests within hours, and nothing prunes the mirror
(docs/skills/repeated-mistakes.md section 7).

    buildroot_pin.py get
    buildroot_pin.py set ghcr.io/projectbluefin/utah-buildroot:<tag>@sha256:<64 hex>
"""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "rebuild-rpms.yml"
MIRROR = "ghcr.io/projectbluefin/utah-buildroot"

LINE = re.compile(r"^(?P<indent>\s*)BUILDROOT_IMAGE:\s*(?P<value>\S+)\s*$", re.MULTILINE)
MIRROR_PIN = re.compile(
    rf"^{re.escape(MIRROR)}:[A-Za-z0-9_][A-Za-z0-9._-]{{0,127}}@sha256:[0-9a-f]{{64}}$"
)


def get(text: str) -> str:
    matches = LINE.findall(text)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one BUILDROOT_IMAGE line, found {len(matches)}")
    return matches[0][1]


def is_mirror_pin(value: str) -> bool:
    return bool(MIRROR_PIN.match(value))


def set_pin(text: str, value: str) -> str:
    if not is_mirror_pin(value):
        raise ValueError(f"not a {MIRROR}:<tag>@sha256:<digest> pin: {value}")
    get(text)  # exactly one line, or refuse
    return LINE.sub(lambda m: f"{m.group('indent')}BUILDROOT_IMAGE: {value}", text)


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "get":
        print(get(WORKFLOW.read_text()))
        return 0
    if len(argv) == 3 and argv[1] == "set":
        WORKFLOW.write_text(set_pin(WORKFLOW.read_text(), argv[2]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
