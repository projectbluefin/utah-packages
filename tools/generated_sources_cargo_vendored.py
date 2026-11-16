#!/usr/bin/env python3
"""Cargo-vendored source0 generators: tealdeer, python-pydantic-core, prefixdevname,
gst-thumbnailers and kanata.

The inputs are ``Cargo.lock`` entries and a vendored ``.crate``/git tree rather
than a single tarball, so these transforms read lockfiles and build the vendored
directory layout packit expects.
"""

import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

from tools import generated_sources as generated_sources

# SHA-512 of the first-party input archives, pinned so a re-rolled upstream
# artifact fails closed instead of silently changing the generated output.
PYDANTIC_CORE_INPUT_SHA512 = {
    "2.46.5": "7af13f280d74ab0ded8e9299820930b0257502017f6a688d7d598e72351e127e178db11aeab987decaf95ca8619e151f244392ad9638ea184625728dcbb7cfff",
}

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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _pydantic_core_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "python-pydantic-core.spec")
    return {
        "name": "python-pydantic-core",
        "version": version,
        "filename": f"pydantic_core-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"https://files.pythonhosted.org/packages/source/p/pydantic_core/pydantic_core-{version}.tar.gz (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as pydantic_core-{version}-vendored.tar.xz",
        },
    }


def _pydantic_core_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "python-pydantic-core.spec")
    pin = PYDANTIC_CORE_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for pydantic_core {version}")
    url = f"https://files.pythonhosted.org/packages/source/p/pydantic_core/pydantic_core-{version}.tar.gz"
    sdist = generated_sources._fetch(url)
    actual = hashlib.sha512(sdist).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    with tarfile.open(fileobj=io.BytesIO(sdist), mode="r:gz") as source:
        lock_text = source.extractfile(f"pydantic_core-{version}/Cargo.lock").read().decode()
    crates = {
        (crate["name"], crate["version"]): generated_sources._fetch(CRATE_URL.format(**crate))
        for crate in cargo_lock_packages(lock_text)
    }
    target = out_dir / f"pydantic_core-{version}-vendored.tar.xz"
    target.write_bytes(_pydantic_core_transform(sdist, version, crates))
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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _cargo_vendored_generate(name: str, version: str, url: str, pin: str | None, out_dir: Path) -> Path:
    """Fetch a pinned release, then every crate its root Cargo.lock pins, and vendor them.

    The release is checked against its SHA-512 pin before any crate is
    downloaded, and each crate against its Cargo.lock SHA-256, so nothing
    reaches the output that was not pinned. Nothing is written on a mismatch.
    """
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for {name} {version}")
    archive = generated_sources._fetch(url)
    actual = hashlib.sha512(archive).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    top = f"{name}-{version}"
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:*") as source:
        lock_member = source.getmember(f"{top}/Cargo.lock")
        lock_text = source.extractfile(lock_member).read().decode()
    crates = {
        (crate["name"], crate["version"]): generated_sources._fetch(CRATE_URL.format(**crate))
        for crate in cargo_lock_packages(lock_text)
    }
    target = out_dir / f"{top}-vendored.tar.xz"
    target.write_bytes(_cargo_vendored_transform(archive, top, crates, CARGO_VENDORED_MTIME))
    return target


def _prefixdevname_transform(source: bytes, version: str, crates: dict) -> bytes:
    return _cargo_vendored_transform(source, f"prefixdevname-{version}", crates, PREFIXDEVNAME_MTIME)


def _prefixdevname_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "prefixdevname.spec")
    return {
        "name": "prefixdevname",
        "version": version,
        "filename": f"prefixdevname-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{PREFIXDEVNAME_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as prefixdevname-{version}-vendored.tar.xz",
        },
    }


def _prefixdevname_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "prefixdevname.spec")
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
    version = generated_sources.spec_version(package_dir, "gst-thumbnailers.spec")
    return {
        "name": "gst-thumbnailers",
        "version": version,
        "filename": f"gst-thumbnailers-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{_gst_thumbnailers_url(version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as gst-thumbnailers-{version}-vendored.tar.xz",
        },
    }


def _gst_thumbnailers_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "gst-thumbnailers.spec")
    return _cargo_vendored_generate(
        "gst-thumbnailers",
        version,
        _gst_thumbnailers_url(version),
        GST_THUMBNAILERS_INPUT_SHA512.get(version),
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
    version = generated_sources.spec_version(package_dir, "kanata.spec")
    return {
        "name": "kanata",
        "version": version,
        "filename": f"kanata-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{KANATA_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as kanata-{version}-vendored.tar.xz",
        },
    }



# --- tealdeer ------------------------------------------------------------------

# Project Bluefin Dakota ships tealdeer (bluefin/tealdeer.bst). Fedora has no
# recipe and Hummingbird ships no Rust crate RPMs, so the tag archive's
# Cargo.lock is vendored beside it, as gst-thumbnailers does.
TEALDEER_UPSTREAM_URL = "https://github.com/tealdeer-rs/tealdeer/archive/refs/tags/v{version}.tar.gz"
TEALDEER_INPUT_SHA512 = {
    "1.8.1": "3601007703b5f95adcd7b8e7a3467100b15d66d4d8fb6f6e11544f0046b844e4c8eedbd92522f49dbee36be92cccc6534687b51bd9e065dc9e0d731c0db593ec",
}


def _tealdeer_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "tealdeer.spec")
    return {
        "name": "tealdeer",
        "version": version,
        "filename": f"tealdeer-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{TEALDEER_UPSTREAM_URL.format(version=version)} (sha512-pinned) and every crates.io crate its Cargo.lock pins (sha256-pinned by Cargo.lock)",
            "method": f"add vendor/<crate>-<version> for each Cargo.lock crate with .cargo-checksum.json, as cargo vendor --versioned-dirs lays it out, and repack deterministically as tealdeer-{version}-vendored.tar.xz",
        },
    }


def _kanata_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "kanata.spec")
    return _cargo_vendored_generate(
        "kanata",
        version,
        KANATA_UPSTREAM_URL.format(version=version),
        KANATA_INPUT_SHA512.get(version),
        out_dir,
    )



def _tealdeer_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "tealdeer.spec")
    return _cargo_vendored_generate(
        "tealdeer",
        version,
        TEALDEER_UPSTREAM_URL.format(version=version),
        TEALDEER_INPUT_SHA512.get(version),
        out_dir,
    )
