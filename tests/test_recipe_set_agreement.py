#!/usr/bin/env python3
"""The three package sources must describe exactly the same set of names.

A recipe removal touches four places (see ``docs/contributing.md`` *Removing a
package*): ``packages/<name>/``, ``config/upstream-sources.json``,
``.packit.yaml``, and the hardcoded counts in ``tests/``. Dropping one of them
leaves the other three at different sizes, which surfaces later as unrelated
failing integer assertions instead of as "you forgot ``config/upstream-sources.json``".

This test makes that fail legibly: it compares the recipe directory names, the
source-lock names, and the ``.packit.yaml`` package names against each other and
names every package that is present in one source and missing from another.
"""

import json
from pathlib import Path
import unittest

from tools.packit_workflow import package_names

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"
PACKIT_CONFIG = ROOT / ".packit.yaml"
HUMMINGBIRD_OWNED = ROOT / "config" / "hummingbird-provided-sources.json"


def recipe_names() -> set[str]:
    return {d.name for d in PACKAGES.iterdir() if d.is_dir()}


def lock_names() -> set[str]:
    data = json.loads(SOURCE_CONFIG.read_text())
    return {entry["name"] for entry in data["packages"]}


def packit_names() -> set[str]:
    return set(package_names(PACKIT_CONFIG))


class RecipeSetAgreementTests(unittest.TestCase):
    def test_all_three_sources_describe_the_same_names(self):
        recipes = recipe_names()
        locks = lock_names()
        packit = packit_names()

        self.assertEqual(
            recipes,
            locks,
            f"packages/ and {SOURCE_CONFIG.name} disagree "
            f"(in packages only: {sorted(recipes - locks)}; "
            f"in locks only: {sorted(locks - recipes)})",
        )
        self.assertEqual(
            recipes,
            packit,
            f"packages/ and {PACKIT_CONFIG.name} disagree "
            f"(in packages only: {sorted(recipes - packit)}; "
            f"in packit only: {sorted(packit - recipes)})",
        )
        self.assertEqual(
            locks,
            packit,
            f"{SOURCE_CONFIG.name} and {PACKIT_CONFIG.name} disagree "
            f"(in locks only: {sorted(locks - packit)}; "
            f"in packit only: {sorted(packit - locks)})",
        )

    def test_hummingbird_owned_sources_are_not_factory_recipes(self):
        owned = set(json.loads(HUMMINGBIRD_OWNED.read_text())["sources"])
        self.assertEqual(recipe_names() & owned, set())


if __name__ == "__main__":
    unittest.main()
