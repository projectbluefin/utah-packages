#!/usr/bin/env python3
"""Refresh the inventory counts ``docs/architecture.md`` quotes.

The Coverage section is hand-written prose that publishes six concrete
numbers:

1. ``ls -d packages/*/ | wc -l``  →  ``len(inventory(root))``
2. ``entries under .packit.yaml:packages``  →  ``sum(r.packit_configured)``
3. ``entries under config/upstream-sources.json:packages``  →
   ``len(source_locks(root))``
4. ``cover all N recipes`` and ``a list of N satisfies`` →
   ``len(inventory(root))``
5. ``validated N source RPMs (A rawhide, B upstream)`` (the whole
   ``tools/validate.py`` success line) → ``validated_summary(records)``
6. ``K of N packages carry a hand-assigned stage`` →
   ``sum('stage' in lock) / len(records)``

Updating the doc by hand on every recipe add or remove is exactly what the
agreement gate tests/test_architecture_counts.py is meant to prevent; this
script rewrites the numbers in place so the workflow that imports a new
recipe does not also have to hand-edit the doc.

Run as ``python3 tools/render_architecture_counts.py --write`` from the
repository root (the workflow does this in the same step as the import).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory, source_locks
from tools.validate import validated_summary

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "architecture.md"


def _replace_one(text: str, pattern: str, replacement: str) -> str:
    """Replace the single match of ``pattern``; raise if not exactly one.

    Uses :func:`re.sub` (not direct string slicing) so the standard
    ``\\g<1>`` / ``\\g<2>`` back-references in ``replacement`` are honored.
    """
    matches = list(
        re.finditer(pattern, text, flags=re.MULTILINE | re.DOTALL)
    )
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one architecture.md claim matching {pattern!r}, "
            f"found {len(matches)}"
        )
    return re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE)


def render(text: str, root: Path) -> str:
    records = inventory(root)
    packit = sum(record.packit_configured for record in records)
    locks = source_locks(root)
    staged = sum("stage" in lock for lock in locks.values())
    n = len(records)

    text = _replace_one(
        text,
        r"(\| `ls -d packages/\*/ \\?\| wc -l` \| `)(\d+)(` \|)",
        rf"\g<1>{n}\g<3>",
    )
    text = _replace_one(
        text,
        r"(\| entries under `\.packit\.yaml:packages` \| `)(\d+)(` \|)",
        rf"\g<1>{packit}\g<3>",
    )
    text = _replace_one(
        text,
        r"(\| entries under `config/upstream-sources\.json:packages` \| `)"
        r"(\d+)(` \|)",
        rf"\g<1>{len(locks)}\g<3>",
    )
    text = _replace_one(
        text,
        r"(The root Packit configuration and the source lock both cover all )"
        r"(\d+)( recipes:)",
        rf"\g<1>{n}\g<3>",
    )
    text = _replace_one(
        text,
        r"(which a list of )(\d+)( satisfies)",
        rf"\g<1>{n}\g<3>",
    )
    # Quote validate's whole success line, provenance split included, so the
    # parenthetical cannot go stale while only the total moves.
    text = _replace_one(
        text,
        r"^validated \d+ source RPMs \([^)\n]*\)$",
        validated_summary(records).replace("\\", r"\\"),
    )
    text = _replace_one(
        text,
        r"(of )(\d+)( packages carry a hand-assigned `stage`)",
        rf"\g<1>{n}\g<3>",
    )
    # Keep the staged numerator honest too; the regex anchors at the start of
    # the line ("K of N packages carry a hand-assigned `stage`").
    text = re.sub(
        r"(^)(\d+)( of \d+ packages carry a hand-assigned `stage`)",
        rf"\g<1>{staged}\g<3>",
        text,
        flags=re.MULTILINE,
        count=1,
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite docs/architecture.md in place (default: dry-run, exit 1 "
        "if the rendered output differs from the file on disk).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (default: %(default)s).",
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=None,
        help="Override the doc path (default: <root>/docs/architecture.md). "
        "Used by tests to render against a fixture copy without standing up "
        "a full packages/ tree.",
    )
    args = parser.parse_args()

    # DOC follows --root so --root <elsewhere> rewrites the other tree's doc
    # with that tree's counts, not this checkout's. --doc overrides the path
    # while keeping the inventory sourced from --root.
    doc = args.doc if args.doc is not None else args.root / "docs" / "architecture.md"
    original = doc.read_text(encoding="utf-8")
    rendered = render(original, args.root)
    if rendered == original:
        return 0
    if args.write:
        doc.write_text(rendered, encoding="utf-8")
        return 0
    sys.stderr.write(
        "docs/architecture.md is out of date; rerun with --write to refresh.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
