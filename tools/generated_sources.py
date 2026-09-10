#!/usr/bin/env python3
"""Deterministic first-party Source0 generation.

The factory contract is that source payloads come from upstream releases and
Fedora dist-git supplies the recipe only. Three recipes consume an archive
that no upstream publishes verbatim:

- gcc: a VCS snapshot of the Red Hat vendor branch (packages/gcc/update-gcc.sh)
- intel-media-driver-free: the upstream tag archive with non-free kernel
  files removed (packages/intel-media-driver-free/strip.py)
- tailscale: a go-vendored bundle (packages/tailscale/create-vendor-tarball.sh)

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
import time
import urllib.request


SCRIPT_PATH = "tools/generated_sources.py"

# gcc.gnu.org rate-limits, and this factory asks it for the same revision from
# every concurrent run: four branches each building gcc at stage 0 is four
# clones at once, and the fourth gets
#   fatal: unable to access 'https://gcc.gnu.org/git/gcc.git/':
#   The requested URL returned error: 429
# before the build root is even up. Retry on the same schedule
# tools/source_pipeline.py uses for its HTTP fetches. This is availability
# only: git verifies every object against its own hash on receipt, and the
# caller still checks the pinned SHA-512 of the archive this produces.
FETCH_ATTEMPTS = 3

GCC_GIT_URL = "https://gcc.gnu.org/git/gcc.git"

# Packit keeps a local reference repository and clones against it
# (packit/utils/repo.py, RepositoryCache) so a repeated clone costs no network.
# The same trick answers the 429 above at its root rather than retrying it: with
# a mirror holding the pinned revision, the fetch is a local object copy and
# gcc.gnu.org is never asked. Set FACTORY_GIT_MIRROR to a directory to use one
# -- CI points it at a cached path keyed by the pinned revision, so a hit needs
# no network at all and a miss seeds the mirror for next time. Unset, or a
# mirror without the revision, falls back to fetching from upstream exactly as
# before. Integrity is unchanged either way: git verifies every object against
# its own hash on receipt, and the caller checks the archive's pinned SHA-512.
MIRROR_ENV = "FACTORY_GIT_MIRROR"

# SHA-512 of the first-party input archives, pinned so a re-rolled upstream
# artifact fails closed instead of silently changing the generated output.
INTEL_MEDIA_INPUT_SHA512 = {
    "26.2.4": "6e01092c06a100279b40ff46afa0c592483edc30e426fe802a79c2fa53b5ba16f952bdb445dfbfbfb7f50ef952727536f08c7eb0b3d06db25521fb9149887494",
}

# The annotated tag is mutable; the commit it resolves to is not. Pin it.
TAILSCALE_COMMITS = {
    "1.98.8": "05a91829316e055517a1e84f7b00016846ef4107",
}


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


# --- gcc -------------------------------------------------------------------


def _gcc_details(package_dir: Path) -> tuple[str, str, str, str]:
    text = (package_dir / "gcc.spec").read_text()
    macros = recipe_macros(text)
    version = macros["gcc_version"]
    prefix = f"gcc-{version}-{macros['DATE']}"
    return macros["gitrev"], version, prefix, macros["gcc_major"]


def _gcc_metadata(package_dir: Path) -> dict:
    revision, version, prefix, major = _gcc_details(package_dir)
    return {
        "name": "gcc",
        "version": version,
        "filename": f"{prefix}.tar.xz",
        "generate": {
            "script": SCRIPT_PATH,
            "input": f"https://gcc.gnu.org/git/gcc.git revision {revision} (vendors/redhat/heads/gcc-{major}-branch)",
            "method": f"git archive --prefix={prefix}/ {revision} | xz -9e (single-stream liblzma, preset 9 extreme)",
        },
    }


def _git_mirror(name: str) -> Path | None:
    """The configured reference mirror for one upstream, or None."""
    configured = os.environ.get(MIRROR_ENV)
    if not configured:
        return None
    return Path(configured) / f"{name}.git"


def _mirror_has(mirror: Path, revision: str) -> bool:
    if not (mirror / "objects").is_dir():
        return False
    return subprocess.run(
        ["git", "-C", str(mirror), "cat-file", "-e", f"{revision}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def _seed_mirror(mirror: Path, url: str, revision: str) -> None:
    """Record a fetched revision in the mirror so later runs need no network."""
    if not (mirror / "objects").is_dir():
        mirror.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", str(mirror)], check=True)
    subprocess.run(
        ["git", "-C", str(mirror), "fetch", "-q", "--depth", "1", url, revision],
        check=False,
    )


def _fetch_revision(repo: Path, url: str, revision: str, name: str) -> None:
    """Fetch one pinned revision, preferring a local mirror over the network."""
    mirror = _git_mirror(name)
    if mirror is not None and _mirror_has(mirror, revision):
        print(f"{name}: {revision} from mirror {mirror}", file=sys.stderr)
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "-q", "--depth", "1", str(mirror), revision],
            check=True,
        )
        return

    # Upstream serves fetch-by-sha1, so the pinned revision is fetched directly;
    # git verifies every object against its own hash on receipt.
    fetch = ["git", "-C", str(repo), "fetch", "-q", "--depth", "1", url, revision]
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        completed = subprocess.run(fetch)
        if completed.returncode == 0:
            break
        if attempt == FETCH_ATTEMPTS:
            raise RuntimeError(
                f"git fetch of {revision} from {url} failed after "
                f"{FETCH_ATTEMPTS} attempts (exit {completed.returncode})"
            )
        time.sleep(2 ** attempt)

    if mirror is not None:
        _seed_mirror(mirror, url, revision)


def _gcc_generate(package_dir: Path, out_dir: Path) -> Path:
    revision, _, prefix, _ = _gcc_details(package_dir)
    target = out_dir / f"{prefix}.tar.xz"
    with tempfile.TemporaryDirectory(prefix="gcc-fetch-", dir=out_dir) as tmp:
        repo = Path(tmp) / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        _fetch_revision(repo, GCC_GIT_URL, revision, "gcc")
        archive = subprocess.Popen(
            ["git", "-C", str(repo), "archive", f"--prefix={prefix}/", revision],
            stdout=subprocess.PIPE,
        )
        with target.open("wb") as sink:
            _xz_compress_stream(iter(lambda: archive.stdout.read(1024 * 1024), b""), sink)
        if archive.wait() != 0:
            raise RuntimeError(f"git archive failed for {revision}")
    return target


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


METADATA = {
    "gcc": _gcc_metadata,
    "intel-media-driver-free": _imd_metadata,
    "tailscale": _tailscale_metadata,
}

GENERATORS = {
    "gcc": _gcc_generate,
    "intel-media-driver-free": _imd_generate,
    "tailscale": _tailscale_generate,
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
