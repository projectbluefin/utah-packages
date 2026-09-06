#!/usr/bin/env python3
"""Enforce the Project Bluefin factory onboarding contract.

The contract itself lives in ``projectbluefin/common``, pinned by commit in
``config/factory-contract.json``. This checks the parts of it that can be
verified from the tree: the skill router indexes every skill, skills carry
front-matter, ``AGENTS.md`` states the mandate, banned files stay out, and
internal documentation links resolve.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

CONTRACT = Path("config/factory-contract.json")
ROUTER = Path("docs/SKILL.md")
MANDATE = Path("docs/skills/skill-improvement.md")
AGENTS = Path("AGENTS.md")

AGENT_SKILLS = Path(".agents/skills")
DOC_SKILLS = Path("docs/skills")

# Files whose presence means agents are logging sessions into the repository
# instead of updating skills.
BANNED_NAMES = {
    "CHANGELOG.md",
    "CHANGES.md",
    "IMPROVEMENTS.md",
    "SESSION.md",
    "NOTES.md",
    "PLAN.md",
    "TODO.md",
}

# AGENTS.md must state the mandate itself; a link to it is not enough, because
# agents read AGENTS.md and stop.
REQUIRED_AGENTS_MARKERS = (
    "## Self-Improvement",
    "docs/SKILL.md",
    "config/factory-contract.json",
    "No changelog files",
    "No session notes committed",
    '"append here"',
)

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FENCE = re.compile(r"^\s*(```|~~~)")


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
         "--exclude-standard"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [Path(name) for name in out.split("\0") if name]


def front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}
    keys: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if match:
            keys[match.group(1)] = match.group(2).strip()
    return keys


def strip_fences(text: str) -> str:
    kept: list[str] = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            kept.append(line)
    return "\n".join(kept)


def check_skills(root: Path, errors: list[str]) -> None:
    if not (root / ROUTER).exists():
        errors.append(f"missing skill router: {ROUTER}")
        return
    if not (root / MANDATE).exists():
        errors.append(f"missing skill-improvement mandate: {MANDATE}")
    router = (root / ROUTER).read_text()
    indexed = {
        os.path.normpath(ROUTER.parent / target.split("#", 1)[0])
        for target in LINK.findall(strip_fences(router))
        if not target.startswith(("http://", "https://", "mailto:", "#"))
    }

    skills = sorted((root / AGENT_SKILLS).glob("*/SKILL.md"))
    skills += sorted(
        path for path in (root / DOC_SKILLS).glob("*.md") if path.name != "README.md"
    )
    if not skills:
        errors.append("no skills found; the factory contract requires at least one")

    for skill in skills:
        rel = skill.relative_to(root)
        keys = front_matter(skill)
        for key in ("name", "description"):
            if not keys.get(key):
                errors.append(f"{rel}: front-matter missing '{key}'")
        if os.path.normpath(rel) not in indexed:
            errors.append(f"{rel}: not indexed in {ROUTER}")


def check_agents(root: Path, errors: list[str]) -> None:
    if not (root / AGENTS).exists():
        errors.append(f"missing {AGENTS}")
        return
    text = (root / AGENTS).read_text()
    for marker in REQUIRED_AGENTS_MARKERS:
        if marker not in text:
            errors.append(f"{AGENTS}: missing required onboarding marker {marker!r}")


def check_contract(root: Path, errors: list[str]) -> None:
    if not (root / CONTRACT).exists():
        errors.append(f"missing pinned factory contract: {CONTRACT}")
        return
    try:
        data = json.loads((root / CONTRACT).read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{CONTRACT}: invalid JSON: {exc}")
        return
    if data.get("repository") != "projectbluefin/common":
        errors.append(f"{CONTRACT}: repository must be projectbluefin/common")
    commit = data.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append(f"{CONTRACT}: commit must be a full 40-character SHA, not a tag")
    if not data.get("contracts"):
        errors.append(f"{CONTRACT}: no contracts pinned")


def check_banned(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.name in BANNED_NAMES:
            errors.append(
                f"{path}: banned by the factory contract; "
                "route the content to docs/skills/ and delete the file"
            )


def check_links(root: Path, files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix != ".md":
            continue
        text = strip_fences((root / path).read_text())
        for target in LINK.findall(text):
            target = target.split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (root / path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                errors.append(f"{path}: broken link to {target}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parent.parent
    files = tracked_files(root)
    errors: list[str] = []

    check_contract(root, errors)
    check_agents(root, errors)
    check_skills(root, errors)
    check_banned(files, errors)
    check_links(root, files, errors)

    if errors:
        print("factory onboarding contract violations:")
        for error in errors:
            print(f"  {error}")
        return 1
    print(f"factory contract satisfied ({len(files)} tracked files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
