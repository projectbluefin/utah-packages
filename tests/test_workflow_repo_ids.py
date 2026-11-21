#!/usr/bin/env python3
"""Every dnf --repo a workflow names is a repository config/hummingbird.repo defines.

dnf fails outright on an unknown --repo id, and a dispatch-only or weekly
workflow finds out only when it next runs. recalculate-hummingbird-gaps.yml
(#1269) and bootstrap-direct-sources.yml (#1272) both kept asking for
tunaos-hummingbird after the repo file renamed its section, and both failed
every run until someone dispatched them.
"""

from __future__ import annotations

import configparser
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
REPO_FILE = ROOT / "config" / "hummingbird.repo"

# `dnf ... --repo <id>` or `--repo=<id>`, also --repoid, on a dnf line. gh's
# own --repo takes owner/name, which never shares a line with dnf.
DNF_REPO = re.compile(r"--repo(?:id)?[ =]['\"]?([A-Za-z0-9_.:-]+)")


def defined_repo_ids() -> set[str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(REPO_FILE)
    return set(parser.sections())


def named_repo_ids() -> list[tuple[str, int, str]]:
    named = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or not re.search(r"\bdnf\b", stripped):
                continue
            named.extend((path.name, number, repo_id) for repo_id in DNF_REPO.findall(stripped))
    return named


class WorkflowRepoIdTests(unittest.TestCase):
    def test_the_repo_file_defines_a_repository(self) -> None:
        self.assertTrue(defined_repo_ids(), f"{REPO_FILE.name} defines no repository")

    def test_workflows_query_the_hummingbird_repository(self) -> None:
        # Without at least one hit the scan below could pass by matching nothing.
        self.assertTrue(named_repo_ids(), "no workflow names a dnf --repo; the scan is broken")

    def test_every_dnf_repo_id_is_defined(self) -> None:
        defined = defined_repo_ids()
        unknown = [
            f"{name}:{number}: --repo {repo_id}"
            for name, number, repo_id in named_repo_ids()
            if repo_id not in defined
        ]
        self.assertEqual(
            unknown,
            [],
            f"these dnf calls name a repository {REPO_FILE.name} does not define "
            f"({', '.join(sorted(defined))}); dnf fails on an unknown --repo",
        )


if __name__ == "__main__":
    unittest.main()
