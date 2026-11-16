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
- 7zip: the upstream release without the RAR handler, codecs and crypto
  and the unRAR license, which carry the "unRAR license restriction"
  (packages/7zip/strip-rar-support.sh)
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
- prefixdevname: the upstream GitHub tag archive (SHA-512-pinned) with a
  `vendor/` tree of every crates.io crate its Cargo.lock pins, laid out as
  `cargo vendor --versioned-dirs` does. Upstream publishes no release asset,
  and the recipe builds offline from vendored crates
- gst-thumbnailers: the upstream GNOME release (SHA-512-pinned) with the same
  `vendor/` tree added. Hummingbird ships no Rust crate RPMs, so the recipe
  bundles its gtk-rs, clap and libglycin-rebind dependencies (#527)
- ghostty: the upstream release (SHA-512-pinned) with a `zig-deps/` directory
  of every Zig package archive its build.zig.zon.json lists, each
  SHA-512-pinned. `zig build` fetches them from the network otherwise, and
  the recipe seeds Zig's package cache from them offline, as Dakota does

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

import errno
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
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request


SCRIPT_PATH = "tools/generated_sources.py"


# --- upstream reachability ------------------------------------------------------
#
# tools/source_pipeline.py runs this script as a subprocess and must tell "the
# upstream host never answered" apart from everything else. Any uncaught
# exception exits 1, and that includes the integrity alarms below (a moved tag,
# a pinned input whose digest changed), which must keep failing the run. So the
# outage case gets its own exception, raised only where the failure is provably
# transport-level, and its own exit code. Nothing else is ever mapped to it: an
# unknown git or generator failure stays an ordinary, fatal exit.
EXIT_UPSTREAM_UNREACHABLE = 75  # EX_TEMPFAIL
# Bound a git fetch/clone so a host that accepts the connection and then stalls
# (git.ffmpeg.org) is reported as unreachable instead of wedging the job.
GIT_NETWORK_TIMEOUT_SECONDS = 300

_UNREACHABLE_ERRNOS = {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN, errno.EHOSTDOWN}

# git/curl diagnostics that only appear when the transport itself failed.
# "repository not found", "couldn't find remote ref", auth prompts and HTTP 4xx
# are deliberately absent: those are permanent and need a human.
_GIT_TRANSPORT_FAILURE = re.compile(
    r"Could not resolve host"
    r"|Failed to connect to"
    r"|Connection timed out"
    r"|Connection refused"
    r"|Connection reset by peer"
    r"|Operation timed out"
    r"|Network is unreachable"
    r"|No route to host"
    r"|The remote end hung up unexpectedly"
    r"|early EOF"
    r"|gnutls_handshake\(\) failed"
    r"|RPC failed; curl (?:18|28|52|55|56|92)\b"
    r"|RPC failed; HTTP (?:408|429|5\d\d)\b"
    r"|returned error: (?:408|429|5\d\d)\b"
)
_GIT_PERMANENT_FAILURE = re.compile(
    r"(?:HTTP|returned error:) 4(?!08|29)\d\d\b"
    r"|couldn't find remote ref"
    r"|[Rr]epository not found"
    r"|Authentication failed"
    r"|certificate"
)


class UpstreamUnreachable(RuntimeError):
    """The upstream host could not be reached; nothing was served to verify."""


def transient_http_status(code: int) -> bool:
    """A status worth retrying later: timeouts, throttling and server errors."""
    return code in (408, 429) or 500 <= code < 600


def is_transport_failure(error: BaseException) -> bool:
    """True only when ``error`` means the host never served a usable answer.

    A 404/410 is the server answering that the file is gone, a certificate
    failure is not an outage, and a URLError with a string reason is a local
    misconfiguration (unknown scheme, missing host): all of those are permanent.
    """
    if isinstance(error, urllib.error.HTTPError):
        return transient_http_status(error.code)
    if isinstance(error, urllib.error.URLError):
        error = error.reason
    if isinstance(error, ssl.CertificateError):
        return False
    if isinstance(error, (socket.gaierror, TimeoutError, ConnectionError, ssl.SSLEOFError)):
        return True
    return isinstance(error, OSError) and error.errno in _UNREACHABLE_ERRNOS


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-generated-source/1"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        if is_transport_failure(error):
            raise UpstreamUnreachable(f"could not reach {url}: {error}") from error
        raise


def git_transport_failure(stderr: str) -> bool:
    return bool(_GIT_TRANSPORT_FAILURE.search(stderr)) and not _GIT_PERMANENT_FAILURE.search(stderr)


def _git_network(command: list[str], remote: str) -> None:
    """Run a git command that talks to ``remote``, classifying only outages."""
    try:
        subprocess.run(command, check=True, capture_output=True, text=True,
                       timeout=GIT_NETWORK_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise UpstreamUnreachable(
            f"git could not reach {remote}: no answer within {GIT_NETWORK_TIMEOUT_SECONDS}s"
        ) from error
    except subprocess.CalledProcessError as error:
        stderr = error.stderr or ""
        sys.stderr.write(stderr)
        if git_transport_failure(stderr):
            detail = next(line.strip() for line in stderr.splitlines() if _GIT_TRANSPORT_FAILURE.search(line))
            raise UpstreamUnreachable(f"git could not reach {remote}: {detail}") from error
        raise


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

SEVENZIP_INPUT_SHA512 = {
    "26.04": "3037cdebf29b1a44e123aee3daec168e8b8ec97b58446c1ba1a54aa1b306d48c2f9fb16bb5ad48ec1cd415e6cd035461cb900de7d848a6bc19a21dd077175935",
    "26.05": "871e9b4794b03568462d43aa8706dcfcc5cbf3d5852b1846c76fca34b3d8fbad3f6c61f163361f9e143e83cd15b6454eeed29d3f86dbe9c9f9c03a213b1eaae9",
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
    payload = _fetch(url)
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
        remote = "https://github.com/tailscale/tailscale.git"
        _git_network(
            ["git", "clone", "-q", "--branch", f"v{version}", "--depth", "1", remote, str(tree)],
            remote,
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
        payload = _fetch(url)
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pin:
            raise RuntimeError(f"input file mismatch for {url}: expected {pin}, got {actual}")
        files[path] = payload
    target = out_dir / f"bluefin-artwork-logos-{commit[:7]}.tar.xz"
    target.write_bytes(_bluefin_artwork_transform(files, commit))
    return target


# --- prefixdevname -----------------------------------------------------------

# Upstream publishes no release asset (the maintainer's spec still points at a
# downloads.githubusercontent.com/releases/download path that 404s today); the
# only stable upstream bytes are the GitHub tag archive, whose sha512 is pinned
# below so the resolver can prove it fetched the intended tree.
PREFIXDEVNAME_UPSTREAM_URL = (
    "https://github.com/msekletar/prefixdevname/archive/refs/tags/v{version}.tar.gz"
)
PREFIXDEVNAME_INPUT_SHA512 = {
    "0.2.0": "ad2133baace6ac660ad8ee81ad98e5ad6042a20a513465eddb25c0761d84586c109938fdd2fe3682505e7b618f57246395286b7f5230f596374feda4f7c6d168",
}
# Fixed mtime stamped on every output member so the bundle is byte-reproducible
# regardless of the source archive's own mtimes.
CARGO_VENDORED_MTIME = 0
PREFIXDEVNAME_MTIME = CARGO_VENDORED_MTIME


def _cargo_vendored_transform(source: bytes, top: str, crates: dict, mtime: int) -> bytes:
    """Add a vendor/ tree to a release tarball, deterministically.

    The archive already lays out the source under <top>/. Its compression is
    detected, so a .tar.gz and a .tar.xz release both work.
    vendor/<crate>-<version>/ is appended for each crate the release root's
    Cargo.lock pins, with its .cargo-checksum.json, exactly as
    `cargo vendor --versioned-dirs` lays it out. Every member is stamped with
    a fixed mtime and zero ownership, so the same inputs always produce the
    same bytes.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:*") as src, \
            tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        members = sorted(src.getmembers(), key=lambda m: m.name.rstrip("/"))
        lock_member = src.getmember(f"{top}/Cargo.lock")
        lock_text = src.extractfile(lock_member).read().decode()
        for member in members:
            if not (member.name == top or member.name.startswith(top + "/")):
                raise RuntimeError(f"archive member outside {top}: {member.name}")
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {}
            member.mtime = mtime
            result.addfile(member, src.extractfile(member) if member.isreg() else None)
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


def _cargo_vendored_generate(name: str, version: str, url: str, pin: str | None, out_dir: Path) -> Path:
    """Fetch a pinned release, then every crate its root Cargo.lock pins, and vendor them.

    The release is checked against its SHA-512 pin before any crate is
    downloaded, and each crate against its Cargo.lock SHA-256, so nothing
    reaches the output that was not pinned. Nothing is written on a mismatch.
    """
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for {name} {version}")
    archive = _fetch(url)
    actual = hashlib.sha512(archive).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    top = f"{name}-{version}"
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:*") as source:
        lock_member = source.getmember(f"{top}/Cargo.lock")
        lock_text = source.extractfile(lock_member).read().decode()
    crates = {
        (crate["name"], crate["version"]): _fetch(CRATE_URL.format(**crate))
        for crate in cargo_lock_packages(lock_text)
    }
    target = out_dir / f"{top}-vendored.tar.xz"
    target.write_bytes(_cargo_vendored_transform(archive, top, crates, CARGO_VENDORED_MTIME))
    return target


def _prefixdevname_transform(source: bytes, version: str, crates: dict) -> bytes:
    return _cargo_vendored_transform(source, f"prefixdevname-{version}", crates, PREFIXDEVNAME_MTIME)


def _prefixdevname_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "prefixdevname.spec")
    return {
        "name": "prefixdevname",
        "version": version,
        "filename": f"prefixdevname-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{PREFIXDEVNAME_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as prefixdevname-{version}-vendored.tar.xz",
        },
    }


def _prefixdevname_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "prefixdevname.spec")
    return _cargo_vendored_generate(
        "prefixdevname",
        version,
        PREFIXDEVNAME_UPSTREAM_URL.format(version=version),
        PREFIXDEVNAME_INPUT_SHA512.get(version),
        out_dir,
    )


# --- gst-thumbnailers ----------------------------------------------------------

# Hummingbird ships no Rust crate RPMs, so the recipe cannot resolve gtk-rs,
# clap or libglycin-rebind from the buildroot (#527). The GNOME release already
# carries a Cargo.lock that pins every dependency to a crates.io checksum, so
# the factory vendors exactly that set beside the release, as prefixdevname
# does. The release itself is pinned here so a re-rolled tarball fails closed.
GST_THUMBNAILERS_UPSTREAM_URL = (
    "https://download.gnome.org/sources/gst-thumbnailers/{major_minor}/gst-thumbnailers-{version}.tar.xz"
)
GST_THUMBNAILERS_INPUT_SHA512 = {
    "1.1.0": "6498ba5824c771359b7b18d1a522459c9b899b7f64fcd99575a94d79810aa9122e158130fc5422b77c2439119af5d6767ec27b01a89e892d21143ca7748a2030",
}


def _gst_thumbnailers_url(version: str) -> str:
    major_minor = ".".join(version.split(".")[:2])
    return GST_THUMBNAILERS_UPSTREAM_URL.format(major_minor=major_minor, version=version)


def _gst_thumbnailers_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "gst-thumbnailers.spec")
    return {
        "name": "gst-thumbnailers",
        "version": version,
        "filename": f"gst-thumbnailers-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{_gst_thumbnailers_url(version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as gst-thumbnailers-{version}-vendored.tar.xz",
        },
    }


def _gst_thumbnailers_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "gst-thumbnailers.spec")
    return _cargo_vendored_generate(
        "gst-thumbnailers",
        version,
        _gst_thumbnailers_url(version),
        GST_THUMBNAILERS_INPUT_SHA512.get(version),
        out_dir,
    )


# --- ghostty -------------------------------------------------------------------

# Ghostty builds with `zig build`, which downloads every package in its Zig
# dependency graph; the hermetic build is offline. The release tarball carries
# that graph for packagers as build.zig.zon.json (Zig package hash -> name and
# URL), so the factory adds each archive to the release tree under zig-deps/,
# byte for byte as upstream serves it, and the recipe seeds Zig's package cache
# from them before building, as Dakota's elements/bluefin/ghostty.bst does
# (its generated block pins the same archives by SHA-256). The release and
# every archive are SHA-512-pinned below; at build time Zig also checks each
# unpacked package against the hash build.zig.zon names.
GHOSTTY_UPSTREAM_URL = "https://release.files.ghostty.org/{version}/ghostty-{version}.tar.gz"
GHOSTTY_MTIME = 0
# A git+ dependency is pinned to a commit: fetch that commit's forge archive.
# Zig hashes the unpacked tree, so the archive yields the same package.
GHOSTTY_GIT_ARCHIVES = {
    "github.com": "https://github.com/{repo}/archive/{commit}.tar.gz",
    "codeberg.org": "https://codeberg.org/{repo}/archive/{commit}.tar.gz",
}
# Version -> SHA-512 of the release, and of each dependency archive keyed by
# the Zig package hash build.zig.zon.json lists it under.
GHOSTTY_INPUT_SHA512 = {
    "1.4.0": {
        "release": "cbe2bebdfe786313050498f128e11b5d3cb1d5083e54ac5f52f7a54f04fa0888c1aea751dfca0fee802714e0cea5bc07640328483bd510b0ea5620ae985c0536",
        "deps": {
            # aro
            "aro-0.0.0-JSD1QtuBNwCASyBtNF3pqTl_W3oAJQGEVyFAtrBSE_Pa": "10c69b46450c36ad16a6541b09a2164bc0327901d6fb0ecbb9a24f680713e0dbbdc71888168a1991433880cd6b83fc431d64a97176158b3118c8533a9252d0c9",
            # bindings
            "N-V-__8AANT61wB--nJ95Gj_ctmzAtcjloZ__hRqNw5lC1Kr": "809986b89a8b452272eeb8b0a7d72c97600b03eaad208aa6ca823722adf645979a4bf03f5c5766ec907988953fdcd036db507305b1e2b79b923c29c1866b17a4",
            # breakpad
            "N-V-__8AALw2uwF_03u4JRkZwRLc3Y9hakkYV7NKRR9-RIZJ": "740b70daaf150a7619839f467eea6dc6d5dcd599861a977b1638c308b7902cb2de5d3927081143c2314e9b0c46c07d646ecec0e9e8d5097ddaa958766c07074d",
            # fontconfig
            "N-V-__8AAOgqbADacob-q2_DMQlmgaG4xKHRuW-6PJ4oJzMZ": "c3e769f74dc21093ada48084bddaca1ab525b1c4f04c5c11f067b69346fab153cad95de8b8238b20b02e8b9679c314bf2e0e9c4218511d8fe0f1826e4c4c6a24",
            # freetype
            "N-V-__8AAKLKpwC4H27Ps_0iL3bPkQb-z6ZVSrB-x_3EEkub": "9d7600af7e981227e37585dca71fbd7bc78b367a54d7705fe03e0f5549ce49e420548fa09b21c6bb137830f779a0a0b965611f50b163297b79fdc5903b4dc11d",
            # gettext
            "N-V-__8AADcZkgn4cMhTUpIz6mShCKyqqB-NBtf_S2bHaTC-": "9e9913fec1d3eeff65e023ee00c5da456baceabd49ce0c0d21f19b9911a60b67546f4ee5716f6f5b7a160b4c13c47604da8762854eba6f17f9bf3fd1c6056828",
            # glslang
            "N-V-__8AABzkUgISeKGgXAzgtutgJsZc0-kkeqBBscJgMkvy": "570d2ff15116f48e195c73d9be1517b05e7c37541af10f6c05779a001e2d0295725349c1f4dd0bcca6f0c7e7e48c5162a60726c3e76cf04619c8e14bd0636ab6",
            # gobject
            "gobject-0.3.2-Skun7LuIogBbEh-6WrLeEzMaRCnOMB3eOf__RaPYSMCZ": "37a080facdc223a9c52f2c47d0a07e5c7b630bb26844c2bd8164cb314fa3799f3e1da357ea81e9bd7a67cc407f541971e8808693da902a5224169d0d858ec77b",
            # gtk4_layer_shell
            "N-V-__8AALiNBAA-_0gprYr92CjrMj1I5bqNu0TSJOnjFNSr": "3b0728daea61d75dafa5dfacf47f6a6b3dd4c7e6d476917850cfd360d3cd2e48aa8e1210cf37f13738fdba37b1aca04b7c642b3204c9655da83e3ee24b3a26cf",
            # harfbuzz
            "N-V-__8AAG02ugUcWec-Ndp-i7JTsJ0dgF8nnJRUInkGLG7G": "1184b9b56c4b9f28cac03a6746d699d522c4194818e2b3fe4c286400c249bad209260137dc5c2aacc640ddd0a44db8999006e137dcabf8493b890a9fcf359170",
            # highway
            "N-V-__8AAGmZhABbsPJLfbqrh6JTHsXhY6qCaLAQyx25e0XE": "96f7ffcba67e6009b974169b2ce4106879018c541d9c2a7280489a00a666f2ceead80d1e2561c4c7fe12a3cbccc6dadc42d3fde5acaea9bb8b379598c44beb5b",
            # imgui
            "N-V-__8AAEbOfQBnvcFcCX2W5z7tDaN8vaNZGamEQtNOe0UI": "4618b8bd6e65ac27cd7cecb3469d135622279d83f8a580c028231578f7023c4465911c5878ee7e40c2f6dda606aef86f27c3cecfb7bc9a6022bd1d89eed17c29",
            # iterm2_themes
            "N-V-__8AAJ3vBQAq1fLMh5J8uWLkeDLS6WAdR2x5KcrmEyz6": "2594f50531f271c2847bedebeb5484996c9e3adc31af187a1cc0f12e0b6a510fdd743108971f53eb217970296e610565e72f5c6add7486d9c00a1dcd69228c1c",
            # jetbrains_mono
            "N-V-__8AAIC5lwAVPJJzxnCAahSvZTIlG-HhtOvnM1uh-66x": "546c4306a3523a676f7c335387b680ae57fb869aa18c52a0034bef7969e75810f43112e8be0e1a6e9738770fe5ba908bd2b6105f0362619bf1f5e30ea09786bc",
            # libpng
            "N-V-__8AAJrvXQCqAT8Mg9o_tk6m0yf5Fz-gCNEOKLyTSerD": "3bb2a7b73113be42b09c2116e6c6f5a7ddb4e2ab06e0b13e10b7314acdccc4bb624ff602e16140c0484f6cde80efa190296226be3da195c6926819f07c723c12",
            # libxev
            "libxev-0.0.0-86vtc8QQFACz0sVc7U-VDiDIgH-XfBuEY5JpABLjHNpn": "093f6e1829837f1601b9fb03bdce950ab3204d00f15655a60cc855f94db56d2d6b9a5861ea10032e8db6eb1851319c99cec260484838c5e78fc225cc27faf720",
            # libxml2
            "N-V-__8AAG3RoQEyRC2Vw7Qoro5SYBf62IHn3HjqtNVY6aWK": "303528ead0f020c8e172beca54d00bb1281f4080885c9f44b979158516b585d71bbcb024999a5712a850e48647b19b1f634a1428ea29f39a48e8e6cbf7c71936",
            # nerd_fonts_symbols_only
            "N-V-__8AAMVLTABmYkLqhZPLXnMl-KyN38R8UVYqGrxqO26s": "60ace3377f04c2c53fa067dde1a082fc3109b534a87ddf9c0a73fa65a82a3e15793351a39434ad4e0fe452cf60f019de27989ac90b74420bb92954efeb4962bc",
            # oniguruma
            "N-V-__8AAHjwMQDBXnLq3Q2QhaivE0kE2aD138vtX2Bq1g7c": "7c89247d8504c635687dc61b39b39b5afefa4851b24409a8eab31273f1cbc88f3db89095ae4b135bd034147d2616c2e18fc74887300b89532eedeab75677f437",
            # pixels
            "N-V-__8AADYiAAB_80AWnH1AxXC0tql9thT-R-DYO1gBqTLc": "ca66e3092481e678033cb4522e984444d2123fedf5fed039a5af58b51d22c3869c9e00246f261d50ea5d11bd1d4b6b61bf32aa9bad13a4f131fd115c3feb484d",
            # plasma_wayland_protocols
            "N-V-__8AAKYZBAB-CFHBKs3u4JkeiT4BMvyHu3Y5aaWF3Bbs": "909432de8881e063bfddd41d83758effc3dee43818d04126ccf6bd06a0ba1d4afd9ecdb49c86c584cad01607f625367b642e5d529d149c3e1732b2136a6b3bb3",
            # sentry
            "N-V-__8AAPlZGwBEa-gxrcypGBZ2R8Bse4JYSfo_ul8i2jlG": "28612a4358b5ec33e1e6ac434d04013dac746f8183c861afa9b6cf24e21db5f7531d8792442de83bffe56f33f7b56c5393a519b69a787501c06cdd60ece836e0",
            # spirv_cross
            "N-V-__8AANb6pwD7O1WG6L5nvD_rNMvnSc9Cpg1ijSlTYywv": "45e951822e2bf630190a33f863b8e05e9f12f57047736bbf973840fd06c583ab0516096c51a041934ca162bc63cf3e48e64220ed4af7c602ca1cb18bd5fe74e9",
            # translate_c
            "translate_c-2.0.0-Q_BUWltOBwBYABF84EUL208pIFeUIwbBs29FmVBaafN5": "09b7779c43072546d4b12b1e97915d78fd7cd1aa69c828aab31864e95ddd22203354c51ef926bc9f269f07694729135cd363d6976ccfe0c824d59dc50479d26b",
            # uucode
            "uucode-0.2.0-ZZjBPoGFVgCiflJNFc6Io8xzC67B6PA5bUkk4LT0kCxg": "803eb3c6e57ce611ca9d08bac60b33249af679231680c1da26ff1d26ada59a84a6ce878186479d4cc00bd1c7d19dd2bc177dee41c460c589008b344f4736d1a2",
            # vaxis
            "vaxis-0.6.0-BWNV_MafDAAEzkVUvrW9NFUqnnMUoeHqrs2mecnD6D7w": "5d015a51a6ecf685f90dd388f6c9ab3595a65c56764647a3a8a0643b3a26cef3e996ccea64055ab43913af4e5f4c0871b628a90ea972295b4400a5075b791ace",
            # wayland
            "N-V-__8AAKrHGAAs2shYq8UkE6bGcR1QJtLTyOE_lcosMn6t": "1a90c26e08280567c1ba2b023f04e14bbf0722eb8606d331cd60c420eca4ab6bb2cddc8cbfcf0c0bf00b00488a77e84eb4e95255f72a6600ade8a841e4d29671",
            # wayland_protocols
            "N-V-__8AAFdWDwA0ktbNUi9pFBHCRN4weXIgIfCrVjfGxqgA": "38359ac00179d052aee54c694dfacac508a7d16096891ee764c692482b582755d6f5747d4e87790e15228abda2c02a781ef796facb600145d37466620fb510f4",
            # wayland_protocols
            "N-V-__8AAKw-DAAaV8bOAAGqA0-oD7o-HNIlPFYKRXSPT03S": "ed642352a88eb9b42ba36c5847dd2023c7b5cdf638e57a2212dba64239017cae597de33e7a4f3530fcc0aac4633a8bd0178138b7e72cb1d42414b87c23b831c4",
            # wuffs
            "N-V-__8AAP5JWgCGP_AD0teWpa4krRvE9VPZzvviGdbmN4jI": "af1bf6d094165b03fd85d838357eae9a11696ea074741ca8a4e29afc2ccf2137fb6dd52b7d9e8c9e88eb660cbf1c53ae9bc6b7fa6085330873dc78397d5fed4e",
            # z2d
            "z2d-0.13.0-j5P_HgsRFABzZDH54gI35P0OSrg7HFyJwS2bXX5uBdU4": "38777dfcd531e0b598ffd3431b8846347e6fbdc098ff1b9e7c43052e8548cfd252c00866385b1314f488335a72da306c59d946eaf5646738bfd09f91bcc23108",
            # zf
            "zf-0.11.0-OIRy8XCRAAB6FiMwIrtD6FqlagnFwpI6YyOu7bXeYH5J": "0ad0901ca1a321195ba314c1964a87320cdaae99fadd74c69a84d67243e6161b0e0959ab4993b28ed27a72646b8fc78abeb469f968147192985179e4bd54c5db",
            # zig_js
            "zig_js-0.0.0-rjCAV7-GAADvMTBL7lPMuvDk7xgS9PCMIZWiOUXLZSlj": "e9795eef44e857f102a801fe1109f0a7b013e513d7cc9cdac6906e0d69eb46f14d2c7fabded14f90dfc3ed607595d3344b24cb267cfa269da4fb8bd5a8e26021",
            # zig_objc
            "zig_objc-0.0.0-Ir_Sp_4tAQDXtPi51nW_jD9LOEzBvU9lofwO9Pzi6IB4": "1fb3170d46be2d995baf49fbfcbe6bf85dff4d4787c5639162c3dd1ba3ba356b270173b51ff7e9c607d8b11a098a8fc0bd3698085bfabe75f43aeac1c6f7e7f1",
            # zig_wayland
            "wayland-0.7.0-dev-lQa1klz9AQB87V0pMKMdm8JvyOx32XR9FxcWnw9wh6XZ": "858816940953809f82a9520024abb627f3d873fa11706f57496a9293a8ad681df2c3091e0b1d0d78b6b2f02b02456b0d362edde96632b0496b3b6f4c23560401",
            # zigimg
            "zigimg-0.1.0-8_eo2ri_FwBqF5UYiggLz4IGjHJO_n9-B6gT9Ayqg8G4": "b630438c48aced233c062fb8efb8b6d491229570da21d8fa64b0709a9e2ba185d3807ca8355c60e62f89ffea4ef7760e6ef87f25e34859e64aa2ffc778ade766",
            # zlib
            "N-V-__8AAB0eQwD-0MdOEBmz7intriBReIsIDNlukNVoNu6o": "8c9642495bafd6fad4ab9fb67f09b268c69ff9af0f4f20cf15dfc18852ff1f312bd8ca41de761b3f8d8e90e77d79f2ccacd3d4c5b19e475ecf09d021fdfe9088",
        },
    },
}


def _ghostty_archive_url(url: str) -> str:
    """The download for a build.zig.zon.json URL: git+ deps become forge archives."""
    if not url.startswith("git+"):
        return url
    match = re.fullmatch(r"git\+https://([^/]+)/([^?#]+?)(?:\.git)?(?:\?[^#]*)?#([0-9a-f]{40})", url)
    if not match or match[1] not in GHOSTTY_GIT_ARCHIVES:
        raise RuntimeError(f"unsupported git dependency (need a pinned commit on a known forge): {url}")
    return GHOSTTY_GIT_ARCHIVES[match[1]].format(repo=match[2], commit=match[3])


def ghostty_dependencies(graph: dict) -> dict[str, str]:
    """Zig package hash -> archive URL, from a release's build.zig.zon.json."""
    return {zig_hash: _ghostty_archive_url(dep["url"]) for zig_hash, dep in graph.items()}


def _ghostty_transform(release: bytes, version: str, deps: dict[str, bytes]) -> bytes:
    """Repack the release tree and add zig-deps/<archive name> for each dependency.

    deps maps an archive's file name to its bytes. Members are sorted and
    stamped with a fixed mtime and zero ownership, so the same inputs always
    produce the same bytes.
    """
    top = f"ghostty-{version}"
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(release), mode="r:*") as src, \
            tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        for member in sorted(src.getmembers(), key=lambda m: m.name.rstrip("/")):
            if not (member.name.rstrip("/") == top or member.name.startswith(top + "/")):
                raise RuntimeError(f"archive member outside {top}: {member.name}")
            if member.name.startswith(f"{top}/zig-deps/") or member.name.rstrip("/") == f"{top}/zig-deps":
                raise RuntimeError(f"release already carries {top}/zig-deps")
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.pax_headers = {}
            member.mtime = GHOSTTY_MTIME
            result.addfile(member, src.extractfile(member) if member.isreg() else None)
        directory = tarfile.TarInfo(f"{top}/zig-deps")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        directory.mtime = GHOSTTY_MTIME
        result.addfile(directory)
        for name in sorted(deps):
            info = tarfile.TarInfo(f"{top}/zig-deps/{name}")
            info.size = len(deps[name])
            info.mode = 0o644
            info.mtime = GHOSTTY_MTIME
            result.addfile(info, io.BytesIO(deps[name]))
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _ghostty_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "ghostty.spec")
    return {
        "name": "ghostty",
        "version": version,
        "filename": f"ghostty-{version}-zig-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{GHOSTTY_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every Zig package archive its build.zig.zon.json lists (sha512-pinned)",
            "method": f"add zig-deps/<archive> for each build.zig.zon.json dependency, as served upstream, and repack deterministically as ghostty-{version}-zig-vendored.tar.xz",
        },
    }


def _ghostty_generate(package_dir: Path, out_dir: Path) -> Path:
    """Fetch the pinned release, then every dependency archive its graph lists.

    The release is checked before any dependency is downloaded. The graph must
    name exactly the pinned packages, and each archive must match its pin;
    nothing is written on a mismatch.
    """
    version = spec_version(package_dir, "ghostty.spec")
    pins = GHOSTTY_INPUT_SHA512.get(version)
    if pins is None:
        raise RuntimeError(f"no pinned input SHA-512 for ghostty {version}")
    url = GHOSTTY_UPSTREAM_URL.format(version=version)
    release = _fetch(url)
    actual = hashlib.sha512(release).hexdigest()
    if actual != pins["release"]:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pins['release']}, got {actual}")
    with tarfile.open(fileobj=io.BytesIO(release), mode="r:*") as source:
        graph = json.load(source.extractfile(f"ghostty-{version}/build.zig.zon.json"))
    urls = ghostty_dependencies(graph)
    if set(urls) != set(pins["deps"]):
        raise RuntimeError(
            f"ghostty {version} build.zig.zon.json does not name the pinned packages: "
            f"unpinned {sorted(set(urls) - set(pins['deps']))}, "
            f"missing {sorted(set(pins['deps']) - set(urls))}"
        )
    deps: dict[str, bytes] = {}
    for zig_hash, dep_url in sorted(urls.items()):
        name = dep_url.rsplit("/", 1)[1]
        if name in deps:
            raise RuntimeError(f"two ghostty dependencies share the archive name {name}")
        payload = _fetch(dep_url)
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pins["deps"][zig_hash]:
            raise RuntimeError(
                f"input archive mismatch for {dep_url}: expected {pins['deps'][zig_hash]}, got {actual}"
            )
        deps[name] = payload
    target = out_dir / f"ghostty-{version}-zig-vendored.tar.xz"
    target.write_bytes(_ghostty_transform(release, version, deps))
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
    # utah-packages#875: git.ffmpeg.org drops or stalls connections, which
    # aborted the daily source check. The locked input was reproduced from this
    # host for utah-packages#877: tag v2.6 resolves to the pinned commit below,
    # and `gzip -n -9` of its `git archive` gives the SHA-512 (423d7c94...)
    # committed in config/upstream-sources.json and packages/rtmpdump/sources.
    # This remote is the approved source and has no mirror; when it is down the
    # generator exits EXIT_UPSTREAM_UNREACHABLE and the pipeline reports
    # rtmpdump `unavailable` rather than accepting anything else.
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
        _git_network(
            ["git", "-C", tmp, "fetch", "-q", "--depth", "1", source["remote"], f"refs/tags/{tag}"],
            source["remote"],
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
    "prefixdevname": _prefixdevname_metadata,
    "gst-thumbnailers": _gst_thumbnailers_metadata,
    "ghostty": _ghostty_metadata,
    "freerdp": _freerdp_metadata,
    "fpaste": _fpaste_metadata,
    "7zip": _sevenzip_metadata,
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
    "prefixdevname": _prefixdevname_generate,
    "gst-thumbnailers": _gst_thumbnailers_generate,
    "ghostty": _ghostty_generate,
    "freerdp": _freerdp_generate,
    "fpaste": _fpaste_generate,
    "7zip": _sevenzip_generate,
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
    try:
        artifact = generate(package, package_dir, out_dir)
    except UpstreamUnreachable as error:
        # Only a proven outage takes this exit; a moved tag, an input digest
        # mismatch or any other failure propagates and exits 1.
        print(f"{package}: upstream unavailable: {error}", file=sys.stderr)
        return EXIT_UPSTREAM_UNREACHABLE
    print(json.dumps({
        "package": package,
        "filename": artifact.name,
        "sha512": sha512_path(artifact),
        "bytes": artifact.stat().st_size,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
