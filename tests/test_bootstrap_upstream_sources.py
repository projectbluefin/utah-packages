#!/usr/bin/env python3

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.bootstrap_upstream_sources import (
    main,
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


class MainTests(unittest.TestCase):
    """`main` is the acceptance policy: which recipes become source locks.

    rpmspec and the network are replaced at the module seams (`rpm_value`,
    `sources`, `sha512`, `generated_candidate`, `prove_generated`) so each
    test drives exactly one decision through the real CLI and file output.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / "packages").mkdir()
        self.declared: dict[str, list[tuple[int, str]]] = {}
        self.downloads: dict[str, tuple[str, str]] = {}
        self.fetched: list[str] = []

    def recipe(self, name: str, sources: list[tuple[int, str]] | None = None, specs: int = 1) -> Path:
        package = self.root / "packages" / name
        package.mkdir()
        for index in range(specs):
            (package / f"{name}{index or ''}.spec").write_text(f"Name: {name}\n")
        if sources is not None:
            self.declared[name] = sources
        return package

    def serve(self, url: str, payload: bytes, filename: str) -> str:
        digest = hashlib.sha512(payload).hexdigest()
        self.downloads[url] = (digest, filename)
        return digest

    def _rpm_value(self, spec: Path, query: str) -> str:
        return {"%{NAME}": spec.parent.name, "%{VERSION}": "1.0"}[query]

    def _sources(self, spec: Path) -> list[tuple[int, str]]:
        return self.declared[spec.parent.name]

    def _sha512(self, url: str) -> tuple[str, str]:
        self.fetched.append(url)
        return self.downloads[url]

    def run_main(self, *argv: str) -> tuple[int, dict, dict]:
        module = "tools.bootstrap_upstream_sources"
        with patch(f"{module}.rpm_value", side_effect=self._rpm_value), \
                patch(f"{module}.sources", side_effect=self._sources), \
                patch(f"{module}.sha512", side_effect=self._sha512), \
                patch("sys.argv", ["bootstrap_upstream_sources.py", "--root", str(self.root), *argv]), \
                patch("sys.stdout", new_callable=io.StringIO):
            code = main()
        output = json.loads((self.root / "config/upstream-sources.json").read_text())
        report = json.loads((self.root / "reports/direct-source-bootstrap.json").read_text())
        return code, output, report

    def reasons(self, report: dict) -> dict[str, str]:
        return {entry["package"]: entry["reason"] for entry in report["rejected"]}

    def test_accepts_a_direct_upstream_source0(self) -> None:
        url = "https://upstream.example/pkg-1.0.tar.xz"
        digest = self.serve(url, b"upstream bytes", "pkg-1.0.tar.xz")
        self.recipe("pkg", [(0, url)])
        code, output, report = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(output, {"schema": 1, "packages": [
            {"name": "pkg", "version": "1.0", "url": url, "filename": "pkg-1.0.tar.xz", "sha512": digest},
        ]})
        self.assertEqual(report, {"accepted": 1, "already_supplied_by_hummingbird": {}, "rejected": []})

    def test_rejects_a_source0_that_is_not_http(self) -> None:
        self.recipe("local", [(0, "local-1.0.tar.gz")])
        self.recipe("ftp", [(0, "ftp://upstream.example/ftp-1.0.tar.gz")])
        self.recipe("nosource0", [(1, "https://upstream.example/patch.tar.gz")])
        _, output, report = self.run_main()
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report), {
            name: "Source0 is not a direct HTTP(S) URL" for name in ("ftp", "local", "nosource0")
        })
        self.assertEqual(self.fetched, [])

    def test_rejects_fedora_hosted_source0_without_downloading_it(self) -> None:
        for host in ("src.fedoraproject.org", "kojipkgs.fedoraproject.org", "fedoraproject.org"):
            self.recipe(host.split(".")[0], [(0, f"https://{host}/repo/pkgs/x/x-1.0.tar.gz")])
        _, output, report = self.run_main()
        self.assertEqual(output["packages"], [])
        self.assertEqual(set(self.reasons(report).values()),
                         {"Source0 points at Fedora infrastructure, not the upstream"})
        self.assertEqual(len(report["rejected"]), 3)
        self.assertEqual(self.fetched, [])

    def test_rejected_entries_name_the_spec_relative_to_the_root(self) -> None:
        self.recipe("pkg", [(0, "pkg-1.0.tar.gz")])
        _, _, report = self.run_main()
        self.assertEqual(report["rejected"][0]["spec"], "packages/pkg/pkg.spec")

    def test_additional_sources_need_an_explicit_selection(self) -> None:
        url = "https://upstream.example/pkg-1.0.tar.xz"
        self.serve(url, b"upstream bytes", "pkg-1.0.tar.xz")
        self.recipe("pkg", [(0, url), (1, "https://upstream.example/extra.tar.xz")])
        _, output, report = self.run_main()
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report),
                         {"pkg": "additional Source entries require an explicit verified source-closure mapping"})
        self.assertEqual(self.fetched, [])

        code, output, report = self.run_main("--package", "pkg")
        self.assertEqual(code, 0)
        self.assertEqual([entry["name"] for entry in output["packages"]], ["pkg"])
        self.assertEqual(report["rejected"], [])

    def test_a_recipe_without_exactly_one_spec_is_rejected(self) -> None:
        self.recipe("none", specs=0)
        self.recipe("two", specs=2)
        _, output, report = self.run_main()
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report), {
            "none": "expected one spec, found 0",
            "two": "expected one spec, found 2",
        })

    def test_explicit_selection_accepts_bytes_matching_the_manifest_pin(self) -> None:
        url = "https://upstream.example/pkg-1.0.tar.xz"
        digest = self.serve(url, b"upstream bytes", "pkg-1.0.tar.xz")
        package = self.recipe("pkg", [(0, url)])
        (package / "sources").write_text(f"SHA512 (pkg-1.0.tar.xz) = {digest}\n")
        code, output, report = self.run_main("--package", "pkg")
        self.assertEqual(code, 0)
        self.assertEqual(output["packages"][0]["sha512"], digest)
        self.assertEqual(report["rejected"], [])

    def test_explicit_selection_rejects_bytes_that_drift_from_the_manifest_pin(self) -> None:
        url = "https://upstream.example/pkg-1.0.tar.xz"
        served = self.serve(url, b"retagged upstream bytes", "pkg-1.0.tar.xz")
        pinned = hashlib.sha512(b"fedora's bytes").hexdigest()
        package = self.recipe("pkg", [(0, url)])
        (package / "sources").write_text(f"SHA512 (pkg-1.0.tar.xz) = {pinned}\n")
        _, output, report = self.run_main("--package", "pkg")
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report)["pkg"],
                         f"upstream bytes for pkg-1.0.tar.xz do not match the pinned manifest: "
                         f"expected {pinned}, got {served}")

    def test_default_scan_does_not_gate_on_the_manifest_pin(self) -> None:
        url = "https://upstream.example/pkg-1.0.tar.xz"
        served = self.serve(url, b"upstream bytes", "pkg-1.0.tar.xz")
        package = self.recipe("pkg", [(0, url)])
        (package / "sources").write_text(f"SHA512 (pkg-1.0.tar.xz) = {'0' * 128}\n")
        _, output, report = self.run_main()
        self.assertEqual(output["packages"][0]["sha512"], served)
        self.assertEqual(report["rejected"], [])

    def test_generated_source_requires_an_explicit_selection(self) -> None:
        self.recipe("gen")
        module = "tools.bootstrap_upstream_sources"
        with patch.dict(f"{module}.GENERATED_SOURCES", {"gen": object()}), \
                patch(f"{module}.generated_candidate") as candidate, \
                patch(f"{module}.prove_generated") as prove:
            _, output, report = self.run_main()
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report),
                         {"gen": "generated Source0 requires an explicit --package selection"})
        candidate.assert_not_called()
        prove.assert_not_called()

    def test_explicit_generated_selection_locks_the_proven_digest(self) -> None:
        package = self.recipe("gen")
        metadata = {"name": "gen", "version": "2.0", "filename": "gen-2.0.tar.gz",
                    "generate": {"from": "vendored"}, "ignored": "not copied"}
        module = "tools.bootstrap_upstream_sources"
        with patch.dict(f"{module}.GENERATED_SOURCES", {"gen": object()}), \
                patch(f"{module}.generated_candidate", return_value=metadata) as candidate, \
                patch(f"{module}.prove_generated", return_value="ab" * 64) as prove:
            code, output, report = self.run_main("--package", "gen")
        self.assertEqual(code, 0)
        candidate.assert_called_once_with(package)
        prove.assert_called_once_with(metadata, package)
        self.assertEqual(output["packages"], [{
            "name": "gen", "version": "2.0", "filename": "gen-2.0.tar.gz",
            "sha512": "ab" * 64, "generate": {"from": "vendored"},
        }])
        self.assertEqual(report["rejected"], [])
        self.assertEqual(self.fetched, [])

    def test_a_failed_generation_proof_is_reported_not_locked(self) -> None:
        self.recipe("gen")
        module = "tools.bootstrap_upstream_sources"
        with patch.dict(f"{module}.GENERATED_SOURCES", {"gen": object()}), \
                patch(f"{module}.generated_candidate", return_value={"name": "gen"}), \
                patch(f"{module}.prove_generated", side_effect=ValueError("non-deterministic generation")):
            _, output, report = self.run_main("--package", "gen")
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.reasons(report), {"gen": "non-deterministic generation"})

    def write_resolution(self, mapping: dict[str, str]) -> None:
        path = self.root / "reports/bluefin-rawhide-resolution.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"resolved_binary_to_source": mapping}))

    def test_skips_a_source_only_when_hummingbird_supplies_every_requested_binary(self) -> None:
        url = "https://upstream.example/partial-1.0.tar.xz"
        self.serve(url, b"partial", "partial-1.0.tar.xz")
        self.recipe("full", [(0, "https://upstream.example/full-1.0.tar.xz")])
        self.recipe("partial", [(0, url)])
        self.write_resolution({"full-libs": "full", "full-tools": "full",
                               "partial-libs": "partial", "partial-extra": "partial"})
        provided = self.root / "provided.txt"
        provided.write_text("full-libs\nfull-tools\npartial-libs\n")
        _, output, report = self.run_main("--provided-packages", str(provided))
        self.assertEqual(report["already_supplied_by_hummingbird"], {"full": ["full-libs", "full-tools"]})
        self.assertEqual([entry["name"] for entry in output["packages"]], ["partial"])
        self.assertEqual(self.fetched, [url])

    def test_provided_sources_inventory_marks_whole_sources_supplied(self) -> None:
        self.recipe("bysource", [(0, "https://upstream.example/bysource-1.0.tar.xz")])
        self.recipe("unrequested", [(0, "https://upstream.example/unrequested-1.0.tar.xz")])
        self.write_resolution({"bysource-libs": "bysource"})
        inventory = self.root / "provided-sources.json"
        inventory.write_text(json.dumps({"sources": ["bysource", "unrequested"]}))
        _, output, report = self.run_main("--provided-sources", str(inventory))
        self.assertEqual(report["already_supplied_by_hummingbird"],
                         {"bysource": ["bysource-libs"], "unrequested": []})
        self.assertEqual(output["packages"], [])
        self.assertEqual(self.fetched, [])

    def test_explicit_selection_processes_a_supplied_package(self) -> None:
        url = "https://upstream.example/full-1.0.tar.xz"
        self.serve(url, b"full", "full-1.0.tar.xz")
        self.recipe("full", [(0, url)])
        self.write_resolution({"full-libs": "full"})
        provided = self.root / "provided.txt"
        provided.write_text("full-libs\n")
        _, output, report = self.run_main("--provided-packages", str(provided), "--package", "full")
        self.assertEqual(report["already_supplied_by_hummingbird"], {"full": ["full-libs"]})
        self.assertEqual([entry["name"] for entry in output["packages"]], ["full"])

    def test_without_merge_the_output_is_replaced(self) -> None:
        url = "https://upstream.example/new-1.0.tar.xz"
        self.serve(url, b"new", "new-1.0.tar.xz")
        self.recipe("new", [(0, url)])
        output_path = self.root / "config/upstream-sources.json"
        output_path.parent.mkdir()
        output_path.write_text(json.dumps({"schema": 1, "packages": [{"name": "old"}]}))
        _, output, _ = self.run_main()
        self.assertEqual([entry["name"] for entry in output["packages"]], ["new"])

    def test_merge_appends_to_the_existing_lock_and_keeps_its_fields(self) -> None:
        url = "https://upstream.example/new-1.0.tar.xz"
        self.serve(url, b"new", "new-1.0.tar.xz")
        self.recipe("new", [(0, url)])
        output_path = self.root / "config/upstream-sources.json"
        output_path.parent.mkdir()
        existing = {"schema": 1, "note": "kept", "packages": [{"name": "old", "stage": 3}]}
        output_path.write_text(json.dumps(existing))
        code, output, _ = self.run_main("--merge", "--package", "new")
        self.assertEqual(code, 0)
        self.assertEqual(output["note"], "kept")
        self.assertEqual(output["packages"][0], {"name": "old", "stage": 3})
        self.assertEqual([entry["name"] for entry in output["packages"]], ["old", "new"])

    def test_merge_without_an_existing_lock_starts_a_schema_1_file(self) -> None:
        url = "https://upstream.example/new-1.0.tar.xz"
        self.serve(url, b"new", "new-1.0.tar.xz")
        self.recipe("new", [(0, url)])
        _, output, _ = self.run_main("--merge")
        self.assertEqual(output["schema"], 1)
        self.assertEqual([entry["name"] for entry in output["packages"]], ["new"])

    def test_merge_refuses_to_overwrite_an_existing_lock(self) -> None:
        url = "https://upstream.example/old-2.0.tar.xz"
        self.serve(url, b"old v2", "old-2.0.tar.xz")
        self.recipe("old", [(0, url)])
        output_path = self.root / "config/upstream-sources.json"
        output_path.parent.mkdir()
        original = json.dumps({"schema": 1, "packages": [{"name": "old", "version": "1.0"}]})
        output_path.write_text(original)
        with self.assertRaisesRegex(ValueError, "source lock already exists: old"):
            self.run_main("--merge", "--package", "old")
        self.assertEqual(output_path.read_text(), original)
