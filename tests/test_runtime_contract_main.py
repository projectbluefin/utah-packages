#!/usr/bin/env python3
"""Executed coverage for ``tools/runtime_contract.py`` main().

``tests/test_runtime_contract.py`` drives the pure functions ``resolve`` and
``base_image``. The command-line surface around them had no executed coverage at
all, yet ``.github/workflows/rebuild-rpms.yml`` shells out to it three times:

* line 98 gates the whole rebuild on ``--check`` before any wave starts;
* line 740 captures the default output into ``$CONTRACT``;
* line 742 captures ``--base-image`` into ``$BASE_IMAGE``, which is then the
  image argument to ``docker run``.

The last two live in the publish job's "Validate Hummingbird-only consumer
transaction" step, which ``tools/publish_gate.py`` requires to run before the
consumer OCI tag may move. A silent change to which stream a mode prints on, or
to an exit status, would therefore either move a bad digest or hand ``docker
run`` something that is not an image reference.

Each case calls ``main()`` in-process with a patched ``sys.argv`` so the assertion
lands on the real statements rather than on a subprocess the coverage report
cannot see. Output is captured per stream, because the distinction between
stdout and stderr is load-bearing: the workflow assigns stdout to a shell
variable.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import runtime_contract

ROOT = Path(__file__).resolve().parent.parent

DIGEST = "sha256:" + "0" * 64
IMAGE = f"quay.io/example/base@{DIGEST}"
BASE_POLICY = f'[base]\nimage = "{IMAGE}"\n'

BLUEFIN = (
    '[fedora]\npackages = ["one", "shared", "skip"]\n'
    '[multimedia]\npackages = ["codec", "shared"]\n'
)
POLICY = (
    BASE_POLICY
    + '[bluefin]\nsections = ["fedora", "multimedia"]\n'
    '[utah]\npackages = ["desktop", "shared"]\n'
    '[unavailable]\npackages = ["skip"]\n'
)
RESOLVED = ["one", "shared", "codec", "desktop"]


class RunResult:
    def __init__(self, status: int, stdout: str, stderr: str) -> None:
        self.status = status
        self.stdout = stdout
        self.stderr = stderr


class MainTestCase(unittest.TestCase):
    """Shared fixture: a factory tree written to a temporary directory."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content)
        return path

    def tree(self, bluefin: str = BLUEFIN, policy: str = POLICY) -> tuple[Path, Path]:
        return self.write("bluefin.toml", bluefin), self.write("policy.toml", policy)

    def run_main(self, *argv: str) -> RunResult:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(runtime_contract.sys, "argv", ["runtime_contract.py", *argv]):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = runtime_contract.main()
        return RunResult(status, out.getvalue(), err.getvalue())


class OutputModeTests(MainTestCase):
    def test_default_mode_prints_one_package_per_line(self) -> None:
        bluefin, policy = self.tree()
        result = self.run_main(str(bluefin), str(policy))
        self.assertEqual(result.status, 0)
        self.assertEqual(result.stdout.splitlines(), RESOLVED)
        self.assertEqual(result.stderr, "")

    def test_json_mode_prints_a_parseable_array_in_resolution_order(self) -> None:
        bluefin, policy = self.tree()
        result = self.run_main(str(bluefin), str(policy), "--json")
        self.assertEqual(result.status, 0)
        self.assertEqual(json.loads(result.stdout), RESOLVED)

    def test_check_mode_reports_the_count_and_the_pinned_image(self) -> None:
        bluefin, policy = self.tree()
        result = self.run_main(str(bluefin), str(policy), "--check")
        self.assertEqual(result.status, 0)
        self.assertEqual(
            result.stdout.strip(),
            f"validated runtime contract: {len(RESOLVED)} packages against {IMAGE}",
        )

    def test_base_image_mode_prints_the_digest_pinned_reference_alone(self) -> None:
        # rebuild-rpms.yml feeds this straight to `docker run "$BASE_IMAGE"`,
        # so nothing but the reference may appear on stdout.
        bluefin, policy = self.tree()
        result = self.run_main(str(bluefin), str(policy), "--base-image")
        self.assertEqual(result.status, 0)
        self.assertEqual(result.stdout.strip(), IMAGE)
        for name in RESOLVED:
            self.assertNotIn(name, result.stdout)

    def test_base_image_takes_precedence_over_the_other_modes(self) -> None:
        # The modes are not declared mutually exclusive, so the resolution order
        # of the if/elif chain is the contract a caller passing two flags gets.
        bluefin, policy = self.tree()
        result = self.run_main(
            str(bluefin), str(policy), "--base-image", "--check", "--json"
        )
        self.assertEqual(result.status, 0)
        self.assertEqual(result.stdout.strip(), IMAGE)

    def test_check_takes_precedence_over_json(self) -> None:
        bluefin, policy = self.tree()
        result = self.run_main(str(bluefin), str(policy), "--check", "--json")
        self.assertEqual(result.status, 0)
        self.assertIn("validated runtime contract", result.stdout)


class RefusalTests(MainTestCase):
    """Every path that must exit non-zero rather than emit a usable answer."""

    def assertRefused(self, result: RunResult, message: str) -> None:
        self.assertEqual(result.status, 1)
        self.assertEqual(result.stdout, "", "a refusal must not print to stdout")
        self.assertIn(message, result.stderr)
        self.assertTrue(result.stderr.startswith("ERROR: "))

    def test_a_missing_policy_file_is_refused_not_raised(self) -> None:
        bluefin, _ = self.tree()
        result = self.run_main(str(bluefin), str(self.root / "absent.toml"))
        self.assertRefused(result, "absent.toml")

    def test_a_missing_bluefin_manifest_is_refused_not_raised(self) -> None:
        _, policy = self.tree()
        result = self.run_main(str(self.root / "absent.toml"), str(policy))
        self.assertRefused(result, "absent.toml")

    def test_unparseable_toml_is_refused_not_raised(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write("policy.toml", "[base\nimage =")
        result = self.run_main(str(bluefin), str(policy))
        self.assertEqual(result.status, 1)
        self.assertTrue(result.stderr.startswith("ERROR: "))

    def test_a_mutable_base_image_never_reaches_docker_run(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write(
            "policy.toml",
            '[base]\nimage = "quay.io/example/base:latest"\n'
            '[bluefin]\nsections = ["fedora"]\n'
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy), "--base-image")
        self.assertRefused(result, "pinned by sha256 digest")

    def test_an_exception_for_a_package_nobody_requested_is_refused(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + '[bluefin]\nsections = ["fedora"]\n'
            "[utah]\npackages = []\n"
            '[unavailable]\npackages = ["ghost"]\n',
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "ghost")

    def test_a_section_the_bluefin_manifest_lacks_is_refused(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + '[bluefin]\nsections = ["missing"]\n'
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "no [missing] section")

    def test_an_empty_section_list_is_refused(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + "[bluefin]\nsections = []\n"
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "no Bluefin sections")

    def test_a_non_list_section_declaration_is_refused(self) -> None:
        bluefin, _ = self.tree()
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + '[bluefin]\nsections = "fedora"\n'
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "[bluefin].sections must be an array of strings")

    def test_a_package_list_of_non_strings_is_refused(self) -> None:
        bluefin = self.write("bluefin.toml", "[fedora]\npackages = [1, 2]\n")
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + '[bluefin]\nsections = ["fedora"]\n'
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "[fedora].packages must be an array of strings")

    def test_a_contract_resolving_to_nothing_is_refused(self) -> None:
        # An empty $CONTRACT would let the consumer transaction "resolve"
        # against a repository that satisfies nothing at all.
        bluefin = self.write("bluefin.toml", "[fedora]\npackages = []\n")
        policy = self.write(
            "policy.toml",
            BASE_POLICY
            + '[bluefin]\nsections = ["fedora"]\n'
            "[utah]\npackages = []\n[unavailable]\npackages = []\n",
        )
        result = self.run_main(str(bluefin), str(policy))
        self.assertRefused(result, "resolved to no packages")


class CommittedConfigurationTests(MainTestCase):
    """The exact invocations rebuild-rpms.yml makes against the real config."""

    BLUEFIN_CONFIG = ROOT / "config" / "bluefin-packages.toml"
    POLICY_CONFIG = ROOT / "config" / "runtime-contract.toml"

    def test_the_committed_contract_passes_the_check_the_rebuild_gates_on(self) -> None:
        result = self.run_main(
            str(self.BLUEFIN_CONFIG), str(self.POLICY_CONFIG), "--check"
        )
        self.assertEqual(result.status, 0, result.stderr)
        self.assertIn("validated runtime contract", result.stdout)

    def test_the_committed_base_image_is_digest_pinned(self) -> None:
        result = self.run_main(
            str(self.BLUEFIN_CONFIG), str(self.POLICY_CONFIG), "--base-image"
        )
        self.assertEqual(result.status, 0, result.stderr)
        self.assertIn("@sha256:", result.stdout.strip())
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_the_committed_contract_lists_every_package_once(self) -> None:
        result = self.run_main(str(self.BLUEFIN_CONFIG), str(self.POLICY_CONFIG))
        self.assertEqual(result.status, 0, result.stderr)
        packages = result.stdout.splitlines()
        self.assertEqual(sorted(packages), sorted(set(packages)))
        self.assertTrue(packages)


if __name__ == "__main__":
    unittest.main()
