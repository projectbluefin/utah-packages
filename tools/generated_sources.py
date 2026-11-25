#!/usr/bin/env python3
"""Deterministic first-party Source0 generation.

The factory contract is that source payloads come from upstream releases and
Fedora dist-git supplies the recipe only. These recipes consume an archive
that no upstream publishes verbatim:

- intel-media-driver-free: the upstream tag archive with non-free kernel
  files removed (packages/intel-media-driver-free/strip.py)
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
- jpegxl: the upstream libjxl release with the three git submodules the
  recipe builds and tests from (sjpeg, skcms without its ICC profiles,
  testdata) filled in at the commits the release tag pins. The release
  archive leaves submodules empty; Fedora's update_third_party.sh tars them
  up by hand as two extra lookaside sources, which a bump cannot produce
- bluefin-artwork-logos: the Bluefin logo SVGs and the license from
  projectbluefin/artwork at a pinned commit. The repository publishes no
  release, and its archive carries every wallpaper (well over 100 MB) for
  three small files, so each file is fetched at the commit, SHA-512-checked,
  and packed into one archive
- bluefin-wallpapers: Bluefin's GNOME wallpaper set from projectbluefin/artwork
  at the commit Dakota's wallpaper image was built from. artwork ships the
  set only as an OCI image, so package-gnome-wallpapers.sh and exactly the
  files it reads are fetched at the commit, SHA-512-checked, and packed at
  their repository paths
- brew-tarball: Universal Blue's prebuilt Homebrew prefix, copied unchanged
  out of the digest-pinned ghcr.io/ublue-os/brew image Dakota stages it from;
  it is published nowhere else (#1039)
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
- gstreamer-plugins-rs: `git archive` of the gst-plugins-rs tag at a pinned
  commit with the same `vendor/` tree, built from Cargo.lock as the recipe's
  patches leave it: Dakota's freedesktop-sdk element patches the lock (#1040)
- hyperv-daemons: the kernel's tools/hv and the tools/build and
  tools/scripts makefiles it includes, cut from the stable kernel release
  (SHA-512-pinned). The kernel publishes no tools/hv archive; Fedora's
  lookaside copy is a hand-cut snapshot of the same paths
- tealdeer: the upstream GitHub tag archive (SHA-512-pinned) with the same
  `vendor/` tree added, for Dakota's tldr client (#1034)
- oo7: the upstream GitHub commit archive (SHA-512-pinned, keyed by the
  spec's commit) with the same `vendor/` tree added. Fedora 44 lacks crate
  RPMs the commit needs, and Hummingbird ships none (#1192)
- bluefin-cli: the upstream GitHub tag archive with the `vendor/` tree of
  the release's own bluefin-cli-<version>-vendor.tar.gz unpacked into it,
  both SHA-512-pinned. Fedora has no recipe, and the vendor archive is a
  release asset no lookaside carries, so it cannot be a second `sources` line

For these, the source lock names this script and records the SHA-512 of the
bytes the transformation produces. Verification re-runs the transformation
from the pinned first-party input and fails closed on any drift; no payload
is fetched from Fedora's lookaside.

Everything runs on the Python standard library plus the git CLI, so it works
in the digest-pinned ghcr.io/projectbluefin/lab-runner FSDK image and on
GitHub-hosted runners without installing anything at runtime.
"""


from __future__ import annotations

import functools
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The generators live in three sibling modules; every name they define is
# re-exported here so `tools.generated_sources.<name>` keeps working.
from tools.generated_sources_common import (
    BLUEFIN_ARTWORK_FILES,
    BLUEFIN_ARTWORK_RAW_URL,
    BLUEFIN_WALLPAPERS_FILES,
    EXIT_UPSTREAM_UNREACHABLE,
    FPASTE_INPUT_SHA512,
    GIT_NETWORK_TIMEOUT_SECONDS,
    GPM_INPUT_SHA512,
    HPLIP_INPUT_SHA512,
    INTEL_MEDIA_INPUT_SHA512,
    OPENAL_SOFT_INPUT_SHA512,
    PYDANTIC_CORE_INPUT_SHA512,
    SCRIPT_PATH,
    SEVENZIP_INPUT_SHA512,
    UpstreamUnreachable,
    _GIT_PERMANENT_FAILURE,
    _GIT_TRANSPORT_FAILURE,
    _UNREACHABLE_ERRNOS,
    _fetch,
    _git_network,
    git_transport_failure,
    is_transport_failure,
    recipe_macros,
    sha512_path,
    spec_version,
    transient_http_status,
)
from tools.generated_sources_archives import (
    CRATES_IO_INDEX,
    CRATE_URL,
    FPASTE_UPSTREAM_URL,
    FREERDP_DOOMED,
    FREERDP_INPUT_SHA512,
    FREERDP_UPSTREAM_URL,
    HPLIP_UPSTREAM_URL,
    HYPERV_KERNEL_INPUT_SHA512,
    HYPERV_KERNEL_URL,
    HYPERV_TOOLS_FILES,
    JPEGXL_DROPPED,
    JPEGXL_INPUTS,
    JPEGXL_UPSTREAM_URL,
    SEVENZIP_UPSTREAM_URL,
    _fpaste_generate,
    _fpaste_metadata,
    _fpaste_transform,
    _freerdp_generate,
    _freerdp_metadata,
    _freerdp_pax_path,
    _freerdp_record_size,
    _freerdp_transform,
    _gpm_generate,
    _gpm_metadata,
    _gpm_transform,
    _hplip_generate,
    _hplip_metadata,
    _hplip_transform,
    _hyperv_generate,
    _hyperv_kept,
    _hyperv_metadata,
    _hyperv_transform,
    _hyperv_url,
    _imd_generate,
    _imd_metadata,
    _imd_stripped,
    _imd_transform,
    _jpegxl_dropped,
    _jpegxl_generate,
    _jpegxl_metadata,
    _jpegxl_transform,
    _openal_soft_dropped,
    _openal_soft_generate,
    _openal_soft_metadata,
    _openal_soft_transform,
    _pydantic_core_generate,
    _pydantic_core_metadata,
    _pydantic_core_transform,
    _sevenzip_dropped,
    _sevenzip_generate,
    _sevenzip_metadata,
    _sevenzip_transform,
    _vendored_crate_members,
    _xz_compress_stream,
    cargo_lock_packages,
)
from tools.generated_sources_vendored import (
    BLUEFIN_CLI_INPUT_SHA512,
    BLUEFIN_CLI_MTIME,
    BLUEFIN_CLI_UPSTREAM_URL,
    BLUEFIN_CLI_VENDOR_URL,
    BREW_TARBALL_MANIFESTS,
    BREW_TARBALL_MEMBER,
    BREW_TARBALL_REGISTRY,
    BREW_TARBALL_REPOSITORY,
    CARGO_VENDORED_MTIME,
    GIT_ARCHIVE_SOURCES,
    GSTREAMER_PLUGINS_RS_COMMITS,
    GSTREAMER_PLUGINS_RS_REMOTE,
    GST_THUMBNAILERS_INPUT_SHA512,
    GST_THUMBNAILERS_UPSTREAM_URL,
    KANATA_INPUT_SHA512,
    KANATA_UPSTREAM_URL,
    OO7_INPUT_SHA512,
    OO7_UPSTREAM_URL,
    PREFIXDEVNAME_INPUT_SHA512,
    PREFIXDEVNAME_MTIME,
    PREFIXDEVNAME_UPSTREAM_URL,
    TEALDEER_INPUT_SHA512,
    TEALDEER_UPSTREAM_URL,
    _OCI_MANIFEST_TYPES,
    _bluefin_artwork_commit,
    _bluefin_artwork_generate,
    _bluefin_artwork_metadata,
    _bluefin_artwork_transform,
    _bluefin_cli_generate,
    _bluefin_cli_metadata,
    _bluefin_cli_transform,
    _bluefin_wallpapers_commit,
    _bluefin_wallpapers_generate,
    _bluefin_wallpapers_metadata,
    _bluefin_wallpapers_transform,
    _brew_tarball_extract,
    _brew_tarball_generate,
    _brew_tarball_metadata,
    _cargo_vendored_generate,
    _cargo_vendored_transform,
    _git_archive_compress,
    _git_archive_generate,
    _git_archive_metadata,
    _git_tag_tar,
    _gst_thumbnailers_generate,
    _gst_thumbnailers_metadata,
    _gst_thumbnailers_url,
    _gstreamer_plugins_rs_generate,
    _gstreamer_plugins_rs_metadata,
    _kanata_generate,
    _kanata_metadata,
    _normalized,
    _oo7_commit_version,
    _oo7_generate,
    _oo7_metadata,
    _oo7_url,
    _patched_cargo_lock,
    _prefixdevname_generate,
    _prefixdevname_metadata,
    _prefixdevname_transform,
    _registry_fetch,
    _tealdeer_generate,
    _tealdeer_metadata,
    _verified_digest,
    recipe_patches,
)


METADATA = {
    **{name: functools.partial(_git_archive_metadata, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_metadata,
    "brew-tarball": _brew_tarball_metadata,
    "python-pydantic-core": _pydantic_core_metadata,
    "gpm": _gpm_metadata,
    "hplip": _hplip_metadata,
    "openal-soft": _openal_soft_metadata,
    "prefixdevname": _prefixdevname_metadata,
    "kanata": _kanata_metadata,
    "gst-thumbnailers": _gst_thumbnailers_metadata,
    "gstreamer-plugins-rs": _gstreamer_plugins_rs_metadata,
    "freerdp": _freerdp_metadata,
    "fpaste": _fpaste_metadata,
    "7zip": _sevenzip_metadata,
    "jpegxl": _jpegxl_metadata,
    "hyperv-daemons": _hyperv_metadata,
    "bluefin-artwork-logos": _bluefin_artwork_metadata,
    "bluefin-wallpapers": _bluefin_wallpapers_metadata,
    "tealdeer": _tealdeer_metadata,
    "oo7": _oo7_metadata,
    "bluefin-cli": _bluefin_cli_metadata,
}

GENERATORS = {
    **{name: functools.partial(_git_archive_generate, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_generate,
    "brew-tarball": _brew_tarball_generate,
    "python-pydantic-core": _pydantic_core_generate,
    "hplip": _hplip_generate,
    "gpm": _gpm_generate,
    "openal-soft": _openal_soft_generate,
    "prefixdevname": _prefixdevname_generate,
    "kanata": _kanata_generate,
    "gst-thumbnailers": _gst_thumbnailers_generate,
    "gstreamer-plugins-rs": _gstreamer_plugins_rs_generate,
    "freerdp": _freerdp_generate,
    "fpaste": _fpaste_generate,
    "7zip": _sevenzip_generate,
    "jpegxl": _jpegxl_generate,
    "hyperv-daemons": _hyperv_generate,
    "bluefin-artwork-logos": _bluefin_artwork_generate,
    "bluefin-wallpapers": _bluefin_wallpapers_generate,
    "tealdeer": _tealdeer_generate,
    "oo7": _oo7_generate,
    "bluefin-cli": _bluefin_cli_generate,
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
