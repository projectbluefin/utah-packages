#!/usr/bin/env python3
"""Deterministic first-party Source0 generation.

The factory contract is that source payloads come from upstream releases and
Fedora dist-git supplies the recipe only. These recipes consume an archive
that no upstream publishes verbatim:

- intel-media-driver-free: the upstream tag archive with non-free kernel
  files removed (packages/intel-media-driver-free/strip.py)
- tailscale: a go-vendored bundle (packages/tailscale/create-vendor-tarball.sh)
- gpm: the upstream release with doc/specs removed, because those PDFs carry
  unclear licensing (the recipe's own comment above its Source line)
- hplip: the upstream release with `locatedriver` removed (a license-related
  removal the recipe's `hplip-repack.sh` performs by hand, documented by the
  comment above the spec's Source0 line)
- freerdp: the upstream release without
  `winpr/libwinpr/crt/unicode_builtin.c` (a file whose license Fedora does
  not allow; the recipe's `freerdp_download_and_repack.sh` deletes it by hand,
  documented by the comment above the spec's Source0 line)
- openal-soft: the upstream release with the bundled fmt tree and the
  non-free utils HRTF datasets removed (packages/openal-soft/make_tarball.sh)
- fpaste: the upstream Codeberg tag archive under the `fpaste-<version>/`
  prefix the recipe's `%autosetup` expects. The recipe's Source0 host
  (pagure.io) was sunset in 2026 and the project publishes no release
  tarball; Fedora's lookaside copy is a hand-made tarball of the same tree
- bluefin-artwork-logos: the Bluefin logo SVGs and the license from
  projectbluefin/artwork at a pinned commit. The repository publishes no
  release, and its archive carries every wallpaper (well over 100 MB) for
  three small files, so each file is fetched at the commit, SHA-512-checked,
  and packed into one archive
- libslirp, rtmpdump: `git archive` of an upstream tag at a pinned commit.
  Neither project publishes a release file; Fedora's tarballs are a GitLab
  tag archive and a hand-run `git archive`, whose tar streams this
  reproduces byte for byte (GIT_ARCHIVE_SOURCES)

For these, the source lock names this script and records the SHA-512 of the
bytes the transformation produces. Verification re-runs the transformation
from the pinned first-party input and fails closed on any drift; no payload
is fetched from Fedora's lookaside.

Everything runs on the Python standard library plus the git CLI (and, for
tailscale, a Go toolchain), so it works in the digest-pinned
ghcr.io/projectbluefin/lab-runner FSDK image and on GitHub-hosted runners
without installing anything at runtime.
"""

from __future__ import annotations

import fnmatch
import functools
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


SCRIPT_PATH = "tools/generated_sources.py"


# SHA-512 of the first-party input archives, pinned so a re-rolled upstream
# artifact fails closed instead of silently changing the generated output.
INTEL_MEDIA_INPUT_SHA512 = {
    "26.2.4": "6e01092c06a100279b40ff46afa0c592483edc30e426fe802a79c2fa53b5ba16f952bdb445dfbfbfb7f50ef952727536f08c7eb0b3d06db25521fb9149887494",
}

# The annotated tag is mutable; the commit it resolves to is not. Pin it.
TAILSCALE_COMMITS = {
    "1.98.8": "05a91829316e055517a1e84f7b00016846ef4107",
}

GPM_INPUT_SHA512 = {
    "1.20.7": "a502741e2f457b47e41c6d155b1f7ef7c95384fd394503f82ddacf80cde9cdc286c906c77be12b6af8565ef1c3ab24d226379c1dcebcfcd15d64bcf3e94b63b9",
}


OPENAL_SOFT_INPUT_SHA512 = {
    "1.24.2": "5ac05fb20b414dfe50e6ac80a69d1e36db5588fd2ccef2606ae1f3b6fc155881d45826031660123101a31469e24bc2bea42993d81b28dd5f18d0d0463988fa65",
}

PYDANTIC_CORE_INPUT_SHA512 = {
    "2.46.5": "7af13f280d74ab0ded8e9299820930b0257502017f6a688d7d598e72351e127e178db11aeab987decaf95ca8619e151f244392ad9638ea184625728dcbb7cfff",
}

FPASTE_INPUT_SHA512 = {
    "0.5.0.0": "0337bca5141d8ec99d2b7ea4710c6852f7abd1c8d6481c5051d572e7fdfe7a99f5741ea69fa802a2d514fa0c23eb215357ef6599a27226880e4e272ed0b8b46f",
}

HPLIP_INPUT_SHA512 = {
    "3.26.6": "1bebae77c6a71029647e391b743dae1b52b0e4ea7ff4a728fbf592160f9f8607e0196d8045189b1f032654d1e9724de464bf9ad2c79c553c4d6ffe9af7d3c5fa",
}

# Commit -> SHA-512 of every file taken from it. A commit is immutable, but
# raw.githubusercontent.com is a CDN; the digests make it fail closed anyway.
BLUEFIN_ARTWORK_FILES = {
    "9ab493bf1fb3ae41594b6bb0a2c5f2350d81de01": {
        "LICENSE": "dc6b68d13b8cf959644b935f1192b02c71aa7a5cf653bd43b4480fa89eec8d4d3f16a2278ec8c3b40ab1fdb233b3173a78fd83590d6f739e0c9e8ff56c282557",
        "assets/vector/logos/bluefin/bluefin-logo-dark.svg": "947ab6e7a24dcabcbef41a2d5f46400c815dbe0199933194e5cf5ffefaf6c547364b9222a60a2fbca01995ac9801778775cd018a93df35ba0442a14394c20ea5",
        "assets/vector/logos/bluefin/bluefin-logo-light.svg": "97ec4f9a726a836928af9a50c8abeb2123205d6c3b1bdb19c1199d1d1429533510df6f78abd8c12b1d1a24047744c664ac47629298210d1aea8a2f797800b42a",
    },
}

BLUEFIN_ARTWORK_RAW_URL = "https://raw.githubusercontent.com/projectbluefin/artwork/{commit}/{path}"


def sha512_path(path: Path) -> str:
    value = hashlib.sha512()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def recipe_macros(text: str) -> dict[str, str]:
    """Collect the tag/%global values a generated Source0 expands from.

    rpmspec is the macro authority for direct downloads, but the generated
    Source0 recipes must stay resolvable without an RPM toolchain, and their
    filenames only ever draw on literal tags and %global definitions.
    """
    macros = dict(re.findall(r"^%global\s+(\w+)\s+(\S+)", text, flags=re.MULTILINE))
    for tag in ("Name", "Version"):
        match = re.search(rf"^{tag}:\s*(\S+)", text, flags=re.MULTILINE)
        if match:
            macros[tag.lower()] = match.group(1)
    return macros


def spec_version(package_dir: Path, spec_name: str) -> str:
    text = (package_dir / spec_name).read_text()
    match = re.search(r"^Version:\s*(\S+)", text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"no Version tag in {spec_name}")
    return match.group(1)


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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"intel-media-{version}-free.tar.gz"
    target.write_bytes(_imd_transform(payload, version))
    return target


# --- tailscale ---------------------------------------------------------------


def _tailscale_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "tailscale.spec")
    commit = TAILSCALE_COMMITS.get(version, "<unpinned>")
    return {
        "name": "tailscale",
        "version": version,
        "filename": f"tailscale-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://github.com/tailscale/tailscale tag v{version} (commit {commit})",
            "method": "go mod tidy && go mod vendor with GOTOOLCHAIN pinned from go.mod, drop unused cmd trees/k8s-operator/tstest, deterministic tar | xz -9e single-stream",
        },
    }


def _tailscale_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "tailscale.spec")
    commit = TAILSCALE_COMMITS.get(version)
    if commit is None:
        raise RuntimeError(f"no pinned commit for tailscale {version}")
    if shutil.which("go") is None:
        raise RuntimeError(
            "tailscale Source0 generation requires a Go toolchain, and the FSDK "
            "catalog has no Go-capable image; add one to projectbluefin/fsdk-containers"
        )
    with tempfile.TemporaryDirectory(prefix="tailscale-vendor-", dir=out_dir) as tmp:
        tree = Path(tmp) / f"tailscale-{version}"
        subprocess.run(
            ["git", "clone", "-q", "--branch", f"v{version}", "--depth", "1",
             "https://github.com/tailscale/tailscale.git", str(tree)],
            check=True,
        )
        head = subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True).strip()
        if head != commit:
            raise RuntimeError(f"tag v{version} moved: expected {commit}, got {head}")
        epoch = subprocess.check_output(["git", "-C", str(tree), "log", "-1", "--format=%ct"], text=True).strip()
        go_version = re.search(r"^go\s+(\S+)", (tree / "go.mod").read_text(), flags=re.MULTILINE).group(1)
        env = {
            **os.environ,
            "GOPROXY": "https://proxy.golang.org,direct",
            "GOTOOLCHAIN": f"go{go_version}",
            "GOMODCACHE": str(Path(tmp) / "gomodcache"),
            "GOCACHE": str(Path(tmp) / "gocache"),
            "GOPATH": str(Path(tmp) / "gopath"),
        }
        subprocess.run(["go", "mod", "tidy"], check=True, cwd=tree, env=env)
        subprocess.run(["go", "mod", "vendor"], check=True, cwd=tree, env=env)
        for subdir in (tree / "cmd").iterdir():
            if subdir.is_dir() and not subdir.name.startswith("tailscale"):
                shutil.rmtree(subdir)
        shutil.rmtree(tree / "k8s-operator", ignore_errors=True)
        shutil.rmtree(tree / "tstest", ignore_errors=True)

        target = out_dir / f"tailscale-{version}-vendored.tar.xz"
        entries = sorted(
            (path for path in tree.rglob("*") if ".git" not in path.relative_to(tree).parts),
            key=lambda path: path.relative_to(tree).as_posix(),
        )
        with target.open("wb") as sink:
            def members():
                base = tarfile.TarInfo(tree.name)
                base.type = tarfile.DIRTYPE
                yield base, None
                for path in entries:
                    arcname = f"{tree.name}/{path.relative_to(tree).as_posix()}"
                    info = tarfile.TarInfo(arcname)
                    if path.is_symlink():
                        info.type = tarfile.SYMTYPE
                        info.linkname = os.readlink(path)
                    elif path.is_dir():
                        info.type = tarfile.DIRTYPE
                    else:
                        info.type = tarfile.REGTYPE
                        info.size = path.stat().st_size
                    yield info, path

            # Buffer the deterministic tar stream, then xz-compress in one pass.
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
                for info, path in members():
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = int(epoch)
                    info.mode = 0o755 if (info.isdir() or (path and os.access(path, os.X_OK))) else 0o644
                    result.addfile(info, path.open("rb") if path and info.isreg() else None)
            _xz_compress_stream(iter([raw.getvalue()]), sink)
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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"openal-soft-{version}-clean.tar.xz"
    target.write_bytes(_openal_soft_transform(payload, version))
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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"FreeRDP-{version}-repack.tar.gz"
    target.write_bytes(_freerdp_transform(payload, version))
    return target


# --- python-pydantic-core ------------------------------------------------------

CRATES_IO_INDEX = "registry+https://github.com/rust-lang/crates.io-index"
CRATE_URL = "https://static.crates.io/crates/{name}/{name}-{version}.crate"


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


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
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"fpaste-{version}.tar.gz"
    target.write_bytes(_fpaste_transform(payload, version))
    return target


# --- bluefin-artwork-logos -------------------------------------------------------


def _bluefin_artwork_commit(package_dir: Path) -> str:
    macros = recipe_macros((package_dir / "bluefin-artwork-logos.spec").read_text())
    commit = macros.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("bluefin-artwork-logos.spec must pin %global commit to a full SHA-1")
    return commit


def _bluefin_artwork_transform(files: dict[str, bytes], commit: str) -> bytes:
    """Pack the fetched files flat under one top directory, deterministically.

    Members are sorted by name, owned by root with no names, mode 0644, and
    stamped with a fixed mtime, so the same inputs always give the same bytes.
    """
    top = f"bluefin-artwork-logos-{commit[:7]}"
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        directory = tarfile.TarInfo(top)
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        directory.mtime = 0
        result.addfile(directory)
        names = {}
        for path in files:
            name = path.rsplit("/", 1)[-1]
            if name in names:
                raise ValueError(f"{path} and {names[name]} flatten to the same name")
            names[name] = path
        for name in sorted(names):
            data = files[names[name]]
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            result.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _bluefin_artwork_metadata(package_dir: Path) -> dict:
    commit = _bluefin_artwork_commit(package_dir)
    filename = f"bluefin-artwork-logos-{commit[:7]}.tar.xz"
    urls = ", ".join(BLUEFIN_ARTWORK_RAW_URL.format(commit=commit, path=path)
                     for path in sorted(BLUEFIN_ARTWORK_FILES.get(commit, {})))
    return {
        "name": "bluefin-artwork-logos",
        "version": spec_version(package_dir, "bluefin-artwork-logos.spec"),
        "filename": filename,
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{urls} (each sha512-pinned)",
            "method": f"fetch each file from projectbluefin/artwork at {commit} and pack them flat and deterministically as {filename}",
        },
    }


def _bluefin_artwork_generate(package_dir: Path, out_dir: Path) -> Path:
    commit = _bluefin_artwork_commit(package_dir)
    pins = BLUEFIN_ARTWORK_FILES.get(commit)
    if pins is None:
        raise RuntimeError(f"no pinned file SHA-512s for projectbluefin/artwork {commit}")
    files = {}
    for path, pin in sorted(pins.items()):
        url = BLUEFIN_ARTWORK_RAW_URL.format(commit=commit, path=path)
        request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = response.read()
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pin:
            raise RuntimeError(f"input file mismatch for {url}: expected {pin}, got {actual}")
        files[path] = payload
    target = out_dir / f"bluefin-artwork-logos-{commit[:7]}.tar.xz"
    target.write_bytes(_bluefin_artwork_transform(files, commit))
    return target


# --- git-archive tag sources -----------------------------------------------------

# Recipes whose Source0 is `git archive` of an upstream tag: the project
# publishes no release file, and the forge's on-the-fly tag archive is not
# stable bytes. The tag is mutable; the commit it resolves to is not, so pin
# that. `compression` is how the Fedora packager compressed the archive:
# libslirp's tar.xz is GitLab's archive, and xz preset 6 over the `git archive`
# tar reproduces Fedora's pinned bytes exactly. rtmpdump's tar is identical to
# Fedora's, but the packager's gzip (zlib-ng) is not reproducible here, so it
# is `gzip -n -9` and the recipe's `sources` pins that digest.
GIT_ARCHIVE_SOURCES = {
    "distribution-gpg-keys": {
        "remote": "https://github.com/rpm-software-management/distribution-gpg-keys.git",
        "tag": "distribution-gpg-keys-{version}-1",
        "compression": "gz",
        "commits": {"1.123": "6f5f4883ceabd6c3d389ecd913b60675b61563da"},
    },
    "libslirp": {
        "remote": "https://gitlab.freedesktop.org/slirp/libslirp.git",
        "tag": "v{version}",
        "compression": "xz",
        "commits": {"4.9.6": "392af90207fc51dd9f9044ee9b1f963f3c851c2c"},
    },
    "rtmpdump": {
        "remote": "https://git.ffmpeg.org/rtmpdump.git",
        "tag": "v{version}",
        "compression": "gz",
        "commits": {"2.6": "138fdb258d9fc26f1843fd1b891180416c9dc575"},
    },
}


def _git_archive_compress(raw: bytes, compression: str) -> bytes:
    if compression == "xz":
        return lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6)
    if compression == "gz":
        proc = subprocess.run(["gzip", "-n", "-9"], input=raw, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError("gzip failed")
        return proc.stdout
    raise ValueError(f"unknown compression {compression!r}")


def _git_archive_metadata(name: str, package_dir: Path) -> dict:
    source = GIT_ARCHIVE_SOURCES[name]
    version = spec_version(package_dir, f"{name}.spec")
    commit = source["commits"].get(version, "<unpinned>")
    tag = source["tag"].format(version=version)
    filename = f"{name}-{version}.tar.{source['compression']}"
    return {
        "name": name,
        "version": version,
        "filename": filename,
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{source['remote']} tag {tag} (commit {commit})",
            "method": f"git archive --format=tar --prefix={name}-{version}/ of the pinned commit, compressed deterministically as {filename}",
        },
    }


def _git_archive_generate(name: str, package_dir: Path, out_dir: Path) -> Path:
    source = GIT_ARCHIVE_SOURCES[name]
    version = spec_version(package_dir, f"{name}.spec")
    commit = source["commits"].get(version)
    if commit is None:
        raise RuntimeError(f"no pinned commit for {name} {version}")
    tag = source["tag"].format(version=version)
    with tempfile.TemporaryDirectory(prefix=f"{name}-git-", dir=out_dir) as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        # Fetch only the tag: rtmpdump's repository advertises refs to the
        # all-zero object, which a full clone refuses.
        subprocess.run(
            ["git", "-C", tmp, "fetch", "-q", "--depth", "1", source["remote"], f"refs/tags/{tag}"],
            check=True,
        )
        head = subprocess.check_output(
            ["git", "-C", tmp, "rev-parse", "FETCH_HEAD^{commit}"], text=True
        ).strip()
        if head != commit:
            raise RuntimeError(f"tag {tag} moved: expected {commit}, got {head}")
        raw = subprocess.check_output(
            ["git", "-C", tmp, "archive", "--format=tar", f"--prefix={name}-{version}/", commit]
        )
    target = out_dir / f"{name}-{version}.tar.{source['compression']}"
    target.write_bytes(_git_archive_compress(raw, source["compression"]))
    return target


METADATA = {
    **{name: functools.partial(_git_archive_metadata, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_metadata,
    "tailscale": _tailscale_metadata,
    "python-pydantic-core": _pydantic_core_metadata,
    "gpm": _gpm_metadata,
    "hplip": _hplip_metadata,
    "openal-soft": _openal_soft_metadata,
    "freerdp": _freerdp_metadata,
    "fpaste": _fpaste_metadata,
    "bluefin-artwork-logos": _bluefin_artwork_metadata,
}

GENERATORS = {
    **{name: functools.partial(_git_archive_generate, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_generate,
    "tailscale": _tailscale_generate,
    "python-pydantic-core": _pydantic_core_generate,
    "hplip": _hplip_generate,
    "gpm": _gpm_generate,
    "openal-soft": _openal_soft_generate,
    "freerdp": _freerdp_generate,
    "fpaste": _fpaste_generate,
    "bluefin-artwork-logos": _bluefin_artwork_generate,
}


def metadata_for(name: str, package_dir: Path) -> dict:
    """Build the source-lock record (minus sha512) for a generated Source0."""
    builder = METADATA.get(name)
    if builder is None:
        raise ValueError(f"no generated source resolver for {name}")
    return builder(package_dir)


def generate(name: str, package_dir: Path, out_dir: Path) -> Path:
    generator = GENERATORS.get(name)
    if generator is None:
        raise ValueError(f"no generated source resolver for {name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    return generator(package_dir, out_dir)


def main() -> int:
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} PACKAGE PACKAGE_DIR OUTPUT_DIR", file=sys.stderr)
        return 2
    package, package_dir, out_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    artifact = generate(package, package_dir, out_dir)
    print(json.dumps({
        "package": package,
        "filename": artifact.name,
        "sha512": sha512_path(artifact),
        "bytes": artifact.stat().st_size,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
