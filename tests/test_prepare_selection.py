"""The package selection `prepare` makes, exercised as the workflow writes it.

The logic lives inline in .github/workflows/rebuild-rpms.yml. Rather than
restate it here and let the copy drift, this extracts the decision block from
the workflow and runs it, so a change to the workflow that breaks the rule is
a failing test rather than an hour of wasted runner time.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/rebuild-rpms.yml"


def decision_block() -> str:
    """The `if selected: ... else: ...` block, dedented to module level."""
    text = WORKFLOW.read_text()
    start = text.index("              if selected:")
    end = text.index("              if should_build:", start)
    block = text[start:end]
    return "\n".join(line[14:] for line in block.splitlines())


def decide(**context) -> bool:
    scope = {
        "full": False,
        "selected": set(),
        "changed": set(),
        "published": {},
        "published_keys": {},
        "identity_matches": False,
        "recipe_name": lambda package: package["name"],
        "norm": lambda version: version.replace("~", "."),
    }
    scope.update(context)
    exec(compile(decision_block(), "<prepare>", "exec"), scope)
    return scope["should_build"]


class PrepareSelectionTests(unittest.TestCase):
    PACKAGE = {"name": "mesa", "version": "26.0"}

    def context(self, **overrides):
        base = {
            "package": self.PACKAGE,
            "name": self.PACKAGE["name"],
            "version": self.PACKAGE["version"],
        }
        base.update(overrides)
        return base

    def test_source_without_a_binary_of_the_same_name_is_not_rebuilt(self):
        # mesa ships mesa-libGL and mesa-dri-drivers, never a plain `mesa`, so
        # it is absent from repodata's binary names by construction. With a
        # matching identity that must not force a rebuild -- this is the bug
        # that rebuilt both WebKitGTK shards on every run.
        self.assertFalse(
            decide(**self.context(
                published={},
                published_keys={"mesa": "sha256:abc"},
                identity_matches=True,
            ))
        )

    def test_identity_mismatch_still_rebuilds(self):
        self.assertTrue(
            decide(**self.context(
                published={"mesa": "26.0"},
                published_keys={"mesa": "sha256:stale"},
                identity_matches=False,
            ))
        )

    def test_changed_recipe_rebuilds_even_with_a_matching_identity(self):
        self.assertTrue(
            decide(**self.context(
                changed={"mesa"},
                published_keys={"mesa": "sha256:abc"},
                identity_matches=True,
            ))
        )

    def test_full_rebuilds_everything(self):
        self.assertTrue(
            decide(**self.context(
                full=True,
                published_keys={"mesa": "sha256:abc"},
                identity_matches=True,
            ))
        )

    def test_without_an_identity_record_the_old_heuristic_still_applies(self):
        # Reading the published Pages repository gives names and versions but
        # no manifest, so absence and version drift must still trigger a build.
        self.assertTrue(
            decide(**self.context(published={}, published_keys={}))
        )
        self.assertTrue(
            decide(**self.context(published={"mesa": "25.0"}, published_keys={}))
        )
        self.assertFalse(
            decide(**self.context(published={"mesa": "26.0"}, published_keys={}))
        )

    def test_explicit_selection_overrides_everything(self):
        self.assertTrue(
            decide(**self.context(
                selected={"mesa"},
                published_keys={"mesa": "sha256:abc"},
                identity_matches=True,
            ))
        )
        self.assertFalse(
            decide(**self.context(
                selected={"grub2"},
                published_keys={},
                published={},
            ))
        )


if __name__ == "__main__":
    unittest.main()
