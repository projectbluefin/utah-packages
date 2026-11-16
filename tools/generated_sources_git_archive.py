#!/usr/bin/env python3
"""Git-archive source0 generators: distribution-gpg-keys, libslirp and rtmpdump.

Each entry locks a commit of a git repository and packs the checked-out tree
with ``git archive``. The commit is immutable, so the archive is reproducible
even though the remote ref moves.
"""

import gzip
import lzma
from pathlib import Path
import subprocess
import tempfile

from tools import generated_sources as generated_sources

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
    version = generated_sources.spec_version(package_dir, f"{name}.spec")
    commit = source["commits"].get(version, "<unpinned>")
    tag = source["tag"].format(version=version)
    filename = f"{name}-{version}.tar.{source['compression']}"
    return {
        "name": name,
        "version": version,
        "filename": filename,
        "generate": {
            "script": generated_sources.SCRIPT_PATH,
            "input": f"{source['remote']} tag {tag} (commit {commit})",
            "method": f"git archive --format=tar --prefix={name}-{version}/ of the pinned commit, compressed deterministically as {filename}",
        },
    }


def _git_archive_generate(name: str, package_dir: Path, out_dir: Path) -> Path:
    source = GIT_ARCHIVE_SOURCES[name]
    version = generated_sources.spec_version(package_dir, f"{name}.spec")
    commit = source["commits"].get(version)
    if commit is None:
        raise RuntimeError(f"no pinned commit for {name} {version}")
    tag = source["tag"].format(version=version)
    with tempfile.TemporaryDirectory(prefix=f"{name}-git-", dir=out_dir) as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        # Fetch only the tag: rtmpdump's repository advertises refs to the
        # all-zero object, which a full clone refuses.
        generated_sources._git_network(
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
