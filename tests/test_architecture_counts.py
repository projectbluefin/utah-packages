#!/usr/bin/env python3
"""Drift gate for the inventory sizes quoted in ``docs/architecture.md``.

The "Coverage" section of the architecture document does not describe the
factory in prose; it publishes four numbers as *verifiable command output* --
``ls -d packages/*/ | wc -l``, the ``.packit.yaml`` and ``config/upstream-sources.json``
entry counts, and the line ``tools/validate.py`` prints. A reader is invited to
run those commands and get the same answer.

Nothing kept them honest. All four said ``193`` while the repository carried
192 recipes, so the one document that states the factory's coverage contract
disagreed with the factory, and adding or removing a package would have moved
it further. Every number below is therefore recomputed from
:func:`tools.package_inventory.inventory` -- the same contract the factory
itself reads -- and compared with what the document claims.
"""

from pathlib import Path
import re
import unittest

from tools.package_inventory import inventory, source_locks
from tools.validate import main as validate_main

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "architecture.md"


def claimed(pattern: str) -> int:
    """The single number ``docs/architecture.md`` states for ``pattern``."""
    matches = re.findall(pattern, DOC.read_text())
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one architecture.md claim matching {pattern!r}, "
            f"found {len(matches)}"
        )
    return int(matches[0])


class ArchitectureCountTests(unittest.TestCase):
    def setUp(self):
        self.records = inventory(ROOT)

    def test_recipe_count_matches_the_packages_tree(self):
        self.assertEqual(
            claimed(r"\| `ls -d packages/\*/ \\\| wc -l` \| `(\d+)` \|"),
            len(self.records),
        )

    def test_packit_entry_count_matches_the_rendered_config(self):
        self.assertEqual(
            claimed(r"\| entries under `\.packit\.yaml:packages` \| `(\d+)` \|"),
            sum(1 for record in self.records if record.packit_configured),
        )

    def test_source_lock_entry_count_matches_the_lock_file(self):
        self.assertEqual(
            claimed(
                r"\| entries under `config/upstream-sources\.json:packages` \| `(\d+)` \|"
            ),
            len(source_locks(ROOT)),
        )

    def test_prose_coverage_claim_matches_the_inventory(self):
        self.assertEqual(claimed(r"cover all (\d+) recipes"), len(self.records))

    def test_quoted_validate_output_is_what_validate_prints(self):
        self.assertEqual(
            claimed(r"validated (\d+) source RPMs"), len(self.records)
        )

    def test_hand_assigned_stage_count_matches_the_lock_file(self):
        # The review table argues that hand-assigned stages are a manual cache
        # of a computed value; the size of that cache is part of the argument.
        declared, total = re.search(
            r"(\d+) of (\d+) packages carry a hand-assigned `stage`", DOC.read_text()
        ).groups()
        self.assertEqual(
            int(declared),
            sum(1 for entry in source_locks(ROOT).values() if "stage" in entry),
        )
        self.assertEqual(int(total), len(self.records))

    def test_validate_still_passes_on_the_documented_inventory(self):
        # The quoted output is only meaningful if validate.py actually succeeds.
        self.assertEqual(validate_main(ROOT), 0)


if __name__ == "__main__":
    unittest.main()
