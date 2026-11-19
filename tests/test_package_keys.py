#!/usr/bin/env python3
"""Fedora and Hummingbird packages are verified against keys pinned here.

The mock root and the container lane resolve from Fedora and Hummingbird over
the network. dnf checks each RPM's signature only when its repository says
gpgcheck=1 and names the key, so these tests fail the moment a configuration
stops doing that, or a pinned key file stops being the key its fingerprint
says it is.
"""

import base64
import configparser
import hashlib
from pathlib import Path
import re
import unittest

from tools.mock_config import (
    FEDORA_KEYS,
    HUMMINGBIRD_KEYS,
    KEYS,
    KEYS_DIR,
    render,
)

ROOT = Path(__file__).resolve().parent.parent
KEY_DIR = ROOT / "config" / "keys"
HUMMINGBIRD_REPO = ROOT / "config" / "hummingbird.repo"
HERMETIC_BUILD = ROOT / "tools" / "hermetic_build.sh"
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"
# Where every job that installs from config/hummingbird.repo mounts config/.
CONTAINER_KEYS_DIR = "/repos/keys"


def dearmor(text: str) -> bytes:
    """The binary packets of the one ASCII-armored key block in `text`."""
    match = re.search(
        r"-----BEGIN PGP PUBLIC KEY BLOCK-----\n(.*?)-----END PGP PUBLIC KEY BLOCK-----",
        text,
        re.DOTALL,
    )
    assert match, "no armored public key block"
    # Armor headers (possibly none) end at the first blank line; a checksum
    # line starts with "=".
    lines = match.group(1).splitlines()
    body = lines[lines.index("") + 1 :]
    data = "".join(line for line in body if not line.startswith("="))
    return base64.b64decode(data, validate=True)


def primary_key_fingerprint(packets: bytes) -> str:
    """The fingerprint of the first packet, which must be a public key.

    RFC 9580: a v4 fingerprint is SHA-1 over 0x99, a two-octet length and the
    packet body; a v6 one is SHA-256 over 0x9B, a four-octet length and the
    body.
    """
    first = packets[0]
    assert first & 0x80, "not an OpenPGP packet"
    if first & 0x40:  # new format
        tag = first & 0x3F
        octet = packets[1]
        if octet < 192:
            length, start = octet, 2
        elif octet < 224:
            length, start = ((octet - 192) << 8) + packets[2] + 192, 3
        elif octet == 255:
            length, start = int.from_bytes(packets[2:6], "big"), 6
        else:
            raise AssertionError("partial length on a key packet")
    else:  # legacy format
        tag = (first >> 2) & 0x0F
        size = {0: 1, 1: 2, 2: 4}[first & 0x03]
        length, start = int.from_bytes(packets[1 : 1 + size], "big"), 1 + size
    assert tag == 6, f"first packet is tag {tag}, not a public key"
    body = packets[start : start + length]
    assert len(body) == length, "truncated key packet"
    version = body[0]
    if version == 4:
        digest = hashlib.sha1(b"\x99" + length.to_bytes(2, "big") + body)  # noqa: S324
    elif version == 6:
        digest = hashlib.sha256(b"\x9b" + length.to_bytes(4, "big") + body)
    else:
        raise AssertionError(f"unsupported key version {version}")
    return digest.hexdigest().upper()


def section(config: str, name: str) -> dict[str, str]:
    """One repository section of a dnf configuration."""
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read_string(config)
    return dict(parser[name])


def mock_dnf_conf() -> str:
    namespace: dict = {"config_opts": {}}
    exec(compile(render(), "mock.cfg", "exec"), namespace)  # noqa: S102
    return namespace["config_opts"]["dnf.conf"]


class PinnedKeyTests(unittest.TestCase):
    def test_every_pinned_key_is_the_key_its_fingerprint_names(self) -> None:
        for name, fingerprint in KEYS.items():
            with self.subTest(key=name):
                path = KEY_DIR / name
                self.assertEqual(primary_key_fingerprint(dearmor(path.read_text())), fingerprint)

    def test_every_key_file_records_its_fingerprint_and_source(self) -> None:
        for name, fingerprint in KEYS.items():
            with self.subTest(key=name):
                preamble = (KEY_DIR / name).read_text().split("-----BEGIN")[0]
                self.assertIn(fingerprint, re.sub(r"\s", "", preamble))
                self.assertIn("Source:", preamble)
                self.assertIn("Cross-checked", preamble)
                self.assertIn("https://", preamble)

    def test_the_key_directory_holds_only_pinned_keys(self) -> None:
        self.assertEqual(sorted(p.name for p in KEY_DIR.iterdir()), sorted(KEYS))

    def test_every_configured_key_is_pinned(self) -> None:
        for name in (*FEDORA_KEYS, *HUMMINGBIRD_KEYS):
            self.assertIn(name, KEYS)


class MockConfigTests(unittest.TestCase):
    def expected(self, names: tuple[str, ...]) -> str:
        return " ".join(f"file://{KEYS_DIR}/{name}" for name in names)

    def test_fedora_and_updates_verify_against_the_fedora_key(self) -> None:
        conf = mock_dnf_conf()
        for repo in ("fedora", "updates"):
            with self.subTest(repo=repo):
                options = section(conf, repo)
                self.assertEqual(options["gpgcheck"], "1")
                self.assertEqual(options["gpgkey"], self.expected(FEDORA_KEYS))

    def test_hummingbird_verifies_against_both_release_keys(self) -> None:
        options = section(mock_dnf_conf(), "public-hummingbird-x86_64-rpms")
        self.assertEqual(options["gpgcheck"], "1")
        self.assertEqual(options["gpgkey"], self.expected(HUMMINGBIRD_KEYS))

    def test_the_factory_own_repositories_are_left_unsigned(self) -> None:
        # Earlier stages and the published repository are this factory's own
        # output, which no RPM key signs; the factory image is cosign-signed.
        namespace: dict = {"config_opts": {}}
        rendered = render(factory_repo="https://example.invalid/repo/", stages_dir="/work/prior")
        exec(compile(rendered, "mock.cfg", "exec"), namespace)  # noqa: S102
        conf = namespace["config_opts"]["dnf.conf"]
        for repo in ("stages", "factory"):
            self.assertEqual(section(conf, repo)["gpgcheck"], "0")

    def test_every_mock_caller_installs_the_keys_where_mock_copies_them_from(self) -> None:
        # mock copies /etc/pki/mock/RPM-GPG-KEY-* into its chroots and nothing
        # else; a key left on the host is a "cannot open file" in dnf.
        install = f"install -D -m 0644 -t {KEYS_DIR} /repos/keys/RPM-GPG-KEY-*"
        for path in (HERMETIC_BUILD, BUILD_STAGE):
            with self.subTest(caller=path.name):
                self.assertIn(install, path.read_text())


class ContainerRepoTests(unittest.TestCase):
    def test_hummingbird_repo_verifies_against_both_release_keys(self) -> None:
        options = section(HUMMINGBIRD_REPO.read_text(), "public-hummingbird-x86_64-rpms")
        self.assertEqual(options["gpgcheck"], "1")
        self.assertEqual(
            options["gpgkey"],
            " ".join(f"file://{CONTAINER_KEYS_DIR}/{name}" for name in HUMMINGBIRD_KEYS),
        )


if __name__ == "__main__":
    unittest.main()
