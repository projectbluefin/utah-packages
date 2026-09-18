#!/usr/bin/env python3
"""Coverage for tools/rebuild_matrix.py, the driver of rebuild-rpms.yml.

rebuild_matrix.py is the half of the rebuild decision that talks to the outside
world: it reads the workflow environment, diffs against a base commit, fetches
the published repository listing and writes GITHUB_OUTPUT. The rules it feeds
live in tools/rebuild_plan.py and are tested there; what is tested here is the
plumbing, because every one of these paths decides whether a package gets built
at all and none of them was executed by the suite before.

Nothing here touches the network or a real git repository: subprocess, urlopen
and the module's ROOT are redirected at the module object, so each case runs the
real functions against a synthetic factory tree.
"""

from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import rebuild_matrix


def primary(*entries: tuple[str, str, str]) -> bytes:
    """Minimal repodata primary.xml carrying only what the plan reads."""
    body = "".join(
        f"<package><name>{name}</name>"
        f"<format><rpm:sourcerpm>{name}-{version}-{release}.src.rpm"
        f"</rpm:sourcerpm></format></package>"
        for name, version, release in entries
    )
    return f"<metadata>{body}</metadata>".encode()


def factory_tree(directory: str, packages: list[dict]) -> Path:
    """A repository root with an inventory and a directory per package.

    The packages carry no spec on purpose: `expected_release` then returns None
    and `is_published` falls back to matching the version alone, which keeps
    these cases about the driver rather than about spec parsing.
    """
    root = Path(directory)
    (root / "config").mkdir(parents=True)
    (root / "config" / "upstream-sources.json").write_text(
        json.dumps({"packages": packages})
    )
    for entry in packages:
        (root / "packages" / entry["name"]).mkdir(parents=True)
    return root


class ChangedRecipesTests(unittest.TestCase):
    def test_no_base_sha_reads_as_no_range_not_as_no_changes(self) -> None:
        # A scheduled run has neither `before` nor a pull request base. Shelling
        # out to `git diff ..HEAD` there would fail the job, so the empty range
        # has to short-circuit before subprocess is reached.
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(rebuild_matrix.changed_recipes(""), set())
        run.assert_not_called()

    def test_all_zero_base_sha_is_treated_as_absent(self) -> None:
        # GitHub sends 40 zeroes for `before` on a branch's first push. It is a
        # well-formed sha that names no commit.
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(rebuild_matrix.changed_recipes("0" * 40), set())
        run.assert_not_called()

    def test_short_or_non_hex_base_sha_is_rejected(self) -> None:
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(rebuild_matrix.changed_recipes("abc123"), set())
            self.assertEqual(rebuild_matrix.changed_recipes("z" * 40), set())
        run.assert_not_called()

    def test_package_names_come_from_the_path_not_the_file(self) -> None:
        diff = "packages/demo/demo.spec\npackages/other/sources\n"
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value=diff
        ):
            self.assertEqual(rebuild_matrix.changed_recipes("a" * 40), {"demo", "other"})

    def test_paths_outside_packages_are_ignored(self) -> None:
        diff = "README.md\ntools/rebuild_plan.py\n.github/workflows/rebuild-rpms.yml\n"
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value=diff
        ):
            self.assertEqual(rebuild_matrix.changed_recipes("a" * 40), set())

    def test_a_bare_packages_directory_entry_names_nothing(self) -> None:
        # `packages/demo` with no trailing component is a directory, not a file
        # inside a recipe, and must not be read as a changed recipe.
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value="packages/demo\n"
        ):
            self.assertEqual(rebuild_matrix.changed_recipes("a" * 40), set())

    def test_inventory_changes_are_unioned_with_recipe_changes(self) -> None:
        diff = f"packages/demo/demo.spec\n{rebuild_matrix.INVENTORY}\n"
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value=diff
        ), mock.patch.object(
            rebuild_matrix, "changed_inventory", return_value={"moved"}
        ):
            self.assertEqual(
                rebuild_matrix.changed_recipes("a" * 40), {"demo", "moved"}
            )


class ChangedInventoryTests(unittest.TestCase):
    def test_untouched_inventory_is_not_read_out_of_git(self) -> None:
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(
                rebuild_matrix.changed_inventory("a" * 40, ["packages/demo/demo.spec"]),
                set(),
            )
        run.assert_not_called()

    def test_an_entry_that_moved_stage_counts_as_changed(self) -> None:
        before = {"packages": [{"name": "demo", "version": "1.0", "stage": 0}]}
        after = {"packages": [{"name": "demo", "version": "1.0", "stage": 1}]}
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, after["packages"])
            with mock.patch.object(rebuild_matrix, "ROOT", root), mock.patch.object(
                rebuild_matrix.subprocess,
                "check_output",
                return_value=json.dumps(before),
            ):
                self.assertEqual(
                    rebuild_matrix.changed_inventory("a" * 40, [rebuild_matrix.INVENTORY]),
                    {"demo"},
                )

    def test_an_identical_entry_is_not_reported_as_changed(self) -> None:
        config = {"packages": [{"name": "demo", "version": "1.0", "stage": 0}]}
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, config["packages"])
            with mock.patch.object(rebuild_matrix, "ROOT", root), mock.patch.object(
                rebuild_matrix.subprocess,
                "check_output",
                return_value=json.dumps(config),
            ):
                self.assertEqual(
                    rebuild_matrix.changed_inventory("a" * 40, [rebuild_matrix.INVENTORY]),
                    set(),
                )

    def test_absent_inventory_at_the_base_proves_nothing_rather_than_everything(
        self,
    ) -> None:
        # The file did not exist at the base commit. Returning every name here
        # would force a full rebuild on the first run after the inventory was
        # introduced; the published comparison is left to decide instead.
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            with mock.patch.object(rebuild_matrix, "ROOT", root), mock.patch.object(
                rebuild_matrix.subprocess,
                "check_output",
                side_effect=subprocess.CalledProcessError(128, "git show"),
            ):
                self.assertEqual(
                    rebuild_matrix.changed_inventory("a" * 40, [rebuild_matrix.INVENTORY]),
                    set(),
                )

    def test_unparseable_inventory_at_the_base_proves_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            with mock.patch.object(rebuild_matrix, "ROOT", root), mock.patch.object(
                rebuild_matrix.subprocess, "check_output", return_value="not json"
            ):
                self.assertEqual(
                    rebuild_matrix.changed_inventory("a" * 40, [rebuild_matrix.INVENTORY]),
                    set(),
                )


class FetchPublishedTests(unittest.TestCase):
    def urlopen(self, responses: dict[str, bytes]):
        def opener(url, timeout=None):  # noqa: ANN001 - urlopen's own signature
            self.requested.append(url)
            return io.BytesIO(responses[url])

        self.requested: list[str] = []
        return opener

    def test_no_factory_repo_fetches_nothing(self) -> None:
        with mock.patch.object(rebuild_matrix.urllib.request, "urlopen") as urlopen:
            self.assertEqual(rebuild_matrix.fetch_published(""), {})
        urlopen.assert_not_called()

    def test_a_base_url_without_a_trailing_slash_is_still_joined_correctly(self) -> None:
        body = gzip.compress(primary(("demo", "1.0", "3.hum1.bfin")))
        responses = {
            "https://repo.example/x86_64/repodata/repomd.xml": (
                b'<repomd><data type="primary">'
                b'<location href="repodata/primary.xml.gz"/></data></repomd>'
            ),
            "https://repo.example/x86_64/repodata/primary.xml.gz": body,
        }
        with mock.patch.object(
            rebuild_matrix.urllib.request, "urlopen", self.urlopen(responses)
        ):
            published = rebuild_matrix.fetch_published("https://repo.example/x86_64")
        self.assertEqual(published, {"demo": ("1.0", "3.hum1.bfin")})
        self.assertEqual(
            self.requested,
            [
                "https://repo.example/x86_64/repodata/repomd.xml",
                "https://repo.example/x86_64/repodata/primary.xml.gz",
            ],
        )

    def test_a_zstd_primary_is_decompressed_through_zstandard(self) -> None:
        # createrepo_c emits .zst on current Fedora. The dependency is imported
        # lazily and is not installed in the test environment, so the branch is
        # proven by standing a recorder in for it: what matters is that the zst
        # path is taken and its output is what gets parsed.
        raw = b"compressed-bytes"
        responses = {
            "https://repo.example/repodata/repomd.xml": (
                b'<repomd><data type="primary">'
                b'<location href="repodata/primary.xml.zst"/></data></repomd>'
            ),
            "https://repo.example/repodata/primary.xml.zst": raw,
        }
        decompressed = primary(("demo", "2.0", "1.hum1.bfin"))

        class Reader:
            def read(self) -> bytes:
                return decompressed

        class Decompressor:
            def stream_reader(self, handle) -> Reader:  # noqa: ANN001
                assert handle.read() == raw
                return Reader()

        module = mock.Mock()
        module.ZstdDecompressor.return_value = Decompressor()
        with mock.patch.dict(sys.modules, {"zstandard": module}), mock.patch.object(
            rebuild_matrix.urllib.request, "urlopen", self.urlopen(responses)
        ):
            published = rebuild_matrix.fetch_published("https://repo.example/")
        self.assertEqual(published, {"demo": ("2.0", "1.hum1.bfin")})


class MainTests(unittest.TestCase):
    def run_main(self, root: Path, env: dict[str, str], **patches):
        output = root / "github-output"
        output.write_text("")
        environ = {"GITHUB_OUTPUT": str(output), **env}
        with mock.patch.object(rebuild_matrix, "ROOT", root), mock.patch.dict(
            rebuild_matrix.os.environ, environ, clear=True
        ), mock.patch.object(
            rebuild_matrix, "changed_recipes", return_value=patches.get("changed", set())
        ):
            if "fetch" in patches:
                with mock.patch.object(
                    rebuild_matrix, "fetch_published", **patches["fetch"]
                ):
                    status = rebuild_matrix.main()
            else:
                status = rebuild_matrix.main()
        return status, dict(
            line.split("=", 1) for line in output.read_text().splitlines() if line
        )

    def test_outputs_are_appended_as_github_output_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(
                directory,
                [{"name": "demo", "version": "1.0", "stage": 0}],
            )
            status, outputs = self.run_main(root, {"FULL": "1"})
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["demo"])
        self.assertEqual(json.loads(outputs["stage0"]), ["demo"])
        self.assertEqual(json.loads(outputs["stage1"]), [])
        self.assertEqual(
            [json.loads(chunk) for chunk in json.loads(outputs["stage0_chunks"])],
            [["demo"]],
        )

    def test_full_run_never_reads_the_published_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            with mock.patch.object(rebuild_matrix, "fetch_published") as fetch:
                status, outputs = self.run_main(
                    root, {"FULL": "1", "FACTORY_REPO": "https://repo.example/"}
                )
        fetch.assert_not_called()
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["demo"])

    def test_a_published_package_is_skipped_and_said_so(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(
                directory,
                [
                    {"name": "demo", "version": "1.0"},
                    {"name": "other", "version": "2.0"},
                ],
            )
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                status, outputs = self.run_main(
                    root,
                    {"FACTORY_REPO": "https://repo.example/"},
                    fetch={"return_value": {"demo": ("1.0", "3.hum1.bfin")}},
                )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["other"])
        self.assertIn("skip demo: already published", out.getvalue())

    def test_a_changed_recipe_is_rebuilt_even_when_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            status, outputs = self.run_main(
                root,
                {"FACTORY_REPO": "https://repo.example/"},
                changed={"demo"},
                fetch={"return_value": {"demo": ("1.0", "3.hum1.bfin")}},
            )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["demo"])

    def test_an_unreachable_published_repository_rebuilds_everything(self) -> None:
        # Availability, not correctness: a 503 from the mirror must not skip a
        # package, and must not fail the run either.
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                status, outputs = self.run_main(
                    root,
                    {"FACTORY_REPO": "https://repo.example/"},
                    fetch={"side_effect": OSError("503")},
                )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["demo"])
        self.assertIn("could not read published repo", err.getvalue())

    def test_no_factory_repository_warns_and_skips_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, [{"name": "demo", "version": "1.0"}])
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                status, outputs = self.run_main(
                    root, {}, fetch={"return_value": {"demo": ("1.0", "3.hum1.bfin")}}
                )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(outputs["build_list"]), ["demo"])
        self.assertIn("no factory repository", err.getvalue())

    def test_a_stage_that_splits_into_chunks_reports_the_split(self) -> None:
        # A stage over the 250-package chunk limit fans out into several matrix
        # jobs. The log line is the only place that is visible before the jobs
        # start, so a silent split is a split nobody can review.
        packages = [
            {"name": f"pkg{index:03d}", "version": "1.0", "stage": 0}
            for index in range(251)
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(directory, packages)
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                status, outputs = self.run_main(root, {"FULL": "1"})
        self.assertEqual(status, 0)
        self.assertEqual(len(json.loads(outputs["stage0_chunks"])), 2)
        self.assertIn("stage 0: 251 packages in 2 chunks", out.getvalue())

    def test_a_stage_with_no_job_stops_the_run_instead_of_dropping_packages(
        self,
    ) -> None:
        # A recipe at stage 11 or beyond falls out of every stage list while
        # staying in build_list, which used to publish a repository quietly
        # missing it.
        with tempfile.TemporaryDirectory() as directory:
            root = factory_tree(
                directory, [{"name": "late", "version": "1.0", "stage": 11}]
            )
            with self.assertRaises(SystemExit) as raised:
                self.run_main(root, {"FULL": "1"})
        self.assertIn("late", str(raised.exception))
        self.assertIn("stage 11", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
