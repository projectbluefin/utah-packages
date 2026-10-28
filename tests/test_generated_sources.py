#!/usr/bin/env python3
"""Unit tests for the deterministic generated-Source0 transformations.

These cover the pure transformation logic only; the end-to-end generation
runs happen on the lab's remote Argo cluster (the execution-environment
policy forbids local generation containers), and bootstrap's prove_generated
double-run gate covers the network path.
"""

import gzip
import io
import json
import lzma
from pathlib import Path
import tarfile
import unittest
from unittest.mock import patch

from tools import generated_sources


ROOT = Path(__file__).resolve().parent.parent


def build_input_archive(version: str) -> bytes:
    """A synthetic media-driver tag archive carrying the strip.py target set."""
    top = f"media-driver-intel-media-{version}"
    members = {
        f"{top}/README.md": b"readme",
        f"{top}/media_driver/agnostic/gen9_kbl/codec/kernel/kernelexport.c": b"nonfree",
        f"{top}/media_driver/agnostic/gen9_kbl/codec/kernel/hw/manager.c": b"nonfree",
        f"{top}/media_driver/agnostic/common/codec/kernel_not_gen.c": b"kept: no gen in path of basename kernel",
        f"{top}/media_driver/agnostic/gen12/codec/cm_gpucopy_kernel": b"nonfree",
        f"{top}/media_driver/agnostic/gen12/codec/cm_gpucopy_kernel_75.c": b"nonfree",
        f"{top}/media_driver/linux/common/cmrt_kernel": b"nonfree",
        f"{top}/media_driver/linux/common/cmrt_kernel.cpp": b"kept: suffix differs",
        f"{top}/media_driver/agnostic/common/media_interfaces.cpp": b"kept",
    }
    directories = {top}
    for name in members:
        parts = name.split("/")
        for depth in range(1, len(parts) - 1):
            directories.add("/".join(parts[: depth + 1]))
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for directory in sorted(directories):
                dirinfo = tarfile.TarInfo(directory)
                dirinfo.type = tarfile.DIRTYPE
                dirinfo.mtime = 1782716737
                dirinfo.uid, dirinfo.gid = 1234, 1234
                dirinfo.uname = dirinfo.gname = "fanys"
                tar.addfile(dirinfo)
            for name in sorted(members):
                info = tarfile.TarInfo(name)
                info.size = len(members[name])
                info.mtime = 1782716737
                info.uid, info.gid = 1234, 1234
                info.uname = info.gname = "fanys"
                tar.addfile(info, io.BytesIO(members[name]))
    return buffer.getvalue()


def read_archive(payload: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        return {
            member.name: tar.extractfile(member).read()
            for member in tar.getmembers()
            if member.isreg()
        }


class IntelMediaDriverFreeTransformTests(unittest.TestCase):
    VERSION = "26.2.4"

    def test_strips_exactly_the_strip_py_removal_set(self):
        result = read_archive(generated_sources._imd_transform(build_input_archive(self.VERSION), self.VERSION))
        names = set(result)
        self.assertNotIn(f"media-driver-intel-media-{self.VERSION}/media_driver/agnostic/gen9_kbl/codec/kernel/kernelexport.c", names)
        self.assertNotIn(f"media-driver-intel-media-{self.VERSION}/media_driver/agnostic/gen12/codec/cm_gpucopy_kernel_75.c", names)
        self.assertNotIn(f"media-driver-intel-media-{self.VERSION}/media_driver/linux/common/cmrt_kernel", names)
        self.assertIn(f"media-driver-intel-media-{self.VERSION}/media_driver/linux/common/cmrt_kernel.cpp", names)
        self.assertIn(f"media-driver-intel-media-{self.VERSION}/media_driver/agnostic/common/media_interfaces.cpp", names)
        self.assertEqual(
            result[f"media-driver-intel-media-{self.VERSION}/README.md"], b"readme"
        )

    def test_transform_is_byte_reproducible(self):
        archive = build_input_archive(self.VERSION)
        first = generated_sources._imd_transform(archive, self.VERSION)
        second = generated_sources._imd_transform(archive, self.VERSION)
        self.assertEqual(first, second)

    def test_transform_normalizes_ownership_and_gzip_header(self):
        result = generated_sources._imd_transform(build_input_archive(self.VERSION), self.VERSION)
        self.assertEqual(result[4:8], b"\x00\x00\x00\x00")  # gzip MTIME
        with tarfile.open(fileobj=io.BytesIO(result), mode="r:gz") as tar:
            for member in tar.getmembers():
                self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))

    def test_members_are_sorted_by_name(self):
        result = generated_sources._imd_transform(build_input_archive(self.VERSION), self.VERSION)
        with tarfile.open(fileobj=io.BytesIO(result), mode="r:gz") as tar:
            names = tar.getnames()
        self.assertEqual(names, sorted(names))


def build_gpm_archive(version: str) -> bytes:
    """A synthetic upstream gpm .tar.lzma carrying doc/specs."""
    top = f"gpm-{version}"
    members = {
        f"{top}/README": b"readme",
        f"{top}/doc/gpm.texinfo": b"kept",
        f"{top}/doc/specs/ps2.pdf": b"unclear licence",
        f"{top}/doc/specs-not/kept.txt": b"kept: only doc/specs itself goes",
        f"{top}/src/daemon/gpm.c": b"kept",
    }
    directories = {top, f"{top}/doc", f"{top}/doc/specs", f"{top}/doc/specs-not", f"{top}/src", f"{top}/src/daemon"}
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for name in sorted(directories, reverse=True):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mtime, info.uid, info.gid, info.uname, info.gname = 1351286460, 1000, 1000, "jcapik", "jcapik"
            tar.addfile(info)
        for name in sorted(members, reverse=True):
            info = tarfile.TarInfo(name)
            info.size = len(members[name])
            info.mtime, info.uid, info.gid, info.uname, info.gname = 1351286460, 1000, 1000, "jcapik", "jcapik"
            tar.addfile(info, io.BytesIO(members[name]))
    return lzma.compress(raw.getvalue(), format=lzma.FORMAT_ALONE)


class GpmTransformTests(unittest.TestCase):
    VERSION = "1.20.7"

    def members(self, payload: bytes) -> list[tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as tar:
            return tar.getmembers()

    def test_removes_exactly_doc_specs(self):
        result = generated_sources._gpm_transform(build_gpm_archive(self.VERSION), self.VERSION)
        names = {member.name for member in self.members(result)}
        self.assertNotIn("gpm-1.20.7/doc/specs", names)
        self.assertNotIn("gpm-1.20.7/doc/specs/ps2.pdf", names)
        self.assertIn("gpm-1.20.7/doc/specs-not/kept.txt", names)
        self.assertIn("gpm-1.20.7/doc/gpm.texinfo", names)
        self.assertIn("gpm-1.20.7/src/daemon/gpm.c", names)

    def test_transform_is_byte_reproducible_sorted_and_ownerless(self):
        archive = build_gpm_archive(self.VERSION)
        first = generated_sources._gpm_transform(archive, self.VERSION)
        self.assertEqual(first, generated_sources._gpm_transform(archive, self.VERSION))
        members = self.members(first)
        self.assertEqual([m.name for m in members], sorted(m.name for m in members))
        for member in members:
            self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))
            self.assertEqual(member.mtime, 1351286460)

    def test_metadata_names_the_recipe_source_and_pinned_input(self):
        metadata = generated_sources.metadata_for("gpm", ROOT / "packages" / "gpm")
        self.assertEqual(metadata["filename"], "gpm-1.20.7.tar.xz")
        self.assertIn("gpm-1.20.7.tar.lzma", metadata["generate"]["input"])
        self.assertIn("1.20.7", generated_sources.GPM_INPUT_SHA512)


def build_openal_soft_archive(version: str) -> bytes:
    """A synthetic upstream openal-soft .tar.bz2 carrying fmt and .def files."""
    top = f"openal-soft-{version}"
    members = {
        f"{top}/CMakeLists.txt": b"kept",
        f"{top}/fmt-11.1.1/src/format.cc": b"bundled",
        f"{top}/fmt-11.1.1/include/fmt/core.h": b"bundled",
        f"{top}/fmt-old/doc.txt": b"bundled: any fmt- prefix goes",
        f"{top}/utils/CIAIR.def": b"non-free dataset",
        f"{top}/utils/presets.txt": b"kept: only .def goes",
        f"{top}/utils/nested/extra.def": b"kept: the recipe glob is not recursive",
        f"{top}/utilsdef/kept.def": b"kept: utilsdef is not utils",
    }
    directories = {top, f"{top}/fmt-11.1.1", f"{top}/fmt-11.1.1/src",
                   f"{top}/fmt-11.1.1/include", f"{top}/fmt-11.1.1/include/fmt",
                   f"{top}/fmt-old", f"{top}/utils", f"{top}/utils/nested",
                   f"{top}/utilsdef"}
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:bz2") as tar:
        for name in sorted(directories, reverse=True):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mtime, info.uid, info.gid, info.uname, info.gname = 1748353371, 1000, 1000, "kcat", "kcat"
            tar.addfile(info)
        for name in sorted(members, reverse=True):
            info = tarfile.TarInfo(name)
            info.size = len(members[name])
            info.mtime, info.uid, info.gid, info.uname, info.gname = 1748353371, 1000, 1000, "kcat", "kcat"
            tar.addfile(info, io.BytesIO(members[name]))
    return raw.getvalue()


class OpenALSoftTransformTests(unittest.TestCase):
    VERSION = "1.24.2"

    def members(self, payload: bytes) -> list[tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as tar:
            return tar.getmembers()

    def test_removes_exactly_fmt_and_top_level_utils_def(self):
        result = generated_sources._openal_soft_transform(build_openal_soft_archive(self.VERSION), self.VERSION)
        names = {member.name for member in self.members(result)}
        self.assertNotIn("openal-soft-1.24.2/fmt-11.1.1", names)
        self.assertNotIn("openal-soft-1.24.2/fmt-11.1.1/src/format.cc", names)
        self.assertNotIn("openal-soft-1.24.2/fmt-old/doc.txt", names)
        self.assertNotIn("openal-soft-1.24.2/utils/CIAIR.def", names)
        self.assertIn("openal-soft-1.24.2/CMakeLists.txt", names)
        self.assertIn("openal-soft-1.24.2/utils/presets.txt", names)
        self.assertIn("openal-soft-1.24.2/utils/nested/extra.def", names)
        self.assertIn("openal-soft-1.24.2/utilsdef/kept.def", names)

    def test_transform_is_byte_reproducible_sorted_and_ownerless(self):
        archive = build_openal_soft_archive(self.VERSION)
        first = generated_sources._openal_soft_transform(archive, self.VERSION)
        self.assertEqual(first, generated_sources._openal_soft_transform(archive, self.VERSION))
        members = self.members(first)
        self.assertEqual([m.name for m in members], sorted(m.name for m in members))
        for member in members:
            self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))
            self.assertEqual(member.mtime, 1748353371)

    def test_metadata_names_the_recipe_source_and_pinned_input(self):
        metadata = generated_sources.metadata_for("openal-soft", ROOT / "packages" / "openal-soft")
        self.assertEqual(metadata["filename"], "openal-soft-1.24.2-clean.tar.xz")
        self.assertIn("openal-soft-1.24.2.tar.bz2", metadata["generate"]["input"])
        self.assertIn("1.24.2", generated_sources.OPENAL_SOFT_INPUT_SHA512)


def build_hplip_archive(version: str) -> bytes:
    """A synthetic upstream hplip .tar.gz carrying `locatedriver`."""
    top = f"hplip-{version}"
    members = {
        f"{top}/Makefile.am": b"kept",
        f"{top}/locatedriver": b"license-encumbered helper",
        f"{top}/prnt/hpcups/hpcups.cpp": b"kept",
    }
    directories = {top, f"{top}/prnt", f"{top}/prnt/hpcups"}
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for name in sorted(directories, reverse=True):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mtime, info.uid, info.gid, info.uname, info.gname = 1748479065, 1000, 1000, "pbuilder", "pbuilder"
                tar.addfile(info)
            for name in sorted(members, reverse=True):
                info = tarfile.TarInfo(name)
                info.size = len(members[name])
                info.mtime, info.uid, info.gid, info.uname, info.gname = 1748479065, 1000, 1000, "pbuilder", "pbuilder"
                tar.addfile(info, io.BytesIO(members[name]))
    return buffer.getvalue()


class HplipTransformTests(unittest.TestCase):
    VERSION = "3.26.6"

    def members(self, payload: bytes) -> list[tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
            return tar.getmembers()

    def test_removes_exactly_locatedriver(self):
        result = generated_sources._hplip_transform(build_hplip_archive(self.VERSION), self.VERSION)
        names = {member.name for member in self.members(result)}
        self.assertNotIn("hplip-3.26.6/locatedriver", names)
        self.assertIn("hplip-3.26.6/Makefile.am", names)
        self.assertIn("hplip-3.26.6/prnt/hpcups/hpcups.cpp", names)

    def test_transform_is_byte_reproducible_sorted_and_ownerless(self):
        archive = build_hplip_archive(self.VERSION)
        first = generated_sources._hplip_transform(archive, self.VERSION)
        self.assertEqual(first, generated_sources._hplip_transform(archive, self.VERSION))
        members = self.members(first)
        self.assertEqual([m.name for m in members], sorted(m.name for m in members))
        for member in members:
            self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))
            self.assertEqual(member.mtime, 1748479065)

    def test_metadata_names_the_recipe_source_and_pinned_input(self):
        metadata = generated_sources.metadata_for("hplip", ROOT / "packages" / "hplip")
        self.assertEqual(metadata["filename"], "hplip-3.26.6-repack.tar.gz")
        self.assertIn("hplip-3.26.6.tar.gz", metadata["generate"]["input"])
        self.assertIn("3.26.6", generated_sources.HPLIP_INPUT_SHA512)


def build_fpaste_archive(prefix: str = "fpaste") -> bytes:
    """A synthetic Codeberg tag archive: `fpaste/` prefix, pax global comment, .gitignore."""
    members = {
        f"{prefix}/.gitignore": b"*.swp\n",
        f"{prefix}/Makefile": b"kept",
        f"{prefix}/fpaste": b"#!/usr/bin/python3\n",
        f"{prefix}/completions/bash/fpaste.bash": b"kept",
    }
    directories = {prefix, f"{prefix}/completions", f"{prefix}/completions/bash"}
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": "84a795a0abd225edb9eaf3d84f1dc80e5418c361"}) as tar:
            for name in sorted(directories, reverse=True):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mode, info.mtime, info.uname, info.gname = 0o775, 1723405207, "root", "root"
                tar.addfile(info)
            for name in sorted(members, reverse=True):
                info = tarfile.TarInfo(name)
                info.size = len(members[name])
                info.mode = 0o775 if name.endswith("/fpaste") else 0o664
                info.mtime, info.uname, info.gname = 1723405207, "root", "root"
                tar.addfile(info, io.BytesIO(members[name]))
    return buffer.getvalue()


class FpasteTransformTests(unittest.TestCase):
    VERSION = "0.5.0.0"

    def members(self, payload: bytes) -> list[tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
            return tar.getmembers()

    def test_moves_the_prefix_and_drops_only_gitignore(self):
        result = generated_sources._fpaste_transform(build_fpaste_archive(), self.VERSION)
        names = {member.name for member in self.members(result)}
        self.assertEqual(names, {
            "fpaste-0.5.0.0",
            "fpaste-0.5.0.0/Makefile",
            "fpaste-0.5.0.0/fpaste",
            "fpaste-0.5.0.0/completions",
            "fpaste-0.5.0.0/completions/bash",
            "fpaste-0.5.0.0/completions/bash/fpaste.bash",
        })

    def test_transform_is_byte_reproducible_sorted_ownerless_and_commentless(self):
        archive = build_fpaste_archive()
        first = generated_sources._fpaste_transform(archive, self.VERSION)
        self.assertEqual(first, generated_sources._fpaste_transform(archive, self.VERSION))
        self.assertEqual(first[4:8], b"\0\0\0\0")
        with tarfile.open(fileobj=io.BytesIO(first), mode="r:gz") as tar:
            members = tar.getmembers()
            self.assertEqual(tar.pax_headers, {})
        self.assertEqual([m.name for m in members], sorted(m.name for m in members))
        for member in members:
            self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))
            self.assertEqual(member.mtime, 1723405207)
            self.assertNotIn("comment", member.pax_headers)
        self.assertEqual({m.name: m.mode for m in members}["fpaste-0.5.0.0/fpaste"], 0o775)

    def test_a_member_outside_the_tag_prefix_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "outside fpaste/"):
            generated_sources._fpaste_transform(build_fpaste_archive("fpaste-0.5.0.0"), self.VERSION)

    def test_metadata_names_the_recipe_source_and_pinned_input(self):
        metadata = generated_sources.metadata_for("fpaste", ROOT / "packages" / "fpaste")
        self.assertEqual(metadata["filename"], "fpaste-0.5.0.0.tar.gz")
        self.assertIn("codeberg.org/sanjay_ankur/fpaste/archive/0.5.0.0.tar.gz", metadata["generate"]["input"])
        self.assertIn("0.5.0.0", generated_sources.FPASTE_INPUT_SHA512)


def build_freerdp_archive(version: str) -> bytes:
    """A synthetic upstream FreeRDP .tar.gz carrying unicode_builtin.c."""
    top = f"FreeRDP-{version}"
    members = {
        f"{top}/CMakeLists.txt": b"kept",
        f"{top}/winpr/libwinpr/crt/unicode.c": b"kept: basename differs",
        f"{top}/winpr/libwinpr/crt/unicode_builtin.c": b"license-encumbered",
    }
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT,
                           pax_headers={"comment": "synthetic global header"}) as tar:
            for name in sorted(members):
                info = tarfile.TarInfo(name)
                info.size = len(members[name])
                info.mtime = 1760900000
                tar.addfile(info, io.BytesIO(members[name]))
    return buffer.getvalue()


class FreerdpTransformTests(unittest.TestCase):
    VERSION = "3.32.2"

    def test_removes_exactly_unicode_builtin_c_and_the_global_header(self):
        result = generated_sources._freerdp_transform(build_freerdp_archive(self.VERSION), self.VERSION)
        names = set(read_archive(result))
        self.assertNotIn("FreeRDP-3.32.2/winpr/libwinpr/crt/unicode_builtin.c", names)
        self.assertIn("FreeRDP-3.32.2/CMakeLists.txt", names)
        self.assertIn("FreeRDP-3.32.2/winpr/libwinpr/crt/unicode.c", names)

    def test_transform_is_byte_reproducible(self):
        archive = build_freerdp_archive(self.VERSION)
        first = generated_sources._freerdp_transform(archive, self.VERSION)
        self.assertEqual(first, generated_sources._freerdp_transform(archive, self.VERSION))

    def test_a_missing_doomed_member_fails_closed(self):
        top = f"FreeRDP-{self.VERSION}"
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                info = tarfile.TarInfo(f"{top}/CMakeLists.txt")
                info.size = 4
                tar.addfile(info, io.BytesIO(b"kept"))
        with self.assertRaisesRegex(RuntimeError, "expected exactly one"):
            generated_sources._freerdp_transform(buffer.getvalue(), self.VERSION)

    def test_metadata_names_the_recipe_source_and_pinned_input(self):
        metadata = generated_sources.metadata_for("freerdp", ROOT / "packages" / "freerdp")
        self.assertEqual(metadata["filename"], "FreeRDP-3.32.2-repack.tar.gz")
        self.assertIn("FreeRDP-3.32.2.tar.gz", metadata["generate"]["input"])
        self.assertIn("3.32.2", generated_sources.FREERDP_INPUT_SHA512)


class BluefinArtworkTransformTests(unittest.TestCase):
    COMMIT = "9ab493bf1fb3ae41594b6bb0a2c5f2350d81de01"
    FILES = {
        "LICENSE": b"Apache License",
        "assets/vector/logos/bluefin/bluefin-logo-light.svg": b"<svg fill='#000'/>",
        "assets/vector/logos/bluefin/bluefin-logo-dark.svg": b"<svg fill='#fff'/>",
    }

    def members(self, payload: bytes) -> list[tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as tar:
            return tar.getmembers()

    def test_files_are_packed_flat_under_the_short_commit(self):
        result = generated_sources._bluefin_artwork_transform(self.FILES, self.COMMIT)
        with tarfile.open(fileobj=io.BytesIO(result), mode="r:xz") as tar:
            self.assertEqual(tar.getnames(), [
                "bluefin-artwork-logos-9ab493b",
                "bluefin-artwork-logos-9ab493b/LICENSE",
                "bluefin-artwork-logos-9ab493b/bluefin-logo-dark.svg",
                "bluefin-artwork-logos-9ab493b/bluefin-logo-light.svg",
            ])
            self.assertEqual(tar.extractfile("bluefin-artwork-logos-9ab493b/bluefin-logo-dark.svg").read(),
                             b"<svg fill='#fff'/>")

    def test_transform_is_byte_reproducible_sorted_and_ownerless(self):
        first = generated_sources._bluefin_artwork_transform(self.FILES, self.COMMIT)
        reordered = dict(reversed(list(self.FILES.items())))
        self.assertEqual(first, generated_sources._bluefin_artwork_transform(reordered, self.COMMIT))
        for member in self.members(first):
            self.assertEqual((member.uid, member.gid, member.uname, member.gname, member.mtime), (0, 0, "", "", 0))

    def test_two_files_with_one_basename_fail_closed(self):
        files = {"a/logo.svg": b"1", "b/logo.svg": b"2"}
        with self.assertRaisesRegex(ValueError, "flatten to the same name"):
            generated_sources._bluefin_artwork_transform(files, self.COMMIT)

    def test_metadata_names_the_recipe_source_and_every_pinned_file(self):
        metadata = generated_sources.metadata_for("bluefin-artwork-logos", ROOT / "packages" / "bluefin-artwork-logos")
        self.assertEqual(metadata["filename"], "bluefin-artwork-logos-9ab493b.tar.xz")
        pins = generated_sources.BLUEFIN_ARTWORK_FILES[self.COMMIT]
        for path in pins:
            self.assertIn(f"projectbluefin/artwork/{self.COMMIT}/{path}", metadata["generate"]["input"])
        self.assertEqual(set(self.FILES), set(pins))

    def test_the_lock_entry_matches_the_metadata(self):
        lock = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        entry = next(p for p in lock["packages"] if p["name"] == "bluefin-artwork-logos")
        metadata = generated_sources.metadata_for("bluefin-artwork-logos", ROOT / "packages" / "bluefin-artwork-logos")
        self.assertEqual({key: entry[key] for key in metadata}, metadata)
        self.assertIn(f"SHA512 ({entry['filename']}) = {entry['sha512']}",
                      (ROOT / "packages" / "bluefin-artwork-logos" / "sources").read_text())

    def test_gnome_control_center_points_about_at_the_installed_logos(self):
        recipe = (ROOT / "packages" / "bluefin-artwork-logos" / "bluefin-artwork-logos.spec").read_text()
        consumer = (ROOT / "packages" / "gnome-control-center" / "gnome-control-center.spec").read_text()
        self.assertIn("Requires: bluefin-artwork-logos\n", consumer)
        self.assertNotIn("pixmaps/fedora", consumer)
        for option, style in (("distributor_logo", "light"), ("dark_mode_distributor_logo", "dark")):
            self.assertIn(f"-D{option}=%{{_datadir}}/bluefin-artwork-logos/bluefin-logo-{style}.png", consumer)
            self.assertIn(f"bluefin-logo-{style}.png", recipe)


class GeneratedMetadataTests(unittest.TestCase):
    def test_intel_media_metadata_uses_spec_version(self):
        metadata = generated_sources.metadata_for(
            "intel-media-driver-free", ROOT / "packages" / "intel-media-driver-free"
        )
        self.assertEqual(metadata["filename"], "intel-media-26.2.4-free.tar.gz")

    def test_tailscale_metadata_pins_the_tag_commit(self):
        metadata = generated_sources.metadata_for("tailscale", ROOT / "packages" / "tailscale")
        self.assertEqual(metadata["filename"], "tailscale-1.98.8-vendored.tar.xz")
        self.assertIn("05a91829316e055517a1e84f7b00016846ef4107", metadata["generate"]["input"])

    def test_unknown_package_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no generated source resolver"):
            generated_sources.metadata_for("zsh", ROOT / "packages" / "zsh")

    def test_no_generated_metadata_mentions_fedora_infrastructure(self):
        for name in generated_sources.METADATA:
            metadata = generated_sources.metadata_for(name, ROOT / "packages" / name)
            self.assertNotIn("fedoraproject.org", str(metadata))


class TailscaleToolchainGapTests(unittest.TestCase):
    def test_generation_fails_closed_without_a_go_toolchain(self):
        with patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Go toolchain"):
                generated_sources.generate("tailscale", ROOT / "packages" / "tailscale", Path("/tmp"))


def _targz(members: dict[str, bytes], mtime: int = 1700000000) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


class PydanticCoreVendorTests(unittest.TestCase):
    VERSION = "9.9.9"

    def fixture(self):
        import hashlib

        crate = _targz({"tinycrate-1.0.0/Cargo.toml": b"[package]", "tinycrate-1.0.0/src/lib.rs": b"//"})
        checksum = hashlib.sha256(crate).hexdigest()
        lock = (
            'version = 4\n\n[[package]]\nname = "pydantic-core"\nversion = "9.9.9"\n\n'
            '[[package]]\nname = "tinycrate"\nversion = "1.0.0"\n'
            'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
            f'checksum = "{checksum}"\n'
        )
        top = f"pydantic_core-{self.VERSION}"
        sdist = _targz({f"{top}/Cargo.lock": lock.encode(), f"{top}/Cargo.toml": b"[package]"})
        return sdist, {("tinycrate", "1.0.0"): crate}, lock

    def test_lock_parsing_skips_the_workspace_root(self):
        _, _, lock = self.fixture()
        crates = generated_sources.cargo_lock_packages(lock)
        self.assertEqual([(c["name"], c["version"]) for c in crates], [("tinycrate", "1.0.0")])

    def test_lock_parsing_refuses_git_sources(self):
        lock = '[[package]]\nname = "x"\nversion = "1"\nsource = "git+https://example.com/x"\n'
        with self.assertRaisesRegex(RuntimeError, "not crates.io"):
            generated_sources.cargo_lock_packages(lock)

    def test_vendor_layout_and_checksum_file(self):
        import json
        import lzma

        sdist, crates, _ = self.fixture()
        out = generated_sources._pydantic_core_transform(sdist, self.VERSION, crates)
        with tarfile.open(fileobj=io.BytesIO(lzma.decompress(out))) as archive:
            names = archive.getnames()
            vendored = f"pydantic_core-{self.VERSION}/vendor/tinycrate-1.0.0"
            self.assertIn(f"{vendored}/src/lib.rs", names)
            checksum = json.loads(archive.extractfile(f"{vendored}/.cargo-checksum.json").read())
        self.assertEqual(set(checksum["files"]), {"Cargo.toml", "src/lib.rs"})

    def test_transform_is_byte_reproducible(self):
        sdist, crates, _ = self.fixture()
        self.assertEqual(
            generated_sources._pydantic_core_transform(sdist, self.VERSION, crates),
            generated_sources._pydantic_core_transform(sdist, self.VERSION, crates),
        )

    def test_a_substituted_crate_fails_closed(self):
        sdist, crates, _ = self.fixture()
        crates[("tinycrate", "1.0.0")] = _targz({"tinycrate-1.0.0/Cargo.toml": b"evil"})
        with self.assertRaisesRegex(RuntimeError, "expected sha256"):
            generated_sources._pydantic_core_transform(sdist, self.VERSION, crates)


if __name__ == "__main__":
    unittest.main()
