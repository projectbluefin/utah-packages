#!/usr/bin/env python3
"""Deterministic first-party Source0 generation.

The registry is the only place that knows every package; the reproducible
transforms live in sibling modules grouped by how they reach upstream: network
tarballs (generated_sources_archive), cargo vendoring (generated_sources_cargo_vendored)
and git archives (generated_sources_git_archive). The registry imports each
sibling's registry functions and re-exports the pins, URLs and transforms so the
module is still importable as a single ``generated_sources`` facade.

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
- kanata: the upstream GitHub tag archive (SHA-512-pinned) with the same
  `vendor/` tree added, for Dakota's keyboard remapper (projectbluefin/utah#1222)
- gst-thumbnailers: the upstream GNOME release (SHA-512-pinned) with the same
  `vendor/` tree added. Hummingbird ships no Rust crate RPMs, so the recipe
  bundles its gtk-rs, clap and libglycin-rebind dependencies (#527)
- tealdeer: the upstream GitHub tag archive (SHA-512-pinned) with the same
  `vendor/` tree added, for Dakota's tldr client (#1034)

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

# This module is imported as tools.generated_sources (source_pipeline.py, the
# tests) *and* run directly (``python3 tools/generated_sources.py`` by the CLI
# test). When run directly the tools/ directory sits on sys.path[0], so the
# sibling modules under the tools package are not importable until the repository
# root is added back. Skipping the re-add when imported keeps importers untouched.
if "tools" not in sys.modules:
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    # Run as a script (tools/ on sys.path[0]): register this module under its
    # package name so the siblings' ``from tools.generated_sources import ...``
    # resolve to the running instance instead of starting a second, circular copy.
    sys.modules["tools.generated_sources"] = sys.modules[__name__]

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


from tools.generated_sources_archive import (
    _bluefin_artwork_generate, _bluefin_artwork_metadata, _fpaste_generate,
    _fpaste_metadata, _freerdp_generate, _freerdp_metadata, _gpm_generate,
    _gpm_metadata, _hplip_generate, _hplip_metadata, _imd_generate,
    _imd_metadata, _openal_soft_generate, _openal_soft_metadata,
    _sevenzip_generate, _sevenzip_metadata, _tailscale_generate,
    _tailscale_metadata,
)
from tools.generated_sources_cargo_vendored import (
    _kanata_generate, _kanata_metadata, _gst_thumbnailers_generate,
    _gst_thumbnailers_metadata, _prefixdevname_generate,
    _prefixdevname_metadata, _pydantic_core_generate, _pydantic_core_metadata,
    _tealdeer_generate, _tealdeer_metadata,
)
from tools.generated_sources_git_archive import _git_archive_generate, _git_archive_metadata

# Re-export every other name the original tools.generated_sources module exposed
# so the public surface is unchanged: bootstrap_upstream_sources.py and the tests
# still see these as attributes of generated_sources after the move.
from tools.generated_sources_archive import (
    FPASTE_UPSTREAM_URL, FREERDP_DOOMED, FREERDP_UPSTREAM_URL, HPLIP_UPSTREAM_URL,
    SEVENZIP_UPSTREAM_URL, TAILSCALE_COMMITS, _bluefin_artwork_commit,
    _freerdp_pax_path, _freerdp_record_size, _imd_stripped, _openal_soft_dropped,
    _sevenzip_dropped,
)
from tools.generated_sources_cargo_vendored import (
    GST_THUMBNAILERS_UPSTREAM_URL, _cargo_vendored_generate, _cargo_vendored_transform,
    _gst_thumbnailers_url,
)
from tools.generated_sources_git_archive import _git_archive_compress

from tools.generated_sources_archive import (
    BLUEFIN_ARTWORK_FILES, BLUEFIN_ARTWORK_RAW_URL, FPASTE_INPUT_SHA512,
    FREERDP_INPUT_SHA512, GPM_INPUT_SHA512, HPLIP_INPUT_SHA512, INTEL_MEDIA_INPUT_SHA512,
    OPENAL_SOFT_INPUT_SHA512, SEVENZIP_INPUT_SHA512, _bluefin_artwork_transform,
    _fpaste_transform, _freerdp_transform, _gpm_transform, _hplip_transform,
    _imd_transform, _openal_soft_transform, _sevenzip_transform,
)
from tools.generated_sources_cargo_vendored import (
    CARGO_VENDORED_MTIME, CRATE_URL, CRATES_IO_INDEX, GST_THUMBNAILERS_INPUT_SHA512,
    KANATA_INPUT_SHA512, KANATA_UPSTREAM_URL, PYDANTIC_CORE_INPUT_SHA512,
    PREFIXDEVNAME_INPUT_SHA512, PREFIXDEVNAME_MTIME, PREFIXDEVNAME_UPSTREAM_URL,
    TEALDEER_INPUT_SHA512, TEALDEER_UPSTREAM_URL,
    _prefixdevname_transform, _pydantic_core_transform,
    cargo_lock_packages, _vendored_crate_members,
)
from tools.generated_sources_git_archive import GIT_ARCHIVE_SOURCES



METADATA = {
    **{name: functools.partial(_git_archive_metadata, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_metadata,
    "tailscale": _tailscale_metadata,
    "python-pydantic-core": _pydantic_core_metadata,
    "gpm": _gpm_metadata,
    "hplip": _hplip_metadata,
    "openal-soft": _openal_soft_metadata,
    "prefixdevname": _prefixdevname_metadata,
    "kanata": _kanata_metadata,
    "gst-thumbnailers": _gst_thumbnailers_metadata,
    "freerdp": _freerdp_metadata,
    "tealdeer": _tealdeer_metadata,
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
    "kanata": _kanata_generate,
    "gst-thumbnailers": _gst_thumbnailers_generate,
    "freerdp": _freerdp_generate,
    "tealdeer": _tealdeer_generate,
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