#!/usr/bin/env python3
"""Keep ``config/upstream-sources.json`` packages in name order.

Every recipe import adds one source-lock entry. Appended at the tail, every
open import pull request edited the same last lines of the file, so each merge
to ``main`` re-conflicted the other open imports. In name order an import edits
only the lines between its alphabetical neighbours, and two imports conflict
only when they land next to each other.

The order is the code-point order of ``name`` -- Python's ``sorted``,
``LC_ALL=C sort``, jq's ``sort_by(.name)`` -- so it is case-sensitive:
``ModemManager`` sorts before ``acl`` and ``libICE`` before ``libacl``.
Sorting moves whole entry objects and never edits one.

    python3 tools/source_lock_order.py           # rewrite in order; idempotent
    python3 tools/source_lock_order.py --check   # exit 1 when out of order

``tools/validate.py`` (``just check``) runs the check;
``just sort-source-locks`` and ``just regenerate-inventory`` run the rewrite.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LOCK = Path("config") / "upstream-sources.json"
FIX_COMMAND = "just sort-source-locks"


def lock_order_key(entry: dict) -> str:
    """The sort key of one lock entry: its ``name``, compared by code point."""
    name = entry.get("name") if isinstance(entry, dict) else None
    if not isinstance(name, str):
        raise ValueError(f"source lock entry has no name: {entry!r}")
    return name


def in_lock_order(packages: list[dict]) -> list[dict]:
    """The same entry objects as ``packages``, reordered by name."""
    return sorted(packages, key=lock_order_key)


def first_misordered(packages: list[dict]) -> tuple[str, str] | None:
    """The first adjacent ``(earlier, later)`` name pair that is out of order."""
    for earlier, later in zip(packages, packages[1:]):
        if lock_order_key(later) < lock_order_key(earlier):
            return lock_order_key(earlier), lock_order_key(later)
    return None


def order_error(path: Path) -> str | None:
    """Why the lock at ``path`` is out of name order, or None when it is not."""
    pair = first_misordered(json.loads(path.read_text()).get("packages", []))
    if pair is None:
        return None
    earlier, later = pair
    return (
        f"{path} packages are not sorted by name: {earlier!r} is listed before "
        f"{later!r}.\nLock entries are kept in name order (code-point, "
        "case-sensitive) so concurrent imports do not all insert at the tail "
        f"and conflict.\nRun `{FIX_COMMAND}` (python3 tools/source_lock_order.py); "
        "it reorders whole entries and never edits one."
    )


def sort_lock(path: Path) -> bool:
    """Rewrite the lock at ``path`` in name order; return whether it moved."""
    document = json.loads(path.read_text())
    packages = document.get("packages", [])
    ordered = in_lock_order(packages)
    if [lock_order_key(entry) for entry in ordered] == [lock_order_key(entry) for entry in packages]:
        return False
    document["packages"] = ordered
    path.write_text(json.dumps(document, indent=2) + "\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true", help="fail instead of rewriting when out of order")
    args = parser.parse_args(argv)
    path = args.root / LOCK
    if args.check:
        error = order_error(path)
        if error:
            print(error, file=sys.stderr)
            return 1
        return 0
    if sort_lock(path):
        print(f"sorted {path} by name")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
