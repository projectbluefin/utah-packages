"""Generators that assemble Source0 from pinned inputs.

Pinned-commit files, OCI blobs, vendored Cargo trees and git archives.
tools/generated_sources.py registers them and re-exports every name defined
here.
"""

from __future__ import annotations

import hashlib
import io
import json
import lzma
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request

from tools.generated_sources_common import (
    BLUEFIN_ARTWORK_FILES,
    BLUEFIN_ARTWORK_RAW_URL,
    BLUEFIN_WALLPAPERS_FILES,
    SCRIPT_PATH,
    UpstreamUnreachable,
    _fetch,
    _git_network,
    is_transport_failure,
    recipe_macros,
    spec_version,
)
from tools.generated_sources_archives import (
    CRATE_URL,
    _vendored_crate_members,
    _xz_compress_stream,
    cargo_lock_packages,
)


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


# --- bluefin-wallpapers ----------------------------------------------------------

# Dakota's bluefin/wallpapers.bst installs the ghcr.io/projectbluefin/
# bluefin-wallpapers-gnome image, which artwork's CI fills by running
# package-gnome-wallpapers.sh over the repository. artwork publishes no file of
# that set and its archive is every wallpaper the project has, so the source is
# the script and exactly the files it reads, fetched at the commit the image
# was built from and kept at their repository paths; the recipe runs the
# script in %build. To move the pin: change commit and gitdate in the spec,
# add the new commit's files to BLUEFIN_WALLPAPERS_FILES, and relock.


def _bluefin_wallpapers_commit(package_dir: Path) -> str:
    macros = recipe_macros((package_dir / "bluefin-wallpapers.spec").read_text())
    commit = macros.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("bluefin-wallpapers.spec must pin %global commit to a full SHA-1")
    return commit


def _bluefin_wallpapers_transform(files: dict[str, bytes], commit: str) -> bytes:
    """Pack the fetched files at their repository paths, deterministically.

    Directories and files are sorted by name, owned by root with no names,
    modes 0755 and 0644, and stamped with a fixed mtime, so the same inputs
    always give the same bytes.
    """
    top = f"bluefin-wallpapers-{commit[:7]}"
    directories = {top}
    for path in files:
        parts = path.split("/")[:-1]
        for depth in range(1, len(parts) + 1):
            directories.add(f"{top}/{'/'.join(parts[:depth])}")
    members = {f"{top}/{path}": path for path in files}
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        for name in sorted(directories | set(members)):
            info = tarfile.TarInfo(name)
            info.mtime = 0
            if name in directories:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                result.addfile(info)
                continue
            data = files[members[name]]
            info.size = len(data)
            info.mode = 0o644
            result.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _bluefin_wallpapers_metadata(package_dir: Path) -> dict:
    commit = _bluefin_wallpapers_commit(package_dir)
    filename = f"bluefin-wallpapers-{commit[:7]}.tar.xz"
    count = len(BLUEFIN_WALLPAPERS_FILES.get(commit, {}))
    return {
        "name": "bluefin-wallpapers",
        "version": spec_version(package_dir, "bluefin-wallpapers.spec"),
        "filename": filename,
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"the {count} files BLUEFIN_WALLPAPERS_FILES lists under "
                     f"{BLUEFIN_ARTWORK_RAW_URL.format(commit=commit, path='')} (each sha512-pinned)",
            "method": f"fetch each file from projectbluefin/artwork at {commit} and pack them at their repository paths, deterministically, as {filename}",
        },
    }


def _bluefin_wallpapers_generate(package_dir: Path, out_dir: Path) -> Path:
    commit = _bluefin_wallpapers_commit(package_dir)
    pins = BLUEFIN_WALLPAPERS_FILES.get(commit)
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
    target = out_dir / f"bluefin-wallpapers-{commit[:7]}.tar.xz"
    target.write_bytes(_bluefin_wallpapers_transform(files, commit))
    return target


# --- brew-tarball ----------------------------------------------------------------

# Project Bluefin Dakota's bluefin/brew-tarball.bst stages the prebuilt Homebrew
# prefix Universal Blue publishes only inside its ghcr.io/ublue-os/brew image, as
# /system_files/usr/share/homebrew.tar.zst. The image's builder runs Homebrew's
# install.sh (a git clone plus portable Ruby), which is not reproducible, so the
# factory takes the file from the image Dakota pins: the per-architecture
# manifest digest, keyed here by the Homebrew version the archive carries. The
# manifest and every blob are checked against their digests and the member is
# copied out unchanged.
BREW_TARBALL_REGISTRY = "https://ghcr.io"
BREW_TARBALL_REPOSITORY = "ublue-os/brew"
BREW_TARBALL_MEMBER = "system_files/usr/share/homebrew.tar.zst"
BREW_TARBALL_MANIFESTS = {
    "7.0.11": "sha256:130848582eed433e85af6fa8c829ddec12ddaa6b18bc037a610b4b8da3c97458",
}
_OCI_MANIFEST_TYPES = (
    "application/vnd.oci.image.manifest.v1+json,"
    "application/vnd.docker.distribution.manifest.v2+json"
)


def _registry_fetch(path: str, token: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "utah-packages-generated-source/1", "Authorization": f"Bearer {token}"}
    if accept:
        headers["Accept"] = accept
    url = f"{BREW_TARBALL_REGISTRY}{path}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        if is_transport_failure(error):
            raise UpstreamUnreachable(f"could not reach {url}: {error}") from error
        raise


def _verified_digest(payload: bytes, digest: str, what: str) -> bytes:
    algorithm, _, expected = digest.partition(":")
    if algorithm != "sha256":
        raise RuntimeError(f"{what}: unsupported digest {digest}")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError(f"{what}: expected {digest}, got sha256:{actual}")
    return payload


def _brew_tarball_extract(manifest: bytes, blob) -> bytes:
    """Return BREW_TARBALL_MEMBER from the topmost layer of ``manifest`` that has it.

    ``blob(digest)`` returns a layer's bytes already checked against its digest.
    """
    layers = json.loads(manifest).get("layers") or []
    for layer in reversed(layers):
        with tarfile.open(fileobj=io.BytesIO(blob(layer["digest"])), mode="r:*") as archive:
            for member in archive.getmembers():
                if member.name.removeprefix("./").lstrip("/") == BREW_TARBALL_MEMBER and member.isreg():
                    return archive.extractfile(member).read()
    raise RuntimeError(f"no layer carries {BREW_TARBALL_MEMBER}")


def _brew_tarball_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "brew-tarball.spec")
    digest = BREW_TARBALL_MANIFESTS.get(version, "<unpinned>")
    return {
        "name": "brew-tarball",
        "version": version,
        "filename": f"homebrew-{version}.tar.zst",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"ghcr.io/{BREW_TARBALL_REPOSITORY}@{digest} (linux/amd64 image manifest; manifest and layers digest-pinned)",
            "method": f"copy /{BREW_TARBALL_MEMBER} unchanged out of the topmost image layer that carries it, as homebrew-{version}.tar.zst",
        },
    }


def _brew_tarball_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "brew-tarball.spec")
    digest = BREW_TARBALL_MANIFESTS.get(version)
    if digest is None:
        raise RuntimeError(f"no pinned image manifest for brew-tarball {version}")
    token_url = f"{BREW_TARBALL_REGISTRY}/token?scope=repository:{BREW_TARBALL_REPOSITORY}:pull"
    token = json.loads(_fetch(token_url))["token"]
    base = f"/v2/{BREW_TARBALL_REPOSITORY}"
    manifest = _verified_digest(
        _registry_fetch(f"{base}/manifests/{digest}", token, _OCI_MANIFEST_TYPES), digest, "image manifest"
    )
    payload = _brew_tarball_extract(
        manifest,
        lambda layer: _verified_digest(_registry_fetch(f"{base}/blobs/{layer}", token), layer, f"layer {layer}"),
    )
    target = out_dir / f"homebrew-{version}.tar.zst"
    target.write_bytes(payload)
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


def _cargo_vendored_transform(source: bytes, top: str, crates: dict, mtime: int, lock_text: str | None = None) -> bytes:
    """Add a vendor/ tree to a release tarball, deterministically.

    The archive already lays out the source under <top>/. Its compression is
    detected, so a .tar.gz and a .tar.xz release both work.
    vendor/<crate>-<version>/ is appended for each crate the release root's
    Cargo.lock pins, with its .cargo-checksum.json, exactly as
    `cargo vendor --versioned-dirs` lays it out. A recipe that patches its
    Cargo.lock passes the patched ``lock_text`` instead; the tree itself stays
    as released. Every member is stamped with a fixed mtime and zero
    ownership, so the same inputs always produce the same bytes.
    """
    raw = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:*") as src, \
            tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        members = sorted(src.getmembers(), key=lambda m: m.name.rstrip("/"))
        if lock_text is None:
            lock_text = src.extractfile(src.getmember(f"{top}/Cargo.lock")).read().decode()
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


def _cargo_vendored_generate(
    name: str, version: str, url: str, pin: str | None, out_dir: Path, top: str | None = None
) -> Path:
    """Fetch a pinned release, then every crate its root Cargo.lock pins, and vendor them.

    The release is checked against its SHA-512 pin before any crate is
    downloaded, and each crate against its Cargo.lock SHA-256, so nothing
    reaches the output that was not pinned. Nothing is written on a mismatch.
    `top` is the archive's top directory, and names the output; it defaults
    to <name>-<version>, and a commit archive passes <name>-<commit>.
    """
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for {name} {version}")
    archive = _fetch(url)
    actual = hashlib.sha512(archive).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    top = top or f"{name}-{version}"
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


# --- kanata --------------------------------------------------------------------

# Project Bluefin Dakota builds kanata from its tag with cargo (bluefin/kanata.bst).
# Fedora has no recipe and Hummingbird ships no Rust crate RPMs, so the tag
# archive's Cargo.lock is vendored beside it, as prefixdevname does. The
# workspace's own members (parser, keyberon, tcp_protocol) are path sources
# inside the archive and need no download.
KANATA_UPSTREAM_URL = "https://github.com/jtroo/kanata/archive/refs/tags/v{version}.tar.gz"
KANATA_INPUT_SHA512 = {
    "1.12.0": "c7473224d0077d1558da062b8787db650937f4125e19b4e4bd66e75a80db5f38ab8ccf0fcd93c20625035b93f309d92b7a182d214478c37e615805baaec6396d",
}


def _kanata_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "kanata.spec")
    return {
        "name": "kanata",
        "version": version,
        "filename": f"kanata-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{KANATA_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as kanata-{version}-vendored.tar.xz",
        },
    }


def _kanata_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "kanata.spec")
    return _cargo_vendored_generate(
        "kanata",
        version,
        KANATA_UPSTREAM_URL.format(version=version),
        KANATA_INPUT_SHA512.get(version),
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


# --- oo7 -----------------------------------------------------------------------

# Fedora builds oo7 against its crate RPMs. Fedora 44 lacks three that the
# pinned commit needs (formatx 0.4, gettext-rs 0.8, zgvariant 1), and
# Hummingbird ships no crate RPMs, so the lock step cannot resolve them (run
# 44224171778). The commit archive carries a Cargo.lock, so the factory
# vendors exactly that set beside it, as gst-thumbnailers does. The archive
# is keyed by the spec's %global commit and pinned here.
OO7_UPSTREAM_URL = "https://github.com/linux-credentials/oo7/archive/{commit}/oo7-{shortcommit}.tar.gz"
OO7_INPUT_SHA512 = {
    "e91b98a7235a4971c6cbb7f0533034afc8a8f618": "4ebce6b36406ad1d53421269a8788226a047a4475b2e69a6d84388c6d0569fddd91357c5c38d1b1a906dc3fb51d50068930ed6ce1ad9ace51025350b6c9dbc79",
}


def _oo7_commit_version(package_dir: Path) -> tuple[str, str]:
    macros = recipe_macros((package_dir / "oo7.spec").read_text())
    commit = macros.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("oo7.spec must pin %global commit to a full SHA-1")
    return commit, macros["version"].replace("%{shortcommit}", commit[:7])


def _oo7_url(commit: str) -> str:
    return OO7_UPSTREAM_URL.format(commit=commit, shortcommit=commit[:7])


def _oo7_metadata(package_dir: Path) -> dict:
    commit, version = _oo7_commit_version(package_dir)
    return {
        "name": "oo7",
        "version": version,
        "filename": f"oo7-{commit}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{_oo7_url(commit)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as oo7-{commit}-vendored.tar.xz",
        },
    }


def _oo7_generate(package_dir: Path, out_dir: Path) -> Path:
    commit, version = _oo7_commit_version(package_dir)
    return _cargo_vendored_generate(
        "oo7", commit, _oo7_url(commit), OO7_INPUT_SHA512.get(commit), out_dir, top=f"oo7-{commit}"
    )


# --- tealdeer ------------------------------------------------------------------

# Project Bluefin Dakota ships tealdeer (bluefin/tealdeer.bst). Fedora has no
# recipe and Hummingbird ships no Rust crate RPMs, so the tag archive's
# Cargo.lock is vendored beside it, as gst-thumbnailers does.
TEALDEER_UPSTREAM_URL = "https://github.com/tealdeer-rs/tealdeer/archive/refs/tags/v{version}.tar.gz"
TEALDEER_INPUT_SHA512 = {
    "1.8.1": "3601007703b5f95adcd7b8e7a3467100b15d66d4d8fb6f6e11544f0046b844e4c8eedbd92522f49dbee36be92cccc6534687b51bd9e065dc9e0d731c0db593ec",
}


def _tealdeer_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "tealdeer.spec")
    return {
        "name": "tealdeer",
        "version": version,
        "filename": f"tealdeer-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{TEALDEER_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as tealdeer-{version}-vendored.tar.xz",
        },
    }


def _tealdeer_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "tealdeer.spec")
    return _cargo_vendored_generate(
        "tealdeer",
        version,
        TEALDEER_UPSTREAM_URL.format(version=version),
        TEALDEER_INPUT_SHA512.get(version),
        out_dir,
    )


# --- bluefin-cli ---------------------------------------------------------------

# Utah's terminal experience (shell tools, prompt hooks, MOTD) from
# tuna-os/bluefin-cli. Fedora has no recipe. Each release publishes, beside its
# tag, bluefin-cli-<version>-vendor.tar.gz: the `go mod vendor` tree of every
# module go.sum pins (scripts/vendor-archive.sh upstream). The lock takes one
# primary source and a second `sources` line resolves only from a dist-git
# lookaside, so both release files are SHA-512-pinned here and the vendor tree
# is unpacked into the tag archive, which builds offline as gum's Source0 and
# Source1 do together.
BLUEFIN_CLI_UPSTREAM_URL = "https://github.com/tuna-os/bluefin-cli/archive/v{version}/bluefin-cli-{version}.tar.gz"
BLUEFIN_CLI_VENDOR_URL = (
    "https://github.com/tuna-os/bluefin-cli/releases/download/v{version}/bluefin-cli-{version}-vendor.tar.gz"
)
# version -> (tag archive SHA-512, vendor archive SHA-512)
BLUEFIN_CLI_INPUT_SHA512: dict[str, tuple[str, str]] = {
    "0.15.0": (
        "540be790f92d45ac61526c6437be74f47ed0353e047768d7577ac54833e51a88cd5937571472a2952cb07fe79af2b9c1611bb75b7a0dcac5d97530e1b1644256",
        "731b2b5954672d2b2f5e824ed1d71ebf93b912276df7aab060cb2a011e7ef7a552a9ae323fb77bf6536cef29a71320a0f74ff99c57b1d01956f2117b74a847a9",
    ),
}
BLUEFIN_CLI_MTIME = 0


def _normalized(member: tarfile.TarInfo, name: str, mtime: int) -> tarfile.TarInfo:
    member.name = name
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    member.pax_headers = {}
    member.mtime = mtime
    return member


def _bluefin_cli_transform(source: bytes, vendor: bytes, version: str) -> bytes:
    """Unpack the release's vendor/ tree into its tag archive, deterministically.

    Every member of both archives is renamed under bluefin-cli-<version>/,
    sorted, owned by root with no names, and stamped with a fixed mtime, so the
    same two inputs always give the same bytes. A tag archive that already
    carries vendor/, or a vendor archive with anything outside vendor/, is
    refused rather than merged.
    """
    top = f"bluefin-cli-{version}"
    members: dict[str, tuple[tarfile.TarInfo, bytes | None]] = {}
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:*") as src:
        for member in src.getmembers():
            name = member.name.rstrip("/")
            if not (name == top or name.startswith(top + "/")):
                raise RuntimeError(f"archive member outside {top}: {member.name}")
            if name == f"{top}/vendor" or name.startswith(f"{top}/vendor/"):
                raise RuntimeError(f"tag archive already carries {name}")
            data = src.extractfile(member).read() if member.isreg() else None
            members[name] = (_normalized(member, name, BLUEFIN_CLI_MTIME), data)
    with tarfile.open(fileobj=io.BytesIO(vendor), mode="r:*") as src:
        for member in src.getmembers():
            name = member.name.rstrip("/").removeprefix("./")
            if not (name == "vendor" or name.startswith("vendor/")):
                raise RuntimeError(f"vendor archive member outside vendor/: {member.name}")
            data = src.extractfile(member).read() if member.isreg() else None
            members[f"{top}/{name}"] = (_normalized(member, f"{top}/{name}", BLUEFIN_CLI_MTIME), data)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as result:
        for name in sorted(members):
            info, data = members[name]
            result.addfile(info, io.BytesIO(data) if data is not None else None)
    out = io.BytesIO()
    _xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _bluefin_cli_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "bluefin-cli.spec")
    return {
        "name": "bluefin-cli",
        "version": version,
        "filename": f"bluefin-cli-{version}-vendored.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{BLUEFIN_CLI_UPSTREAM_URL.format(version=version)} and "
                     f"{BLUEFIN_CLI_VENDOR_URL.format(version=version)} (each sha512-pinned)",
            "method": f"unpack the release's vendor/ tree into the tag archive and repack deterministically as bluefin-cli-{version}-vendored.tar.xz",
        },
    }


def _bluefin_cli_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "bluefin-cli.spec")
    pins = BLUEFIN_CLI_INPUT_SHA512.get(version)
    if pins is None:
        raise RuntimeError(f"no pinned input SHA-512 for bluefin-cli {version}")
    payloads = []
    for url, pin in zip((BLUEFIN_CLI_UPSTREAM_URL.format(version=version),
                         BLUEFIN_CLI_VENDOR_URL.format(version=version)), pins):
        payload = _fetch(url)
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pin:
            raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
        payloads.append(payload)
    target = out_dir / f"bluefin-cli-{version}-vendored.tar.xz"
    target.write_bytes(_bluefin_cli_transform(*payloads, version))
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


def _git_tag_tar(name: str, remote: str, tag: str, commit: str, prefix: str, scratch: Path) -> bytes:
    """`git archive` of ``commit`` under ``prefix``, once ``tag`` is proven to resolve to it."""
    with tempfile.TemporaryDirectory(prefix=f"{name}-git-", dir=scratch) as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        # Fetch only the tag: rtmpdump's repository advertises refs to the
        # all-zero object, which a full clone refuses.
        _git_network(
            ["git", "-C", tmp, "fetch", "-q", "--depth", "1", remote, f"refs/tags/{tag}"],
            remote,
        )
        head = subprocess.check_output(
            ["git", "-C", tmp, "rev-parse", "FETCH_HEAD^{commit}"], text=True
        ).strip()
        if head != commit:
            raise RuntimeError(f"tag {tag} moved: expected {commit}, got {head}")
        return subprocess.check_output(
            ["git", "-C", tmp, "archive", "--format=tar", f"--prefix={prefix}/", commit]
        )


def _git_archive_generate(name: str, package_dir: Path, out_dir: Path) -> Path:
    source = GIT_ARCHIVE_SOURCES[name]
    version = spec_version(package_dir, f"{name}.spec")
    commit = source["commits"].get(version)
    if commit is None:
        raise RuntimeError(f"no pinned commit for {name} {version}")
    tag = source["tag"].format(version=version)
    raw = _git_tag_tar(name, source["remote"], tag, commit, f"{name}-{version}", out_dir)
    target = out_dir / f"{name}-{version}.tar.{source['compression']}"
    target.write_bytes(_git_archive_compress(raw, source["compression"]))
    return target


# --- gstreamer-plugins-rs --------------------------------------------------------

# Dakota ships freedesktop-sdk's components/gstreamer-plugins-rs.bst: the
# gst-plugins-rs tag, built for the rtp, gif, hlssink3, dav1d and spotify
# plugins from vendored crates (#1040). The project publishes no release file,
# so the input is `git archive` of the tag's pinned commit, as above. The
# recipe does not build the lock as released: its patches (freedesktop-sdk's
# move from git gtk-rs to crates.io, then the workspace cut to the five
# plugins) change it, so every spec Patch is applied to Cargo.lock first and
# that lock decides the vendored set. The tree stays as released; %prep
# applies the same patches.
GSTREAMER_PLUGINS_RS_REMOTE = "https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs.git"
GSTREAMER_PLUGINS_RS_COMMITS = {
    "0.15.4": "1afff3711855238433862c0ce3bf34918e500386",
}


def recipe_patches(package_dir: Path, spec_name: str) -> list[Path]:
    """The recipe's Patch files, in spec order."""
    patches = []
    for line in (package_dir / spec_name).read_text().splitlines():
        match = re.match(r"Patch\d*\s*:\s*(\S+)\s*$", line)
        if match:
            if "%" in match.group(1):
                raise ValueError(f"{spec_name}: Patch {match.group(1)} uses a macro; name the file")
            patches.append(package_dir / match.group(1))
    return patches


def _patched_cargo_lock(lock_text: str, patches: list[Path], scratch: Path) -> str:
    """Cargo.lock after every patch's Cargo.lock hunks, applied by git apply.

    The scratch directory is its own repository, so git applies the paths
    there even when the output directory sits inside a checkout.
    """
    with tempfile.TemporaryDirectory(prefix="cargo-lock-", dir=scratch) as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        lock = Path(tmp) / "Cargo.lock"
        lock.write_text(lock_text)
        if patches:
            subprocess.run(
                ["git", "-C", tmp, "apply", "--include=Cargo.lock", *(str(p.resolve()) for p in patches)],
                check=True,
            )
        return lock.read_text()


def _gstreamer_plugins_rs_metadata(package_dir: Path) -> dict:
    version = spec_version(package_dir, "gstreamer-plugins-rs.spec")
    commit = GSTREAMER_PLUGINS_RS_COMMITS.get(version, "<unpinned>")
    filename = f"gst-plugins-rs-{version}-vendored.tar.xz"
    return {
        "name": "gstreamer-plugins-rs",
        "version": version,
        "filename": filename,
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"{GSTREAMER_PLUGINS_RS_REMOTE} tag {version} (commit {commit}) and every crates.io crate its Cargo.lock pins after the recipe's patches (sha256-pinned by that Cargo.lock)",
            "method": f"git archive --format=tar --prefix=gst-plugins-rs-{version}/ of the pinned commit, add vendor/<crate>-<version> for each patched Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as {filename}",
        },
    }


def _gstreamer_plugins_rs_generate(package_dir: Path, out_dir: Path) -> Path:
    version = spec_version(package_dir, "gstreamer-plugins-rs.spec")
    commit = GSTREAMER_PLUGINS_RS_COMMITS.get(version)
    if commit is None:
        raise RuntimeError(f"no pinned commit for gstreamer-plugins-rs {version}")
    patches = recipe_patches(package_dir, "gstreamer-plugins-rs.spec")
    top = f"gst-plugins-rs-{version}"
    archive = _git_tag_tar("gstreamer-plugins-rs", GSTREAMER_PLUGINS_RS_REMOTE, version, commit, top, out_dir)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
        released = source.extractfile(source.getmember(f"{top}/Cargo.lock")).read().decode()
    lock_text = _patched_cargo_lock(released, patches, out_dir)
    crates = {
        (crate["name"], crate["version"]): _fetch(CRATE_URL.format(**crate))
        for crate in cargo_lock_packages(lock_text)
    }
    target = out_dir / f"{top}-vendored.tar.xz"
    target.write_bytes(_cargo_vendored_transform(archive, top, crates, CARGO_VENDORED_MTIME, lock_text))
    return target
