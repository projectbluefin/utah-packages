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
- hyperv-daemons: the kernel's tools/hv and the tools/build and
  tools/scripts makefiles it includes, cut from the stable kernel release
  (SHA-512-pinned). The kernel publishes no tools/hv archive; Fedora's
  lookaside copy is a hand-cut snapshot of the same paths
- tealdeer: the upstream GitHub tag archive (SHA-512-pinned) with the same
  `vendor/` tree added, for Dakota's tldr client (#1034)
- oo7: the upstream GitHub commit archive (SHA-512-pinned, keyed by the
  spec's commit) with the same `vendor/` tree added. Fedora 44 lacks crate
  RPMs the commit needs, and Hummingbird ships none (#1192)

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
    "1.25.2": "2881556cd21ee9aebfcbd256e385e8dc63f8e67c916e1d583f597d24184015aa608ca6b21802a236b7fbdb10a407c2dc2320494a1d79e9920fd1ca6a966d8a2f",
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

# projectbluefin/artwork commit -> SHA-512 of every file bluefin-wallpapers
# takes from it: the files package-gnome-wallpapers.sh reads, the script
# itself, and LICENSE. Same fail-closed reasoning as BLUEFIN_ARTWORK_FILES.
BLUEFIN_WALLPAPERS_FILES = {
    "72c74badbdd7c60d006e89aca74e248316dddd54": {
        "LICENSE": "dc6b68d13b8cf959644b935f1192b02c71aa7a5cf653bd43b4480fa89eec8d4d3f16a2278ec8c3b40ab1fdb233b3173a78fd83590d6f739e0c9e8ff56c282557",
        "package-gnome-wallpapers.sh": "06819757d9db52bd5a81d58b6af916852b3efce7f7a31e9d7d274a2ab60d97d284f15845b5134b9d92b744e02bbf7066ffa959ac9006c534f87170944f85d48c",
        "wallpapers/01-bluefin/01-bluefin-day.jxl": "8ecbe89dc2b179c5dc40303e24bcecc87c3965e965cdc0af2e0ab4cb1e39c1654a528f0a88f8f327e57634b1e593df7fd7c148de2ceb8ff4dc5e85ba9249d4af",
        "wallpapers/01-bluefin/01-bluefin-night.jxl": "c250ea851d71e0aa44d4722b99e9325bf98043fc34cc6ba052b326282692b9c290d36157e377cdb700df8117f4c1af64f1ddaf6e2777bcf60f358fe27fb171bf",
        "wallpapers/01-bluefin/01-bluefin.xml": "60494a9e2e5785586ef4e0ccbbda779c3ed632bfcb29296f8a13167cbb6eacc601f816cd4a85f756aa00308dc4c0bf706c425aee7c8252659818dd597198b7a2",
        "wallpapers/02-bluefin/02-bluefin-day.jxl": "bab9c1b5449f8decc0a773cb02b25a16927c66574d7e41fcbc658e717c5dad72605249b04f17a9ff952730ba824181e2bf8ea76cc5efda290a5c002cadbbc43f",
        "wallpapers/02-bluefin/02-bluefin-night.jxl": "b7e35c163d4d552158f69d19e5595bf770680783e0fc4b01cba8d609ec1edad686f2de7ae84762c12bd8292affd3a60a7fb9303fe2dc8b1217cf09172c01eee7",
        "wallpapers/02-bluefin/02-bluefin.xml": "45e1f7a5ad5d2f99fdfa8336a7ebe8b22a79765becef3e6a4859002ff3e9ed3282d3217dfcf5d51a434e5046d6a5af51577b9909dd89c78ae38ebaa6773f34ef",
        "wallpapers/03-bluefin/03-bluefin-day.jxl": "cf7bae010a370258721bf41b661d57e7b2a4471871995740795c91d957a01965df956c1694635760d1543646fba94df943390c90fd2be4bb30c70cc5e88aacd0",
        "wallpapers/03-bluefin/03-bluefin-night.jxl": "0d50a290625d2fd8bc942ed00e05bca99460dff7bae6aa49a6e6eb8183def98863fcaafa48963b3904370d074caa9ef935a463430d559378083976ab08bd8cac",
        "wallpapers/03-bluefin/03-bluefin.xml": "f53b4e12356cf485865983cf8b706c86d787128c03f1d5e445e3152c59dfd39694a50b99523bbd938d78da1536e382900221309526629b4c7adf05fe4a88b073",
        "wallpapers/04-bluefin/04-bluefin-day.jxl": "6da456d801c680af9978e8c7b5f4801df055f1eb1263049e662cc5a0b754261735a9bc760220a54b1dfd87cf2e12f8272e7f972c87eb1328c7156a9d96a62dc1",
        "wallpapers/04-bluefin/04-bluefin-night.jxl": "84736a1a93f7e13968d89704e6e1dccbe183e7d8030ea65f11aee05c3dc8a5df5d50b1b141317b8999598a98582ba93244b5253bf0683a526312565d7ed2dbd3",
        "wallpapers/04-bluefin/04-bluefin.xml": "6942effd049c368e66d038f3b862bb3c02c32e9bcbc0b8fd75e7ce8c00b4c52ad86a217c16ea338bbeda4f195da9d24deb2037797f53c7311aeb04af5fab42be",
        "wallpapers/05-bluefin/05-bluefin-day.jxl": "c87c6ca0476a59cfc735f536600928ca7b1045e975094c2e464a396f8f4896e69f8362dd31f9b6e6de613c6f6ba72071bf2c3084f5d19700a2161f876c7a5162",
        "wallpapers/05-bluefin/05-bluefin-night.jxl": "6ee1d51184a1bac984c0401490368205f310ddbfade15a1a8cb9af1b0a04c658399000e2e704ae28312482e1802cb7e1549c71cde3785e673f55aca300bc2811",
        "wallpapers/05-bluefin/05-bluefin.xml": "849705187cca1ac7c0cea213d5efb5857b5c4df2dafdd2ee7f85ea8afa0ce30acc5e1b8220e6459046ed0db4dcf94c91029b0e09a8b732b2bdf08692e9d21151",
        "wallpapers/06-bluefin/06-bluefin-day.jxl": "a2f205a223bab3c3c129f38a49cf90eadf40682f377351721f9fdd4e5cb6e964c8354b5277d785f4f295c3f63d7ed82d257e3cab1cd31202df231bfd46325f64",
        "wallpapers/06-bluefin/06-bluefin-night.jxl": "e104db81a73b7419142fe7f6eadaee387e781a7a429d398645c643bef1fe23ee6c7adbe20b9cad18173bea06d8d75825086425b8dea65466a4ea46d7af000c7a",
        "wallpapers/06-bluefin/06-bluefin.xml": "428c64e41419d1962a4d1ddaaa22cef10e5b4e5613f6e8ccebcc356a9cb82dd24556f625975a69895f06e846b80d34da5f778429798ecfa67487c2ad2f4b4e11",
        "wallpapers/07-bluefin/07-bluefin-day.jxl": "d7f5ed8dd60db2d1bbf6b9a583d7c383857958176b2555d598bbb1d634c1a2850a21b2625f3251d06516a2e7637a9134fadf47344008aedde9214570e8416cda",
        "wallpapers/07-bluefin/07-bluefin-night.jxl": "58036d9d27ddf8bf51e4eea2abe01b621d846e7a95e73733aa4bd0c9811e6424917703882a17d33c6a5d89949b631491cf6355334c6cef0c5b6bff2be74fd947",
        "wallpapers/07-bluefin/07-bluefin.xml": "1f9bd80203836fcf037a6f482d4ff35fab3cc414e59e3d1464fb8f9a6c2bc039ef59a490d568c8ffdf4d63048b842da424727f2f87b197bec547b92580be3172",
        "wallpapers/08-bluefin/08-bluefin-day.jxl": "c9757d629a306955c59ee49ea3b6f93e904ce528e341b0eba1e0fbd7cf11db80e99bf5e97dfaa65f591ffa12c6bd0fa5124c5586dbca4f635850c21eba54686c",
        "wallpapers/08-bluefin/08-bluefin-night.jxl": "11545c597c719ac7c0ba10620373cc97fc97aca75a616608c8a8f1f59d09d980e7e7b205fddb61fa74e04445255a455de84905496181e10a5df8494699ba99df",
        "wallpapers/08-bluefin/08-bluefin.xml": "2641b669b30c9f7673d22c81556639688d92c0e6e2899ae0bb05b8f76e8a4815a0c85526b2d470622dcc2a7feeac4429f3d6fa152428f13b8485a06c5298c289",
        "wallpapers/09-bluefin/09-bluefin-day.jxl": "524ca958ce21b3b61d0fe77165ce3514e51fecb1ebeca97f75ca106e14fed3dbe0cb62dce5461223b4a764791fa2813216fa61197a3ad535cf87386c6bf3364e",
        "wallpapers/09-bluefin/09-bluefin-night.jxl": "fd524b6f9fbe166216ce822162be41e7cb0cc0ceef70a9a11cc7a8109c65c089f9df14f75fc3f603aab433f3d6feef6ddeb2b95cc3f8582b37fd2a034a22627a",
        "wallpapers/09-bluefin/09-bluefin.xml": "0fa0bb079446874bc1e85e8a67b1e201280a0b297052f0cbff29aa9ecf964be4da5caf39111341282ed1a26ac661852c3534c4c1a6db67bda55c0414180cd338",
        "wallpapers/10-bluefin/10-bluefin-day.jxl": "9f608f716470fc1064fb295e56fd08a90e2512218e0cd782eb057b5b948704493d4cbca8aeaea20e24f634802ed392e446f00baddf668cdfdde54040aeaa1331",
        "wallpapers/10-bluefin/10-bluefin-night.jxl": "5f7f8f2074e26cee9c52aaf8054a54206c16336933040a4047eba4333186769eec111f21fdc9cf5c0feadae5ae994fbdc3421749d8f0df59ca3c39809f0325cf",
        "wallpapers/10-bluefin/10-bluefin.xml": "1b2c478cebf6fcbad13f64cfcaf1d2401f14ccaf9303ec7d88423b69cdbdfb80491dae28c4aaadb9449b852f2aa2f4c02164b1375171622be861ab2af1f59e39",
        "wallpapers/11-bluefin/11-bluefin-day.svg": "21237a1c0e88b45da3b8f3a24ea5f29380bbfa8d5486870d2c2ce8ab16194a5cbf015d01291af46860f87cad5e55efc4366547b574df7253009d245e52cdfe65",
        "wallpapers/11-bluefin/11-bluefin-night.svg": "0051f11b490027977942d03a782eb22ee89aece9d423226dbe6c0324c845a4b6d8060d6afe53dc4052b79c3d3a4dd7aadda99ae7c8575e47fe5c39302c3afe92",
        "wallpapers/11-bluefin/11-bluefin.xml": "79b239d5c618fc04b5bd2c378957f5c612bfef28092704fceb3f5e5a4fdb18010152c9ee4b166a55d8ae658d402d512ab8880048d1bdf01cbb86e33a83160464",
        "wallpapers/12-bluefin/12-bluefin-day.jxl": "a4280b079395e0c0b3514d14e7a202b6c74cea09eedee58390acd911d8a7aecd9abfba7bfa155a2d67c2b80f3b94e09b0077ff9eb549c855ef34bf9bf03382a9",
        "wallpapers/12-bluefin/12-bluefin-night.jxl": "d28a8843c863937ad480bb81e3e464cd75244feed9f4af15da9baabb88541f090d407634c049fef13f500aa5279c2379da3eaba4ca764423e6c44e5f97259dd5",
        "wallpapers/12-bluefin/12-bluefin.xml": "913a37dda699bb088636b6c69280b2e12fbd54160951264c89e9ad02abffe922f0db8c483f2d984ea8257178a84aefe4c2b3c1c280689dce555a87e9a97a27ae",
        "wallpapers/chicken/chicken.jxl": "f9797e82215c73ee521d9fcf844410ff12e43b25e9441e0edabf9d491f3ab7f5550620b6315c8218f34550bf48dcbeac5d3b5a58ca4b2bfd670ad9dc9c2bf72a",
        "wallpapers/xe-clouds/xe-clouds.jxl": "ac31ca5375cb24491bf46be168e783b5e949b4472c51424f2207ee9d500cef219dd6672e3ec5b2709705dd093c5b100327e37ebf0db79fb883f61a53f4bb1c84",
        "wallpapers/xe-foothills/xe-foothills.jxl": "2b3a739c7984d001c0b6ae8f7f1f2efe26545e46a829a9c71afe8995a44e1ec8fa40e0fbd3a67d54673fc36ddddcf11c117d2afc984fd0cc29577cd2221e9413",
        "wallpapers/xe-red-tulip/xe-red-tulip.jxl": "71e1fa0204995299d9e9cac65d71b8c1c0e847da76b7c085b299142384de1e0e3df5d1edc6d3b5f908b868cfcc9746057b9500ac0fe15be26e029c75b0d117a7",
        "wallpapers/xe-space-needle/xe-space-needle.jxl": "28e1b353bd159c22c9d8721a039b3dc6390dd6af3505f50a985c81968ffb062e79ef536b464345d34d105a80cf49ad28e1ad1813b6f28e5f0023187b48d9357f",
        "wallpapers/xe-sunset/xe-sunset.jxl": "8a06f114317c90dc5abab5fa1c0ac645c317d26b9963e75f9b44289f4ec532c2e545b98cdc5a5090604a8bcab17dd4080f205d65ebcd97b22104f001bbc26f44",
        "wallpapers/gnome-background-properties/01-bluefin.xml": "2cc99a19df1950fad8f5cea394f784c7fde8d13a976341df16d1992f8b8034a626ce2e4d0c6d4352bf8f1fa94bc13e67daf2c65f981c9d2c3f36f8af20ad640b",
        "wallpapers/gnome-background-properties/02-bluefin.xml": "7f5b62c7332e516a09444c23919e8253fa54e56294bc70a261d5250ed1b84e147805f5286468f3645630b33b12a6d9df3a8612d3fbd8b45b13bc97a83873e187",
        "wallpapers/gnome-background-properties/03-bluefin.xml": "ff69c9d09e9faeab06ae70cb4d9802ab938d26ad1770b1602f379722048f0157fa1b4f6a93659ca3d76090b7fb730ed071efd331ec5eedf38a3e2379d9b89088",
        "wallpapers/gnome-background-properties/04-bluefin.xml": "5f4c6634899d4807c93b2e50bceaf4776f493fde9a3c10b40604481c831bab766ed30081977570a1e7695a65f96128e5f1ab00ab44e3dc7612adb381fd4eb0ab",
        "wallpapers/gnome-background-properties/05-bluefin.xml": "6cbf49478a03939e96fae39b7e45df9ffc326908dc6857dfd8f0df6894abb9a24380782940981a26e639a13c9eba39c8738e37c081ca47340f4f3dd9256ec4e9",
        "wallpapers/gnome-background-properties/06-bluefin.xml": "647570bc5aa4ddda198179836efa22eecc6512321969bc959bc1089fb1bde652875432aa7af39bae328aa49c6ecc8c6e5d7269eca557bac6cdfee1ead0281665",
        "wallpapers/gnome-background-properties/07-bluefin.xml": "8dd890da8b723766c142701fdca48606c6f58da350dd32e3bb1781d075a0685b5b2073afbc368044f224145a4373b6cf645de1933b388d876e81ee8df9ab211a",
        "wallpapers/gnome-background-properties/08-bluefin.xml": "b95e5b410cca354919059898ed42ae7b472a55663ffa6644a85e4aea725f7203ca8494ad81ff511fd533ff2c13bf555531e6631d4a7be35b883742d2df8d66a0",
        "wallpapers/gnome-background-properties/09-bluefin.xml": "90cde02d26dba9b49757de807ba4917d8234d86820f2c8b016ad585d7636d4ef7e40b4a43fc02eb4722993db65dc878219b3275f565d255fe1c7ff36d90ab720",
        "wallpapers/gnome-background-properties/10-bluefin.xml": "5c54095d7baa92350d4961051f95bc46898672fa1d20bacec3aef0287a9bd8196bd7ba4ade7f82cf64462653f2bf468653cec9a8f6cce13d16419e4721223b9c",
        "wallpapers/gnome-background-properties/11-bluefin.xml": "319a3afbf6d15e7774c55e8f7049585b4178b2f0af5a12178ab56007c7c8dc4f24f6e45df6c28e94ff328d4a23e98eef33ce1b50449630297c0dc5d3d4c1195a",
        "wallpapers/gnome-background-properties/12-bluefin.xml": "0b217e0caeef29637bdde8fd9221f2767743d93ed89bab613e5272880af0d1ffdb71c7449d7457a85d9108a6d701e06f678290350bdbf92dc2e2514e664401c7",
        "wallpapers/gnome-background-properties/chicken.xml": "97044c004bbac845f9b468f2ee9b8a434c90f44450c58a3d545766ad78927007d329912f2f2b8e1252d84c5699f0276d3ff843d4936cd94433a84c76e42e9ff2",
        "wallpapers/gnome-background-properties/xe_clouds.xml": "522678c09d12cdc76ea95d4c6510c0c6628c00b3c35474e89009850d294e0db68b105afac857668237ab1a2e47e89b0b7c95c28bcc748233bab126f0e91a584a",
        "wallpapers/gnome-background-properties/xe_foothills.xml": "3fb1f356328a8531be04eb7ea47c8db8a77ff4ffbcbbbbd9be26652f13a5cb17ea429f29579b6d5420f8344112138b6e0aa0d6c1743cbd6f8e98b0a59fa2ebae",
        "wallpapers/gnome-background-properties/xe_red_tulip.xml": "03be3fb83c5aded948f0d900ee76b11cacc15bfe20fb539509345bb1ec548b3b063dcd3fd6a191ab8d060d05a2d20d40960c146bf9d53993d3c5137ad52ea6c2",
        "wallpapers/gnome-background-properties/xe_space_needle.xml": "a2044b452b746507776456f1c696cf304047517253feea5749ab9963c9bc3d6bfc916538264fcb675906515eefcc943be0d99b05af2bc303d6d79696cb871a8f",
        "wallpapers/gnome-background-properties/xe_sunset.xml": "e4a86fb333ae2cde897551e29850b6ab6c151b8dc9c33615a237fad949d0e48715ffb1314566da39081532161a42d74817c9f812e6e1e591481166dac515e1fc",
    },
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
    "brew-tarball": _brew_tarball_metadata,
    "python-pydantic-core": _pydantic_core_metadata,
    "gpm": _gpm_metadata,
    "hplip": _hplip_metadata,
    "openal-soft": _openal_soft_metadata,
    "prefixdevname": _prefixdevname_metadata,
    "kanata": _kanata_metadata,
    "gst-thumbnailers": _gst_thumbnailers_metadata,
    "freerdp": _freerdp_metadata,
    "fpaste": _fpaste_metadata,
    "7zip": _sevenzip_metadata,
    "hyperv-daemons": _hyperv_metadata,
    "bluefin-artwork-logos": _bluefin_artwork_metadata,
    "bluefin-wallpapers": _bluefin_wallpapers_metadata,
    "tealdeer": _tealdeer_metadata,
    "oo7": _oo7_metadata,
}

GENERATORS = {
    **{name: functools.partial(_git_archive_generate, name) for name in GIT_ARCHIVE_SOURCES},
    "intel-media-driver-free": _imd_generate,
    "tailscale": _tailscale_generate,
    "brew-tarball": _brew_tarball_generate,
    "python-pydantic-core": _pydantic_core_generate,
    "hplip": _hplip_generate,
    "gpm": _gpm_generate,
    "openal-soft": _openal_soft_generate,
    "prefixdevname": _prefixdevname_generate,
    "kanata": _kanata_generate,
    "gst-thumbnailers": _gst_thumbnailers_generate,
    "freerdp": _freerdp_generate,
    "fpaste": _fpaste_generate,
    "7zip": _sevenzip_generate,
    "hyperv-daemons": _hyperv_generate,
    "bluefin-artwork-logos": _bluefin_artwork_generate,
    "bluefin-wallpapers": _bluefin_wallpapers_generate,
    "tealdeer": _tealdeer_generate,
    "oo7": _oo7_generate,
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
