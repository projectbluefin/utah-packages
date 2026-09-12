#!/usr/bin/env python3

from pathlib import Path
import re
import unittest

from tools.mock_config import (
    EXCLUDED_EVERYWHERE,
    FEDORA_RELEASEVER,
    HUMMINGBIRD_WINS,
    render,
)

ROOT = Path(__file__).resolve().parent.parent
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"


def workflow_list(variable: str) -> tuple[str, ...]:
    """The comma-separated value the container path assigns to a shell name."""
    text = BUILD_STAGE.read_text()
    match = re.search(rf'^\s*{variable}="([^"]*)"', text, re.MULTILINE)
    assert match, f"{variable} is not set in {BUILD_STAGE.name}"
    return tuple(name for name in match.group(1).split(",") if name)


class PolicyAgreementTests(unittest.TestCase):
    """The container root and the mock root must encode the same policy.

    Both exist while the mock backend is opt-in. Two copies of a build-root
    policy is exactly how the five stage files drifted before they were merged
    into one, so this fails the moment they disagree rather than letting one
    backend build against different rules than the other.
    """

    def test_hummingbird_precedence_list_matches_the_container(self) -> None:
        self.assertEqual(workflow_list("HB_EXCLUDE"), HUMMINGBIRD_WINS)

    def test_global_exclusion_list_matches_the_container(self) -> None:
        self.assertEqual(workflow_list("GLOBAL_EXCLUDE"), EXCLUDED_EVERYWHERE)

    def test_builds_against_the_same_fedora_the_container_uses(self) -> None:
        self.assertIn(
            f"fedora:{FEDORA_RELEASEVER}",
            BUILD_STAGE.read_text(),
            "the mock root and the container must pair Hummingbird with the "
            "same Fedora",
        )


class RenderTests(unittest.TestCase):
    def test_pairs_fedora_with_hummingbird(self) -> None:
        config = render()
        self.assertIn("[fedora]", config)
        self.assertIn("[public-hummingbird-x86_64-rpms]", config)
        self.assertIn("priority=10", config)

    def test_excludes_the_superseded_ruby_from_every_repository(self) -> None:
        config = render()
        main_section = config.split("[fedora]")[0]
        for name in EXCLUDED_EVERYWHERE:
            self.assertIn(name, main_section)

    def test_fedora_may_not_answer_for_what_an_earlier_stage_built(self) -> None:
        config = render(prior_built=("accountsservice", "accountsservice-libs"))
        fedora = config.split("[fedora]")[1].split("[updates]")[0]
        self.assertIn("accountsservice-libs", fedora)
        # And the same exclusion reaches updates, which is a separate repo.
        updates = config.split("[updates]")[1]
        self.assertIn("accountsservice-libs", updates)

    def test_omits_the_optional_repositories_when_not_given(self) -> None:
        config = render()
        self.assertNotIn("[stages]", config)
        self.assertNotIn("[factory]", config)

    def test_adds_prior_stage_and_published_repositories_when_given(self) -> None:
        config = render(
            factory_repo="https://example.invalid/repo/",
            stages_dir="/work/prior",
        )
        self.assertIn("baseurl=file:///work/prior", config)
        self.assertIn("baseurl=https://example.invalid/repo/", config)
        # Earlier stages outrank the published repository, which outranks
        # Hummingbird and Fedora.
        self.assertLess(config.index("[stages]"), config.index("[factory]"))

    def test_is_a_python_config_mock_can_execute(self) -> None:
        # A mock config is executed as Python, so a rendering mistake shows up
        # as a syntax error inside mock rather than as a bad build root.
        namespace: dict = {"config_opts": {}}
        exec(compile(render(), "mock.cfg", "exec"), namespace)  # noqa: S102
        self.assertEqual(namespace["config_opts"]["target_arch"], "x86_64")
        self.assertIn("dnf.conf", namespace["config_opts"])


if __name__ == "__main__":
    unittest.main()
