#!/usr/bin/env python3
"""Executed coverage for tools/rebuild_matrix.py.

The module is the driver .github/workflows/rebuild-rpms.yml runs to decide
which packages a rebuild builds. Every case here redirects `subprocess`,
`urllib.request.urlopen` and the module's `ROOT` at the module object, so no
case touches the network or a real git repository.
"""

import gzip
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from tools import rebuild_matrix


HAS_ZSTANDARD = importlib.util.find_spec("zstandard") is not None


ZERO_SHA = "0" * 40
SHA = "a" * 40


COMMON_NS = "http://linux.duke.edu/metadata/common"
RPM_NS = "http://linux.duke.edu/metadata/rpm"
METADATA_OPEN = f'<metadata xmlns="{COMMON_NS}" xmlns:rpm="{RPM_NS}">'


def primary(*entries: tuple[str, str, str]) -> bytes:
    """Minimal repodata primary.xml carrying only what the plan reads.

    Namespaced as real repodata is: published_from_primary reads it with a
    regex, but dependents_from_primary and stale_from_primary parse it as XML
    and see nothing without the declarations.
    """
    return package_primary(
        *((name, version, release, (), ()) for name, version, release in entries)
    )


def package_primary(*entries: tuple[str, str, str, tuple, tuple]) -> bytes:
    """primary.xml where each binary also declares Provides and Requires."""
    body = ""
    for name, version, release, provides, requires in entries:
        provided = "".join(f'<rpm:entry name="{cap}"/>' for cap in provides)
        needed = "".join(f'<rpm:entry name="{cap}"/>' for cap in requires)
        body += (
            f"<package><name>{name}-libs</name>"
            f"<format><rpm:sourcerpm>{name}-{version}-{release}.src.rpm</rpm:sourcerpm>"
            f"<rpm:provides>{provided}</rpm:provides>"
            f"<rpm:requires>{needed}</rpm:requires>"
            "</format></package>"
        )
    return f"{METADATA_OPEN}{body}</metadata>".encode()


def write_root(root: Path, packages: list[dict], *, specs: set[str] | None = None) -> Path:
    """An inventory, a hummingbird.repo and optional recipes under `root`."""
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "upstream-sources.json").write_text(
        json.dumps({"schema": 1, "packages": packages})
    )
    (root / "config" / "hummingbird.repo").write_text(
        "[hummingbird]\nbaseurl=https://example.invalid/hummingbird/\n"
    )
    (root / "config" / "hummingbird-provided-sources.json").write_text(
        json.dumps({"schema": 1, "sources": []})
    )
    for entry in packages:
        name = entry["name"]
        package_dir = root / "packages" / name
        package_dir.mkdir(parents=True, exist_ok=True)
        if specs is not None and name not in specs:
            continue
        (package_dir / f"{name}.spec").write_text(
            f"Name:           {name}\n"
            f"Version:        {entry.get('version', '1.0')}\n"
            "Release:        1%{?dist}\n"
        )
    return root


class ChangedRecipesTest(unittest.TestCase):
    """changed_recipes: the git-diff half, and its refusal to guess."""

    def test_absent_base_sha_reads_no_range(self):
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(rebuild_matrix.changed_recipes(""), set())
        run.assert_not_called()

    def test_all_zero_base_sha_reads_no_range(self):
        # The `before` of a branch's first push is forty zeroes, which is a
        # well-formed sha that names nothing.
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(rebuild_matrix.changed_recipes(ZERO_SHA), set())
        run.assert_not_called()

    def test_malformed_base_sha_reads_no_range(self):
        for value in ("HEAD", "abc123", "z" * 40, SHA + "a"):
            with self.subTest(value=value):
                with mock.patch.object(
                    rebuild_matrix.subprocess, "check_output"
                ) as run:
                    self.assertEqual(rebuild_matrix.changed_recipes(value), set())
                run.assert_not_called()

    def test_recipe_paths_become_package_names(self):
        paths = (
            "packages/mozc/mozc.spec\n"
            "packages/mozc/sources\n"
            "packages/gnome-shell/gnome-shell.spec\n"
            "docs/skills/package-build-cache.md\n"
            "packages\n"
        )
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value=paths
        ) as run:
            self.assertEqual(
                rebuild_matrix.changed_recipes(SHA), {"mozc", "gnome-shell"}
            )
        run.assert_called_once_with(
            ["git", "diff", "--name-only", f"{SHA}..HEAD"], text=True
        )

    def test_inventory_change_joins_the_recipe_change(self):
        paths = f"packages/mozc/mozc.spec\n{rebuild_matrix.INVENTORY}\n"
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value=paths
        ), mock.patch.object(
            rebuild_matrix, "changed_inventory", return_value={"gnome-shell"}
        ):
            self.assertEqual(
                rebuild_matrix.changed_recipes(SHA), {"mozc", "gnome-shell"}
            )


class ChangedInventoryTest(unittest.TestCase):
    """changed_inventory: reads the old config out of git, never the diff text."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.object(rebuild_matrix, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_after(self, packages: list[dict]) -> None:
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / rebuild_matrix.INVENTORY).write_text(
            json.dumps({"packages": packages})
        )

    def test_untouched_inventory_reads_nothing(self):
        with mock.patch.object(rebuild_matrix.subprocess, "check_output") as run:
            self.assertEqual(
                rebuild_matrix.changed_inventory(SHA, ["packages/mozc/mozc.spec"]),
                set(),
            )
        run.assert_not_called()

    def test_absent_inventory_at_base_proves_nothing(self):
        # Not "everything changed" -- the published comparison must decide.
        self.write_after([{"name": "mozc", "version": "2.0"}])
        with mock.patch.object(
            rebuild_matrix.subprocess,
            "check_output",
            side_effect=subprocess.CalledProcessError(128, "git show"),
        ):
            self.assertEqual(
                rebuild_matrix.changed_inventory(SHA, [rebuild_matrix.INVENTORY]),
                set(),
            )

    def test_unparseable_inventory_at_base_proves_nothing(self):
        self.write_after([{"name": "mozc", "version": "2.0"}])
        with mock.patch.object(
            rebuild_matrix.subprocess, "check_output", return_value="{not json"
        ):
            self.assertEqual(
                rebuild_matrix.changed_inventory(SHA, [rebuild_matrix.INVENTORY]),
                set(),
            )

    def test_reports_only_the_entries_that_moved(self):
        before = {
            "packages": [
                {"name": "mozc", "version": "1.0", "stage": 0},
                {"name": "gnome-shell", "version": "51", "stage": 9},
            ]
        }
        # gnome-shell moves stage only: invisible in the published NEVR, and
        # exactly the change this function exists to catch.
        self.write_after(
            [
                {"name": "mozc", "version": "1.0", "stage": 0},
                {"name": "gnome-shell", "version": "51", "stage": 10},
            ]
        )
        with mock.patch.object(
            rebuild_matrix.subprocess,
            "check_output",
            return_value=json.dumps(before),
        ) as run:
            self.assertEqual(
                rebuild_matrix.changed_inventory(SHA, [rebuild_matrix.INVENTORY]),
                {"gnome-shell"},
            )
        run.assert_called_once_with(
            ["git", "show", f"{SHA}:{rebuild_matrix.INVENTORY}"], text=True
        )


class FetchPrimaryTest(unittest.TestCase):
    """fetch_primary: repomd indirection and decompression."""

    def test_absent_base_url_fetches_nothing(self):
        with mock.patch.object(rebuild_matrix.urllib.request, "urlopen") as urlopen:
            self.assertEqual(rebuild_matrix.fetch_primary(""), b"")
        urlopen.assert_not_called()

    def _serve(self, href: str, payload: bytes):
        repomd = f'<repomd><data><location href="{href}"/></data></repomd>'.encode()

        def urlopen(url, timeout=None):
            body = repomd if url.endswith("repodata/repomd.xml") else payload
            return io.BytesIO(body)

        return urlopen

    def test_gzip_primary_is_decompressed_and_url_gains_a_slash(self):
        raw = gzip.compress(primary(("mozc", "2.0", "1.hum42.bfin")))
        seen: list[str] = []

        def urlopen(url, timeout=None):
            seen.append(url)
            return self._serve("repodata/abc-primary.xml.gz", raw)(url, timeout)

        with mock.patch.object(
            rebuild_matrix.urllib.request, "urlopen", side_effect=urlopen
        ):
            # No trailing slash: the function has to add one or every path
            # below resolves against the parent directory.
            result = rebuild_matrix.fetch_primary("file:///repo")
        self.assertIn(b"mozc-2.0-1.hum42.bfin.src.rpm", result)
        self.assertEqual(
            seen,
            ["file:///repo/repodata/repomd.xml", "file:///repo/repodata/abc-primary.xml.gz"],
        )

    def test_trailing_slash_is_not_doubled(self):
        raw = gzip.compress(primary(("mozc", "2.0", "1.hum42.bfin")))
        seen: list[str] = []

        def urlopen(url, timeout=None):
            seen.append(url)
            return self._serve("repodata/abc-primary.xml.gz", raw)(url, timeout)

        with mock.patch.object(
            rebuild_matrix.urllib.request, "urlopen", side_effect=urlopen
        ):
            rebuild_matrix.fetch_primary("file:///repo/")
        self.assertEqual(seen[0], "file:///repo/repodata/repomd.xml")

    @unittest.skipUnless(HAS_ZSTANDARD, "zstandard is not installed")
    def test_zstd_primary_is_decompressed(self):
        import zstandard

        raw = zstandard.ZstdCompressor().compress(
            primary(("mozc", "2.0", "1.hum42.bfin"))
        )
        with mock.patch.object(
            rebuild_matrix.urllib.request,
            "urlopen",
            side_effect=self._serve("repodata/abc-primary.xml.zst", raw),
        ):
            result = rebuild_matrix.fetch_primary("file:///repo/")
        self.assertIn(b"mozc-2.0-1.hum42.bfin.src.rpm", result)


class HummingbirdBaseurlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo_file = Path(self.tmp.name) / "hummingbird.repo"

    def test_baseurl_is_returned_with_exactly_one_trailing_slash(self):
        for written in (
            "https://example.invalid/hb",
            "https://example.invalid/hb/",
            "https://example.invalid/hb///",
        ):
            with self.subTest(written=written):
                self.repo_file.write_text(f"[hummingbird]\nbaseurl={written}\nenabled=1\n")
                self.assertEqual(
                    rebuild_matrix.hummingbird_baseurl(self.repo_file),
                    "https://example.invalid/hb/",
                )

    def test_missing_baseurl_is_refused_rather_than_guessed(self):
        self.repo_file.write_text("[hummingbird]\nenabled=1\n")
        with self.assertRaises(ValueError) as caught:
            rebuild_matrix.hummingbird_baseurl(self.repo_file)
        self.assertIn("no baseurl", str(caught.exception))


class FetchPublishedTest(unittest.TestCase):
    def test_published_is_keyed_by_source_name(self):
        with mock.patch.object(
            rebuild_matrix,
            "fetch_primary",
            return_value=primary(("mozc", "2.0", "1.hum42.bfin")),
        ):
            self.assertEqual(
                rebuild_matrix.fetch_published("file:///repo/"),
                {"mozc": ("2.0", "1.hum42.bfin")},
            )

    def test_unreadable_repository_yields_nothing_published(self):
        with mock.patch.object(rebuild_matrix, "fetch_primary", return_value=b""):
            self.assertEqual(rebuild_matrix.fetch_published(""), {})


class MainTest(unittest.TestCase):
    """main(): the env it reads, the warnings it prints, the outputs it writes."""

    PACKAGES = [
        {"name": "mozc", "version": "2.0", "stage": 0},
        {"name": "gnome-shell", "version": "51", "stage": 9},
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "github_output"
        self.output.write_text("")

    def run_main(self, packages=None, *, specs=None, env=None, fetch=None, changed=None):
        """Run main() against a fixture root, returning (rc, stdout, outputs)."""
        write_root(self.root, packages or self.PACKAGES, specs=specs)
        environ = {"GITHUB_OUTPUT": str(self.output)}
        environ.update(env or {})
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(rebuild_matrix, "ROOT", self.root), mock.patch.dict(
            os.environ, environ, clear=True
        ), mock.patch.object(
            rebuild_matrix, "changed_recipes", return_value=set(changed or ())
        ) as changed_call, mock.patch.object(
            rebuild_matrix,
            "fetch_primary",
            side_effect=fetch if fetch is not None else [b"", b""],
        ):
            with redirect_stdout(out), redirect_stderr(err):
                code = rebuild_matrix.main()
        outputs = dict(
            line.split("=", 1)
            for line in self.output.read_text().splitlines()
            if "=" in line
        )
        self.changed_call = changed_call
        self.stderr = err.getvalue()
        return code, out.getvalue(), outputs

    def test_full_run_reads_repo_for_pruning_but_rebuilds_all(self):
        with mock.patch.object(rebuild_matrix, "fetch_primary", return_value=b"") as fetch:
            write_root(self.root, self.PACKAGES)
            with mock.patch.object(
                rebuild_matrix, "ROOT", self.root
            ), mock.patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": str(self.output),
                    "FULL": "1",
                    "FACTORY_REPO": "file:///repo/",
                },
                clear=True,
            ), mock.patch.object(
                rebuild_matrix, "changed_recipes", return_value=set()
            ):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = rebuild_matrix.main()
        fetch.assert_called_once_with("file:///repo/")
        self.assertEqual(code, 0)
        outputs = dict(
            line.split("=", 1) for line in self.output.read_text().splitlines()
        )
        self.assertEqual(
            json.loads(outputs["build_list"]), ["mozc", "gnome-shell"]
        )

    def test_base_sha_is_read_from_the_environment(self):
        self.run_main(env={"BASE_SHA": SHA, "FACTORY_REPO": "file:///repo/"})
        self.changed_call.assert_called_once_with(SHA)

    def test_absent_factory_repo_forbids_skipping(self):
        code, out, outputs = self.run_main(env={})
        self.assertEqual(code, 0)
        self.assertIn("no factory repository for the build root", self.stderr)
        # Nothing may be skipped as published, so both packages build.
        self.assertEqual(json.loads(outputs["build_list"]), ["mozc", "gnome-shell"])

    def test_unreadable_published_repo_rebuilds_everything(self):
        code, out, outputs = self.run_main(
            env={"FACTORY_REPO": "file:///repo/"},
            fetch=OSError("mirror is gone"),
        )
        self.assertEqual(code, 0)
        self.assertIn("could not read published repo, rebuilding all", self.stderr)
        self.assertIn("mirror is gone", self.stderr)
        self.assertEqual(json.loads(outputs["build_list"]), ["mozc", "gnome-shell"])

    def test_published_recipe_is_skipped_and_named(self):
        published = primary(("mozc", "2.0", "1.hum42.bfin"))
        code, out, outputs = self.run_main(
            # No spec for either package: the release cannot be predicted, so
            # the version match alone decides, as it does for %autorelease.
            specs=set(),
            env={"FACTORY_REPO": "file:///repo/"},
            fetch=[published, f"{METADATA_OPEN}</metadata>".encode()],
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.stderr, "")
        self.assertIn("published repo has 1 source packages", out)
        self.assertIn("skip mozc: already published", out)
        self.assertEqual(json.loads(outputs["build_list"]), ["gnome-shell"])

    def test_unreadable_hummingbird_repo_is_survivable(self):
        published = primary(("mozc", "2.0", "1.hum42.bfin"))
        code, out, outputs = self.run_main(
            specs=set(),
            env={"FACTORY_REPO": "file:///repo/"},
            fetch=[published, OSError("hummingbird is gone")],
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "could not read the Hummingbird repository", self.stderr
        )
        # The judgement is not made, so the run trusts the recipe match alone.
        self.assertIn("skip mozc: already published", out)

    def test_a_stage_with_no_job_is_fatal(self):
        # Silently dropping these published a repository missing them.
        packages = [
            {"name": "mozc", "version": "2.0", "stage": 0},
            {"name": "late", "version": "1.0", "stage": 11},
        ]
        with self.assertRaises(SystemExit) as caught:
            self.run_main(packages, env={})
        self.assertIn("no job exists for stage 11 or later", str(caught.exception))
        self.assertIn("late", str(caught.exception))

    def test_outputs_carry_every_stage_and_the_cache_list(self):
        code, out, outputs = self.run_main(env={})
        self.assertEqual(code, 0)
        for stage in range(11):
            self.assertIn(f"stage{stage}", outputs)
            self.assertIn(f"stage{stage}_chunks", outputs)
        self.assertEqual(json.loads(outputs["stage0"]), ["mozc"])
        self.assertEqual(json.loads(outputs["stage9"]), ["gnome-shell"])
        self.assertEqual(
            json.loads(outputs["cacheable"]), ["mozc", "gnome-shell"]
        )
        self.assertIn("will build 2 of 2 packages", out)

    def test_outputs_are_appended_not_rewritten(self):
        # GITHUB_OUTPUT is shared with every other step in the job.
        self.output.write_text("earlier_step=kept\n")
        code, out, outputs = self.run_main(env={})
        self.assertEqual(code, 0)
        self.assertEqual(outputs["earlier_step"], "kept")

    def test_changed_recipes_are_excluded_from_the_build_cache(self):
        write_root(self.root, self.PACKAGES)
        with mock.patch.object(rebuild_matrix, "ROOT", self.root), mock.patch.dict(
            os.environ, {"GITHUB_OUTPUT": str(self.output)}, clear=True
        ), mock.patch.object(
            rebuild_matrix, "changed_recipes", return_value={"mozc"}
        ), mock.patch.object(
            rebuild_matrix, "fetch_primary", return_value=b""
        ):
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(rebuild_matrix.main(), 0)
        outputs = dict(
            line.split("=", 1) for line in self.output.read_text().splitlines()
        )
        self.assertIn("changed package recipes: mozc", out.getvalue())
        # An author who just edited a recipe is owed a real build.
        self.assertEqual(json.loads(outputs["cacheable"]), ["gnome-shell"])

    def test_no_changed_recipes_is_reported_as_none(self):
        code, out, outputs = self.run_main(env={})
        self.assertIn("changed package recipes: none", out)

    def test_a_stale_published_build_rebuilds_and_says_what_went_missing(self):
        # Exactly the recipe on disk, and still wrong: linked against a
        # soname the build root no longer carries.
        published = package_primary(
            ("mozc", "2.0", "1.hum42.bfin", (), ("libavcodec.so.62",)),
            ("gnome-shell", "51", "1.hum42.bfin", (), ()),
        )
        code, out, outputs = self.run_main(
            specs=set(),
            env={"FACTORY_REPO": "file:///repo/"},
            fetch=[published, f"{METADATA_OPEN}</metadata>".encode()],
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "rebuild mozc: published build requires libavcodec.so.62, "
            "which nothing provides",
            out,
        )
        self.assertIn("skip gnome-shell: already published", out)
        self.assertEqual(json.loads(outputs["build_list"]), ["mozc"])
        # A stale package must not be served out of the build cache: the key
        # would hit and hand back the broken build.
        self.assertEqual(json.loads(outputs["cacheable"]), [])

    def test_a_published_dependent_is_dragged_with_what_it_links_against(self):
        # gnome-shell matches the published listing and would be skipped, but
        # mozc is rebuilding underneath it.
        published = package_primary(
            ("mozc", "2.0", "1.hum42.bfin", ("libmozc.so.1",), ()),
            ("gnome-shell", "51", "1.hum42.bfin", (), ("libmozc.so.1",)),
        )
        code, out, outputs = self.run_main(
            specs=set(),
            env={"FACTORY_REPO": "file:///repo/"},
            fetch=[published, f"{METADATA_OPEN}</metadata>".encode()],
            changed={"mozc"},
        )
        self.assertEqual(code, 0)
        self.assertIn("rebuild gnome-shell: depends on something being rebuilt", out)
        self.assertEqual(
            json.loads(outputs["build_list"]), ["mozc", "gnome-shell"]
        )

    def test_a_stage_over_the_matrix_cap_is_reported_in_chunks(self):
        # A matrix above 256 jobs expands to nothing rather than failing, so
        # the stage is handed over in chunks and the split is announced.
        packages = [
            {"name": f"pkg{index:03d}", "version": "1.0", "stage": 0}
            for index in range(260)
        ]
        code, out, outputs = self.run_main(packages, env={})
        self.assertEqual(code, 0)
        self.assertIn("stage 0: 260 packages in 2 chunks", out)
        chunks = json.loads(outputs["stage0_chunks"])
        self.assertEqual([len(json.loads(chunk)) for chunk in chunks], [250, 10])
        # Chunking splits the handover, never the selection.
        self.assertEqual(len(json.loads(outputs["stage0"])), 260)


if __name__ == "__main__":
    unittest.main()
