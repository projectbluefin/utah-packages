"""Pin the format the architecture.md renderer expects to find.

The renderer walks ``docs/architecture.md`` looking for six concrete
number-bearing claims and replaces them with the live inventory.  A
doc that doesn't match (typo, restructure, removed table) raises on the
first non-matching claim rather than silently leaving stale numbers.
These tests pin the location and shape of those claims.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tools.package_inventory import inventory, source_locks
from tools.validate import validated_summary

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "architecture.md"
RENDERER = ROOT / "tools" / "render_architecture_counts.py"


def _number_after_line(text: str, prefix: str) -> str:
    """Return the digit-block on the line that begins with ``prefix``."""
    for line in text.splitlines():
        if line.startswith(prefix):
            match = re.search(r"\b(\d+)\b", line)
            assert match, f"no digit in line {line!r}"
            return match.group(1)
    raise AssertionError(f"no line begins with {prefix!r} in architecture.md")


class RenderArchitectureCountsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        records = inventory(ROOT)
        locks = source_locks(ROOT)
        cls.n_recipes = len(records)
        cls.n_packit = sum(record.packit_configured for record in records)
        cls.n_locks = len(locks)
        cls.n_staged = sum("stage" in lock for lock in locks.values())
        cls.validated_line = validated_summary(records)

    def assert_every_claim_matches(self, text: str) -> None:
        n = str(self.n_recipes)
        self.assertEqual(_number_after_line(text, "| `ls -d packages/*/"), n)
        self.assertEqual(
            _number_after_line(text, "| entries under `.packit.yaml:packages`"),
            str(self.n_packit),
        )
        self.assertEqual(
            _number_after_line(
                text, "| entries under `config/upstream-sources.json:packages`"
            ),
            str(self.n_locks),
        )
        # 'cover all N recipes' and 'a list of N satisfies' both target the
        # recipe count; either clause rewriting would break the renderer.
        self.assertEqual(re.findall(r"cover all (\d+) recipes", text), [n])
        self.assertEqual(re.findall(r"a list of (\d+) satisfies", text), [n])
        self.assertEqual(
            re.findall(r"^validated \d+ source RPMs \(.*\)$", text, flags=re.MULTILINE),
            [self.validated_line],
        )
        self.assertEqual(
            re.findall(
                r"^(\d+) of \d+ packages carry a hand-assigned `stage`",
                text,
                flags=re.MULTILINE,
            ),
            [str(self.n_staged)],
        )

    def test_architecture_doc_has_every_claim_the_renderer_replaces(self) -> None:
        self.assert_every_claim_matches(DOC.read_text(encoding="utf-8"))

    def test_renderer_is_a_noop_when_doc_is_current(self) -> None:
        """The workflow runs the renderer, then `pytest tests -q`; the
        renderer must accept an already-current doc and exit 0.
        """
        result = subprocess.run(
            [sys.executable, str(RENDERER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"renderer exited {result.returncode} on a current doc:\n"
            f"{result.stdout}{result.stderr}",
        )

    def test_renderer_rewrites_every_claim_to_match_the_inventory(self) -> None:
        """Round-trip: stale every claim in a copy of the doc, rewrite it with
        --write, then assert every claim matches.  Tests the regex patterns,
        not just the inventory; if a pattern silently stops matching, this
        test catches it.  Render into a fixture copy via ``--doc`` so a test
        run never mutates the tracked architecture.md (#366 review).
        """
        stale = DOC.read_text(encoding="utf-8")
        stale = re.sub(r"`\d+` \|", "`1` |", stale)
        stale = re.sub(r"cover all \d+ recipes", "cover all 1 recipes", stale)
        stale = re.sub(r"a list of \d+ satisfies", "a list of 1 satisfies", stale)
        stale = re.sub(
            r"^validated \d+ source RPMs \(.*\)$",
            "validated 1 source RPMs (1 rawhide)",
            stale,
            flags=re.MULTILINE,
        )
        stale = re.sub(
            r"^\d+ of \d+ packages carry a hand-assigned `stage`",
            "0 of 1 packages carry a hand-assigned `stage`",
            stale,
            flags=re.MULTILINE,
        )
        with tempfile.TemporaryDirectory() as tmp:
            fixture_doc = Path(tmp) / "architecture.md"
            fixture_doc.write_text(stale, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(RENDERER), "--write", "--doc", str(fixture_doc)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assert_every_claim_matches(fixture_doc.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
