#!/usr/bin/env python3
"""The factory onboarding contract holds, and its checks actually fail."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.factory_contract import main

ROOT = Path(__file__).resolve().parent.parent


def fixture() -> Path:
    """A minimal tree that satisfies the contract, as a throwaway git repo."""
    root = Path(tempfile.mkdtemp())
    (root / "docs" / "skills").mkdir(parents=True)
    (root / ".agents" / "skills" / "demo").mkdir(parents=True)
    (root / "config").mkdir()

    (root / "config" / "factory-contract.json").write_text(
        json.dumps(
            {
                "repository": "projectbluefin/common",
                "commit": "0" * 40,
                "contracts": {"factory-onboarding": "docs/skills/x.md"},
            }
        )
    )
    (root / "AGENTS.md").write_text(
        "# Agents\n\n"
        "See [router](docs/SKILL.md) and "
        "[pin](config/factory-contract.json).\n\n"
        "## Self-Improvement\n\n"
        "- No changelog files.\n"
        "- No session notes committed to the repository.\n"
        '- No "append here" docs.\n'
    )
    (root / "docs" / "SKILL.md").write_text(
        "# Router\n\n"
        "- [demo](../.agents/skills/demo/SKILL.md)\n"
        "- [improve](skills/skill-improvement.md)\n"
    )
    (root / "docs" / "skills" / "skill-improvement.md").write_text(
        "---\nname: skill-improvement\ndescription: Write learning back.\n---\n"
    )
    (root / ".agents" / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A demo skill.\n---\n"
    )

    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


class FactoryContractTests(unittest.TestCase):
    def test_repository_satisfies_the_contract(self):
        self.assertEqual(main([str(ROOT)]), 0)

    def test_fixture_is_a_passing_baseline(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(main([str(root)]), 0)

    def test_banned_changelog_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / "CHANGELOG.md").write_text("# nope\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        self.assertEqual(main([str(root)]), 1)

    def test_unindexed_skill_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / "docs" / "skills" / "orphan.md").write_text(
            "---\nname: orphan\ndescription: Not in the router.\n---\n"
        )
        self.assertEqual(main([str(root)]), 1)

    def test_skill_without_front_matter_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / ".agents" / "skills" / "demo" / "SKILL.md").write_text("# demo\n")
        self.assertEqual(main([str(root)]), 1)

    def test_agents_missing_mandate_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / "AGENTS.md").write_text("# Agents\n\nnothing here\n")
        self.assertEqual(main([str(root)]), 1)

    def test_unpinned_contract_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / "config" / "factory-contract.json").write_text(
            json.dumps(
                {
                    "repository": "projectbluefin/common",
                    "commit": "main",
                    "contracts": {"factory-onboarding": "docs/skills/x.md"},
                }
            )
        )
        self.assertEqual(main([str(root)]), 1)

    def test_broken_internal_link_fails(self):
        root = fixture()
        self.addCleanup(shutil.rmtree, root)
        (root / "docs" / "skills" / "skill-improvement.md").write_text(
            "---\nname: skill-improvement\ndescription: Write learning back.\n---\n"
            "[gone](../nowhere.md)\n"
        )
        self.assertEqual(main([str(root)]), 1)


if __name__ == "__main__":
    unittest.main()
