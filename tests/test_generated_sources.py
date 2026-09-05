#!/usr/bin/env python3
"""Unit tests for the deterministic generated-Source0 transformations.

These cover the pure transformation logic only; the end-to-end generation
runs happen on the lab's remote Argo cluster (the execution-environment
policy forbids local generation containers), and bootstrap's prove_generated
double-run gate covers the network path.
"""

import gzip
import io
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


class GeneratedMetadataTests(unittest.TestCase):
    def test_gcc_filename_expands_spec_macros(self):
        metadata = generated_sources.metadata_for("gcc", ROOT / "packages" / "gcc")
        self.assertEqual(metadata["filename"], "gcc-16.2.1-20260819.tar.xz")
        self.assertEqual(metadata["version"], "16.2.1")
        self.assertEqual(metadata["generate"]["script"], "tools/generated_sources.py")

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


if __name__ == "__main__":
    unittest.main()
