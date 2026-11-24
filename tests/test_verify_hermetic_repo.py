#!/usr/bin/env python3
"""The hermetic repository is checked against its lock before the offline build.

mock-hermetic-repo saves whatever each lock URL answers, and the build root
resolves with gpgcheck=0. tools/verify_hermetic_repo.py holds every RPM in the
materialized repository to the lock's sigmd5 and NEVRA, with nothing missing
and nothing extra, and tools/hermetic_build.sh runs it inside the retried
fetch and again on the finished repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import verify_hermetic_repo
from tools.verify_hermetic_repo import VerifyError, inspect, verify

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "hermetic_build.sh"
URL = "https://packages.example/hummingbird/x86_64/Packages"


def _header(entries: list[tuple[int, int, bytes, int]]) -> bytes:
    index, store = b"", b""
    for tag, kind, value, count in entries:
        if kind == 4:
            store += b"\0" * (-len(store) % 4)
        index += struct.pack(">IIII", tag, kind, len(store), count)
        store += value
    return b"\x8e\xad\xe8\x01\0\0\0\0" + struct.pack(">II", len(entries), len(store)) + index + store


def _pgp_signature(key_id: str) -> bytes:
    """A v4 OpenPGP signature packet carrying only an issuer subpacket."""
    issuer = bytes([9, 16]) + bytes.fromhex(key_id)
    body = bytes([4, 0, 1, 8]) + struct.pack(">H", len(issuer)) + issuer + struct.pack(">H", 0) + b"\0\0"
    return bytes([0x89]) + struct.pack(">H", len(body)) + body


def make_rpm(path: Path, name: str, version: str = "1.0", release: str = "1.hum1",
             arch: str = "x86_64", epoch: int | None = None, payload: bytes = b"payload",
             key_id: str | None = None, claimed_md5: bytes | None = None) -> str:
    """Write a minimal RPM and return the SIGMD5 rpm would record for it."""
    tags = [(1000, 6, name.encode() + b"\0", 1), (1001, 6, version.encode() + b"\0", 1),
            (1002, 6, release.encode() + b"\0", 1), (1022, 6, arch.encode() + b"\0", 1)]
    if epoch is not None:
        tags.append((1003, 4, struct.pack(">I", epoch), 1))
    covered = _header(tags) + payload
    md5 = hashlib.md5(covered, usedforsecurity=False).digest()
    signature = [(1004, 7, claimed_md5 or md5, 16)]
    if key_id:
        packet = _pgp_signature(key_id)
        signature.append((1002, 7, packet, len(packet)))
    sig = _header(signature)
    sig += b"\0" * (-len(sig) % 8)
    lead = b"\xed\xab\xee\xdb" + b"\0" * 92
    path.write_bytes(lead + sig + covered)
    return md5.hex()


def entry(name: str, sigmd5: str, *, version: str = "1.0", release: str = "1.hum1",
          arch: str = "x86_64", epoch: str | None = None, url: str | None = None,
          signature: str | None = None) -> dict:
    url = url or f"{URL}/{name}-{version}-{release}.{arch}.rpm"
    return {"name": name, "epoch": epoch, "version": version, "release": release, "arch": arch,
            "license": "MIT", "sigmd5": sigmd5, "signature": signature, "url": url}


def lock(*entries: dict) -> dict:
    return {"version": "1.1.0", "buildroot": {"rpms": list(entries)}, "config": {}}


class VerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.directory.name) / "repo"
        self.repo.mkdir()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def rpm(self, name: str, **fields) -> dict:
        header = {k: fields.pop(k) for k in ("version", "release", "arch") if k in fields}
        epoch = fields.pop("epoch", None)
        locked = entry(name, "", epoch=None if epoch is None else str(epoch), **header, **fields)
        locked["sigmd5"] = make_rpm(self.repo / verify_hermetic_repo.file_name(locked["url"]), name,
                                    epoch=epoch, **header)
        return locked

    def test_a_repository_that_matches_its_lock_passes(self) -> None:
        a = self.rpm("zip", release="46.1.hum1")
        b = self.rpm("NetworkManager-libnm", epoch=1, version="1.58.1", release="5.hum1")
        c = self.rpm("g++", arch="noarch")
        self.assertEqual(verify(lock(a, b, c), self.repo), [])

    def test_md5_is_computed_over_header_and_payload(self) -> None:
        path = self.repo / "x.rpm"
        md5 = make_rpm(path, "x", epoch=2)
        info = inspect(path)
        self.assertEqual(info["sigmd5"], md5)
        self.assertEqual((info["name"], info["epoch"], info["version"], info["release"], info["arch"]),
                         ("x", "2", "1.0", "1.hum1", "x86_64"))

    def test_a_tampered_rpm_fails(self) -> None:
        good = self.rpm("zip")
        path = self.repo / "zip-1.0-1.hum1.x86_64.rpm"
        # Same NEVRA, different payload -- a mirror's substitute. It even
        # claims the locked MD5 in its own signature header; the check
        # computes the digest from the bytes and is not fooled.
        make_rpm(path, "zip", payload=b"evil", claimed_md5=bytes.fromhex(good["sigmd5"]))
        errors = verify(lock(good), self.repo)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("zip-1.0-1.hum1.x86_64.rpm: SIGMD5", errors[0])
        self.assertIn(f"does not match the locked {good['sigmd5']}", errors[0])

    def test_a_missing_rpm_fails(self) -> None:
        good = self.rpm("zip")
        absent = entry("unzip", "0" * 32)
        errors = verify(lock(good, absent), self.repo)
        self.assertEqual(errors, ["unzip-1.0-1.hum1.x86_64.rpm: locked (unzip-1.0-1.hum1.x86_64) "
                                  "but missing from the repository"])

    def test_an_extra_rpm_fails_wherever_it_sits(self) -> None:
        good = self.rpm("zip")
        make_rpm(self.repo / "evil-1.0-1.x86_64.rpm", "evil")
        (self.repo / "nested").mkdir()
        make_rpm(self.repo / "nested" / "glibc-9.0-1.x86_64.rpm", "glibc")
        errors = verify(lock(good), self.repo)
        self.assertEqual(sorted(errors), [
            "evil-1.0-1.x86_64.rpm: in the repository but not in the lock",
            "nested/glibc-9.0-1.x86_64.rpm: in the repository but not in the lock",
        ])

    def test_a_nevra_mismatch_fails(self) -> None:
        # The file's MD5 is the one locked, but the lock entry names a
        # different package: the lock and the bytes disagree about what this is.
        for field, value in (("name", "unzip"), ("version", "2.0"), ("release", "2.hum1"),
                             ("arch", "aarch64"), ("epoch", "1")):
            with self.subTest(field=field):
                locked = self.rpm("zip")
                locked[field] = value
                errors = verify(lock(locked), self.repo)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(f"{field} ", errors[0])
                self.assertIn(f"does not match the locked {value!r}", errors[0])
                for path in self.repo.glob("*.rpm"):
                    path.unlink()

    def test_a_lock_entry_without_sigmd5_fails_closed(self) -> None:
        locked = self.rpm("zip")
        locked["sigmd5"] = None
        self.assertEqual(verify(lock(locked), self.repo),
                         ["zip-1.0-1.hum1.x86_64.rpm: lock entry has no sigmd5; refusing to trust it"])

    def test_a_non_rpm_fails(self) -> None:
        locked = entry("zip", "0" * 32)
        (self.repo / "zip-1.0-1.hum1.x86_64.rpm").write_text("<html>mirror error</html>")
        errors = verify(lock(locked), self.repo)
        self.assertEqual(len(errors), 1)
        self.assertIn("cannot read as an RPM", errors[0])

    def test_the_locked_signing_key_id_must_match(self) -> None:
        path = self.repo / "zip-1.0-1.hum1.x86_64.rpm"
        md5 = make_rpm(path, "zip", key_id="199e2f91fd431d51")
        self.assertEqual(inspect(path)["signature"], "fd431d51")
        self.assertEqual(verify(lock(entry("zip", md5, signature="fd431d51")), self.repo), [])
        errors = verify(lock(entry("zip", md5, signature="6d9f90a6")), self.repo)
        self.assertEqual(errors, ["zip-1.0-1.hum1.x86_64.rpm: signed by key ID fd431d51 but the lock "
                                  "records 6d9f90a6"])
        make_rpm(path, "zip")
        self.assertIn("signed by key ID None", verify(lock(entry("zip", md5, signature="fd431d51")),
                                                     self.repo)[0])

    def test_local_entries_are_named_by_their_decoded_path(self) -> None:
        locked = entry("g++", "", url="file:///work/factory/result/g%2B%2B-1.0-1.hum1.x86_64.rpm")
        locked["sigmd5"] = make_rpm(self.repo / "g++-1.0-1.hum1.x86_64.rpm", "g++")
        self.assertEqual(verify(lock(locked), self.repo), [])

    def test_the_command_line_fails_closed(self) -> None:
        good = self.rpm("zip")
        lockfile = Path(self.directory.name) / "lock.json"
        lockfile.write_text(json.dumps(lock(good)))
        self.assertEqual(verify_hermetic_repo.main(["--lockfile", str(lockfile), "--repo", str(self.repo)]), 0)
        make_rpm(self.repo / "zip-1.0-1.hum1.x86_64.rpm", "zip", payload=b"evil")
        self.assertEqual(verify_hermetic_repo.main(["--lockfile", str(lockfile), "--repo", str(self.repo)]), 1)


class MaterializeTests(unittest.TestCase):
    """hermetic_build.sh's materialize(), run with a stand-in mock-hermetic-repo."""

    def run_materialize(self, serve: dict[str, str], local: list[dict], remote: list[dict],
                        attempts: int = 2, first_bad: str | None = None,
                        ) -> tuple[subprocess.CompletedProcess, Path]:
        script = SCRIPT.read_text()
        helper = script[script.index("NET_ATTEMPTS="):script.index("render_config() {")]
        assert 'sleep "$delay"' in helper, "online() sleep line moved; update the stub"
        helper = helper.replace('sleep "$delay"', "true")
        helper += script[script.index("redirect_fedora_urls() {"):script.index("materialize() {")]
        materialize = script[script.index("materialize() {"):script.index("build() {")]
        materialize = materialize.replace("/tools/", f"{ROOT}/tools/")
        directory = Path(self.directory.name)
        hermetic = directory / "hermetic"
        (hermetic / "lock").mkdir(parents=True)
        (hermetic / "lock" / "buildroot_lock.json").write_text(json.dumps(lock(*remote, *local)))
        bin_dir = directory / "bin"
        bin_dir.mkdir(exist_ok=True)
        os.symlink(sys.executable, bin_dir / "python3")
        (bin_dir / "createrepo_c").write_text("#!/bin/sh\nexit 0\n")
        # Stand-in for mock-hermetic-repo: "downloads" every locked URL from
        # SERVE (url -> file), the way any mirror or redirect could answer.
        (bin_dir / "mock-hermetic-repo").write_text(f"""#!/bin/sh
attempt=$(grep -c fetch {directory}/fetches 2>/dev/null || true)
echo fetch >> {directory}/fetches
exec {sys.executable} -c '
import json, shutil, sys, os
lock, out, attempt, first_bad = sys.argv[1], sys.argv[2], sys.argv[4], sys.argv[5]
serve = json.load(open(sys.argv[3]))
os.makedirs(out, exist_ok=True)
bad = False
for r in json.load(open(lock))["buildroot"]["rpms"]:
    dest = os.path.join(out, os.path.basename(r["url"]))
    with open("{directory}/requests", "a") as log:
        print(r["url"], file=log)
    if attempt == "" and r["url"] == first_bad:
        with open(dest, "w") as rpm:
            rpm.write("not an RPM")
        bad = True
    else:
        shutil.copy(serve[r["url"]], dest)
if bad:
    sys.exit("createrepo_c: rpmReadPackageFile() error")
os.makedirs(os.path.join(out, "repodata"), exist_ok=True)
os.makedirs(os.path.join(out, "registry.example/fedora"))
' "$2" "$4" {directory}/serve.json "$attempt" "{first_bad or ""}"
""")
        for tool in ("createrepo_c", "mock-hermetic-repo"):
            (bin_dir / tool).chmod(0o755)
        (directory / "serve.json").write_text(json.dumps(serve))
        probe = f"""
set -euo pipefail
PACKAGE=probe
H={hermetic}
{helper}
{materialize}
materialize
"""
        result = subprocess.run(["bash", "-c", probe], capture_output=True, text=True,
                                env={"PATH": f"{bin_dir}:/usr/bin:/bin",
                                     "HERMETIC_NET_ATTEMPTS": str(attempts),
                                     "REPORT_DIR": str(directory / "reports")})
        return result, directory

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        base = Path(self.directory.name)
        self.mirror = base / "mirror"
        self.factory = base / "factory"
        self.mirror.mkdir()
        self.factory.mkdir()
        self.good = entry("zip", make_rpm(self.mirror / "zip.good", "zip"))
        make_rpm(self.mirror / "zip.evil", "zip", payload=b"evil")
        name = "ModemManager-glib-1.0-1.hum1.bfin.x86_64.rpm"
        self.local = entry("ModemManager-glib", make_rpm(self.factory / name, "ModemManager-glib",
                                                         release="1.hum1.bfin"),
                           release="1.hum1.bfin", url=f"file://{self.factory}/{name}")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_a_matching_fetch_materializes(self) -> None:
        result, directory = self.run_materialize({self.good["url"]: str(self.mirror / "zip.good")},
                                                 [self.local], [self.good])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("verified 1 RPMs", result.stdout)
        self.assertIn("verified 2 RPMs", result.stdout)
        self.assertIn("hermetic repository: 2 RPMs", result.stdout)

    def test_a_tampered_download_is_refetched_then_refused(self) -> None:
        result, directory = self.run_materialize({self.good["url"]: str(self.mirror / "zip.evil")},
                                                 [self.local], [self.good], attempts=2)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        # Each attempt went through the check, and the retry cleaned up first.
        self.assertEqual((directory / "fetches").read_text().count("fetch"), 2)
        self.assertEqual(result.stdout.count("zip-1.0-1.hum1.x86_64.rpm: SIGMD5"), 2, result.stdout)
        self.assertIn("::error title=lock fetch failed::probe: lock fetch failed 2 times", result.stdout)
        self.assertNotIn("hermetic repository:", result.stdout)

    def test_a_failed_fetch_refetches_only_the_unreadable_rpm(self) -> None:
        other = entry("zstd", make_rpm(self.mirror / "zstd.good", "zstd"))
        result, directory = self.run_materialize({
            self.good["url"]: str(self.mirror / "zip.good"),
            other["url"]: str(self.mirror / "zstd.good"),
        }, [], [self.good, other], first_bad=other["url"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("zstd-1.0-1.hum1.x86_64.rpm: cannot read as an RPM", result.stdout)
        self.assertEqual((directory / "requests").read_text().splitlines(),
                         [self.good["url"], other["url"], other["url"]])
        self.assertIn("hermetic repository: 2 RPMs", result.stdout)

    def test_a_verification_retry_recreates_the_bootstrap_image(self) -> None:
        zip_rpm = "zip-1.0-1.hum1.x86_64.rpm"
        original = f"https://mirror.example/fedora/linux/{zip_rpm}"
        redirect = f"https://download.fedoraproject.org/pub/fedora/linux/{zip_rpm}"
        wanted = dict(self.good, url=original)
        other = entry("zstd", make_rpm(self.mirror / "zstd.good", "zstd"))
        result, directory = self.run_materialize({
            original: str(self.mirror / "zip.evil"),
            redirect: str(self.mirror / "zip.good"),
            other["url"]: str(self.mirror / "zstd.good"),
        }, [], [wanted, other])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((directory / "requests").read_text().splitlines(),
                         [original, other["url"], redirect])
        self.assertTrue((directory / "hermetic/repo/registry.example/fedora").is_dir())

    def test_a_tampered_local_rpm_is_refused(self) -> None:
        make_rpm(Path(urlparse_path(self.local["url"])), "ModemManager-glib", release="1.hum1.bfin",
                 payload=b"evil")
        result, _ = self.run_materialize({self.good["url"]: str(self.mirror / "zip.good")},
                                         [self.local], [self.good])
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ModemManager-glib-1.0-1.hum1.bfin.x86_64.rpm: SIGMD5", result.stdout)
        self.assertNotIn("hermetic repository:", result.stdout)

    def test_whole_lock_verification_gates_offline_build(self) -> None:
        script = SCRIPT.read_text()
        materialize, build = script.split("\nbuild() {\n", 1)
        fetch = materialize.index('  online "lock fetch"')
        local_copy = materialize.index('done < "$H/local.txt"')
        verify = materialize.index(
            'python3 /tools/verify_hermetic_repo.py --lockfile "$H/lock/buildroot_lock.json" --repo "$H/repo"'
        )
        publish = materialize.index('createrepo_c -q "$H/repo"')
        self.assertLess(fetch, local_copy)
        self.assertLess(local_copy, verify)
        self.assertLess(verify, publish)
        self.assertLess(build.index("  materialize\n"), build.index("  build_offline 1"))


def urlparse_path(url: str) -> str:
    from urllib.parse import unquote, urlparse
    return unquote(urlparse(url).path)



class BadLeadTests(unittest.TestCase):
    def test_a_non_rpm_names_its_size_and_first_bytes(self) -> None:
        # #1208: a CDN error page, an empty body and a truncated download need
        # different fixes, so the error says which one arrived.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shadow-utils-4.20.0-2.hum1.x86_64.rpm"
            path.write_bytes(b"<HTML><HEAD><TITLE>Access Denied</TITLE>" + b"x" * 200)
            with self.assertRaises(VerifyError) as caught:
                inspect(path)
        message = str(caught.exception)
        self.assertIn("bad lead", message)
        self.assertIn("240 bytes", message)
        self.assertIn("Access Denied", message)

if __name__ == "__main__":
    unittest.main()
