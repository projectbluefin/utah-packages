#!/usr/bin/env python3
"""Drift gate for the inventory sizes quoted in ``docs/architecture.md``.

The "Coverage" section of the architecture document does not describe the
factory in prose; it publishes four numbers as *verifiable command output* --
``ls -d packages/*/ | wc -l``, the ``.packit.yaml`` and ``config/upstream-sources.json``
entry counts, and the line ``tools/validate.py`` prints. A reader is invited to
run those commands and get the same answer.

Nothing kept them honest. All four claimed stale counts while the repository
inventory evolved, so the document stating the factory's coverage contract
disagreed with the factory. Every number below is therefore recomputed from
:func:`tools.package_inventory.inventory` -- the same contract the factory
itself reads -- and compared with what the document claims.
"""

from contextlib import redirect_stdout
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.package_inventory import inventory, source_locks
from tools.validate import main as validate_main
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
        self.doc_text = DOC.read_text()

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

    def test_srpm_pilot_matrix_package_count_matches_inventory(self):
        self.assertEqual(
            claimed(r"which a list of (\d+) satisfies while\s+still producing no jobs"),
            len(self.records),
        )

    def test_validate_output_and_quoted_report(self):
        # Capture the actual stdout of validate.py and assert it passes.
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = validate_main(ROOT)
        self.assertEqual(exit_code, 0, "tools/validate.py did not pass")
        validate_output = stdout.getvalue().strip()

        # Extract the validated count from validate.py's actual output line.
        match = re.search(r"^validated (\d+) source RPMs$", validate_output)
        self.assertIsNotNone(
            match,
            f"unexpected output format from tools/validate.py: {validate_output!r}",
        )
        validated_count = int(match.group(1))
        self.assertEqual(validated_count, len(self.records))

        # Assert the doc's quoted text matches validate.py's actual output line.
        self.assertEqual(
            claimed(r"validated (\d+) source RPMs"),
            validated_count,
        )
        self.assertIn(
            f"```text\n{validate_output}\n```",
            self.doc_text,
            "docs/architecture.md code block does not match validate.py output",
        )

    def test_hand_assigned_stage_count_matches_the_lock_file(self):
        # The review table argues that hand-assigned stages are a manual cache
        # of a computed value; the size of that cache is part of the argument.
        match = re.search(
            r"(\d+) of (\d+) packages carry a hand-assigned `stage`", self.doc_text
        )
        self.assertIsNotNone(match, "stage assignment claim not found in docs/architecture.md")
        declared, total = match.groups()
        self.assertEqual(
            int(declared),
            sum(1 for entry in source_locks(ROOT).values() if "stage" in entry),
        )
        self.assertEqual(int(total), len(self.records))


if __name__ == "__main__":
    unittest.main()
