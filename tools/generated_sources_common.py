"""Shared plumbing for tools/generated_sources.py.

Upstream reachability, recipe parsing and hashing helpers every generator
uses. tools/generated_sources.py re-exports every name defined here.
"""

from __future__ import annotations

import errno
import hashlib
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
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
    "26.3.5": "29d1032a1fe46e2102e337a826980bf9395cac161b60fee9b07ed9e784da01cdf5c3db2ac0e95300ce8900108bec2f66686058122ad75067639fcb2e4f66712a",
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
