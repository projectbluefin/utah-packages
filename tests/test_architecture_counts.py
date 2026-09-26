#!/usr/bin/env python3
"""Keep the inventory counts published by ``docs/architecture.md`` honest.

The Coverage section publishes command output and invites readers to reproduce
it.  Each claim must agree with the repository inventory, and the quoted
``validate.py`` result must come from a successful run of that script.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import unittest

from tools.package_inventory import inventory, source_locks


ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "architecture.md"


def claimed(pattern: str) -> int:
    """Return the one number ``architecture.md`` states for ``pattern``."""
    matches = re.findall(pattern, DOC.read_text())
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one architecture.md claim matching {pattern!r}, "
            f"found {len(matches)}"
        )
    return int(matches[0])


class ArchitectureCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = inventory(ROOT)

    def test_recipe_count_matches_the_inventory(self) -> None:
        self.assertEqual(
            claimed(r"\| `ls -d packages/\*/ .*wc -l` \| `(\d+)` \|"),
            len(self.records),
        )

    def test_packit_entry_count_matches_the_inventory(self) -> None:
        self.assertEqual(
            claimed(r"\| entries under `\.packit\.yaml:packages` \| `(\d+)` \|"),
            sum(record.packit_configured for record in self.records),
        )

    def test_source_lock_entry_count_matches_the_inventory(self) -> None:
        self.assertEqual(
            claimed(
                r"\| entries under `config/upstream-sources\.json:packages` "
                r"\| `(\d+)` \|"
            ),
            len(source_locks(ROOT)),
        )

    def test_prose_coverage_claim_matches_the_inventory(self) -> None:
        self.assertEqual(claimed(r"cover all (\d+) recipes"), len(self.records))

    def test_packit_guard_claim_matches_the_inventory(self) -> None:
        self.assertEqual(
            claimed(r"a list of (\d+) satisfies"),
            len(self.records),
        )

    def test_quoted_validate_output_matches_successful_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "validate.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        match = re.search(r"validated (\d+) source RPMs", result.stdout.strip())
        self.assertIsNotNone(match, result.stdout)
        assert match is not None
        self.assertEqual(
            claimed(r"validated (\d+) source RPMs"),
            int(match.group(1)),
        )

    def test_hand_assigned_stage_count_matches_the_inventory(self) -> None:
        match = re.search(
            r"(\d+) of (\d+) packages carry a hand-assigned `stage`",
            DOC.read_text(),
        )
        self.assertIsNotNone(
            match,
            "docs/architecture.md no longer states the hand-assigned stage count "
            "in the form 'N of M packages carry a hand-assigned `stage`'",
        )
        declared, total = match.groups()
        locks = source_locks(ROOT)
        self.assertEqual(
            int(declared),
            sum("stage" in entry for entry in locks.values()),
        )
        self.assertEqual(int(total), len(self.records))


if __name__ == "__main__":
    unittest.main()
