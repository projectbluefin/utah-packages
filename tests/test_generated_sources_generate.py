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
import difflib
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
import urllib.error
import urllib.request
from unittest.mock import patch

from tools import generated_sources, generated_sources_archives, generated_sources_vendored

from tests import test_generated_sources
from tests.test_generated_sources import (
    build_fpaste_archive,
    build_freerdp_archive,
    build_gpm_archive,
    build_hplip_archive,
    build_input_archive,
    build_kernel_archive,
    build_openal_soft_archive,
    build_sevenzip_archive,
    read_archive,
)


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
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for intel-media 99.0.0"):
                generated_sources.generate("intel-media-driver-free", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "input archive mismatch"):
                generated_sources.generate("intel-media-driver-free", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
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
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for gpm 2.0"):
                generated_sources.generate("gpm", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("gpm", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
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
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for fpaste 0.6.0.0"):
                generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.FPASTE_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("fpaste", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"fpaste-{self.VERSION}.tar.gz")
        self.assertEqual(target.read_bytes(), generated_sources._fpaste_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])


class SinglePinGenerateCases:
    """Shared cases for generators that download one SHA-512-pinned archive.

    Subclasses name the package, the spec, the pin table, the upstream URL,
    the target filename and a synthetic upstream archive their transform
    accepts. A tampered or re-rolled download must stop the generator before
    it writes anything, and an unpinned version must stop it before it
    downloads anything.
    """

    PACKAGE = ""
    SPEC = ""
    VERSION = ""
    UNPINNED = "99.0.0"
    UNPINNED_MESSAGE = ""

    def setUp(self):
        super().setUp()
        self.write_spec(self.SPEC, self.VERSION)
        self.payload = self.build_payload()

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec(self.SPEC, self.UNPINNED)
        fetch = UrlopenRecorder({})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, self.UNPINNED_MESSAGE):
                generated_sources.generate(self.PACKAGE, self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.url(): self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.url()}"):
                generated_sources.generate(self.PACKAGE, self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.url(): self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(self.pins(), {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate(self.PACKAGE, self.package_dir, self.out_dir)
        self.assertEqual(target, self.out_dir / self.target_name())
        self.assertEqual(target.read_bytes(), self.transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.url()])


class HypervGenerateTests(SinglePinGenerateCases, PackageDirMixin, unittest.TestCase):
    PACKAGE = "hyperv-daemons"
    SPEC = "hyperv-daemons.spec"
    VERSION = "7.3.1"
    UNPINNED_MESSAGE = "no pinned input SHA-512 for linux 99.0.0"

    def build_payload(self) -> bytes:
        return build_kernel_archive(self.VERSION)

    def url(self) -> str:
        return f"https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-{self.VERSION}.tar.xz"

    def pins(self) -> dict:
        return generated_sources_archives.HYPERV_KERNEL_INPUT_SHA512

    def target_name(self) -> str:
        return f"tools-hv-{self.VERSION}.tar.xz"

    def transform(self, payload: bytes, version: str) -> bytes:
        return generated_sources_archives._hyperv_transform(payload, version)


class HplipGenerateTests(SinglePinGenerateCases, PackageDirMixin, unittest.TestCase):
    PACKAGE = "hplip"
    SPEC = "hplip.spec"
    VERSION = "3.26.6"
    UNPINNED_MESSAGE = "no pinned input SHA-512 for hplip 99.0.0"

    def build_payload(self) -> bytes:
        return build_hplip_archive(self.VERSION)

    def url(self) -> str:
        return f"https://downloads.sourceforge.net/project/hplip/hplip/{self.VERSION}/hplip-{self.VERSION}.tar.gz"

    def pins(self) -> dict:
        return generated_sources_archives.HPLIP_INPUT_SHA512

    def target_name(self) -> str:
        return f"hplip-{self.VERSION}-repack.tar.gz"

    def transform(self, payload: bytes, version: str) -> bytes:
        return generated_sources_archives._hplip_transform(payload, version)


class FreerdpGenerateTests(SinglePinGenerateCases, PackageDirMixin, unittest.TestCase):
    PACKAGE = "freerdp"
    SPEC = "freerdp.spec"
    VERSION = "3.32.2"
    UNPINNED_MESSAGE = "no pinned input SHA-512 for freerdp 99.0.0"

    def build_payload(self) -> bytes:
        return build_freerdp_archive(self.VERSION)

    def url(self) -> str:
        return f"https://github.com/FreeRDP/FreeRDP/archive/{self.VERSION}/FreeRDP-{self.VERSION}.tar.gz"

    def pins(self) -> dict:
        return generated_sources_archives.FREERDP_INPUT_SHA512

    def target_name(self) -> str:
        return f"FreeRDP-{self.VERSION}-repack.tar.gz"

    def transform(self, payload: bytes, version: str) -> bytes:
        return generated_sources_archives._freerdp_transform(payload, version)


class JpegxlGenerateTests(PackageDirMixin, unittest.TestCase):
    """jpegxl pins the release archive and every submodule archive it fills in."""

    VERSION = "0.12.0"
    URL = f"https://github.com/libjxl/libjxl/archive/v{VERSION}/jpegxl-{VERSION}.tar.gz"
    SJPEG_REMOTE = "https://github.com/webmproject/sjpeg"
    SKCMS_REMOTE = "https://github.com/google/skcms"

    def setUp(self):
        super().setUp()
        self.write_spec("jpegxl.spec", self.VERSION)
        # Reuse the transform tests' synthetic archives; reaching the class
        # through its module keeps pytest from collecting it a second time.
        archives = test_generated_sources.JpegxlTransformTests()
        self.release = archives.release()
        self.submodules = archives.submodules()
        self.sjpeg_commit, self.sjpeg = self.submodules["third_party/sjpeg"]
        self.skcms_commit, self.skcms = self.submodules["third_party/skcms"]
        self.sjpeg_url = f"{self.SJPEG_REMOTE}/archive/{self.sjpeg_commit}.tar.gz"
        self.skcms_url = f"{self.SKCMS_REMOTE}/archive/{self.skcms_commit}.tar.gz"
        self.payloads = {self.URL: self.release, self.sjpeg_url: self.sjpeg, self.skcms_url: self.skcms}

    def pins(self, sjpeg_pin: str | None = None) -> dict:
        return {
            "sha512": sha512(self.release),
            "submodules": {
                "third_party/sjpeg": (self.SJPEG_REMOTE, self.sjpeg_commit, sjpeg_pin or sha512(self.sjpeg)),
                "third_party/skcms": (self.SKCMS_REMOTE, self.skcms_commit, sha512(self.skcms)),
            },
        }

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("jpegxl.spec", "0.99.0")
        fetch = UrlopenRecorder({})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned inputs for jpegxl 0.99.0"):
                generated_sources.generate("jpegxl", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_release_archive_fails_before_fetching_submodules(self):
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("jpegxl", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_a_rerolled_submodule_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources_archives.JPEGXL_INPUTS, {self.VERSION: self.pins(sjpeg_pin="0" * 128)}):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.sjpeg_url}"):
                generated_sources.generate("jpegxl", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archives_are_combined_into_the_named_target(self):
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources_archives.JPEGXL_INPUTS, {self.VERSION: self.pins()}):
            target = generated_sources.generate("jpegxl", self.package_dir, self.out_dir)
        self.assertEqual(target, self.out_dir / f"jpegxl-{self.VERSION}.tar.xz")
        self.assertEqual(
            target.read_bytes(),
            generated_sources_archives._jpegxl_transform(self.release, self.submodules, self.VERSION),
        )
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL, self.sjpeg_url, self.skcms_url])


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
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, f"no pinned file SHA-512s for projectbluefin/artwork {self.COMMIT}"):
                generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_changed_file_fails_closed_and_writes_nothing(self):
        self.pins[self.COMMIT]["LICENSE"] = sha512(b"something else")
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, self.pins, clear=True):
            with self.assertRaisesRegex(RuntimeError, "input file mismatch for .*/LICENSE"):
                generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_files_are_packed_into_the_named_target(self):
        fetch = UrlopenRecorder(self.payloads)
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_ARTWORK_FILES, self.pins, clear=True):
            target = generated_sources.generate("bluefin-artwork-logos", self.package_dir, self.out_dir)
        self.assertEqual(target.name, "bluefin-artwork-logos-9ab493b.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._bluefin_artwork_transform(self.FILES, self.COMMIT))
        self.assertEqual(sorted(url for url, _, _ in fetch.requests), sorted(self.payloads))


class SevenZipGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "26.04"
    URL = f"https://github.com/ip7z/7zip/archive/{VERSION}/7zip-{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("7zip.spec", self.VERSION)
        self.payload = build_sevenzip_archive(self.VERSION)

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("7zip.spec", "1.00")
        fetch = UrlopenRecorder({})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for 7zip 1.00"):
                generated_sources.generate("7zip", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("7zip", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.SEVENZIP_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("7zip", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"7zip-{self.VERSION}.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._sevenzip_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])

    def test_an_unreachable_upstream_is_classified_as_unavailable(self):
        outage = urllib.error.URLError(ConnectionRefusedError("connection refused"))
        with patch.object(urllib.request, "urlopen", side_effect=outage), \
                patch.dict(generated_sources.SEVENZIP_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            with self.assertRaisesRegex(generated_sources.UpstreamUnreachable, "github.com/ip7z/7zip"):
                generated_sources.generate("7zip", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])


class OpenALSoftGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "1.25.2"
    URL = f"https://openal-soft.org/openal-releases/openal-soft-{VERSION}.tar.bz2"

    def setUp(self):
        super().setUp()
        self.write_spec("openal-soft.spec", self.VERSION)
        self.payload = build_openal_soft_archive(self.VERSION)

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("openal-soft.spec", "1.0.0")
        fetch = UrlopenRecorder({})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for openal-soft 1.0.0"):
                generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(fetch.requests, [])

    def test_a_rerolled_upstream_archive_fails_closed_and_writes_nothing(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.URL}"):
                generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_is_transformed_into_the_named_target(self):
        fetch = UrlopenRecorder({self.URL: self.payload})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.OPENAL_SOFT_INPUT_SHA512, {self.VERSION: sha512(self.payload)}):
            target = generated_sources.generate("openal-soft", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"openal-soft-{self.VERSION}-clean.tar.xz")
        self.assertEqual(target.read_bytes(), generated_sources._openal_soft_transform(self.payload, self.VERSION))
        self.assertEqual([url for url, _, _ in fetch.requests], [self.URL])


class BrewTarballGenerateTests(PackageDirMixin, unittest.TestCase):
    """The Homebrew archive is copied out of a digest-pinned image (#1039)."""

    VERSION = "7.0.11"
    REGISTRY = "https://ghcr.io"
    TOKEN_URL = f"{REGISTRY}/token?scope=repository:ublue-os/brew:pull"
    MEMBER = "system_files/usr/share/homebrew.tar.zst"

    def setUp(self):
        super().setUp()
        self.write_spec("brew-tarball.spec", self.VERSION)
        self.archive = b"zstd homebrew prefix"
        self.files_layer = targz({"system_files/etc/profile.d/brew.sh": b"#!/bin/sh"})
        self.tarball_layer = targz({self.MEMBER: self.archive})
        self.layer_digests = [
            "sha256:" + hashlib.sha256(layer).hexdigest() for layer in (self.files_layer, self.tarball_layer)
        ]
        self.manifest = json.dumps({"layers": [{"digest": digest} for digest in self.layer_digests]}).encode()
        self.manifest_digest = "sha256:" + hashlib.sha256(self.manifest).hexdigest()

    def payloads(self, tarball_layer: bytes | None = None) -> dict[str, bytes]:
        base = f"{self.REGISTRY}/v2/ublue-os/brew"
        return {
            self.TOKEN_URL: b'{"token": "anonymous"}',
            f"{base}/manifests/{self.manifest_digest}": self.manifest,
            f"{base}/blobs/{self.layer_digests[0]}": self.files_layer,
            f"{base}/blobs/{self.layer_digests[1]}": tarball_layer or self.tarball_layer,
        }

    def test_metadata_names_the_archive_and_the_pinned_manifest(self):
        entry = generated_sources.metadata_for("brew-tarball", self.package_dir)
        self.assertEqual(entry["filename"], f"homebrew-{self.VERSION}.tar.zst")
        self.assertIn(
            f"ghcr.io/ublue-os/brew@{generated_sources.BREW_TARBALL_MANIFESTS[self.VERSION]}",
            entry["generate"]["input"],
        )

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("brew-tarball.spec", "0.0.1")
        with patch.object(urllib.request, "urlopen") as urlopen:
            with self.assertRaisesRegex(RuntimeError, "no pinned image manifest for brew-tarball 0.0.1"):
                generated_sources.generate("brew-tarball", self.package_dir, self.out_dir)
        urlopen.assert_not_called()

    def test_the_member_is_copied_unchanged_from_the_topmost_layer(self):
        fetch = UrlopenRecorder(self.payloads())
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BREW_TARBALL_MANIFESTS, {self.VERSION: self.manifest_digest}):
            target = generated_sources.generate("brew-tarball", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"homebrew-{self.VERSION}.tar.zst")
        self.assertEqual(target.read_bytes(), self.archive)
        # The topmost layer carries the member, so the lower one is never fetched.
        self.assertNotIn(
            f"{self.REGISTRY}/v2/ublue-os/brew/blobs/{self.layer_digests[0]}",
            [url for url, _, _ in fetch.requests],
        )

    def test_a_moved_manifest_fails_closed(self):
        fetch = UrlopenRecorder(self.payloads())
        pinned = "sha256:" + "0" * 64
        fetch.payloads[f"{self.REGISTRY}/v2/ublue-os/brew/manifests/{pinned}"] = self.manifest
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BREW_TARBALL_MANIFESTS, {self.VERSION: pinned}):
            with self.assertRaisesRegex(RuntimeError, f"image manifest: expected {pinned}"):
                generated_sources.generate("brew-tarball", self.package_dir, self.out_dir)
        self.assertFalse(self.out_dir.exists() and any(self.out_dir.iterdir()))

    def test_a_substituted_layer_fails_closed(self):
        fetch = UrlopenRecorder(self.payloads(tarball_layer=targz({self.MEMBER: b"evil"})))
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BREW_TARBALL_MANIFESTS, {self.VERSION: self.manifest_digest}):
            with self.assertRaisesRegex(RuntimeError, f"layer {self.layer_digests[1]}: expected"):
                generated_sources.generate("brew-tarball", self.package_dir, self.out_dir)
        self.assertFalse(self.out_dir.exists() and any(self.out_dir.iterdir()))


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
            with patch.object(subprocess, "run") as run:
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
        with patch.object(generated_sources_archives, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for pydantic_core 0.0.1"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_a_rerolled_sdist_fails_closed_before_any_crate_download(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.SDIST_URL}"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.SDIST_URL])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_sdist_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PYDANTIC_CORE_INPUT_SHA512, {self.VERSION: sha512(self.sdist)}):
            target = generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        self.assertEqual([url for url, _, _ in fetch.requests], [self.SDIST_URL, self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())

    def test_a_substituted_crate_download_fails_closed(self):
        fetch = UrlopenRecorder({self.SDIST_URL: self.sdist, self.crate_url: targz({"tinycrate-1.0.0/x": b"evil"})})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PYDANTIC_CORE_INPUT_SHA512, {self.VERSION: sha512(self.sdist)}):
            with self.assertRaisesRegex(RuntimeError, "crate tinycrate 1.0.0: expected sha256"):
                generated_sources.generate("python-pydantic-core", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_an_sdist_member_outside_its_top_directory_is_refused(self):
        lock = f'[[package]]\nname = "pydantic-core"\nversion = "{self.VERSION}"\n'
        sdist = targz({f"{self.TOP}/Cargo.lock": lock.encode(), "elsewhere/setup.py": b"x"})
        with self.assertRaisesRegex(RuntimeError, "sdist member outside pydantic_core-2.46.5: elsewhere/setup.py"):
            generated_sources._pydantic_core_transform(sdist, self.VERSION, {})


class PrefixdevnameGenerateTests(PackageDirMixin, unittest.TestCase):
    VERSION = "0.2.0"
    TOP = f"prefixdevname-{VERSION}"
    ARCHIVE_URL = f"https://github.com/msekletar/prefixdevname/archive/refs/tags/v{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("prefixdevname.spec", self.VERSION)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        lock = (
            f'[[package]]\nname = "prefixdevname"\nversion = "{self.VERSION}"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.archive = targz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/Cargo.toml": b"[x]"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("prefixdevname.spec", "0.0.1")
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for prefixdevname 0.0.1"):
                generated_sources.generate("prefixdevname", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_a_rerolled_archive_fails_closed_before_any_crate_download(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.ARCHIVE_URL}"):
                generated_sources.generate("prefixdevname", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_archive_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PREFIXDEVNAME_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            target = generated_sources.generate("prefixdevname", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL, self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())

    def test_a_substituted_crate_download_fails_closed(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: targz({"tinycrate-1.0.0/x": b"evil"})})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.PREFIXDEVNAME_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            with self.assertRaisesRegex(RuntimeError, "crate tinycrate 1.0.0: expected sha256"):
                generated_sources.generate("prefixdevname", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])


class KanataGenerateTests(PackageDirMixin, unittest.TestCase):
    """Dakota's keyboard remapper, vendored from its GitHub tag archive (utah#1222)."""

    VERSION = "1.12.0"
    TOP = f"kanata-{VERSION}"
    ARCHIVE_URL = f"https://github.com/jtroo/kanata/archive/refs/tags/v{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("kanata.spec", self.VERSION)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        # Workspace members are path sources: no `source`, nothing to fetch.
        lock = (
            f'[[package]]\nname = "kanata"\nversion = "{self.VERSION}"\n\n'
            '[[package]]\nname = "kanata-parser"\nversion = "0.1.0"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.archive = targz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/parser/Cargo.toml": b"[x]"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_metadata_names_the_generated_vendored_archive(self):
        entry = generated_sources.metadata_for("kanata", self.package_dir)
        self.assertEqual(entry["filename"], f"{self.TOP}-vendored.tar.xz")
        self.assertIn(self.ARCHIVE_URL, entry["generate"]["input"])

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("kanata.spec", "0.0.1")
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for kanata 0.0.1"):
                generated_sources.generate("kanata", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_registry_crates_are_vendored_and_workspace_members_are_not_fetched(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.KANATA_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            target = generated_sources.generate("kanata", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL, self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            names = archive.getnames()
        self.assertIn(f"{self.TOP}/parser/Cargo.toml", names)
        self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", names)


class BluefinCliGenerateTests(PackageDirMixin, unittest.TestCase):
    """The tag archive plus the release's vendor/ tree, both pinned (utah's terminal experience)."""

    VERSION = "0.12.0"
    TOP = f"bluefin-cli-{VERSION}"
    ARCHIVE_URL = f"https://github.com/tuna-os/bluefin-cli/archive/v{VERSION}/bluefin-cli-{VERSION}.tar.gz"
    VENDOR_URL = (f"https://github.com/tuna-os/bluefin-cli/releases/download/v{VERSION}/"
                  f"bluefin-cli-{VERSION}-vendor.tar.gz")

    def setUp(self):
        super().setUp()
        self.write_spec("bluefin-cli.spec", self.VERSION)
        self.archive = targz({f"{self.TOP}/go.mod": b"module x\n", f"{self.TOP}/main.go": b"package main\n"})
        self.vendor = targz({"vendor/modules.txt": b"# example.com/m v1.0.0\n",
                             "vendor/example.com/m/m.go": b"package m\n"})
        self.pins = {self.VERSION: (sha512(self.archive), sha512(self.vendor))}

    def generate(self, payloads: dict[str, bytes]) -> tuple[Path, UrlopenRecorder]:
        fetch = UrlopenRecorder(payloads)
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.BLUEFIN_CLI_INPUT_SHA512, self.pins):
            return generated_sources.generate("bluefin-cli", self.package_dir, self.out_dir), fetch

    def test_metadata_names_both_pinned_inputs(self):
        entry = generated_sources.metadata_for("bluefin-cli", self.package_dir)
        self.assertEqual(entry["filename"], f"{self.TOP}-vendored.tar.xz")
        self.assertIn(self.ARCHIVE_URL, entry["generate"]["input"])
        self.assertIn(self.VENDOR_URL, entry["generate"]["input"])

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("bluefin-cli.spec", "0.0.1")
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for bluefin-cli 0.0.1"):
                generated_sources.generate("bluefin-cli", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_the_vendor_tree_lands_inside_the_tag_archive_reproducibly(self):
        target, fetch = self.generate({self.ARCHIVE_URL: self.archive, self.VENDOR_URL: self.vendor})
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL, self.VENDOR_URL])
        first = target.read_bytes()
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(first))) as archive:
            members = archive.getmembers()
        names = [member.name for member in members]
        self.assertEqual(names, sorted(names))
        self.assertIn(f"{self.TOP}/main.go", names)
        self.assertIn(f"{self.TOP}/vendor/modules.txt", names)
        self.assertIn(f"{self.TOP}/vendor/example.com/m/m.go", names)
        self.assertEqual({(m.mtime, m.uid, m.gid, m.uname) for m in members}, {(0, 0, 0, "")})
        target.unlink()
        again, _ = self.generate({self.ARCHIVE_URL: self.archive, self.VENDOR_URL: self.vendor})
        self.assertEqual(again.read_bytes(), first)

    def test_a_substituted_vendor_archive_fails_closed(self):
        evil = targz({"vendor/modules.txt": b"evil"})
        with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.VENDOR_URL}"):
            self.generate({self.ARCHIVE_URL: self.archive, self.VENDOR_URL: evil})
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_a_vendor_member_outside_vendor_is_refused(self):
        vendor = targz({"vendor/modules.txt": b"", "main.go": b"package evil\n"})
        with self.assertRaisesRegex(RuntimeError, "vendor archive member outside vendor/: main.go"):
            generated_sources._bluefin_cli_transform(self.archive, vendor, self.VERSION)

    def test_a_tag_archive_that_already_vendors_is_refused(self):
        archive = targz({f"{self.TOP}/vendor/modules.txt": b""})
        with self.assertRaisesRegex(RuntimeError, "tag archive already carries"):
            generated_sources._bluefin_cli_transform(archive, self.vendor, self.VERSION)



def tarxz(members: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:xz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 1700000000
            archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


class GstThumbnailersGenerateTests(PackageDirMixin, unittest.TestCase):
    """The GNOME release is a .tar.xz under a major.minor directory (#527)."""

    VERSION = "1.1.0"
    TOP = f"gst-thumbnailers-{VERSION}"
    ARCHIVE_URL = f"https://download.gnome.org/sources/gst-thumbnailers/1.1/{TOP}.tar.xz"

    def setUp(self):
        super().setUp()
        self.write_spec("gst-thumbnailers.spec", self.VERSION)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        lock = (
            f'[[package]]\nname = "gst-thumbnailers"\nversion = "{self.VERSION}"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.archive = tarxz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/meson.build": b"project()"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_metadata_names_the_generated_vendored_archive(self):
        entry = generated_sources.metadata_for("gst-thumbnailers", self.package_dir)
        self.assertEqual(entry["filename"], f"{self.TOP}-vendored.tar.xz")
        self.assertEqual(entry["generate"]["script"], generated_sources.SCRIPT_PATH)
        self.assertIn(self.ARCHIVE_URL, entry["generate"]["input"])

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("gst-thumbnailers.spec", "0.0.1")
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for gst-thumbnailers 0.0.1"):
                generated_sources.generate("gst-thumbnailers", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_a_rerolled_release_fails_closed_before_any_crate_download(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive})
        with patch.object(urllib.request, "urlopen", fetch):
            with self.assertRaisesRegex(RuntimeError, f"input archive mismatch for {self.ARCHIVE_URL}"):
                generated_sources.generate("gst-thumbnailers", self.package_dir, self.out_dir)
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL])
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_the_pinned_release_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.GST_THUMBNAILERS_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            target = generated_sources.generate("gst-thumbnailers", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        self.assertEqual([url for url, _, _ in fetch.requests], [self.ARCHIVE_URL, self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            names = archive.getnames()
            self.assertIn(f"{self.TOP}/meson.build", names)
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", names)
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/.cargo-checksum.json", names)
            self.assertEqual({m.mtime for m in archive.getmembers()}, {generated_sources.CARGO_VENDORED_MTIME})

    def test_generation_is_byte_reproducible(self):
        outputs = []
        for run in range(2):
            fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
            with patch.object(urllib.request, "urlopen", fetch), \
                    patch.dict(generated_sources.GST_THUMBNAILERS_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
                target = generated_sources.generate("gst-thumbnailers", self.package_dir, self.out_dir / str(run))
            outputs.append(target.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_a_substituted_crate_download_fails_closed(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: targz({"tinycrate-1.0.0/x": b"evil"})})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.GST_THUMBNAILERS_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            with self.assertRaisesRegex(RuntimeError, "crate tinycrate 1.0.0: expected sha256"):
                generated_sources.generate("gst-thumbnailers", self.package_dir, self.out_dir)
        self.assertEqual(list(self.out_dir.iterdir()), [])


def unified_diff(path: str, old: str, new: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{path}", f"b/{path}"))


class GstreamerPluginsRsGenerateTests(PackageDirMixin, unittest.TestCase):
    """A git tag whose Cargo.lock the recipe's patches change before vendoring (#1040)."""

    VERSION = "1.0"
    TOP = f"gst-plugins-rs-{VERSION}"
    git = GitArchiveGenerateTests.git

    def setUp(self):
        super().setUp()
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"
        workspace = '[[package]]\nname = "gst-plugin-x"\nversion = "1.0"\n'
        self.released_lock = (
            f'{workspace}\n[[package]]\nname = "gitcrate"\nversion = "0.1.0"\n'
            'source = "git+https://example.com/gitcrate#0123"\n'
        )
        patched_lock = (
            f'{workspace}\n[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.repo = self.tmp / "upstream"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "Cargo.lock").write_text(self.released_lock)
        (self.repo / "Cargo.toml").write_text("[workspace]\n")
        self.git("add", "Cargo.lock", "Cargo.toml")
        self.git("commit", "-q", "-m", "release")
        self.git("tag", "-a", self.VERSION, "-m", "release")
        self.commit = self.git("rev-parse", "HEAD")
        (self.package_dir / "0001-lock.patch").write_text(unified_diff("Cargo.lock", self.released_lock, patched_lock))
        # Only Cargo.lock hunks reach the lock; this one must not be applied there.
        (self.package_dir / "0002-toml.patch").write_text(
            unified_diff("Cargo.toml", "[workspace]\n", '[workspace]\nmembers = ["x"]\n')
        )
        self.write_recipe("Patch:          0001-lock.patch\nPatch1: 0002-toml.patch\n")

    def write_recipe(self, patches: str, version: str = VERSION) -> None:
        (self.package_dir / "gstreamer-plugins-rs.spec").write_text(
            f"Name: gstreamer-plugins-rs\nVersion:        {version}\nRelease: 1\n{patches}"
        )

    def pinned(self):
        return patch.multiple(
            generated_sources_vendored,
            GSTREAMER_PLUGINS_RS_REMOTE=str(self.repo),
            GSTREAMER_PLUGINS_RS_COMMITS={self.VERSION: self.commit},
        )

    def test_metadata_pins_the_carried_recipe_commit(self):
        entry = generated_sources.metadata_for("gstreamer-plugins-rs", ROOT / "packages" / "gstreamer-plugins-rs")
        self.assertEqual(entry["filename"], "gst-plugins-rs-0.15.4-vendored.tar.xz")
        self.assertIn("gst-plugins-rs.git tag 0.15.4 (commit 1afff3711855238433862c0ce3bf34918e500386)",
                      entry["generate"]["input"])

    def test_the_carried_recipe_names_its_patch_files(self):
        package_dir = ROOT / "packages" / "gstreamer-plugins-rs"
        patches = generated_sources.recipe_patches(package_dir, "gstreamer-plugins-rs.spec")
        self.assertEqual([p.name for p in patches], [
            "0001-Update-Cargo.lock-for-non-git-dependencies.patch",
            "0002-Limit-the-workspace-to-the-plugins-this-recipe-builds.patch",
        ])
        self.assertTrue(all(p.is_file() for p in patches))

    def test_an_unpinned_version_fails_before_running_git(self):
        self.write_recipe("", version="9.9")
        with patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "no pinned commit for gstreamer-plugins-rs 9.9"):
                generated_sources.generate("gstreamer-plugins-rs", self.package_dir, self.out_dir)
        run.assert_not_called()

    def test_a_patch_named_by_macro_is_refused(self):
        self.write_recipe("Patch: %{name}-fix.patch\n")
        with self.assertRaisesRegex(ValueError, "uses a macro"):
            generated_sources.recipe_patches(self.package_dir, "gstreamer-plugins-rs.spec")

    def test_the_patched_lock_decides_the_vendored_crates(self):
        fetch = UrlopenRecorder({self.crate_url: self.crate})
        with self.pinned(), patch.object(urllib.request, "urlopen", fetch):
            target = generated_sources.generate("gstreamer-plugins-rs", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        self.assertEqual([url for url, _, _ in fetch.requests], [self.crate_url])
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())
            # The tree stays as released; %prep applies the patches.
            self.assertEqual(archive.extractfile(f"{self.TOP}/Cargo.lock").read().decode(), self.released_lock)
            self.assertEqual(archive.extractfile(f"{self.TOP}/Cargo.toml").read(), b"[workspace]\n")
        self.assertEqual([path.name for path in self.out_dir.iterdir()], [target.name])

    def test_without_the_lock_patch_the_git_crate_is_refused(self):
        self.write_recipe("")
        with self.pinned(), patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "gitcrate 0.1.0 comes from git"):
                generated_sources.generate("gstreamer-plugins-rs", self.package_dir, self.out_dir)
        fetch.assert_not_called()


class TealdeerGenerateTests(PackageDirMixin, unittest.TestCase):
    """Dakota's tldr client, vendored from its GitHub tag archive (#1034)."""

    VERSION = "1.8.1"
    TOP = f"tealdeer-{VERSION}"
    ARCHIVE_URL = f"https://github.com/tealdeer-rs/tealdeer/archive/refs/tags/v{VERSION}.tar.gz"

    def setUp(self):
        super().setUp()
        self.write_spec("tealdeer.spec", self.VERSION)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        lock = (
            f'[[package]]\nname = "tealdeer"\nversion = "{self.VERSION}"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.archive = targz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/Cargo.toml": b"[x]"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_metadata_names_the_generated_vendored_archive(self):
        entry = generated_sources.metadata_for("tealdeer", self.package_dir)
        self.assertEqual(entry["filename"], f"{self.TOP}-vendored.tar.xz")
        self.assertIn(self.ARCHIVE_URL, entry["generate"]["input"])

    def test_an_unpinned_version_fails_before_any_download(self):
        self.write_spec("tealdeer.spec", "0.0.1")
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for tealdeer 0.0.1"):
                generated_sources.generate("tealdeer", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_the_pinned_archive_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.TEALDEER_INPUT_SHA512, {self.VERSION: sha512(self.archive)}):
            target = generated_sources.generate("tealdeer", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())


class Oo7GenerateTests(PackageDirMixin, unittest.TestCase):
    """oo7 at a pinned commit, vendored from its GitHub commit archive (#1192)."""

    COMMIT = "e91b98a7235a4971c6cbb7f0533034afc8a8f618"
    TOP = f"oo7-{COMMIT}"
    ARCHIVE_URL = f"https://github.com/linux-credentials/oo7/archive/{COMMIT}/oo7-e91b98a.tar.gz"

    def write_oo7_spec(self, commit: str) -> None:
        (self.package_dir / "oo7.spec").write_text(
            f"%global commit {commit}\nName: oo7\nVersion:        0.7.0~beta^1.%{{shortcommit}}\nRelease: 1\n"
        )

    def setUp(self):
        super().setUp()
        self.write_oo7_spec(self.COMMIT)
        self.crate = targz({"tinycrate-1.0.0/src/lib.rs": b"//"})
        lock = (
            '[[package]]\nname = "oo7"\nversion = "0.7.0-alpha"\n\n'
            f'[[package]]\nname = "tinycrate"\nversion = "1.0.0"\nsource = "{CRATES_IO}"\n'
            f'checksum = "{hashlib.sha256(self.crate).hexdigest()}"\n'
        )
        self.archive = targz({f"{self.TOP}/Cargo.lock": lock.encode(), f"{self.TOP}/Cargo.toml": b"[x]"})
        self.crate_url = "https://static.crates.io/crates/tinycrate/tinycrate-1.0.0.crate"

    def test_metadata_expands_the_commit_into_version_and_filename(self):
        entry = generated_sources.metadata_for("oo7", self.package_dir)
        self.assertEqual(entry["version"], "0.7.0~beta^1.e91b98a")
        self.assertEqual(entry["filename"], f"{self.TOP}-vendored.tar.xz")
        self.assertIn(self.ARCHIVE_URL, entry["generate"]["input"])

    def test_an_unpinned_commit_fails_before_any_download(self):
        self.write_oo7_spec("0" * 40)
        with patch.object(generated_sources_vendored, "_fetch") as fetch:
            with self.assertRaisesRegex(RuntimeError, "no pinned input SHA-512 for oo7"):
                generated_sources.generate("oo7", self.package_dir, self.out_dir)
        fetch.assert_not_called()

    def test_a_short_commit_is_refused(self):
        self.write_oo7_spec("e91b98a")
        with self.assertRaisesRegex(ValueError, "full SHA-1"):
            generated_sources.metadata_for("oo7", self.package_dir)

    def test_the_pinned_archive_and_its_locked_crates_are_vendored(self):
        fetch = UrlopenRecorder({self.ARCHIVE_URL: self.archive, self.crate_url: self.crate})
        with patch.object(urllib.request, "urlopen", fetch), \
                patch.dict(generated_sources.OO7_INPUT_SHA512, {self.COMMIT: sha512(self.archive)}):
            target = generated_sources.generate("oo7", self.package_dir, self.out_dir)
        self.assertEqual(target.name, f"{self.TOP}-vendored.tar.xz")
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(target.read_bytes()))) as archive:
            self.assertIn(f"{self.TOP}/vendor/tinycrate-1.0.0/src/lib.rs", archive.getnames())


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



class UpstreamReachabilityTests(PackageDirMixin, unittest.TestCase):
    """Only a proven transport outage becomes EXIT_UPSTREAM_UNREACHABLE.

    source_pipeline maps that exit, and nothing else, to "unavailable"; a moved
    tag, an input mismatch or an unknown git failure must stay an ordinary,
    fatal exit (utah-packages#875).
    """

    FFMPEG_DOWN = (
        "fatal: unable to access 'https://git.ffmpeg.org/rtmpdump.git/': "
        "Failed to connect to git.ffmpeg.org port 443 after 130000 ms: Connection timed out\n"
    )

    def run_main(self, generate_side_effect):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["generated_sources.py", "rtmpdump", str(self.package_dir), str(self.out_dir)]
        with patch.object(sys, "argv", argv), patch.object(generated_sources, "generate", side_effect=generate_side_effect), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = generated_sources.main()
        return code, stderr.getvalue()

    def test_git_transport_failures_are_classified_as_unreachable(self):
        for stderr in (
            self.FFMPEG_DOWN,
            "fatal: unable to access 'https://x/': Could not resolve host: x\n",
            "error: RPC failed; curl 56 GnuTLS recv error (-54)\nfatal: early EOF\n",
            "fatal: unable to access 'https://x/': The requested URL returned error: 503\n",
        ):
            with self.subTest(stderr=stderr):
                self.assertTrue(generated_sources.git_transport_failure(stderr))

    def test_permanent_git_failures_are_not_unreachable(self):
        for stderr in (
            "fatal: couldn't find remote ref refs/tags/v2.6\n",
            "remote: Repository not found.\nfatal: repository 'https://x/' not found\n",
            "fatal: unable to access 'https://x/': The requested URL returned error: 404\n",
            "fatal: unable to access 'https://x/': server certificate verification failed\n",
            "fatal: Authentication failed for 'https://x/'\n",
            "fatal: '/nowhere' does not appear to be a git repository\n",
        ):
            with self.subTest(stderr=stderr):
                self.assertFalse(generated_sources.git_transport_failure(stderr))

    def test_an_unreachable_git_host_raises_upstream_unreachable(self):
        self.write_spec("rtmpdump.spec", "2.6")
        self.out_dir.mkdir(parents=True)

        def run(command, **kwargs):
            if "fetch" in command:
                raise subprocess.CalledProcessError(128, command, output="", stderr=self.FFMPEG_DOWN)

        with patch.object(subprocess, "run", side_effect=run):
            with self.assertRaisesRegex(generated_sources.UpstreamUnreachable, "git.ffmpeg.org"):
                generated_sources.generate("rtmpdump", self.package_dir, self.out_dir)

    def test_a_stalled_git_host_raises_upstream_unreachable(self):
        self.write_spec("rtmpdump.spec", "2.6")
        self.out_dir.mkdir(parents=True)

        def run(command, **kwargs):
            if "fetch" in command:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        with patch.object(subprocess, "run", side_effect=run):
            with self.assertRaises(generated_sources.UpstreamUnreachable):
                generated_sources.generate("rtmpdump", self.package_dir, self.out_dir)

    def test_an_unknown_git_failure_stays_a_plain_error(self):
        self.write_spec("rtmpdump.spec", "2.6")
        missing = self.tmp / "no-such-repository"
        entry = {"remote": str(missing), "tag": "v{version}", "compression": "gz",
                 "commits": {"2.6": "f" * 40}}
        with patch.dict(generated_sources.GIT_ARCHIVE_SOURCES, {"rtmpdump": entry}):
            with self.assertRaises(subprocess.CalledProcessError):
                generated_sources.generate("rtmpdump", self.package_dir, self.out_dir)

    def test_http_fetch_outage_is_unreachable_but_a_404_is_not(self):
        outage = urllib.error.URLError(ConnectionRefusedError("connection refused"))
        with patch.object(urllib.request, "urlopen", side_effect=outage):
            with self.assertRaises(generated_sources.UpstreamUnreachable):
                generated_sources._fetch("https://down.example/x")
        gone = urllib.error.HTTPError("https://gone.example/x", 404, "Not Found", {}, None)
        with patch.object(urllib.request, "urlopen", side_effect=gone):
            with self.assertRaises(urllib.error.HTTPError):
                generated_sources._fetch("https://gone.example/x")

    def test_main_exits_75_only_for_an_unreachable_upstream(self):
        code, stderr = self.run_main(generated_sources.UpstreamUnreachable("git could not reach x"))
        self.assertEqual(code, generated_sources.EXIT_UPSTREAM_UNREACHABLE)
        self.assertEqual(code, 75)
        self.assertIn("upstream unavailable", stderr)

    def test_main_propagates_integrity_failures(self):
        for error in (
            RuntimeError("tag v2.6 moved: expected aaaa, got bbbb"),
            RuntimeError("input archive mismatch for https://x: expected aa, got bb"),
            subprocess.CalledProcessError(128, ["git", "fetch"]),
        ):
            with self.subTest(error=str(error)):
                with self.assertRaises(type(error)):
                    self.run_main(error)


if __name__ == "__main__":
    unittest.main()
