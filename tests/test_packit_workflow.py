#!/usr/bin/env python3

import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock

from tools.packit_workflow import (
    MATRIX_CHUNK,
    main,
    package_chunks,
    package_names,
    result,
)

# GitHub expands a matrix of more than 256 jobs to no jobs at all, without
# failing. MATRIX_CHUNK exists only to stay under that number, so the number
# is restated here: a chunk size raised past it is the regression this file
# is meant to catch.
GITHUB_MATRIX_CAP = 256


def write_config(directory: str, names: list[str]) -> Path:
    config = Path(directory) / ".packit.yaml"
    config.write_text(
        "actions:\n"
        "  create-archive:\n"
        "    - echo source.tar.xz\n"
        "packages:\n"
        + "".join(f"  {name}:\n    specfile_path: {name}.spec\n" for name in names)
    )
    return config


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Drive main() exactly as the workflow drives it, capturing stdout."""
    stdout = io.StringIO()
    with mock.patch.object(sys, "argv", ["packit_workflow.py", *argv]):
        with contextlib.redirect_stdout(stdout):
            code = main()
    return code, stdout.getvalue()


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


class PackageChunkTests(unittest.TestCase):
    def test_default_chunk_size_stays_under_the_github_matrix_cap(self) -> None:
        self.assertLessEqual(MATRIX_CHUNK, GITHUB_MATRIX_CAP)

    def test_a_list_below_the_cap_is_one_chunk(self) -> None:
        names = [f"pkg-{index}" for index in range(MATRIX_CHUNK)]

        chunks = package_chunks(names)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(json.loads(chunks[0]), names)

    def test_a_list_above_the_cap_is_split_and_no_chunk_exceeds_it(self) -> None:
        names = [f"pkg-{index}" for index in range(MATRIX_CHUNK + 95)]

        chunks = package_chunks(names)

        self.assertEqual(len(chunks), 2)
        for chunk in chunks:
            decoded = json.loads(chunk)
            self.assertLessEqual(len(decoded), MATRIX_CHUNK)
            self.assertLessEqual(len(decoded), GITHUB_MATRIX_CAP)

    def test_chunking_is_lossless_and_order_preserving(self) -> None:
        names = [f"pkg-{index}" for index in range(7)]

        rejoined: list[str] = []
        for chunk in package_chunks(names, size=2):
            rejoined.extend(json.loads(chunk))

        self.assertEqual(rejoined, names)

    def test_an_empty_package_list_yields_an_empty_matrix(self) -> None:
        # Not a single chunk holding nothing: that would be one job that
        # builds no package while the run stays green.
        self.assertEqual(package_chunks([]), [])

    def test_a_non_positive_chunk_size_is_refused(self) -> None:
        for size in (0, -1):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    package_chunks(["alpha"], size=size)

    def test_each_chunk_is_json_the_workflow_can_pass_through_fromjson(self) -> None:
        chunks = package_chunks(["alpha", "beta"], size=1)

        for chunk in chunks:
            decoded = json.loads(chunk)
            self.assertIsInstance(decoded, list)
            self.assertTrue(all(isinstance(name, str) for name in decoded))


class PackitWorkflowCliTests(unittest.TestCase):
    def test_packages_prints_the_json_list_the_discover_step_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = write_config(directory, ["alpha", "beta-plus"])

            code, output = run_cli(["packages", "--config", str(config)])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), ["alpha", "beta-plus"])

    def test_chunks_prints_the_json_list_of_chunks_fromjson_consumes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = write_config(directory, ["alpha", "beta", "gamma"])

            code, output = run_cli(
                ["chunks", "--config", str(config), "--size", "2"]
            )

        self.assertEqual(code, 0)
        chunks = json.loads(output)
        self.assertEqual(
            [json.loads(chunk) for chunk in chunks],
            [["alpha", "beta"], ["gamma"]],
        )

    def test_chunks_defaults_to_the_capped_chunk_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = write_config(
                directory, [f"pkg{index}" for index in range(MATRIX_CHUNK + 1)]
            )

            code, output = run_cli(["chunks", "--config", str(config)])

        self.assertEqual(code, 0)
        chunks = json.loads(output)
        self.assertEqual([len(json.loads(chunk)) for chunk in chunks], [MATRIX_CHUNK, 1])

    def test_result_prints_the_package_record_the_chunk_workflow_collects(self) -> None:
        code, output = run_cli(
            [
                "result",
                "--package",
                "demo",
                "--status",
                "success",
                "--nevra",
                "demo-1.0-1.fc44",
            ]
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output),
            {"nevra": "demo-1.0-1.fc44", "package": "demo", "status": "success"},
        )

    def test_result_nevra_defaults_to_empty_for_a_failed_package(self) -> None:
        code, output = run_cli(
            ["result", "--package", "demo", "--status", "failure"]
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(output),
            {"nevra": "", "package": "demo", "status": "failure"},
        )

    def test_a_status_outside_the_accepted_set_exits_non_zero(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stderr(io.StringIO()):
                run_cli(["result", "--package", "demo", "--status", "maybe"])

        self.assertNotEqual(raised.exception.code, 0)

    def test_a_missing_subcommand_exits_non_zero(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stderr(io.StringIO()):
                run_cli([])

        self.assertNotEqual(raised.exception.code, 0)

    def test_the_script_entrypoint_propagates_the_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = write_config(directory, ["alpha"])
            argv = ["packit_workflow.py", "packages", "--config", str(config)]

            with mock.patch.object(sys, "argv", argv):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    with self.assertRaises(SystemExit) as raised:
                        runpy.run_path(
                            "tools/packit_workflow.py", run_name="__main__"
                        )

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(json.loads(stdout.getvalue()), ["alpha"])


if __name__ == "__main__":
    unittest.main()
