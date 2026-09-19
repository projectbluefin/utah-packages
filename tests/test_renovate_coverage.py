#!/usr/bin/env python3
"""Every container image this factory runs must be tracked by something.

Two pins died in one week -- quay.io/fedora/fedora and quay.io/packit/packit,
the latter twice -- and each took every job in the run down with exit 125
before a line of its script ran. Neither was tracked: Renovate's docker manager
reads Dockerfiles, `container:` and `services:`, and both were named inside a
`docker run` shell line, which no built-in manager scans.

renovate.json now carries a custom manager for that shape. These tests assert
the manager still covers every such pin, so a workflow added later cannot
quietly reintroduce an untracked one.
"""

from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
RENOVATE = ROOT / "renovate.json"

# Any quay.io image pinned by digest, tagged or not.
ANY_PINNED_IMAGE = re.compile(r"(quay\.io/[^\s@:]+)(:[^\s@]+)?@sha256:[a-f0-9]{64}")

# The bootc-os pin is deliberately excluded: its own comment ties it to
# runtime-contract.toml's BASE_IMAGE, the image Utah consumes, so it must move
# with that contract rather than on its own.
MANUALLY_PINNED = {"quay.io/hummingbird-community/bootc-os"}


def build_root_manager() -> dict:
    config = json.loads(RENOVATE.read_text())
    managers = [
        m for m in config.get("customManagers", []) if m.get("depTypeTemplate") == "build-root-image"
    ]
    assert len(managers) == 1, "expected exactly one build-root-image custom manager"
    return managers[0]


def manager_pattern(manager: dict) -> re.Pattern:
    """Renovate's regex flavour uses (?<name>...); Python wants (?P<name>...)."""
    assert len(manager["matchStrings"]) == 1
    return re.compile(manager["matchStrings"][0].replace("(?<", "(?P<"))


def workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


class RenovateCoverageTests(unittest.TestCase):
    def test_every_run_script_image_is_tracked(self) -> None:
        pattern = manager_pattern(build_root_manager())
        untracked = []
        for path in workflow_files():
            text = path.read_text()
            tracked = {m.group(0) for m in pattern.finditer(text)}
            for found in ANY_PINNED_IMAGE.finditer(text):
                if found.group(1) in MANUALLY_PINNED:
                    continue
                if found.group(0) not in tracked:
                    untracked.append(f"{path.name}: {found.group(0)}")
        self.assertEqual(
            untracked,
            [],
            "these image pins are not matched by the build-root-image manager, "
            "so nothing will refresh them when the digest is collected; write "
            "them as image:tag@sha256:... ",
        )

    def test_the_manager_matches_the_pins_that_actually_rotted(self) -> None:
        pattern = manager_pattern(build_root_manager())
        found = {}
        for path in workflow_files():
            for match in pattern.finditer(path.read_text()):
                found[match.group("depName")] = match.group("currentValue")
        self.assertIn("quay.io/fedora/fedora", found)
        self.assertIn("quay.io/packit/packit", found)

    def test_the_fedora_build_root_tracks_a_release_not_latest(self) -> None:
        # Following :latest here would carry the factory to a new Fedora major
        # on somebody else's schedule. The build root is a deliberate choice.
        pattern = manager_pattern(build_root_manager())
        tags = {
            m.group("currentValue")
            for path in workflow_files()
            for m in pattern.finditer(path.read_text())
            if m.group("depName") == "quay.io/fedora/fedora"
        }
        self.assertEqual(tags, {"44"})

    def test_the_manually_pinned_image_is_left_alone(self) -> None:
        # bootc-os moves with runtime-contract.toml, not on its own.
        pattern = manager_pattern(build_root_manager())
        gaps = (WORKFLOWS / "recalculate-hummingbird-gaps.yml").read_text()
        self.assertIn("bootc-os@sha256:", gaps)
        self.assertIsNone(pattern.search(gaps))

    def test_a_digest_update_may_land_without_a_human(self) -> None:
        # The replacement is whatever the pinned tag already resolves to, and a
        # rotted pin fails the whole run; waiting for review costs more than it
        # protects. A major is a different matter and is not covered here.
        config = json.loads(RENOVATE.read_text())
        rules = [
            r
            for r in config["packageRules"]
            if r.get("matchDepTypes") == ["build-root-image"]
        ]
        self.assertEqual(len(rules), 1)
        self.assertTrue(rules[0]["automerge"])
        self.assertEqual(rules[0]["matchUpdateTypes"], ["digest"])

    def test_no_rule_automerges_an_action_update(self) -> None:
        # An action ref is executable code that runs with contents: write,
        # packages: write and id-token: write. A rotted action pin does not
        # fail the run the way a rotted build-root digest does -- it runs
        # something else -- so automerging buys no availability here and
        # spends the only review this supply chain gets.
        config = json.loads(RENOVATE.read_text())
        self.assertFalse(config.get("automerge", False), "top-level automerge must stay off")
        offenders = [
            r.get("description", r)
            for r in config["packageRules"]
            if "github-actions" in (r.get("matchManagers") or [])
            and (r.get("automerge") or r.get("platformAutomerge"))
        ]
        self.assertEqual(offenders, [], "github-actions updates must be human-reviewed")

    def test_the_actions_rule_states_its_stance_explicitly(self) -> None:
        # config:recommended is a moving target. Leaving github-actions to the
        # top-level default would let a preset bump re-enable automerge with no
        # diff in this file, so the rule is pinned off on purpose.
        config = json.loads(RENOVATE.read_text())
        rules = [
            r for r in config["packageRules"]
            if "github-actions" in (r.get("matchManagers") or [])
        ]
        self.assertEqual(len(rules), 1, "expected exactly one github-actions rule")
        self.assertIs(rules[0]["automerge"], False)
        self.assertIs(rules[0]["platformAutomerge"], False)


if __name__ == "__main__":
    unittest.main()
