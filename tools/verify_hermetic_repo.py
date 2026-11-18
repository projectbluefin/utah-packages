#!/usr/bin/env python3
"""Check a materialized hermetic repository against the build-root lock.

``tools/hermetic_build.sh build`` turns ``buildroot_lock.json`` into a local
repository: mock-hermetic-repo downloads the network half of the lock, and
the ``file://`` half is copied from the earlier stages and the published
factory. mock-hermetic-repo saves whatever each URL answers, and the mock
configuration resolves with ``gpgcheck=0``, so nothing on that path says the
bytes in the repository are the ones the lock named. This does, before the
offline build installs any of them:

* every RPM the lock names is in the repository, under the file name the
  materialization gives it, and no other ``*.rpm`` is (createrepo_c indexes
  the tree recursively, so an extra file anywhere in it would be installable);
* the MD5 of each file's header and payload -- the region rpm's ``SIGMD5``
  covers -- equals the lock's ``sigmd5``. It is computed from the bytes, not
  read from the file's own signature header, which a replaced file controls;
* the name, epoch, version, release and arch in that (MD5-covered) header
  equal the lock entry;
* when the lock records a ``signature`` (mock's last 8 hex digits of the key
  ID from ``%{SIGPGP:pgpsig}``), the file carries a signature from that key
  ID. This is a consistency check, not signature verification: a key ID is
  not a key.

The check is keyed by the lock entry, never by the URL a file came from, so a
mirror, a redirect or a retry through another URL passes through the same
gate. It fails closed: a lock entry without a ``sigmd5`` is an error.

Only the Python standard library is used, so the check does not depend on the
rpm version inside the build root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

LEAD_MAGIC = b"\xed\xab\xee\xdb"
LEAD_SIZE = 96
HEADER_MAGIC = b"\x8e\xad\xe8\x01"

TAG_NAME = 1000
TAG_VERSION = 1001
TAG_RELEASE = 1002
TAG_EPOCH = 1003
TAG_ARCH = 1022
# Signature header tags. mock's "signature" field reads %{SIGPGP}, which is
# RPMSIGTAG_PGP; GPG is its DSA twin.
SIGTAG_PGP = 1002
SIGTAG_GPG = 1005

TYPE_INT32 = 4
TYPE_STRING = 6
TYPE_BIN = 7
TYPE_I18NSTRING = 9


class VerifyError(Exception):
    """A repository that does not match its lock."""


def _header(data: bytes, offset: int) -> tuple[dict[int, tuple[int, int, int]], bytes, int]:
    """Parse one header structure at offset: (index, store, end offset)."""
    if data[offset:offset + 4] != HEADER_MAGIC:
        raise VerifyError("not an RPM header (bad magic)")
    try:
        count, store_size = struct.unpack(">II", data[offset + 8:offset + 16])
    except struct.error as error:
        raise VerifyError("truncated RPM header") from error
    index_start = offset + 16
    store_start = index_start + 16 * count
    end = store_start + store_size
    if end > len(data):
        raise VerifyError("truncated RPM header")
    index = {}
    for i in range(count):
        tag, kind, where, n = struct.unpack(">IIII", data[index_start + 16 * i:index_start + 16 * i + 16])
        index[tag] = (kind, where, n)
    return index, data[store_start:end], end


def _string(index, store, tag) -> str | None:
    if tag not in index:
        return None
    kind, where, _ = index[tag]
    if kind not in (TYPE_STRING, TYPE_I18NSTRING):
        raise VerifyError(f"header tag {tag} is not a string")
    end = store.find(b"\0", where)
    if end < 0:
        raise VerifyError(f"header tag {tag} is unterminated")
    return store[where:end].decode("utf-8", "replace")


def _int32(index, store, tag) -> int | None:
    if tag not in index:
        return None
    kind, where, _ = index[tag]
    if kind != TYPE_INT32:
        raise VerifyError(f"header tag {tag} is not an int32")
    return struct.unpack(">I", store[where:where + 4])[0]


def _binary(index, store, tag) -> bytes | None:
    if tag not in index:
        return None
    kind, where, n = index[tag]
    if kind != TYPE_BIN:
        raise VerifyError(f"signature tag {tag} is not binary")
    return store[where:where + n]


def _subpacket_issuer(area: bytes) -> str | None:
    """The issuer key ID among OpenPGP signature subpackets, if any."""
    i = 0
    while i < len(area):
        first = area[i]
        if first < 192:
            length, i = first, i + 1
        elif first < 255:
            length, i = ((first - 192) << 8) + area[i + 1] + 192, i + 2
        else:
            length, i = struct.unpack(">I", area[i + 1:i + 5])[0], i + 5
        body = area[i:i + length]
        kind = body[0] & 0x7F if body else None
        if kind == 16 and len(body) >= 9:  # issuer key ID
            return body[1:9].hex()
        if kind == 33 and len(body) >= 10:  # issuer fingerprint: key ID is its tail
            return body[-8:].hex()
        i += length
    return None


def signature_key_id(packet: bytes) -> str | None:
    """The issuer key ID (16 hex digits) of one OpenPGP signature packet."""
    if not packet or not packet[0] & 0x80:
        return None
    if packet[0] & 0x40:  # new format
        first = packet[1]
        if first < 192:
            start = 2
        elif first < 224:
            start = 3
        else:
            start = 6
    else:
        start = 1 + (1 << (packet[0] & 0x03))
    body = packet[start:]
    if not body:
        return None
    if body[0] == 3 and len(body) >= 15:
        return body[7:15].hex()
    if body[0] in (4, 5, 6):
        size = 4 if body[0] == 6 else 2
        offset = 4
        hashed_len = int.from_bytes(body[offset:offset + size], "big")
        hashed = body[offset + size:offset + size + hashed_len]
        offset += size + hashed_len
        unhashed_len = int.from_bytes(body[offset:offset + size], "big")
        unhashed = body[offset + size:offset + size + unhashed_len]
        return _subpacket_issuer(hashed) or _subpacket_issuer(unhashed)
    return None


def inspect(path: Path) -> dict:
    """NEVRA, MD5 of header+payload, and SIGPGP key ID of one RPM file."""
    data = path.read_bytes()
    if data[:4] != LEAD_MAGIC or len(data) < LEAD_SIZE:
        raise VerifyError("not an RPM file (bad lead)")
    sig_index, sig_store, sig_end = _header(data, LEAD_SIZE)
    main = sig_end + (-sig_end % 8)
    index, store, _ = _header(data, main)
    epoch = _int32(index, store, TAG_EPOCH)
    key_id = None
    for tag in (SIGTAG_PGP, SIGTAG_GPG):
        packet = _binary(sig_index, sig_store, tag)
        if packet:
            key_id = signature_key_id(packet)
            break
    return {
        "name": _string(index, store, TAG_NAME),
        "epoch": None if epoch is None else str(epoch),
        "version": _string(index, store, TAG_VERSION),
        "release": _string(index, store, TAG_RELEASE),
        "arch": _string(index, store, TAG_ARCH),
        "sigmd5": hashlib.md5(data[main:], usedforsecurity=False).hexdigest(),
        "signature": None if key_id is None else key_id[-8:],
    }


def file_name(url: str) -> str:
    """The name a lock entry's RPM has inside the repository.

    mock-hermetic-repo saves a download as os.path.basename(url); the
    file:// half is copied by its decoded path (tools/hermetic_build.sh).
    """
    if url.startswith("file://"):
        return os.path.basename(unquote(urlparse(url).path))
    return os.path.basename(url)


def nevra(entry: dict) -> str:
    epoch = f"{entry['epoch']}:" if entry.get("epoch") not in (None, "", "0") else ""
    return f"{entry.get('name')}-{epoch}{entry.get('version')}-{entry.get('release')}.{entry.get('arch')}"


def verify(lock: dict, repo: Path) -> list[str]:
    """Every mismatch between the lock and the repository; empty when none."""
    errors: list[str] = []
    expected: dict[str, dict] = {}
    for entry in lock["buildroot"]["rpms"]:
        name = file_name(entry.get("url") or "")
        if not name.endswith(".rpm"):
            errors.append(f"{nevra(entry)}: lock URL {entry.get('url')!r} does not name an RPM")
            continue
        if name in expected:
            errors.append(f"{name}: named by more than one lock entry")
            continue
        expected[name] = entry
    present: dict[str, Path] = {}
    for path in sorted(repo.rglob("*.rpm")):
        relative = path.relative_to(repo).as_posix()
        if relative in expected and path.is_file() and not path.is_symlink():
            present[relative] = path
        else:
            errors.append(f"{relative}: in the repository but not in the lock")
    for name, entry in expected.items():
        path = present.get(name)
        if path is None:
            errors.append(f"{name}: locked ({nevra(entry)}) but missing from the repository")
            continue
        sigmd5 = str(entry.get("sigmd5") or "").lower()
        if len(sigmd5) != 32:
            errors.append(f"{name}: lock entry has no sigmd5; refusing to trust it")
            continue
        try:
            actual = inspect(path)
        except (VerifyError, OSError) as error:
            errors.append(f"{name}: cannot read as an RPM: {error}")
            continue
        if actual["sigmd5"] != sigmd5:
            errors.append(f"{name}: SIGMD5 {actual['sigmd5']} does not match the locked {sigmd5}")
            continue
        for field in ("name", "epoch", "version", "release", "arch"):
            locked = entry.get(field)
            locked = None if locked in (None, "", "(none)") else str(locked)
            if actual[field] != locked:
                errors.append(f"{name}: {field} {actual[field]!r} does not match the locked {locked!r} "
                              f"({nevra(entry)})")
        locked_key = entry.get("signature")
        if locked_key and actual["signature"] != str(locked_key).lower()[-8:]:
            errors.append(f"{name}: signed by key ID {actual['signature']} but the lock records {locked_key}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lockfile", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    args = parser.parse_args(argv)
    lock = json.loads(args.lockfile.read_text())
    errors = verify(lock, args.repo)
    for error in errors:
        print(f"::error title=hermetic repository does not match the lock::{error}")
    if errors:
        print(f"{args.repo}: {len(errors)} mismatch(es) against {args.lockfile}; refusing to build from it",
              file=sys.stderr)
        return 1
    print(f"verified {len(lock['buildroot']['rpms'])} RPMs in {args.repo} against {args.lockfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
