#!/usr/bin/env python3
"""Unit tests for the generate step of tools/generated_sources.py.

tests/test_generated_sources.py covers the pure archive transformations.
This file covers what runs around them: the pinned-input checks each
generator applies before transforming anything, the crate and sdist layout
refusals, and the CLI that bootstrap_upstream_sources.prove_generated runs as
a subprocess. The network is replaced by in-memory archives, so nothing here
downloads.
"""

import contextlib
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import generated_sources

from tests.test_generated_sources import build_fpaste_archive, build_gpm_archive, build_input_archive, build_openal_soft_archive, read_archive


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "generated_sources.py"
CRATES_IO = generated_sources.CRATES_IO_INDEX


def sha512(data: bytes) -> str:
    return hashlib.sha512(data).hexdigest()


def targz(members: dict[str, bytes], modes: dict[str, int] | None = None, mtime: int = 1700000000) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            info.mode = (modes or {}).get(name, 0o644)
            archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class UrlopenRecorder:
    """Stands in for urllib.request.urlopen, serving bytes by URL."""

    def __init__(self, payloads: dict[str, bytes]):
        self.payloads = payloads
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request.full_url, request.get_header("User-agent"), timeout))
        return FakeResponse(self.payloads[request.full_url])


class PackageDirMixin:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.package_dir = self.tmp / "package"
        self.package_dir.mkdir()
        self.out_dir = self.tmp / "out" / "nested"

    def write_spec(self, spec_name: str, version: str | None) -> None:
        body = "Name: example\n"
        if version is not None:
            body += f"Version:        {version}\n"
        body += "Release: 1\n"
        (self.package_dir / spec_name).write_text(body)


class SpecVersionTests(PackageDirMixin, unittest.TestCase):
    def test_reads_the_version_tag(self):
        self.write_spec("gpm.spec", "1.20.7")
        self.assertEqual(generated_sources.spec_version(self.package_dir, "gpm.spec"), "1.20.7")

    def test_a_spec_without_version_is_refused(self):
        self.write_spec("gpm.spec", None)
        with self.assertRaisesRegex(ValueError, "no Version tag in gpm.spec"):
            generated_sources.spec_version(self.package_dir, "gpm.spec")

    def test_a_version_inside_a_line_does_not_count(self):
        (self.package_dir / "gpm.spec").write_text("# Version: 9\nName: gpm\n")
        with self.assertRaisesRegex(ValueError, "no Version tag"):
            generated_sources.spec_version(self.package_dir, "gpm.spec")


class DispatchTests(PackageDirMixin, unittest.TestCase):
    def test_unknown_package_is_refused_before_creating_the_output_dir(self):
        with self.assertRaisesRegex(ValueError, "no generated source resolver for zsh"):
            generated_sources.generate("zsh", self.package_dir, self.out_dir)
        self.assertFalse(self.out_dir.exists())

    def test_every_metadata_resolver_has_a_generator(self):
        self.assertEqual(set(generated_sources.METADATA), set(generated_sources.GENERATORS))


class IntelMediaGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "26.2.4"
    URL = f"https://github.com/intel/media-driver/archive/intel-media-{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("intel-media-driver-free.spec", self.VERSION)
        self.payload = build_input_archive(self.VERSION)

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("intel-media-driver-free.spec", "99.0.0")
        fetch = UrlopenRecorder({})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for intel-media 99.0.0"):
                generated_sources.generate("intel-media-driver-free", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "input archive mismatch"):
                generated_sources.generate("intel-media-driver-free", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.INTEL_MEDIA_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("intel-media-driver-free", self.package_dir, self.out_dir)
        self.assertEqual(target, self.out_dir / f"intel-media-{self.VERSION}-free.tar.gz")
        self.assertEqual(target.read_bytes(), generated_sources._imd_transform(self.payload, self.VERSION))
        self.assertNotIn("nonfree", {data.decode() for data in read_archive(target.read_bytes()).values()})
        self.assertEqual(fetch.requests, [(self.URL, "utah-packages-generated-source/1", 300)])


class GpmGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "1.20.7"
    URL = f"https://www.nico.schottelius.org/software/gpm/archives/gpm-{VERSION}.tar.lzma"

    def setUp(self):
        super().setUp()
        self.write_spec("gpm.spec", self.VERSION)
        self.payload = build_gpm_archive(self.VERSION)

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("gpm.spec", "2.0")
        fetch = UrlopenRecorder({})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for gpm 2.0"):
                generated_sources.generate("gpm", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("gpm", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.GPM_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("gpm", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"gpm-{self.VERSION}.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._gpm_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])


class FpasteGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "0.5.0.0"
    URL = f"https://codeberg.org/sanjay_ankur/fpaste/archive/{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("fpaste.spec", self.VERSION)
        self.payload = build_fpaste_archive()

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("fpaste.spec", "0.6.0.0")
        fetch = UrlopenRecorder({})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for fpaste 0.6.0.0"):
                generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.FPASTE_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"fpaste-{self.VERSION}.tar.gz")
        self.assertEqual(target.read_bytes(), generated_sources._fpaste_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])


class BluefinArtworkGenerateTests(PackageDirMixin, unittest.TestCase):
    COMMIT = "9ab493bf1fb3ae41594b6bb0a2c5f2350d81de01"
    FILES = {"LICENSE": b"Apache License", "logos/bluefin-logo-light.svg": b"<svg/>"}

    def setUp(self):
        super().setUp()
        self.write_commit(self.COMMIT)
        self.payloads = {generated_sources.BLUEFIN_ARTWORK_RAW_URL.format(commit=self.COMMIT, path=path): data
                         for path, data in self.FILES.items()}
        self.pins = {self.COMMIT: {path: sha512(data) for path, data in self.FILES.items()}}

    def write_commit(self, commit: str) -> None:
        (self.package_dir / "bluefin-artwork-logos.spec").write_text(
            f"%global commit {commit}\nName: bluefin-artwork-logos\nVersion: 0\n")

    def test_a_short_or_missing_commit_is_refused(self):
        self.write_commit("9ab493b")
        with self.assertRaisesRegex(ValueError, "full SHA-1"):
            generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)

    def test_an_unpinned_commit_fails_before_any_download(self):
        fetch = UrlopenRecorder({})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, f"no pinned file SHA-512s for projectbluefin/artwork {self.COMMIT}"):
                generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_changed_file_fails_closed_and_writes_nothing(self):
        self.pins[self.COMMIT]["LICENSE"] = sha512(b"something else")
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, self.pins, clear=True):
            with self.assertRaisesRegex(RuntimeError, "input file mismatch for .*/LICENSE"):
                generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_files_are_packed_into_the_named_target(self):
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, self.pins, clear=True):
            target = generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(target.name, "bluefin-artwork-logos-9ab493b.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._bluefin_artwork_transform(self.FILES, self.COMMIT))
        self.assertEqual(sorted(url for url, _, _ in fetch.requests), sorted(self.payloads))


class OpenALSoftGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "1.24.2"
    URL = f"https://openal-soft.org/openal-releases/openal-soft-{VERSION}.tar.bz2"

    def setUp(self):
        super().setUp()
        self.write_spec("openal-soft.spec", self.VERSION)
        self.payload = build_openal_soft_archive(self.VERSION)

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("openal-soft.spec", "1.0.0")
        fetch = UrlopenRecorder({})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for openal-soft 1.0.0"):
                generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.OPENAL_SOFT_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"openal-soft-{self.VERSION}-clean.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._openal_soft_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])


class TailscaleGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "1.98.8"

    def setUp(self):
        super().setUp()
        self.write_spec("tailscale.spec", self.VERSION)
        self.out_dir.mkdir(parents=True)

    def test_an_unpinned_version_fails_before_looking_for_go(self):
        self.write_spec("tailscale.spec", "1.0.0")
        with patch("shutil.which") as which:
            with self.assertRaisesRegex(RuntimeError, "no pinned commit for tailscale 1.0.0"):
                generated_sources.generate("tailscale", self.package_dir, self.out_dir)
        which.assert_not_called()

    def test_a_moved_tag_fails_closed_before_vendoring(self):
        runs = []
        with patch("shutil.which", return_value="/usr/bin/go"), \
                patch.object(generated_sources.subprocess, "run", side_effect=lambda cmd, **_: runs.append(cmd)), \
                patch.object(generated_sources.subprocess, "check_output", return_value="f" * 40 + "\n"):
            with self.assertRaisesRegex(RuntimeError, f"tag v{self.VERSION} moved: expected 05a9"):
                generated_sources.generate("tailscale", self.package_dir, self.out_dir)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][:6], ["git", "clone", "-q", "--branch", f"v{self.VERSION}", "--depth"])
        self.assertFalse((self.out_dir / f"tailscale-{self.VERSION}-vendored.tar.xz").exists())


class GitArchiveGenerateTests(PackageDirMixin, unittest.TestCase):
    """libslirp and rtmpdump, generated from a local repository carrying the tag."""

    VERSION = "1.0"

    def git(self, *args: str) -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_AUTHOR_DATE": "1700000000 +0000", "GIT_COMMITTER_DATE": "1700000000 +0000",
        }
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True, env=env).strip()

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "upstream"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "README").write_text("readme\n")
        self.git("add", "README")
        self.git("commit", "-q", "-m", "release")
        self.git("tag", "-a", f"v{self.VERSION}", "-m", "release")
        self.commit = self.git("rev-parse", "HEAD")

    def source(self, name: str, compression: str, commit: str | None = None):
        entry = {"remote": str(self.repo), "tag": "v{version}", "compression": compression,
                 "commits": {self.VERSION: commit or self.commit}}
        self.write_spec(f"{name}.spec", self.VERSION)
        return patch.dict(generated_sources.GIT_ARCHIVE_SOURCES, {name: entry})

    def expected_tar(self, name: str) -> bytes:
        return subprocess.check_output(
            ["git", "-C", str(self.repo), "archive", "--format=tar", f"--prefix={name}-{self.VERSION}/", self.commit]
        )

    def test_an_unpinned_version_fails_before_running_git(self):
        with self.source("libslirp", "xz"):
            self.write_spec("libslirp.spec", "9.9")
            with patch.object(generated_sources.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "no pinned commit for libslirp 9.9"):
                    generated_sources.generate("libslirp", self.package_dir, self.out_dir)
        run.assert_not_called()

    def test_the_xz_archive_is_the_git_archive_tar_at_preset_6(self):
        with self.source("libslirp", "xz"):
            target = generated_sources.generate("libslirp", self.package_dir, self.out_dir)
        self.assertEqual(target.name, "libslirp-1.0.tar.xz")
        raw = self.expected_tar("libslirp")
        self.assertEqual(target.read_bytes(),
                         lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6))

    def test_the_gz_archive_is_reproducible_and_carries_no_timestamp(self):
        with self.source("rtmpdump", "gz"):
            first = generated_sources.generate("rtmpdump", self.package_dir, self.out_dir).read_bytes()
            second = generated_sources.generate("rtmpdump", self.package_dir, self.out_dir).read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(first[4:8], b"\0\0\0\0")
        self.assertEqual(gzip.decompress(first), self.expected_tar("rtmpdump"))

    def test_a_moved_tag_fails_closed_and_writes_nothing(self):
        with self.source("libslirp", "xz", commit="f" * 40):
            with self.assertRaisesRegex(RuntimeError, f"tag v{self.VERSION} moved: expected ffff"):
                generated_sources.generate("libslirp", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_metadata_pins_the_tag_commit_of_the_carried_recipes(self):
        slirp = generated_sources.metadata_for("libslirp", ROOT / "packages" / "libslirp")
        self.assertEqual(slirp["filename"], "libslirp-4.9.6.tar.xz")
        self.assertIn("392af90207fc51dd9f9044ee9b1f963f3c851c2c", slirp["generate"]["input"])
        rtmp = generated_sources.metadata_for("rtmpdump", ROOT / "packages" / "rtmpdump")
        self.assertEqual(rtmp["filename"], "rtmpdump-2.6.tar.gz")
        self.assertIn("git.ffmpeg.org/rtmpdump.git tag v2.6", rtmp["generate"]["input"])


class CrateVendoringTests(unittest.TestCase):
    def crate(self, members, modes=None):
        payload = targz(members, modes)
        return {"name": "tiny", "version": "1.0.0", "checksum": hashlib.sha256(payload).hexdigest()}, payload

    def vendored(self, crate, payload):
        return {
            info.name: (info, data)
            for info, data in generated_sources._vendored_crate_members(crate, payload, "top/vendor", 42)
        }

    def test_a_lock_entry_without_checksum_is_refused(self):
        lock = f'[[package]]\nname = "tiny"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
        with self.assertRaisesRegex(RuntimeError, "tiny 1.0.0 has no checksum"):
            generated_sources.cargo_lock_packages(lock)

    def test_lock_entries_are_sorted_by_name_then_version(self):
        lock = "".join(
            f'[[package]]\nname = "{name}"\nversion = "{version}"\nsource = "{CRATES_IO}"\nchecksum = "c"\n\n'
            for name, version in (("zeta", "1.0.0"), ("alpha", "2.0.0"), ("alpha", "1.0.0"))
        )
        crates = generated_sources.cargo_lock_packages(lock)
        self.assertEqual(
            [(c["name"], c["version"]) for c in crates],
            [("alpha", "1.0.0"), ("alpha", "2.0.0"), ("zeta", "1.0.0")],
        )

    def test_a_member_outside_the_crate_directory_is_refused(self):
        crate, payload = self.crate({"tiny-1.0.0/Cargo.toml": b"ok", "other-9/evil.rs": b"x"})
        with self.assertRaisesRegex(RuntimeError, "member outside its directory: other-9/evil.rs"):
            list(generated_sources._vendored_crate_members(crate, payload, "top/vendor", 0))

    def test_a_shipped_cargo_checksum_is_regenerated_not_trusted(self):
        crate, payload = self.crate({
            "tiny-1.0.0/Cargo.toml": b"ok",
            "tiny-1.0.0/.cargo-checksum.json": b'{"files":{"Cargo.toml":"forged"}}',
        })
        members = self.vendored(crate, payload)
        checksum = json.loads(members["top/vendor/tiny-1.0.0/.cargo-checksum.json"][1])
        self.assertEqual(checksum["files"], {"Cargo.toml": hashlib.sha256(b"ok").hexdigest()})
        self.assertEqual(checksum["package"], crate["checksum"])

    def test_executable_bits_and_nested_directories_are_kept(self):
        crate, payload = self.crate(
            {"tiny-1.0.0/build.sh": b"#!/bin/sh", "tiny-1.0.0/src/a/b.rs": b"//"},
            modes={"tiny-1.0.0/build.sh": 0o755},
        )
        members = self.vendored(crate, payload)
        base = "top/vendor/tiny-1.0.0"
        self.assertEqual(members[f"{base}/build.sh"][0].mode, 0o755)
        self.assertEqual(members[f"{base}/src/a/b.rs"][0].mode, 0o644)
        for directory in (base, f"{base}/src", f"{base}/src/a"):
            self.assertTrue(members[directory][0].isdir(), directory)
        self.assertEqual({info.mtime for info, _ in members.values()}, {42})


class PydanticCoreGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "2.46.5"
    TOP = f"pydantic_core-{VERSION}"
    SDIST_URL = f"https://files.pythonhosted.org/packages/source/p/pydantic_core/{TOP}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("python-pydantic-core.spec", self.VERSION)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        lock = (
            f'[[package]]\nname = "pydantic-core"\nversion = "{self.VERSION}"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.sdist = targz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/pyproject.toml": b"[x]"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("python-pydantic-core.spec", "0.0.1")
        with patch.object(generated_sources, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for pydantic_core 0.0.1"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_a_rerolled_sdist_fails_closed_before_any_crate_download(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.SDIST_URL}"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.SDIST_URL])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_sdist_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist, self.crate_url: self.crate})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PYDANTIC_CORE_INPUT_SHA512, {self.VERSION: sha512(self.sdist)}):
            target = generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        self.assertEqual([url for url, _, _ in fetch.requests], [self.SDIST_URL, self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())

    def test_a_substituted_crate_download_fails_closed(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist, self.crate_url: targz({"tinycrate-1.0.0/x": b"evil"})})
        with patch.object(generated_sources.urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PYDANTIC_CORE_INPUT_SHA512, {self.VERSION: sha512(self.sdist)}):
            with self.assertRaisesRegex(RuntimeError, "crate tinycrate 1.0.0: expected sha256"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_an_sdist_member_outside_its_top_directory_is_refused(self):
        lock = f'[[package]]\nname = "pydantic-core"\nversion = "{self.VERSION}"\n'
        sdist = targz({f"{self.TOP}/Cargo.lock": lock.encode(), "elsewhere/setup.py": b"x"})
        with self.assertRaisesRegex(RuntimeError, "sdist member outside pydantic_core-2.46.5: elsewhere/setup.py"):
            generated_sources._pydantic_core_transform(sdist, self.VERSION, {})


class CliTests(unittest.TestCase):
    def run_main(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = generated_sources.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_wrong_argument_count_prints_usage_and_exits_2(self):
        for argv in (["generated_sources.py"], ["generated_sources.py", "gpm", "dir"],
                     ["generated_sources.py", "gpm", "dir", "out", "extra"]):
            with self.subTest(argv=argv):
                code, stdout, stderr = self.run_main(argv)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn("usage:", stderr)
                self.assertIn("PACKAGE PACKAGE_DIR OUTPUT_DIR", stderr)

    def test_success_reports_the_artifact_digest_as_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "gpm-1.20.7.tar.xz"
            artifact.write_bytes(b"generated bytes")
            with patch.object(generated_sources, "generate", return_value=artifact) as generate:
                code, stdout, _ = self.run_main(["generated_sources.py", "gpm", "pkgdir", tmp])
        self.assertEqual(code, 0)
        generate.assert_called_once_with("gpm", Path("pkgdir"), Path(tmp))
        self.assertEqual(json.loads(stdout), {
            "package": "gpm",
            "filename": "gpm-1.20.7.tar.xz",
            "sha512": sha512(b"generated bytes"),
            "bytes": len(b"generated bytes"),
        })

    def test_the_script_runs_standalone_and_fails_on_an_unknown_package(self):
        # prove_generated invokes the file directly, so its __main__ guard and
        # import-free startup are part of the contract.
        with tempfile.TemporaryDirectory() as tmp:
            usage = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
            unknown = subprocess.run(
                [sys.executable, str(SCRIPT), "zsh", tmp, str(Path(tmp) / "out")],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(usage.returncode, 2)
        self.assertIn("usage:", usage.stderr)
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("no generated source resolver for zsh", unknown.stderr)
        self.assertEqual(unknown.stdout, "")


if __name__ == "__main__":
    unittest.main()
