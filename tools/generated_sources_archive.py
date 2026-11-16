#!/usr/bin/env python3
"""Network-tarball source0 generators: intel-media-driver-free, tailscale,
gpm, openal-soft, 7zip, hplip, freerdp, fpaste and bluefin-artwork-logos.

Each transform fetches a pinned upstream artifact, extracts it, and returns the
``sources``/``spec`` record for the source lock. Reachability failures are
classified by the shared infra in ``generated_sources`` so a real outage still
exits with :data:`generated_sources.EXIT_UPSTREAM_UNREACHABLE`.
"""

import fnmatch
import gzip
import hashlib
import io
import lzma
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

from tools import generated_sources as generated_sources

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
    version = generated_sources.spec_version(package_dir, "intel-media-driver-free.spec")
    return {
        "name": "intel-media-driver-free",
        "version": version,
        "filename": f"intel-media-{version}-free.tar.gz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"https://github.com/intel/media-driver/archive/intel-media-{version}.tar.gz (sha512-pinned)",
            "method": f"remove non-free EU kernel files from the tag archive (strip.py removal set) and repack deterministically as intel-media-{version}-free.tar.gz",
        },
    }


def _imd_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "intel-media-driver-free.spec")
    pin = INTEL_MEDIA_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for intel-media {version}")
    url = f"https://github.com/intel/media-driver/archive/intel-media-{version}.tar.gz"
    payload = generated_sources._fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"intel-media-{version}-free.tar.gz"
    target.write_bytes(_imd_transform(payload, version))
    return target


# --- tailscale ---------------------------------------------------------------


def _tailscale_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "tailscale.spec")
    commit = TAILSCALE_COMMITS.get(version, "<unpinned>")
    return {
        "name": "tailscale",
        "version": version,
        "filename": f"tailscale-{version}-vendored.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"https://github.com/tailscale/tailscale tag v{version} (commit {commit})",
            "method": "go mod tidy && go mod vendor with GOTOOLCHAIN pinned from go.mod, drop unused cmd trees/k8s-operator/tstest, deterministic tar | xz -9e single-stream",
        },
    }


def _tailscale_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "tailscale.spec")
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
        generated_sources._git_network(
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
            generated_sources._xz_compress_stream(iter([raw.getvalue()]), sink)
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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _gpm_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "gpm.spec")
    return {
        "name": "gpm",
        "version": version,
        "filename": f"gpm-{version}.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"https://www.nico.schottelius.org/software/gpm/archives/gpm-{version}.tar.lzma (sha512-pinned)",
            "method": f"remove doc/specs (unclear licensing, per gpm.spec) from the upstream release and repack deterministically as gpm-{version}.tar.xz",
        },
    }


def _gpm_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "gpm.spec")
    pin = GPM_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for gpm {version}")
    url = f"https://www.nico.schottelius.org/software/gpm/archives/gpm-{version}.tar.lzma"
    payload = generated_sources._fetch(url)
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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _openal_soft_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "openal-soft.spec")
    return {
        "name": "openal-soft",
        "version": version,
        "filename": f"openal-soft-{version}-clean.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"https://openal-soft.org/openal-releases/openal-soft-{version}.tar.bz2 (sha512-pinned)",
            "method": f"remove the bundled fmt-*/ tree and utils/*.def datasets (non-free, per make_tarball.sh) from the upstream release and repack deterministically as openal-soft-{version}-clean.tar.xz",
        },
    }


def _openal_soft_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "openal-soft.spec")
    pin = OPENAL_SOFT_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for openal-soft {version}")
    url = f"https://openal-soft.org/openal-releases/openal-soft-{version}.tar.bz2"
    payload = generated_sources._fetch(url)
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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _sevenzip_metadata(package_dir: Path) -> dict:
    version = generated_sources.spec_version(package_dir, "7zip.spec")
    return {
        "name": "7zip",
        "version": version,
        "filename": f"7zip-{version}.tar.xz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{SEVENZIP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove the RAR handler, codecs, crypto and unRarLicense.txt (unRAR license restriction, per strip-rar-support.sh) from the upstream release and repack deterministically as 7zip-{version}.tar.xz",
        },
    }


def _sevenzip_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "7zip.spec")
    pin = SEVENZIP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for 7zip {version}")
    url = SEVENZIP_UPSTREAM_URL.format(version=version)
    payload = generated_sources._fetch(url)
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
    version = generated_sources.spec_version(package_dir, "hplip.spec")
    return {
        "name": "hplip",
        "version": version,
        "filename": f"hplip-{version}-repack.tar.gz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{HPLIP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove locatedriver (license-related, per hplip.spec/hplip-repack.sh) from the upstream release and repack deterministically as hplip-{version}-repack.tar.gz",
        },
    }


def _hplip_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "hplip.spec")
    pin = HPLIP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for hplip {version}")
    url = HPLIP_UPSTREAM_URL.format(version=version)
    payload = generated_sources._fetch(url)
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
    version = generated_sources.spec_version(package_dir, "freerdp.spec")
    return {
        "name": "freerdp",
        "version": version,
        "filename": f"FreeRDP-{version}-repack.tar.gz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{FREERDP_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"remove {FREERDP_DOOMED} (license not allowed, per freerdp.spec/freerdp_download_and_repack.sh) from the upstream release and repack deterministically as FreeRDP-{version}-repack.tar.gz",
        },
    }


def _freerdp_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "freerdp.spec")
    pin = FREERDP_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for freerdp {version}")
    url = FREERDP_UPSTREAM_URL.format(version=version)
    payload = generated_sources._fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"FreeRDP-{version}-repack.tar.gz"
    target.write_bytes(_freerdp_transform(payload, version))
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
    version = generated_sources.spec_version(package_dir, "fpaste.spec")
    return {
        "name": "fpaste",
        "version": version,
        "filename": f"fpaste-{version}.tar.gz",
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{FPASTE_UPSTREAM_URL.format(version=version)} (sha512-pinned)",
            "method": f"move the Codeberg tag archive from fpaste/ to fpaste-{version}/ without .gitignore (the tree of Fedora's hand-made tarball; pagure.io, the recipe's Source0 host, is gone) and repack deterministically as fpaste-{version}.tar.gz",
        },
    }


def _fpaste_generate(package_dir: Path, out_dir: Path) -> Path:
    version = generated_sources.spec_version(package_dir, "fpaste.spec")
    pin = FPASTE_INPUT_SHA512.get(version)
    if pin is None:
        raise RuntimeError(f"no pinned input SHA-512 for fpaste {version}")
    url = FPASTE_UPSTREAM_URL.format(version=version)
    payload = generated_sources._fetch(url)
    actual = hashlib.sha512(payload).hexdigest()
    if actual != pin:
        raise RuntimeError(f"input archive mismatch for {url}: expected {pin}, got {actual}")
    target = out_dir / f"fpaste-{version}.tar.gz"
    target.write_bytes(_fpaste_transform(payload, version))
    return target


# --- bluefin-artwork-logos -------------------------------------------------------


def _bluefin_artwork_commit(package_dir: Path) -> str:
    macros = generated_sources.recipe_macros((package_dir / "bluefin-artwork-logos.spec").read_text())
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
    generated_sources._xz_compress_stream(iter([raw.getvalue()]), out)
    return out.getvalue()


def _bluefin_artwork_metadata(package_dir: Path) -> dict:
    commit = _bluefin_artwork_commit(package_dir)
    filename = f"bluefin-artwork-logos-{commit[:7]}.tar.xz"
    urls = ", ".join(BLUEFIN_ARTWORK_RAW_URL.format(commit=commit, path=path)
                     for path in sorted(BLUEFIN_ARTWORK_FILES.get(commit, {})))
    return {
        "name": "bluefin-artwork-logos",
        "version": generated_sources.spec_version(package_dir, "bluefin-artwork-logos.spec"),
        "filename": filename,
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
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
        payload = generated_sources._fetch(url)
        actual = hashlib.sha512(payload).hexdigest()
        if actual != pin:
            raise RuntimeError(f"input file mismatch for {url}: expected {pin}, got {actual}")
        files[path] = payload
    target = out_dir / f"bluefin-artwork-logos-{commit[:7]}.tar.xz"
    target.write_bytes(_bluefin_artwork_transform(files, commit))
    return target
