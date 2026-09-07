#!/usr/bin/env python3

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bootstrap_upstream_sources import (
    manifest_pins,
    merge_candidates,
    plan_targets,
    prove_generated,
    sha512,
)


class ManifestPinsTests(unittest.TestCase):
    def test_missing_manifest_yields_no_pins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(manifest_pins(Path(directory)), {})

    def test_parses_every_sha512_record(self) -> None:
        first, second = "a" * 128, "b" * 128
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(
                f"SHA512 (one-1.0.tar.xz) = {first}\n"
                f"SHA512 (two-2.0.tar.gz) = {second}\n"
            )
            self.assertEqual(
                manifest_pins(package),
                {"one-1.0.tar.xz": first, "two-2.0.tar.gz": second},
            )

    def test_ignores_non_sha512_and_malformed_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(
                "MD5 (legacy-1.0.tar.gz) = " + "c" * 32 + "\n"
                "SHA512 (short-1.0.tar.gz) = " + "d" * 64 + "\n"
                "SHA512 (upper-1.0.tar.gz) = " + "E" * 128 + "\n"
                "not a manifest line\n"
                "\n"
            )
            self.assertEqual(manifest_pins(package), {})

    def test_tolerates_surrounding_whitespace(self) -> None:
        digest = "f" * 128
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(f"  SHA512 (one-1.0.tar.xz) = {digest}  \n")
            self.assertEqual(manifest_pins(package), {"one-1.0.tar.xz": digest})


class MergeCandidatesTests(unittest.TestCase):
    def test_appends_to_existing_packages_without_disturbing_them(self) -> None:
        existing = {"schema": 1, "packages": [{"name": "locked", "sha512": "0" * 128}]}
        merged = merge_candidates(existing, [{"name": "fresh", "sha512": "1" * 128}])
        self.assertEqual(
            merged["packages"],
            [{"name": "locked", "sha512": "0" * 128}, {"name": "fresh", "sha512": "1" * 128}],
        )
        self.assertEqual(merged["schema"], 1)

    def test_does_not_mutate_the_existing_payload(self) -> None:
        packages = [{"name": "locked"}]
        existing = {"schema": 1, "packages": packages}
        merge_candidates(existing, [{"name": "fresh"}])
        self.assertEqual(packages, [{"name": "locked"}])
        self.assertEqual(existing["packages"], [{"name": "locked"}])

    def test_rejects_a_candidate_that_would_overwrite_a_lock(self) -> None:
        existing = {"schema": 1, "packages": [{"name": "locked"}]}
        with self.assertRaises(ValueError) as raised:
            merge_candidates(existing, [{"name": "locked"}])
        self.assertIn("source lock already exists: locked", str(raised.exception))

    def test_rejects_duplicate_candidates_in_one_batch(self) -> None:
        with self.assertRaises(ValueError) as raised:
            merge_candidates({"packages": []}, [{"name": "twice"}, {"name": "twice"}])
        self.assertIn("duplicate candidate: twice", str(raised.exception))

    def test_merging_nothing_into_an_empty_payload_keeps_it_empty(self) -> None:
        self.assertEqual(merge_candidates({"schema": 1}, []), {"schema": 1, "packages": []})


class PlanTargetsTests(unittest.TestCase):
    def _packages(self, directory: str, names: list[str]) -> Path:
        packages = Path(directory) / "packages"
        packages.mkdir()
        for name in names:
            (packages / name).mkdir()
        (packages / "stray-file").write_text("not a recipe\n")
        return packages

    def test_skips_packages_hummingbird_already_supplies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packages = self._packages(directory, ["alpha", "beta", "gamma"])
            selected = plan_targets(packages, {"beta": ["beta-libs"]})
            self.assertEqual([path.name for path in selected], ["alpha", "gamma"])

    def test_ignores_non_directory_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packages = self._packages(directory, ["alpha"])
            self.assertEqual([path.name for path in plan_targets(packages, {})], ["alpha"])

    def test_explicit_selection_overrides_the_supplied_skip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packages = self._packages(directory, ["alpha", "beta"])
            selected = plan_targets(packages, {"beta": ["beta-libs"]}, only="beta")
            self.assertEqual([path.name for path in selected], ["beta"])

    def test_unknown_explicit_selection_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packages = self._packages(directory, ["alpha"])
            with self.assertRaises(ValueError) as raised:
                plan_targets(packages, {}, only="missing")
            self.assertIn("no package recipe named missing", str(raised.exception))


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    def read(self, size: int) -> bytes:
        block = self._payload[self._offset : self._offset + size]
        self._offset += len(block)
        return block

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> bool:
        return False


class Sha512Tests(unittest.TestCase):
    def _download(self, url: str, payload: bytes) -> tuple[str, str]:
        with patch(
            "tools.bootstrap_upstream_sources.urllib.request.urlopen",
            return_value=FakeResponse(payload),
        ):
            return sha512(url)

    def test_digests_the_whole_body_across_read_blocks(self) -> None:
        payload = b"x" * (1024 * 1024 * 2 + 17)
        digest, _ = self._download("https://upstream.example/pkg-1.0.tar.xz", payload)
        self.assertEqual(digest, hashlib.sha512(payload).hexdigest())

    def test_filename_comes_from_the_url_basename(self) -> None:
        _, filename = self._download("https://upstream.example/a/b/pkg-1.0.tar.xz", b"body")
        self.assertEqual(filename, "pkg-1.0.tar.xz")

    def test_fragment_overrides_a_meaningless_basename(self) -> None:
        _, filename = self._download(
            "https://crates.io/api/v1/crates/serde/1.0.0/download#/serde-1.0.0.crate", b"body"
        )
        self.assertEqual(filename, "serde-1.0.0.crate")

    def test_fragment_leading_slash_is_stripped(self) -> None:
        _, filename = self._download("https://upstream.example/download#//pkg.tar.gz", b"body")
        self.assertEqual(filename, "pkg.tar.gz")

    def test_request_carries_the_bootstrap_user_agent(self) -> None:
        with patch(
            "tools.bootstrap_upstream_sources.urllib.request.urlopen",
            return_value=FakeResponse(b"body"),
        ) as urlopen:
            sha512("https://upstream.example/pkg-1.0.tar.xz")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "utah-packages-bootstrap/1")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 120)


class ProveGeneratedTests(unittest.TestCase):
    """`prove_generated` is the determinism gate in front of a generated source lock."""

    def _generator(self, payloads: list[bytes], filename: str = "pkg-1.0.tar.gz"):
        produced = iter(payloads)

        def run(command, **_):
            work = Path(command[4])
            (work / filename).write_bytes(next(produced))

        return run

    def test_returns_the_digest_when_both_runs_agree(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "tools.bootstrap_upstream_sources.subprocess.run",
                side_effect=self._generator([b"same", b"same"]),
            ) as run:
                digest = prove_generated(candidate, Path(directory))
            self.assertEqual(digest, hashlib.sha512(b"same").hexdigest())
            self.assertEqual(run.call_count, 2)

    def test_rejects_a_non_deterministic_generator(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "tools.bootstrap_upstream_sources.subprocess.run",
                side_effect=self._generator([b"first", b"second"]),
            ):
                with self.assertRaises(ValueError) as raised:
                    prove_generated(candidate, Path(directory))
        self.assertIn("non-deterministic generation for pkg", str(raised.exception))

    def test_missing_artifact_is_an_error(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        with tempfile.TemporaryDirectory() as directory:
            with patch("tools.bootstrap_upstream_sources.subprocess.run", return_value=None):
                with self.assertRaises(ValueError) as raised:
                    prove_generated(candidate, Path(directory))
        self.assertIn("generation did not produce pkg-1.0.tar.gz", str(raised.exception))

    def test_accepts_generated_bytes_that_match_the_manifest_pin(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        digest = hashlib.sha512(b"same").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(f"SHA512 (pkg-1.0.tar.gz) = {digest}\n")
            with patch(
                "tools.bootstrap_upstream_sources.subprocess.run",
                side_effect=self._generator([b"same", b"same"]),
            ):
                self.assertEqual(prove_generated(candidate, package), digest)

    def test_rejects_generated_bytes_that_drift_from_the_manifest_pin(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        pinned = hashlib.sha512(b"fedora payload").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(f"SHA512 (pkg-1.0.tar.gz) = {pinned}\n")
            with patch(
                "tools.bootstrap_upstream_sources.subprocess.run",
                side_effect=self._generator([b"ours", b"ours"]),
            ):
                with self.assertRaises(ValueError) as raised:
                    prove_generated(candidate, package)
        message = str(raised.exception)
        self.assertIn("do not match the manifest pin", message)
        self.assertIn(pinned, message)
        self.assertIn("repin packages/pkg/sources", message)

    def test_a_pin_for_another_filename_does_not_gate_the_digest(self) -> None:
        candidate = {"name": "pkg", "filename": "pkg-1.0.tar.gz"}
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "sources").write_text(f"SHA512 (other-1.0.tar.gz) = {'a' * 128}\n")
            with patch(
                "tools.bootstrap_upstream_sources.subprocess.run",
                side_effect=self._generator([b"same", b"same"]),
            ):
                self.assertEqual(
                    prove_generated(candidate, package), hashlib.sha512(b"same").hexdigest()
                )


if __name__ == "__main__":
    unittest.main()
