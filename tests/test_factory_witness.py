#!/usr/bin/env python3
"""The published factory image is the only witness for what may be skipped.

prepare decides what is already built by reading a repository listing, and
every build root installs from that same repository. Both used to read a URL
-- a GitHub Pages mirror that had been retired but never taken down, frozen at
67 packages -- so every run skipped 7 recipes and rebuilt 333, and webkitgtk
sat on the serial path for five hours with no change to its recipe. The image
publish writes is the only thing that moves, so it is the only thing either
half may read. These tests hold that shape.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
REBUILD = WORKFLOWS / "rebuild-rpms.yml"
BUILD_STAGE = WORKFLOWS / "build-stage.yml"
LOAD_ACTION = ROOT / ".github" / "actions" / "load-factory-repo" / "action.yml"


def uncommented(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.strip().startswith("#")
    )


class FactoryWitnessTests(unittest.TestCase):
    def test_no_workflow_reads_the_retired_pages_mirror(self) -> None:
        offenders = [
            path.name
            for path in sorted(WORKFLOWS.glob("*.yml"))
            if "projectbluefin.github.io" in uncommented(path)
        ]
        self.assertEqual(offenders, [], "the Pages mirror is retired and stale")

    def test_no_repository_variable_can_split_the_witness(self) -> None:
        # vars.FACTORY_REPO was how the two halves first came to disagree.
        for path in (REBUILD, BUILD_STAGE):
            self.assertNotIn("vars.FACTORY_REPO", uncommented(path), path.name)

    def test_prepare_resolves_the_image_and_reads_it_for_the_plan(self) -> None:
        text = uncommented(REBUILD)
        self.assertIn("factory_image: ${{ steps.factory_image.outputs.image }}", text)
        self.assertIn("./.github/actions/load-factory-repo", text)
        self.assertIn('export FACTORY_REPO="file://$PWD/work/factory"', text)

    def test_every_build_wave_is_handed_the_same_image(self) -> None:
        text = uncommented(REBUILD)
        waves = re.findall(r"(?m)^  rebuild\d+:$", text)
        self.assertEqual(len(waves), 11)
        self.assertEqual(
            text.count("factory_image: ${{ needs.prepare.outputs.factory_image }}"),
            len(waves),
        )

    def test_the_build_root_installs_from_the_extracted_repository(self) -> None:
        text = uncommented(BUILD_STAGE)
        self.assertIn("./.github/actions/load-factory-repo", text)
        self.assertEqual(text.count("FACTORY_REPO: ${{ steps.factory.outputs.url }}"), 2)
        # The container mounts $PWD/work at /work, so that is the only path
        # the repository can be enabled under.
        self.assertIn("url=file:///$TARGET", LOAD_ACTION.read_text())

    def test_the_load_action_asserts_the_repository_arrived(self) -> None:
        self.assertIn('test -f "$TARGET/repodata/repomd.xml"', LOAD_ACTION.read_text())

    def test_debuginfo_is_not_built_only_to_be_discarded(self) -> None:
        text = uncommented(BUILD_STAGE)
        self.assertIn("!work/result/**/*-debuginfo-*.rpm", text)
        self.assertEqual(text.count('--define "debug_package %{nil}"'), 2)
        # debug_package alone is not enough: %mingw_debug_package sets
        # __debug_package itself, which runs the native find-debuginfo and
        # leaves .debug files no subpackage declares (run 380, ten specs).
        self.assertEqual(text.count('--define "__debug_install_post %{nil}"'), 2)

    def test_publish_seeds_from_the_image_prepare_witnessed(self) -> None:
        """The seed and the skip witness have to be the same image.

        prepare resolves the branch tag first and falls back to latest. While
        publish seeded from a hardcoded latest, a second push to a pull request
        dropped every package that had been skipped because the *branch* tag
        carried it: absent from the seed and absent from this run's artifacts,
        so absent from the republished image. Two sources of truth for "what is
        already built" is the bug this workflow exists to have removed.
        """
        text = uncommented(REBUILD)
        self.assertIn('image="${{ needs.prepare.outputs.factory_image }}"', text)
        self.assertNotIn('utah-packages:latest"', text)

    def test_a_failed_prepare_stops_precedence_and_publish(self) -> None:
        text = uncommented(REBUILD)
        self.assertEqual(text.count("needs.prepare.result == 'success'"), 2)


if __name__ == "__main__":
    unittest.main()


class IcuAgreementTests(unittest.TestCase):
    """The build root must keep the ICU 77 provider the consumer side refuses.

    Hummingbird ships libicu 77.1 beside 78.3 under one package name, so dnf
    installs exactly one, and Hummingbird itself has migrated to 78: every
    current build links libicuuc.so.78 and only superseded ones link .so.77.
    From that it looks as though excluding libicu 77 from the Hummingbird
    repository in the build root could not strand anything, and these tests
    asserted exactly that for one revision.

    It is wrong, and the way it is wrong is the point. The build root is not
    only Hummingbird: it carries Fedora binaries Hummingbird never rebuilt, and
    libical-3.0.20-7.fc44 requires libicuuc.so.77 outright. Fedora libicu is
    already excluded from the root so Hummingbird wins the name, which leaves
    Hummingbird superseded libicu-77 as the last provider of .so.77. Excluding
    it too left none, and bluez stopped resolving at stage 0 of run
    35443117478 -- a worse failure than the publish-gate one it was meant to
    fix, because it loses every build rather than one gate.

    So the two halves are deliberately asymmetric, and that asymmetry is what
    is pinned here: the consumer transaction excludes ICU 77 because nothing it
    installs may link it; the build root does not, because Fedora build deps
    legitimately do.
    """

    SPELLING = "libicu-77.*-*hum1"

    def test_the_consumer_transaction_still_excludes_icu_77(self):
        self.assertIn(self.SPELLING, uncommented(REBUILD),
                      "the consumer transaction must exclude libicu 77")

    def test_the_build_root_does_not_exclude_the_last_provider_of_so_77(self):
        text = uncommented(BUILD_STAGE)
        hb_line = next(line for line in text.splitlines()
                       if line.strip().startswith("HB_REPO_EXCLUDE="))
        self.assertNotIn("libicu", hb_line,
                         "excluding libicu from the build root strands Fedora "
                         "packages that require libicuuc.so.77 (bluez, run "
                         "35443117478)")

    def test_the_mock_root_agrees_with_the_container_root(self):
        # The two build roots encode one policy; test_mock_config.py asserts
        # that in general, and this pins the specific decision so a future
        # change has to make it in both places or fail here.
        import tools.mock_config as mock_config
        self.assertNotIn(
            self.SPELLING, mock_config.HUMMINGBIRD_REPO_EXCLUDE,
            "the mock root must not exclude libicu 77 either")

    def test_the_spelling_keeps_release_as_its_own_field(self):
        # Where ICU 77 *is* excluded, the spelling still matters: dnf splits a
        # package spec on dashes before globbing each field, so libicu-77.*hum1
        # parses 77.*hum1 as the version and matches nothing.
        text = uncommented(REBUILD)
        self.assertNotIn("libicu-77.*hum1", text.replace(self.SPELLING, ""))

    def test_fedora_icu_77_is_not_excluded_either(self):
        # 012cb6a reverted a blanket exclusion for the same underlying reason.
        for line in uncommented(BUILD_STAGE).splitlines():
            if "fedora.excludepkgs" in line:
                self.assertNotIn("libicu-77", line)
