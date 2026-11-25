"""Generators that rewrite a single upstream release archive.

Each strips or normalizes an upstream tarball (or sdist plus vendored crates)
into the Source0 its recipe expects. tools/generated_sources.py registers
them and re-exports every name defined here.
"""

from __future__ import annotations

import fnmatch
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path
import subprocess
import tarfile

from tools.generated_sources_common import (
    FPASTE_INPUT_SHA512,
    GPM_INPUT_SHA512,
    HPLIP_INPUT_SHA512,
    INTEL_MEDIA_INPUT_SHA512,
    OPENAL_SOFT_INPUT_SHA512,
    PYDANTIC_CORE_INPUT_SHA512,
    SCRIPT_PATH,
    SEVENZIP_INPUT_SHA512,
    _fetch,
    spec_version,
)


def _xz_compress_stream(chunks, sink) -> None:
    """Single-stream xz, equivalent to `xz -9e` single-threaded output."""
    compressor = lzma.LZMACompressor(
        format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=9 | lzma.PRESET_EXTREME
    )
    for chunk in chunks:
        data = compressor.compress(chunk)
        if data:
            sink.write(data)
    sink.write(compressor.flush())


# --- intel-media-driver-free ------------------------------------------------


def _imd_stripped(relpath: str) -> bool:
    """The exact removal set of packages/intel-media-driver-free/strip.py."""
    base = relpath.rstrip("/").rsplit("/", 1)[-1]
    if base == "kernel" and "gen" in relpath:
        return True
    if fnmatch.fnmatch(base, "cm_gpucopy_kernel*"):
        return True
    return base == "cmrt_kernel"


def _imd_transform(archive: bytes, version: str) -> bytes:
    """Repack the tag archive without the non-free kernel files.

    Streams tar members straight from the verified input archive, so member
    modes and mtimes come from the archive itself and nothing leaks from the
    local filesystem (extraction order, uids, or wall-clock time). Members
    are emitted sorted by name with ownership zeroed and the gzip header
    carries no name or timestamp, making the output byte-reproducible.
    """
    top = f"media-driver-intel-media-{version}"
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        members = source.getmembers()

        def relative(name: str) -> str:
            stripped = name.rstrip("/")
            return stripped[len(top) + 1:] if stripped.startswith(top + "/") else stripped

        doomed = {m.name.rstrip("/") for m in members if _imd_stripped(relative(m.name)) and relative(m.name)}

        def dropped(name: str) -> bool:
            name = name.rstrip("/")
            return any(name == item or name.startswith(item + "/") for item in doomed)

        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in sorted(members, key=lambda m: m.name):
                if dropped(member.name):
                    continue
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                result.addfile(member, source.extractfile(member) if member.isreg() else None)
        tar_bytes = tar_buf.getvalue()
        proc = subprocess.Popen(
            ["gzip", "-n", "-9"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, _ = proc.communicate(tar_bytes)
        if proc.returncode != 0:
            raise RuntimeError("gzip failed")
        return out


def _imd_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "intel-media-driver-free.spec")
    return {
        "name": "intel-media-driver-free",
        "version": version,
        "filename": f"intel-media-{version}-free.tar.gz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://github.com/intel/media-driver/archive/intel-media-{version}.tar.gz (sha512-pinned)",
            "method": f"remove non-free EU kernel files from the tag archive (strip.py removal set) and repack deterministically as intel-media-{version}-free.tar.gz",
        },
    }


def _imd_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "intel-media-driver-free.spec")
    pin = INTEL_MEDIA_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for intel-media {version}")
    url = f"https://github.com/intel/media-driver/archive/intel-media-{version}.tar.gz"
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"intel-media-{version}-free.tar.gz"
    target.write_bytes(_imd_transform(payload, version))
    return target


# --- gpm ---------------------------------------------------------------------


def _gpm_transform(archive: bytes, version: str) -> bytes:
    """Repack the upstream .tar.lzma without doc/specs, as Fedora's recipe does.

    packages/gpm/gpm.spec documents the transformation above its Source line:
    unpack the upstream tarball, remove doc/specs (PDFs with unclear
    licensing), and recompress as .tar.xz. Fedora's lookaside copy is that
    tarball made by hand, so its bytes cannot be reproduced; this makes the
    same tree deterministically. Members keep the archive's own modes and
    mtimes, are sorted by name with ownership zeroed, and are compressed as a
    single xz stream.
    """
    doomed = f"gpm-{version}/doc/specs"
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(archive)), mode="r:") as source:
        members = sorted(source.getmembers(), key=lambda m: m.name.rstrip("/"))
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in members:
                name = member.name.rstrip("/")
                if name == doomed or name.startswith(doomed + "/"):
                    continue
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                result.addfile(member, source.extractfile(member) if member.isreg() else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _gpm_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "gpm.spec")
    return {
        "name": "gpm",
        "version": version,
        "filename": f"gpm-{version}.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://www.nico.schottelius.org/software/gpm/archives/gpm-{version}.tar.lzma (sha512-pinned)",
            "method": f"remove doc/specs (unclear licensing, per gpm.spec) from the upstream release and repack deterministically as gpm-{version}.tar.xz",
        },
    }


def _gpm_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "gpm.spec")
    pin = GPM_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for gpm {version}")
    url = f"https://www.nico.schottelius.org/software/gpm/archives/gpm-{version}.tar.lzma"
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"gpm-{version}.tar.xz"
    target.write_bytes(_gpm_transform(payload, version))
    return target


# --- openal-soft -----------------------------------------------------------------


def _openal_soft_dropped(name: str, version: str) -> bool:
    """The exact removal set of packages/openal-soft/make_tarball.sh.

    The script deletes the bundled fmt tree (`rm -rf openal-soft-$VERSION/fmt-*/`)
    and the non-free HRTF datasets (`rm -rf openal-soft-$VERSION/utils/*.def`,
    a non-recursive glob, so a .def nested deeper would stay).
    """
    top = f"openal-soft-{version}"
    rel = name.rstrip("/")
    if rel == top or not rel.startswith(top + "/"):
        return False
    rest = rel[len(top) + 1:]
    first, _, remainder = rest.partition("/")
    if first.startswith("fmt-"):
        return True
    return first == "utils" and "/" not in remainder and remainder.endswith(".def")


def _openal_soft_transform(archive: bytes, version: str) -> bytes:
    """Repack the upstream .tar.bz2 without fmt and the non-free datasets.

    Same tree make_tarball.sh produces by hand, made deterministically:
    members keep the archive's own modes and mtimes, are sorted by name with
    ownership zeroed, and are compressed as a single xz stream. Fedora's
    lookaside copy is that tarball made by hand, so its bytes cannot be
    reproduced; the kept 343 files were verified byte-identical against it.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:bz2") as source:
        members = sorted(source.getmembers(), key=lambda m: m.name.rstrip("/"))
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in members:
                if _openal_soft_dropped(member.name, version):
                    continue
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                result.addfile(member, source.extractfile(member) if member.isreg() else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _openal_soft_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "openal-soft.spec")
    return {
        "name": "openal-soft",
        "version": version,
        "filename": f"openal-soft-{version}-clean.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://openal-soft.org/openal-releases/openal-soft-{version}.tar.bz2 (sha512-pinned)",
            "method": f"remove the bundled fmt-*/ tree and utils/*.def datasets (non-free, per make_tarball.sh) from the upstream release and repack deterministically as openal-soft-{version}-clean.tar.xz",
        },
    }


def _openal_soft_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "openal-soft.spec")
    pin = OPENAL_SOFT_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for openal-soft {version}")
    url = f"https://openal-soft.org/openal-releases/openal-soft-{version}.tar.bz2"
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"openal-soft-{version}-clean.tar.xz"
    target.write_bytes(_openal_soft_transform(payload, version))
    return target


# --- 7zip ---------------------------------------------------------------------

SEVENZIP_UPSTREAM_URL = "https://github.com/ip7z/7zip/archive/{version}/7zip-{version}.tar.gz"


def _sevenzip_dropped(name: str, version: str) -> bool:
    """The exact removal set of packages/7zip/strip-rar-support.sh.

    The script runs `rm -rf CPP/7zip/Archive/Rar/`, `rm -f
    CPP/7zip/Compress/Rar*.*`, `rm -f CPP/7zip/Crypto/Rar*.*` and `rm -f
    DOC/unRarLicense.txt`. Both `Rar*.*` globs are non-recursive and need a dot.
    """
    top = f"7zip-{version}"
    rel = name.rstrip("/")
    if not rel.startswith(top + "/"):
        return False
    rest = rel[len(top) + 1:]
    rar = "CPP/7zip/Archive/Rar"
    if rest == rar or rest.startswith(rar + "/"):
        return True
    if rest == "DOC/unRarLicense.txt":
        return True
    for directory in ("CPP/7zip/Compress/", "CPP/7zip/Crypto/"):
        if rest.startswith(directory):
            leaf = rest[len(directory):]
            return "/" not in leaf and fnmatch.fnmatchcase(leaf, "Rar*.*")
    return False


def _sevenzip_transform(archive: bytes, version: str) -> bytes:
    """Repack the upstream .tar.gz without RAR support, as Fedora's recipe does.

    Same tree strip-rar-support.sh produces by hand, made deterministically:
    members keep the archive's own modes and mtimes, are sorted by name with
    ownership zeroed, and are compressed as a single xz stream. The script
    writes zstd, which the standard library cannot produce, so the recipe's
    Source names the .tar.xz instead; rpmbuild unpacks either the same way.
    GitHub's pax_global_header (the commit id) carries no member and is not
    kept.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        members = sorted(source.getmembers(), key=lambda m: m.name.rstrip("/"))
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in members:
                if _sevenzip_dropped(member.name, version):
                    continue
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.pax_headers = {}
                result.addfile(member, source.extractfile(member) if member.isreg() else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _sevenzip_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "7zip.spec")
    return {
        "name": "7zip",
        "version": version,
        "filename": f"7zip-{version}.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{SEVENZIP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove the RAR handler, codecs, crypto and unRarLicense.txt (unRAR license restriction, per strip-rar-support.sh) from the upstream release and repack deterministically as 7zip-{version}.tar.xz",
        },
    }


def _sevenzip_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "7zip.spec")
    pin = SEVENZIP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for 7zip {version}")
    url = SEVENZIP_UPSTREAM_URL.format(version=version)
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"7zip-{version}.tar.xz"
    target.write_bytes(_sevenzip_transform(payload, version))
    return target


# --- jpegxl --------------------------------------------------------------------

JPEGXL_UPSTREAM_URL = "https://github.com/libjxl/libjxl/archive/v{version}/jpegxl-{version}.tar.gz"

# Per release: the SHA-512 of the libjxl tag archive, and for each submodule
# the recipe needs, the commit the tag's gitlink pins (GitHub contents API,
# `repos/libjxl/libjxl/contents/<path>?ref=v<version>`) and the SHA-512 of
# that commit's GitHub archive.
JPEGXL_INPUTS = {
    "0.12.0": {
        "sha512": "71d45123e47588c8028c0e01a7820c7a18d98df05c29b5318ab6858eaff5f249879763907201ba19a93f817c6ef75c393c1974d2a0cc8e461c4e2709ca6fa45f",
        "submodules": {
            "third_party/sjpeg": ("https://github.com/webmproject/sjpeg", "94e0df6d0f8b44228de5be0ff35efb9f946a13c9", "d3e175628fff9e3a2adb300d760a5eb686080eb7681d95215f89c8c94c6ea7b07b74b0c8eed396d01505977e6dbf3a401d1ee5e93ecce2f9e7671042bd12316e"),
            "third_party/skcms": ("https://github.com/google/skcms", "96d9171c94b937a1b5f0293de7309ac16311b722", "63dc75a2898e848ec0c68d06ea5b13e65304088ab205ceef8c5d36aacf233a6478158653f6da0ab417671fa00d08e66bffe593caa351a5802fc1129553e70f43"),
            "testdata": ("https://github.com/libjxl/testdata", "73695d303670c90e4d506ea89d9901b081385089", "8c02a1b7752da9ec93c228436c4bbcdafb5b655e6386a76cf9ccfc4b1c5d4614d9ec3b9931281a57a5348720d4641ff518cb6ed9e06a5dcb0725fd9fda138618"),
        },
    },
}

# update_third_party.sh deletes these from the trees it packs.
JPEGXL_DROPPED = ("third_party/skcms/profiles",)


def _jpegxl_dropped(rel: str) -> bool:
    return any(rel == path or rel.startswith(path + "/") for path in JPEGXL_DROPPED)


def _jpegxl_transform(archive: bytes, submodules: dict[str, tuple[str, bytes]], version: str) -> bytes:
    """Fill the release archive's empty submodule directories.

    `submodules` maps a path inside the release (`third_party/sjpeg`) to the
    commit and the GitHub archive of that commit, whose `<repo>-<commit>/`
    top level is renamed to `libjxl-<version>/<path>/`. Members keep their
    archives' modes and mtimes and are sorted by name with ownership zeroed,
    as one xz stream.
    """
    top = f"libjxl-{version}"
    kept: dict[str, tuple[tarfile.TarInfo, bytes | None]] = {}

    def take(source: tarfile.TarFile, prefix: str, target: str) -> None:
        for member in source:
            name = member.name.rstrip("/")
            if name != prefix and not name.startswith(prefix + "/"):
                continue
            rel = (target + name[len(prefix):]).lstrip("/")
            if _jpegxl_dropped(rel):
                continue
            if not (member.isdir() or member.isreg() or member.issym()):
                raise RuntimeError(f"unexpected member type in {member.name}")
            payload = source.extractfile(member).read() if member.isreg() else None
            kept[f"{top}/{rel}" if rel else top] = (member, payload)

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        take(source, top, "")
    for path, (commit, payload) in sorted(submodules.items()):
        if any(name.startswith(f"{top}/{path}/") for name in kept):
            raise RuntimeError(f"submodule {path} is not empty in the release archive")
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as source:
            first = next(iter(source.getmembers()), None)
            if first is None or not first.name.rstrip("/").endswith(f"-{commit}"):
                raise RuntimeError(f"archive for {path} is not of commit {commit}")
            take(source, first.name.rstrip("/"), path)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        for name in sorted(kept):
            member, payload = kept[name]
            member.name = name
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {}
            result.addfile(member, io.BytesIO(payload) if payload is not None else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _jpegxl_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "jpegxl.spec")
    pins = JPEGXL_INPUTS.get(version, {}).get("submodules", {})
    parts = ", ".join(f"{path} {remote} commit {commit}" for path, (remote, commit, _) in sorted(pins.items()))
    return {
        "name": "jpegxl",
        "version": version,
        "filename": f"jpegxl-{version}.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{JPEGXL_UPSTREAM_URL.format(version=version)} (sha512-pinned); submodule archives (sha512-pinned): {parts}",
            "method": f"fill the release's empty sjpeg, skcms (minus profiles/, per update_third_party.sh) and testdata submodules at the tag's gitlinks and repack deterministically as jpegxl-{version}.tar.xz",
        },
    }


def _jpegxl_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "jpegxl.spec")
    pins = JPEGXL_INPUTS.get(version)
    if pins is None:
        raise RuntimeError(f"no pinned inputs for jpegxl {version}")

    def fetch(url: str, pin: str) -> bytes:
        payload = _fetch(url)
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pin:
            raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
        return payload

    archive = fetch(JPEGXL_UPSTREAM_URL.format(version=version), pins["sha512"])
    submodules = {
        path: (commit, fetch(f"{remote}/archive/{commit}.tar.gz", pin))
        for path, (remote, commit, pin) in pins["submodules"].items()
    }
    target = out_dir / f"jpegxl-{version}.tar.xz"
    target.write_bytes(_jpegxl_transform(archive, submodules, version))
    return target


# --- hyperv-daemons ----------------------------------------------------------

HYPERV_KERNEL_URL = "https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version}.tar.xz"

# kernel.org signs sha256sums.asc, not the archive's SHA-512; the SHA-256
# listed there for each release was checked against these bytes.
HYPERV_KERNEL_INPUT_SHA512 = {
    "7.3.1": "eac8912be329999150a71257adc513e6a52891d122641943c3a440f775267705eff0b275b4d90d5298518ca638ab48fc2b7c3ee109d82f0bb34a1ac081e9c3a2",
}

# The paths of Fedora's tools-hv snapshot: tools/hv builds through the
# kernel's tools build system and includes exactly these files of it.
HYPERV_TOOLS_FILES = (
    "tools/build/Build",
    "tools/build/Build.include",
    "tools/build/Makefile",
    "tools/build/Makefile.build",
    "tools/build/Makefile.feature",
    "tools/build/Makefile.include",
    "tools/scripts/Makefile.arch",
    "tools/scripts/Makefile.include",
    "tools/scripts/utilities.mak",
)


def _hyperv_kept(rel: str) -> bool:
    return rel == "tools/hv" or rel.startswith("tools/hv/") or rel in HYPERV_TOOLS_FILES


def _hyperv_transform(archive: bytes, version: str) -> bytes:
    """Cut tools/hv and the build files it includes out of a kernel release.

    Members are renamed from `linux-<version>/tools/...` to `tools/...`, the
    layout the recipe's `%setup -n tools/hv` expects, and keep the kernel
    archive's own modes and mtimes. The tools/build and tools/scripts
    directories get entries of their own, sorted by name with ownership
    zeroed, as one xz stream.
    """
    top = f"linux-{version}/"
    kept: dict[str, tuple[tarfile.TarInfo, bytes | None]] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:xz") as source:
        for member in source:
            name = member.name.rstrip("/")
            if not name.startswith(top):
                continue
            rel = name[len(top):]
            if member.isdir() and rel in ("tools", "tools/build", "tools/scripts"):
                kept[rel] = (member, None)
            elif _hyperv_kept(rel) and (member.isdir() or member.isreg()):
                payload = source.extractfile(member).read() if member.isreg() else None
                kept[rel] = (member, payload)
    missing = [rel for rel in ("tools/hv/Makefile", *HYPERV_TOOLS_FILES) if rel not in kept]
    if missing:
        raise RuntimeError(f"linux-{version} lacks {', '.join(missing)}")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        for rel in sorted(kept):
            member, payload = kept[rel]
            member.name = rel
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {}
            result.addfile(member, io.BytesIO(payload) if payload is not None else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _hyperv_url(version: str) -> str:
    return HYPERV_KERNEL_URL.format(major=version.split(".")[0], version=version)


def _hyperv_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "hyperv-daemons.spec")
    return {
        "name": "hyperv-daemons",
        "version": version,
        "filename": f"tools-hv-{version}.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{_hyperv_url(version)} (sha512-pinned)",
            "method": f"cut tools/hv and the tools/build and tools/scripts makefiles it includes from the stable kernel release and repack deterministically as tools-hv-{version}.tar.xz",
        },
    }


def _hyperv_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "hyperv-daemons.spec")
    pin = HYPERV_KERNEL_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for linux {version}")
    url = _hyperv_url(version)
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"tools-hv-{version}.tar.xz"
    target.write_bytes(_hyperv_transform(payload, version))
    return target



# --- hplip ---------------------------------------------------------------------

HPLIP_UPSTREAM_URL = "https://downloads.sourceforge.net/project/hplip/hplip/{version}/hplip-{version}.tar.gz"


def _hplip_transform(archive: bytes, version: str) -> bytes:
    """Repack the upstream .tar.gz without `locatedriver`, as Fedora's recipe does.

    packages/hplip/hplip.spec documents the transformation above its Source0
    line: unpack the upstream tarball, remove `locatedriver` (a
    license-related removal, see https://bugs.launchpad.net/hplip/+bug/2028938
    via the recipe's `hplip-repack.sh`), and recompress. Fedora's lookaside
    copy is that tarball made by hand, so its bytes cannot be reproduced;
    this makes the same tree deterministically. Members keep the archive's
    own modes and mtimes, are sorted by name with ownership zeroed, and are
    compressed with `gzip -n -9` so no name or timestamp enters the header.
    """
    doomed = f"hplip-{version}/locatedriver"
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        members = sorted(source.getmembers(), key=lambda m: m.name.rstrip("/"))
        with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in members:
                name = member.name.rstrip("/")
                if name == doomed:
                    continue
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                result.addfile(member, source.extractfile(member) if member.isreg() else None)
    tar_bytes = tar_buf.getvalue()
    proc = subprocess.Popen(
        ["gzip", "-n", "-9"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    out, _ = proc.communicate(tar_bytes)
    if proc.returncode != 0:
        raise RuntimeError("gzip failed")
    return out


def _hplip_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "hplip.spec")
    return {
        "name": "hplip",
        "version": version,
        "filename": f"hplip-{version}-repack.tar.gz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{HPLIP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove locatedriver (license-related, per hplip.spec/hplip-repack.sh) from the upstream release and repack deterministically as hplip-{version}-repack.tar.gz",
        },
    }


def _hplip_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "hplip.spec")
    pin = HPLIP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for hplip {version}")
    url = HPLIP_UPSTREAM_URL.format(version=version)
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"hplip-{version}-repack.tar.gz"
    target.write_bytes(_hplip_transform(payload, version))
    return target

# --- freerdp ---------------------------------------------------------------------

FREERDP_UPSTREAM_URL = "https://github.com/FreeRDP/FreeRDP/archive/{version}/FreeRDP-{version}.tar.gz"

FREERDP_INPUT_SHA512 = {
    "3.32.2": "2f036908fc96650fcec0810c05cf7fbad08f7c47a27aa7951b25e4bc1f390eb47223eaeaf622715bf2df6bd056e7f245502a3af57e606fd53d214c121a862a7e",
}

FREERDP_DOOMED = "winpr/libwinpr/crt/unicode_builtin.c"


def _freerdp_record_size(header: bytes) -> int:
    raw = header[124:136].split(b"\0")[0].strip()
    return int(raw or b"0", 8)


def _freerdp_pax_path(data: bytes) -> str | None:
    for line in data.split(b"\n"):
        if b"=" not in line:
            continue
        key, _, value = line.partition(b"=")
        if key.split(b" ", 1)[-1] == b"path":
            return value.decode()
    return None


def _freerdp_transform(archive: bytes, version: str) -> bytes:
    """Repack the upstream .tar.gz without unicode_builtin.c, as Fedora's recipe does.

    packages/freerdp/freerdp.spec documents the transformation above its
    Source0 line: download the upstream release, delete
    `*/winpr/libwinpr/crt/unicode_builtin.c` (a file whose license is not
    allowed), and recompress with `gzip -9 -n`. GNU tar's `--delete` also
    drops the leading `pax_global_header` records, so Fedora's lookaside copy
    starts at the top directory. This drops the same records by raw 512-byte
    slicing and leaves every other member byte-identical, which reproduces
    Fedora's archive exactly (the generated 3.32.2 output hashes identically
    to the lookaside copy). Exactly one matching member is required; anything
    else fails closed.
    """
    top = f"FreeRDP-{version}"
    doomed = f"{top}/{FREERDP_DOOMED}"
    payload = gzip.decompress(archive)
    records = [payload[i:i + 512] for i in range(0, len(payload), 512)]
    drops: set[int] = set()
    pending: list[tuple[int, int, bytes]] = []
    found = 0
    seen_member = False
    i = 0
    while i < len(records):
        header = records[i]
        if header == b"\0" * 512:
            break
        kind = header[156:157]
        span = 1 + (_freerdp_record_size(header) + 511) // 512
        if kind == b"g":
            if not seen_member:
                drops.update(range(i, i + span))
            pending = []
        elif kind in (b"x", b"L", b"K"):
            pending.append((i, span, kind))
        else:
            seen_member = True
            name = header[:100].split(b"\0")[0].decode()
            prefix = header[345:500].split(b"\0")[0].decode()
            full = f"{prefix}/{name}" if prefix else name
            for (at, length, ext) in pending:
                data = b"".join(records[at + 1:at + length])
                if ext == b"x":
                    override = _freerdp_pax_path(data)
                    if override is not None:
                        full = override
                elif ext == b"L":
                    full = data.split(b"\0")[0].decode()
            if full == doomed:
                found += 1
                for (at, length, _) in pending:
                    drops.update(range(at, at + length))
                drops.update(range(i, i + span))
            pending = []
        i += span
    if found != 1:
        raise RuntimeError(f"expected exactly one {doomed} member, found {found}")
    out = b"".join(record for index, record in enumerate(records) if index not in drops)
    proc = subprocess.Popen(
        ["gzip", "-n", "-9"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    compressed, _ = proc.communicate(out)
    if proc.returncode != 0:
        raise RuntimeError("gzip failed")
    return compressed


def _freerdp_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "freerdp.spec")
    return {
        "name": "freerdp",
        "version": version,
        "filename": f"FreeRDP-{version}-repack.tar.gz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{FREERDP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove {FREERDP_DOOMED} (license not allowed, per freerdp.spec/freerdp_download_and_repack.sh) from the upstream release and repack deterministically as FreeRDP-{version}-repack.tar.gz",
        },
    }


def _freerdp_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "freerdp.spec")
    pin = FREERDP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for freerdp {version}")
    url = FREERDP_UPSTREAM_URL.format(version=version)
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"FreeRDP-{version}-repack.tar.gz"
    target.write_bytes(_freerdp_transform(payload, version))
    return target


# --- python-pydantic-core ------------------------------------------------------

CRATES_IO_INDEX = "registry+https://github.com/rust-lang/crates.io-index"
CRATE_URL = "https://static.crates.io/crates/{name}/{name}-{version}.crate"




def cargo_lock_packages(lock_text: str) -> list[dict]:
    """The crates.io packages a Cargo.lock pins, with their SHA-256 checksums.

    Cargo.lock is TOML; tomllib is standard library from Python 3.11. Anything
    not from crates.io (git or path sources) is refused: the vendored bundle
    must be reproducible from checksum-pinned registry downloads alone. The
    workspace root itself has no source and is skipped.
    """
    import tomllib

    crates = []
    for package in tomllib.loads(lock_text).get("package", []):
        source = package.get("source")
        if source is None:
            continue
        if source != CRATES_IO_INDEX:
            raise RuntimeError(f"{package['name']} {package['version']} comes from {source}, not crates.io")
        if not package.get("checksum"):
            raise RuntimeError(f"{package['name']} {package['version']} has no checksum in Cargo.lock")
        crates.append({"name": package["name"], "version": package["version"], "checksum": package["checksum"]})
    return sorted(crates, key=lambda crate: (crate["name"], crate["version"]))


def _vendored_crate_members(crate: dict, payload: bytes, prefix: str, mtime: int):
    """Yield (TarInfo, bytes) for one crate laid out as `cargo vendor --versioned-dirs` does.

    The .crate is checked against the Cargo.lock checksum first, so crates.io
    cannot substitute bytes. .cargo-checksum.json lists every file's SHA-256
    and the package checksum, which is what a cargo directory source verifies.
    """
    actual = hashlib.sha256(payload).hexdigest()
    if actual != crate["checksum"]:
        raise RuntimeError(f"crate {crate['name']} {crate['version']}: expected sha256 {crate['checksum']}, got {actual}")
    top = f"{crate['name']}-{crate['version']}"
    directory = f"{prefix}/{top}"
    contents: dict[str, bytes] = {}
    executable: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as source:
        for member in source.getmembers():
            if not member.isreg():
                continue
            if not member.name.startswith(top + "/"):
                raise RuntimeError(f"crate {top} has a member outside its directory: {member.name}")
            relative = member.name[len(top) + 1:]
            if relative == ".cargo-checksum.json":  # regenerated below
                continue
            contents[relative] = source.extractfile(member).read()
            if member.mode & 0o111:
                executable.add(relative)
    checksum = {
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())},
        "package": crate["checksum"],
    }
    contents[".cargo-checksum.json"] = json.dumps(checksum, sort_keys=True, separators=(",", ":")).encode()
    directories = {directory}
    for relative in contents:
        parts = relative.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            directories.add(f"{directory}/{'/'.join(parts[:index])}")
    for name in sorted(directories):
        info = tarfile.TarInfo(name)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.mtime = mtime
        yield info, None
    for relative, data in sorted(contents.items()):
        info = tarfile.TarInfo(f"{directory}/{relative}")
        info.size = len(data)
        info.mode = 0o755 if relative in executable else 0o644
        info.mtime = mtime
        yield info, data


def _pydantic_core_transform(sdist: bytes, version: str, crates: dict[tuple[str, str], bytes]) -> bytes:
    """Repack the sdist with vendor/ added, as a byte-reproducible tar.xz.

    The sdist's own members pass through unchanged; vendor/ is appended with
    the mtime of the sdist's Cargo.lock. Ownership is zeroed and every member
    is emitted in sorted order, so the same inputs always give the same bytes.
    """
    top = f"pydantic_core-{version}"
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(sdist), mode="r:gz") as source, \
            tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        members = sorted(source.getmembers(), key=lambda member: member.name)
        lock_member = next(member for member in members if member.name == f"{top}/Cargo.lock")
        lock_text = source.extractfile(lock_member).read().decode()
        mtime = int(lock_member.mtime)
        for member in members:
            if not (member.name == top or member.name.startswith(top + "/")):
                raise RuntimeError(f"sdist member outside {top}: {member.name}")
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {}
            result.addfile(member, source.extractfile(member) if member.isreg() else None)
        vendor = tarfile.TarInfo(f"{top}/vendor")
        vendor.type = tarfile.DIRTYPE
        vendor.mode = 0o755
        vendor.mtime = mtime
        result.addfile(vendor)
        for crate in cargo_lock_packages(lock_text):
            payload = crates[(crate["name"], crate["version"])]
            for info, data in _vendored_crate_members(crate, payload, f"{top}/vendor", mtime):
                result.addfile(info, io.BytesIO(data) if data is not None else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _pydantic_core_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "python-pydantic-core.spec")
    return {
        "name": "python-pydantic-core",
        "version": version,
        "filename": f"pydantic_core-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://files.pythonhosted.org/packages/source/p/pydantic_core/pydantic_core-{version}.tar.gz (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as pydantic_core-{version}-vendored.tar.xz",
        },
    }


def _pydantic_core_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "python-pydantic-core.spec")
    pin = PYDANTIC_CORE_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for pydantic_core {version}")
    url = f"https://files.pythonhosted.org/packages/source/p/pydantic_core/pydantic_core-{version}.tar.gz"
    sdist = _fetch(url)
    actual = hashlib.sha512(sdist).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    with tarfile.open(fileobj=io.BytesIO(sdist), mode="r:gz") as source:
        lock_text = source.extractfile(f"pydantic_core-{version}/Cargo.lock").read().decode()
    crates = {
        (crate["name"], crate["version"]): _fetch(CRATE_URL.format(**crate))
        for crate in cargo_lock_packages(lock_text)
    }
    target = out_dir / f"pydantic_core-{version}-vendored.tar.xz"
    target.write_bytes(_pydantic_core_transform(sdist, version, crates))
    return target


# --- fpaste ----------------------------------------------------------------------

FPASTE_UPSTREAM_URL = "https://codeberg.org/sanjay_ankur/fpaste/archive/{version}.tar.gz"


def _fpaste_transform(archive: bytes, version: str) -> bytes:
    """Move the Codeberg tag archive from `fpaste/` to `fpaste-<version>/`.

    packages/fpaste/fpaste.spec takes Source0 from pagure.io, which was sunset
    in 2026; the project moved to Codeberg and publishes no release tarball.
    Fedora's lookaside copy is a hand-made `fpaste-<version>/` tarball whose
    tree equals the tag archive's minus `.gitignore` (unpacked and diffed for
    0.5.0.0), so its bytes cannot be reproduced; this makes the same tree
    deterministically. The pax global header carrying the commit id goes with
    the old prefix; members keep the archive's own modes and mtimes, are
    sorted by name with ownership zeroed, and are compressed with
    `gzip -n -9` so no name or timestamp enters the header.
    """
    old, new = "fpaste", f"fpaste-{version}"
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        members = sorted(source.getmembers(), key=lambda m: m.name.rstrip("/"))
        with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.PAX_FORMAT) as result:
            for member in members:
                name = member.name.rstrip("/")
                if name != old and not name.startswith(old + "/"):
                    raise RuntimeError(f"fpaste archive member outside {old}/: {member.name}")
                if name == f"{old}/.gitignore":
                    continue
                data = source.extractfile(member) if member.isreg() else None
                member.name = new + name[len(old):]
                member.pax_headers = {}
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                result.addfile(member, data)
    proc = subprocess.Popen(["gzip", "-n", "-9"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = proc.communicate(tar_buf.getvalue())
    if proc.returncode != 0:
        raise RuntimeError("gzip failed")
    return out


def _fpaste_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "fpaste.spec")
    return {
        "name": "fpaste",
        "version": version,
        "filename": f"fpaste-{version}.tar.gz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{FPASTE_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"move the Codeberg tag archive from fpaste/ to fpaste-{version}/ without .gitignore (the tree of Fedora's hand-made tarball; pagure.io, the recipe's Source0 host, is gone) and repack deterministically as fpaste-{version}.tar.gz",
        },
    }


def _fpaste_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "fpaste.spec")
    pin = FPASTE_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for fpaste {version}")
    url = FPASTE_UPSTREAM_URL.format(version=version)
    payload = _fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"fpaste-{version}.tar.gz"
    target.write_bytes(_fpaste_transform(payload, version))
    return target
