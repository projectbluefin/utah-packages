#!/usr/bin/env python3
"""Coverage for tools/packit_workflow.py, the discovery helper behind
.github/workflows/packit-srpm-pilot.yml.

``package_chunks`` exists because GitHub caps a matrix at 256 jobs and a larger
matrix expands to no jobs at all without failing the run, so the cap is asserted
directly rather than inferred from a package count. ``main`` is driven through a
subprocess the way the workflow drives it, because what the workflow consumes is
stdout, not a return value.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.packit_workflow import (
    MATRIX_CHUNK,
    package_chunks,
    package_names,
    result,
)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "tools" / "packit_workflow.py"

CONFIG = (
    "actions:\n"
    "  create-archive:\n"
    "    - echo source.tar.xz\n"
    "packages:\n"
    "  alpha:\n"
    "    specfile_path: alpha.spec\n"
    "  beta-plus:\n"
    "    specfile_path: beta.spec\n"
)


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WORKFLOW), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class PackitWorkflowTests(unittest.TestCase):
    def test_lists_monorepo_packages_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".packit.yaml"
            config.write_text(
                "actions:\n"
                "  create-archive:\n"
                "    - echo source.tar.xz\n"
                "packages:\n"
                "  alpha:\n"
                "    specfile_path: alpha.spec\n"
                "  beta-plus:\n"
                "    specfile_path: beta.spec\n"
            )

            self.assertEqual(package_names(config), ["alpha", "beta-plus"])

    def test_emits_machine_readable_package_result(self) -> None:
        self.assertEqual(
            json.loads(result("demo", "success", "demo-1.0-1.fc44")),
            {
                "nevra": "demo-1.0-1.fc44",
                "package": "demo",
                "status": "success",
            },
        )


# GitHub's documented ceiling. Asserting against MATRIX_CHUNK alone would
# follow the constant wherever it moved, so the cap is anchored to the platform
# limit instead: raising MATRIX_CHUNK past this is the regression.
GITHUB_MATRIX_CAP = 256


class PackageChunkTests(unittest.TestCase):
    def test_the_default_chunk_size_stays_under_the_github_cap(self) -> None:
        self.assertLessEqual(MATRIX_CHUNK, GITHUB_MATRIX_CAP)

    def test_a_list_within_the_cap_is_one_chunk(self) -> None:
        names = [f"pkg{index}" for index in range(MATRIX_CHUNK)]

        chunks = package_chunks(names)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(json.loads(chunks[0]), names)

    def test_one_package_past_the_cap_splits_rather_than_overflowing(self) -> None:
        names = [f"pkg{index}" for index in range(MATRIX_CHUNK + 1)]

        chunks = package_chunks(names)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(json.loads(chunks[-1])), 1)

    def test_no_chunk_ever_exceeds_the_github_matrix_cap(self) -> None:
        # 345 packages is the size that silently produced zero jobs.
        names = [f"pkg{index}" for index in range(345)]

        for chunk in package_chunks(names):
            self.assertLessEqual(len(json.loads(chunk)), GITHUB_MATRIX_CAP)

    def test_chunking_loses_no_package_and_preserves_order(self) -> None:
        names = [f"pkg{index}" for index in range(345)]

        rejoined = [
            name for chunk in package_chunks(names) for name in json.loads(chunk)
        ]

        self.assertEqual(rejoined, names)

    def test_no_packages_yields_no_matrix_entries(self) -> None:
        # An empty chunk would be a job that builds nothing but still reports.
        self.assertEqual(package_chunks([]), [])

    def test_a_non_positive_chunk_size_is_rejected(self) -> None:
        for size in (0, -1):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    package_chunks(["alpha"], size)


class CommandLineTests(unittest.TestCase):
    """The workflow reads stdout, so every case asserts on stdout."""

    def _tree(self, directory: str) -> Path:
        root = Path(directory)
        (root / ".packit.yaml").write_text(CONFIG)
        return root

    def test_packages_prints_the_json_list_the_discover_step_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = run("packages", cwd=self._tree(directory))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), ["alpha", "beta-plus"])

    def test_packages_reads_an_explicit_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "other.yaml"
            config.write_text(CONFIG)

            completed = run("packages", "--config", str(config))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), ["alpha", "beta-plus"])

    def test_chunks_prints_a_matrix_of_json_encoded_package_lists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = run("chunks", cwd=self._tree(directory))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        matrix = json.loads(completed.stdout)
        # fromJson() feeds each entry to packit-srpm-chunk.yml as `packages`,
        # so each entry must itself parse as a package list.
        self.assertEqual(matrix, [json.dumps(["alpha", "beta-plus"])])
        self.assertEqual(json.loads(matrix[0]), ["alpha", "beta-plus"])

    def test_chunks_honours_an_explicit_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = run("chunks", "--size", "1", cwd=self._tree(directory))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            [json.loads(chunk) for chunk in json.loads(completed.stdout)],
            [["alpha"], ["beta-plus"]],
        )

    def test_result_prints_the_machine_readable_package_verdict(self) -> None:
        completed = run(
            "result",
            "--package",
            "demo",
            "--status",
            "failure",
            "--nevra",
            "demo-1.0-1.fc44",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {"nevra": "demo-1.0-1.fc44", "package": "demo", "status": "failure"},
        )

    def test_result_defaults_nevra_to_the_empty_string(self) -> None:
        completed = run("result", "--package", "demo", "--status", "success")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["nevra"], "")

    def test_an_unknown_status_is_refused(self) -> None:
        completed = run("result", "--package", "demo", "--status", "maybe")

        self.assertNotEqual(completed.returncode, 0)

    def test_a_missing_subcommand_is_refused(self) -> None:
        completed = run()

        self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
