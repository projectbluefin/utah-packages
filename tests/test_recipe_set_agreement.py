#!/usr/bin/env python3
"""The rebuild set is recorded in three places; they must describe one set.

Adding or removing a recipe touches `packages/`, `config/upstream-sources.json`
and `.packit.yaml` together (see `docs/contributing.md`, "Removing a package").
A change that reaches only some of them leaves the repository self-inconsistent,
and the package-count assertions elsewhere in this suite then fail as bare
integer mismatches that do not say which place was missed. This test names it.
"""

import json
from pathlib import Path
import unittest

from tools.packit_workflow import package_names


ROOT = Path(__file__).resolve().parent.parent
PACKIT_CONFIG = ROOT / ".packit.yaml"
SOURCE_CONFIG = ROOT / "config" / "upstream-sources.json"


def recipe_names() -> set[str]:
    return {path.name for path in (ROOT / "packages").iterdir() if path.is_dir()}


def lock_names() -> set[str]:
    return {
        package["name"]
        for package in json.loads(SOURCE_CONFIG.read_text())["packages"]
    }


class RecipeSetAgreementTests(unittest.TestCase):
    def test_every_recipe_has_a_source_lock(self) -> None:
        self.assertEqual(
            recipe_names() - lock_names(),
            set(),
            "recipes in packages/ with no entry in config/upstream-sources.json: "
            "a recipe without a lock is not eligible to build",
        )

    def test_no_source_lock_outlives_its_recipe(self) -> None:
        self.assertEqual(
            lock_names() - recipe_names(),
            set(),
            "entries in config/upstream-sources.json with no packages/<name>/ "
            "directory: delete the lock when the recipe is dropped",
        )

    def test_packit_config_covers_exactly_the_recipes(self) -> None:
        configured = set(package_names(PACKIT_CONFIG))
        self.assertEqual(
            configured.symmetric_difference(recipe_names()),
            set(),
            "`.packit.yaml` disagrees with packages/: regenerate it with "
            "`python3 tools/render_packit_config.py --write`",
        )


if __name__ == "__main__":
    unittest.main()
