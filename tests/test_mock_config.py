#!/usr/bin/env python3

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tools.mock_config import (
    HUMMINGBIRD_REPO_EXCLUDE,
    FEDORA_RELEASEVER,
    HUMMINGBIRD_WINS,
    render,
)

ROOT = Path(__file__).resolve().parent.parent
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"
# Where the container path now declares its Fedora release. The build stages
# no longer name the image at all: they run utah-buildroot:run, the bytes
# prepare pulled once for the whole run, because pulling a pinned digest per
# job raced quay garbage-collecting it and lost mid-run.
REBUILD = ROOT / ".github" / "workflows" / "rebuild-rpms.yml"
# The container lane builds with tools/build_container.sh. build-stage.yml
# keeps its own copy of the same root in the "Resolve the package cache key"
# step. Both copies must agree with the mock root.
BUILD_CONTAINER = ROOT / "tools" / "build_container.sh"
CONTAINER_ROOTS = (BUILD_STAGE, BUILD_CONTAINER)


def workflow_list(variable: str, path: Path = BUILD_STAGE) -> tuple[str, ...]:
    """The comma-separated value a container-lane file first assigns to a shell name."""
    text = path.read_text()
    match = re.search(rf'^\s*{variable}="([^"]*)"', text, re.MULTILINE)
    assert match, f"{variable} is not set in {path.name}"
    return tuple(name for name in match.group(1).split(",") if name)


class PolicyAgreementTests(unittest.TestCase):
    """The container root and the mock root must encode the same policy.

    Both exist while the mock backend is opt-in. Two copies of a build-root
    policy is exactly how the five stage files drifted before they were merged
    into one, so this fails the moment they disagree rather than letting one
    backend build against different rules than the other.
    """

    def test_hummingbird_precedence_list_matches_the_container(self) -> None:
        for path in CONTAINER_ROOTS:
            with self.subTest(path=path.name):
                self.assertEqual(workflow_list("HB_EXCLUDE", path), HUMMINGBIRD_WINS)

    def test_hummingbird_repo_exclusion_matches_the_container(self) -> None:
        for path in CONTAINER_ROOTS:
            with self.subTest(path=path.name):
                self.assertEqual(
                    workflow_list("HB_REPO_EXCLUDE", path), HUMMINGBIRD_REPO_EXCLUDE
                )

    def test_both_roots_wait_out_a_stalled_hummingbird_download(self) -> None:
        # dnf's default aborts a transfer under 1000 B/s for 30 s; with one
        # baseurl that is a hard failure (issue #1160).
        repo = (ROOT / "config" / "hummingbird.repo").read_text()
        mock = render().split("[public-hummingbird-x86_64-rpms]")[1]
        for setting in ("minrate=1", "timeout=300"):
            self.assertIn(f"\n{setting}\n", repo)
            self.assertIn(f"\n{setting}\n", mock)

    def test_builds_against_the_same_fedora_the_container_uses(self) -> None:
        # The invariant is unchanged -- both roots must pair Hummingbird with
        # one Fedora release -- but the container path declares it in
        # config/buildroot-image now, rather than at each of the
        # four places that used to name the image.
        from tools import buildroot_pin

        pin = buildroot_pin.get()
        # A mirror tag starts with the Fedora release it copied (44-<date>-...).
        tag = pin.rsplit("@", 1)[0].rsplit(":", 1)[1]
        self.assertTrue(
            tag == str(FEDORA_RELEASEVER) or tag.startswith(f"{FEDORA_RELEASEVER}-"),
            "the mock root and the container must pair Hummingbird with the "
            "same Fedora",
        )


class RenderTests(unittest.TestCase):
    def test_pairs_fedora_with_hummingbird(self) -> None:
        config = render()
        self.assertIn("[fedora]", config)
        self.assertIn("[public-hummingbird-x86_64-rpms]", config)
        self.assertIn("priority=10", config)

    def test_excludes_the_legacy_ruby_from_the_repository_shipping_it(self) -> None:
        config = render()
        hummingbird = config.split("[public-hummingbird-x86_64-rpms]")[1]
        for name in HUMMINGBIRD_REPO_EXCLUDE:
            self.assertIn(name, hummingbird)

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


class RepositoryPrecedenceTests(unittest.TestCase):
    """What wins when two repositories offer the same package name (#1214).

    A factory build such as libicu-78.3-1.hum1.bfin competes with Hummingbird's
    libicu-78.3-9.hum1, which has the higher release. dnf's `priority` (lower
    number wins) is what keeps the higher release from deciding it, so the
    order must be stages, then the factory, then Hummingbird, and Fedora must
    not answer for a name Hummingbird ships newer.
    """

    @staticmethod
    def priorities(config: str) -> dict[str, int]:
        found: dict[str, int] = {}
        for section in re.split(r"^\[", config, flags=re.MULTILINE)[1:]:
            name = section.split("]", 1)[0]
            match = re.search(r"^priority=(\d+)$", section, re.MULTILINE)
            if match:
                found[name] = int(match.group(1))
        return found

    def test_stages_beat_the_factory_which_beats_hummingbird(self) -> None:
        found = self.priorities(
            render(factory_repo="file:///work/factory", stages_dir="/work/prior")
        )
        self.assertLess(found["stages"], found["factory"])
        self.assertLess(found["factory"], found["public-hummingbird-x86_64-rpms"])

    def test_the_factory_beats_hummingbird_without_a_stages_repository(self) -> None:
        found = self.priorities(render(factory_repo="file:///work/factory"))
        self.assertLess(found["factory"], found["public-hummingbird-x86_64-rpms"])

    def test_hummingbird_is_not_outranked_by_fedora(self) -> None:
        config = render()
        self.assertNotIn("priority", config.split("[fedora]")[1].split("[updates]")[0])
        self.assertIn(
            "libicu", config.split("[fedora]")[1].split("[updates]")[0]
        )

    def test_the_container_lane_uses_the_same_priorities(self) -> None:
        found = self.priorities(
            render(factory_repo="file:///work/factory", stages_dir="/work/prior")
        )
        for path in CONTAINER_ROOTS:
            with self.subTest(path=path.name):
                text = path.read_text()
                stages = re.search(r"\[stages\].*?priority=(\d+)", text, re.DOTALL)
                factory = re.search(r"\[factory\].*?priority=(\d+)", text, re.DOTALL)
                self.assertIsNotNone(stages, f"no [stages] priority in {path.name}")
                self.assertIsNotNone(factory, f"no [factory] priority in {path.name}")
                self.assertEqual(int(stages.group(1)), found["stages"])
                self.assertEqual(int(factory.group(1)), found["factory"])


class BestTests(unittest.TestCase):
    def test_the_mock_root_resolves_like_the_container_lane(self) -> None:
        # best=1 refused Hummingbird's superseded-but-consistent sets
        # (python3-gpg only at gpgme 2.0.1-3.1); the container lane never
        # asked for best.
        rendered = render()
        self.assertIn("\nbest=0\n", rendered)
        self.assertNotIn("\nbest=1\n", rendered)


class CommandLineTests(unittest.TestCase):
    """The command line hermetic_build.sh and build-stage.yml shell out to.

    Both callers always pass every list flag, often as an empty string, so the
    script must turn "" into no names at all rather than into an empty
    excludepkgs entry, and must write exactly what render() would.
    """

    SCRIPT = ROOT / "tools" / "mock_config.py"

    def run_cli(self, *args: str) -> tuple[Path, dict]:
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        tmp = Path(workdir.name)
        # A parent that does not exist yet: the callers never create it.
        output = tmp / "nested" / "mock.cfg"
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT), "--output", str(output), *args],
            capture_output=True,
            text=True,
            cwd=tmp,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return output, json.loads(result.stdout)

    def test_the_hermetic_invocation_with_empty_lists_renders_the_default_root(self) -> None:
        output, summary = self.run_cli(
            "--factory-repo", "",
            "--stages-dir", "",
            "--prior-built", "",
            "--bootstrap-image", "quay.example/buildroot@sha256:abc",
            "--hummingbird-exclude", "",
        )
        config = output.read_text()
        self.assertEqual(
            config, render(bootstrap_image="quay.example/buildroot@sha256:abc")
        )
        for line in config.splitlines():
            if line.startswith("excludepkgs="):
                self.assertNotIn(",,", line)
                self.assertFalse(line.endswith(","), line)
        self.assertEqual(
            summary,
            {
                "config": str(output),
                "factory_repo": False,
                "prior_built": 0,
                "root": "utah-hummingbird-x86_64",
                "stages": False,
            },
        )

    def test_comma_lists_reach_the_config_without_empty_names(self) -> None:
        output, summary = self.run_cli(
            "--factory-repo", "https://example.invalid/repo/",
            "--stages-dir", "/work/prior",
            "--prior-built", "accountsservice,,accountsservice-libs,",
            "--hummingbird-exclude", "libicu-77.*-*hum1,libicu-devel-77.*-*hum1",
            "--root-name", "utah-test",
        )
        self.assertEqual(
            output.read_text(),
            render(
                root_name="utah-test",
                factory_repo="https://example.invalid/repo/",
                stages_dir="/work/prior",
                prior_built=("accountsservice", "accountsservice-libs"),
                hummingbird_extra_excludes=(
                    "libicu-77.*-*hum1",
                    "libicu-devel-77.*-*hum1",
                ),
            ),
        )
        self.assertEqual(summary["prior_built"], 2)
        self.assertTrue(summary["factory_repo"])
        self.assertTrue(summary["stages"])
        self.assertEqual(summary["root"], "utah-test")

    def test_the_output_flag_is_required(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--output", result.stderr)


if __name__ == "__main__":
    unittest.main()
