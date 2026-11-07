#!/usr/bin/env python3

import contextlib
import email.message
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from tools.generated_sources import EXIT_UPSTREAM_UNREACHABLE
from tools.source_pipeline import (
    FETCH_ATTEMPTS,
    LOOKASIDE,
    ChallengePage,
    UnavailableSource,
    bundled_sources,
    digest,
    fetch,
    fetch_with_fallbacks,
    main,
    selected,
    source_manifest,
    stage_for_packit,
    verify_signature,
    verify_staged_sources,
)


@contextlib.contextmanager
def working_directory(path: Path):
    """source_manifest and bundled_sources resolve ``packages/`` from the cwd."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(previous)


SOURCE_PIPELINE = Path(__file__).resolve().parent.parent / "tools" / "source_pipeline.py"


class SourcePipelineTests(unittest.TestCase):
    def test_uses_upstream_without_touching_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch("tools.source_pipeline.fetch") as fetch:
                chosen = fetch_with_fallbacks(["https://upstream.example/source", "https://mirror.example/source"], destination)
            self.assertEqual(chosen, "https://upstream.example/source")
            fetch.assert_called_once_with("https://upstream.example/source", destination)

    def test_uses_fallback_only_after_upstream_transport_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages" / "demo").mkdir(parents=True)
            payload = b"verified fallback bytes"
            expected_sha512 = hashlib.sha512(payload).hexdigest()
            expected_sha256 = hashlib.sha256(payload).hexdigest()
            upstream = "https://upstream.example/source"
            fallback = "https://mirror.example/source"
            checksum_url = "https://upstream.example/SHA256SUMS"
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo",
                                "url": upstream,
                                "fallback_urls": [fallback],
                                "sha256_url": checksum_url,
                                "filename": "demo.tar.gz",
                                "sha512": expected_sha512,
                            }
                        ]
                    }
                )
            )

            def fetch_source(url: str, target: Path) -> None:
                if url == upstream:
                    raise RuntimeError("upstream unavailable")
                if url == checksum_url:
                    target.write_text(f"{expected_sha256}  demo.tar.gz\n")
                else:
                    target.write_bytes(payload)

            argv = [
                str(SOURCE_PIPELINE),
                "demo",
                "--config",
                str(config),
                "--output",
                str(root / "sources"),
                "--report-dir",
                str(root / "reports"),
            ]
            with working_directory(root), patch.object(sys, "argv", argv), patch(
                "tools.source_pipeline.fetch", side_effect=fetch_source
            ) as fetched:
                self.assertEqual(main(), 0)

            accepted = root / "sources" / "demo" / "demo.tar.gz"
            self.assertEqual(accepted.read_bytes(), payload)
            self.assertEqual(hashlib.sha512(accepted.read_bytes()).hexdigest(), expected_sha512)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["resolved_url"], fallback)
            self.assertEqual(
                [call.args[0] for call in fetched.call_args_list],
                [upstream, fallback, checksum_url],
            )

    def test_reports_every_failed_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch("tools.source_pipeline.fetch", side_effect=RuntimeError("offline")):
                with self.assertRaisesRegex(RuntimeError, "upstream.example.*mirror.example"):
                    fetch_with_fallbacks(["https://upstream.example/source", "https://mirror.example/source"], destination)

    def test_stages_verified_source_for_packit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "upstream.tar.xz"
            source.write_bytes(b"verified source")
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo",
                                "url": source.as_uri(),
                                "filename": source.name,
                                "sha512": hashlib.sha512(source.read_bytes()).hexdigest(),
                            }
                        ]
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SOURCE_PIPELINE),
                    "demo",
                    "--config",
                    str(config),
                    "--output",
                    str(root / "sources"),
                    "--report-dir",
                    str(root / "reports"),
                    "--stage-into",
                    str(root / "packages"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((package_dir / source.name).read_bytes(), b"verified source")

    def test_rejects_source_overwritten_after_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            source = package_dir / "demo-1.0.tar.gz"
            source.write_bytes(b"packit generated archive")
            package = {
                "name": "demo",
                "filename": source.name,
                "sha512": hashlib.sha512(b"verified upstream archive").hexdigest(),
            }

            with self.assertRaisesRegex(ValueError, "SHA-512 mismatch"):
                verify_staged_sources(package, root / "packages")

    def test_verifies_nothing_for_a_recipe_with_no_upstream_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "nosource"
            package_dir.mkdir(parents=True)
            # What Packit's create-archive action leaves behind. It is not a
            # source and must not be treated as one.
            (package_dir / "nosource-1.tar.gz").write_bytes(b"placeholder")
            package = {"name": "nosource", "version": "1", "no_upstream_source": True}

            self.assertEqual(verify_staged_sources(package, root / "packages"), [])


FAKE_GENERATOR = """\
import pathlib
import shutil
import sys

package, package_dir, out_dir = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
fixture = package_dir / "payload.bin"
shutil.copyfile(fixture, out_dir / f"{package}.tar.xz")
"""


class GeneratedSourcePipelineTests(unittest.TestCase):
    """The generate path: run the locked script, hash-verify the artifact."""

    def run_pipeline(self, root: Path, package: dict):
        package_dir = root / "packages" / package["name"]
        package_dir.mkdir(parents=True)
        payload = b"deterministically generated bytes"
        (package_dir / "payload.bin").write_bytes(payload)
        script = root / "tools"
        script.mkdir()
        (script / "fake-gen.py").write_text(FAKE_GENERATOR)
        config = root / "sources.json"
        entry = {
            "name": package["name"],
            "filename": f"{package['name']}.tar.xz",
            "sha512": hashlib.sha512(payload).hexdigest()
            if package.get("matching", True)
            else "ab" * 64,
            "generate": {"script": "tools/fake-gen.py", "input": "test", "method": "test"},
        }
        if package.get("with_url"):
            entry["url"] = "https://example.org/should-not-be-here.tar.xz"
        config.write_text(json.dumps({"packages": [entry]}))
        return subprocess.run(
            [
                sys.executable,
                str(SOURCE_PIPELINE),
                package["name"],
                "--config",
                str(config),
                "--output",
                str(root / "sources"),
                "--report-dir",
                str(root / "reports"),
                "--stage-into",
                str(root / "packages"),
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def test_generated_source_is_built_verified_and_staged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, {"name": "demo-gen"})
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(
                (root / "packages" / "demo-gen" / "demo-gen.tar.xz").read_bytes(),
                b"deterministically generated bytes",
            )
            report = (root / "reports" / "demo-gen.json").read_text()
            self.assertIn('"result": "accepted"', report)
            self.assertIn("generated:tools/fake-gen.py", report)

    def test_generated_source_with_wrong_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, {"name": "demo-gen", "matching": False})
            self.assertEqual(result.returncode, 1)
            self.assertIn("SHA-512 mismatch", result.stdout)
            self.assertFalse((root / "packages" / "demo-gen" / "demo-gen.tar.xz").exists())

    def test_generated_entry_must_not_carry_a_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, {"name": "demo-gen", "with_url": True})
            self.assertEqual(result.returncode, 1)
            self.assertIn("must not carry url", result.stderr + result.stdout)

    def test_missing_generation_script_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo-gen"
            package_dir.mkdir(parents=True)
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo-gen",
                                "filename": "demo-gen.tar.xz",
                                "sha512": "ab" * 64,
                                "generate": {"script": "tools/does-not-exist.py"},
                            }
                        ]
                    }
                )
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SOURCE_PIPELINE),
                    "demo-gen",
                    "--config",
                    str(config),
                    "--output",
                    str(root / "sources"),
                    "--report-dir",
                    str(root / "reports"),
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("generation script does not exist", result.stdout)


class FetchRetryTests(unittest.TestCase):
    """An upstream that answers with nothing must be named, not hashed.

    git.zx2c4.com served zero bytes for wireguard-tools and the pipeline
    reported the SHA-512 of the empty string as a digest mismatch, which reads
    as a tampered tarball. These cases lock in the retry and the honest error.
    """

    @staticmethod
    def response(payload: bytes):
        return io.BytesIO(payload)

    def test_empty_body_is_retried_and_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            responses = [self.response(b""), self.response(b""), self.response(b"real bytes")]
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=responses) as urlopen, \
                    patch("tools.source_pipeline.time.sleep") as sleep:
                fetch("https://upstream.example/source", destination)
            self.assertEqual(destination.read_bytes(), b"real bytes")
            self.assertEqual(urlopen.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])

    def test_persistently_empty_body_is_reported_as_empty_not_as_a_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            responses = [self.response(b"") for _ in range(FETCH_ATTEMPTS)]
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=responses), \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(RuntimeError) as raised:
                    fetch("https://upstream.example/source", destination)
            message = str(raised.exception)
            self.assertIn("returned an empty body", message)
            self.assertIn(f"after {FETCH_ATTEMPTS} attempts", message)
            self.assertNotIn("SHA-512", message)

    def test_transport_failure_is_retried_up_to_the_attempt_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch(
                "tools.source_pipeline.urllib.request.urlopen",
                side_effect=urllib.error.URLError(ConnectionResetError("connection reset")),
            ) as urlopen, patch("tools.source_pipeline.time.sleep"):
                with self.assertRaisesRegex(RuntimeError, "failed to fetch"):
                    fetch("https://upstream.example/source", destination)
            self.assertEqual(urlopen.call_count, FETCH_ATTEMPTS)

    @staticmethod
    def typed_response(payload: bytes, content_type: str):
        response = io.BytesIO(payload)
        response.headers = email.message.Message()
        response.headers["Content-Type"] = content_type
        return response

    def test_html_challenge_page_is_not_hashed_as_the_archive(self) -> None:
        """linuxtv.org and salsa.debian.org answer archive URLs with an anti-bot page."""
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            page = self.typed_response(b"<html>Making sure you're not a bot!</html>", "text/html; charset=utf-8")
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=[page]) as urlopen, \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(ChallengePage) as raised:
                    fetch("https://upstream.example/demo-1.0.tar.xz", destination)
            self.assertIn("returned an HTML page", str(raised.exception))
            self.assertEqual(urlopen.call_count, 1)

    def test_html_challenge_page_falls_back_to_the_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            responses = [
                self.typed_response(b"<html>challenge</html>", "text/html"),
                self.typed_response(b"archive bytes", "application/x-xz"),
            ]
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=responses), \
                    patch("tools.source_pipeline.time.sleep"):
                chosen = fetch_with_fallbacks(
                    ["https://upstream.example/demo-1.0.tar.xz", "https://mirror.example/demo-1.0.tar.xz"],
                    destination,
                )
            self.assertEqual(chosen, "https://mirror.example/demo-1.0.tar.xz")
            self.assertEqual(destination.read_bytes(), b"archive bytes")

    def test_a_challenge_page_is_not_an_outage(self) -> None:
        """The host answered, so a challenge is fatal and actionable, never ``unavailable``."""
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            page = self.typed_response(b"<html>challenge</html>", "text/html")
            dead = urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=[page] + [dead] * FETCH_ATTEMPTS), \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(RuntimeError) as raised:
                    fetch_with_fallbacks(
                        ["https://upstream.example/demo-1.0.tar.xz", "https://mirror.example/demo-1.0.tar.xz"],
                        destination,
                    )
            self.assertNotIsInstance(raised.exception, UnavailableSource)
            self.assertIn("returned an HTML page", str(raised.exception))

    def test_html_is_accepted_when_the_url_names_an_html_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "notes.html"
            page = self.typed_response(b"<html>notes</html>", "text/html")
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=[page]):
                fetch("https://upstream.example/notes.html", destination)
            self.assertEqual(destination.read_bytes(), b"<html>notes</html>")

    def test_a_digest_mismatch_never_falls_back_to_another_url(self) -> None:
        """A fallback is availability, never a second chance at integrity."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "upstream.tar.gz"
            good.write_bytes(b"upstream bytes")
            mirror = root / "mirror.tar.gz"
            mirror.write_bytes(b"different bytes")
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "demo",
                                "url": good.as_uri(),
                                "fallback_urls": [mirror.as_uri()],
                                "filename": "demo.tar.gz",
                                "sha512": hashlib.sha512(b"different bytes").hexdigest(),
                            }
                        ]
                    }
                )
            )
            result = subprocess.run(
                [sys.executable, str(SOURCE_PIPELINE), "demo",
                 "--config", str(config),
                 "--output", str(root / "sources"),
                 "--report-dir", str(root / "reports")],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("SHA-512 mismatch", result.stdout)
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz").exists())


class UnavailableSourceTests(unittest.TestCase):
    """An upstream that never answered is tracked, not fatal.

    The daily job verifies rtmpdump from git.ffmpeg.org, which drops the
    connection and times out. That is a transient outage: the job must record
    it and keep going for the rest of inventory, so an unreachable upstream is
    reported as ``unavailable`` while a digest mismatch stays fatal.
    """

    @staticmethod
    def _run(root: Path, packages: list[dict], package: str | None = None) -> tuple[int, str]:
        """Run the pipeline in-process so urlopen/subprocess mocks apply.

        The subprocess runner used elsewhere cannot be mocked, and an
        unavailable upstream must be simulated, not contacted for real.
        """
        config = root / "sources.json"
        config.write_text(json.dumps({"packages": packages}))
        previous_cwd = Path.cwd()
        previous_argv = sys.argv
        captured = io.StringIO()
        invocation = ["source_pipeline.py"]
        if package is not None:
            invocation.append(package)
        invocation += ["--config", str(config),
                       "--output", str(root / "sources"),
                       "--report-dir", str(root / "reports")]
        try:
            os.chdir(root)
            sys.argv = invocation
            with contextlib.redirect_stdout(captured):
                code = main()
            return code, captured.getvalue()
        finally:
            os.chdir(previous_cwd)
            sys.argv = previous_argv

    def test_fetch_reports_unavailable_not_a_generic_error(self) -> None:
        """A transport failure that exhausts retries is an UnavailableSource."""
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with self._dead_upstream(), patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(UnavailableSource):
                    fetch("https://dead.example/source", destination)

    def test_fetch_with_fallbacks_tries_every_url_before_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with self._dead_upstream() as urlopen, patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(UnavailableSource) as raised:
                    fetch_with_fallbacks(
                        ["https://a.example/x", "https://b.example/y"], destination
                    )
            self.assertEqual(
                [call.args[0].full_url for call in urlopen.call_args_list],
                ["https://a.example/x"] * FETCH_ATTEMPTS + ["https://b.example/y"] * FETCH_ATTEMPTS,
            )
            self.assertIn("https://a.example/x", str(raised.exception))
            self.assertIn("https://b.example/y", str(raised.exception))

    def test_mirror_serves_the_locked_bytes_when_the_primary_is_down(self) -> None:
        """The real fetch path: a dead primary falls back to a reachable mirror."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"mirror bytes"

            def fake_urlopen(request, timeout=None):
                if "dead" in request.full_url:
                    raise urllib.error.URLError(socket.gaierror(-2, "Name or service not known"))
                return io.BytesIO(payload)

            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [{
                    "name": "demo",
                    "url": "https://dead.example/demo.tar.gz",
                    "fallback_urls": ["https://mirror.example/demo.tar.gz"],
                    "filename": "demo.tar.gz",
                    "sha512": hashlib.sha512(payload).hexdigest(),
                }])
            self.assertEqual(code, 0, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "accepted")
            self.assertEqual(report["resolved_url"], "https://mirror.example/demo.tar.gz")
            self.assertEqual(json.loads((root / "reports" / "unavailable.json").read_text()), [])

    def test_a_permanent_404_is_not_unavailable_and_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            gone = urllib.error.HTTPError("https://gone.example/x", 404, "Not Found", {}, None)
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=gone) as urlopen, \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaisesRegex(RuntimeError, "404") as raised:
                    fetch("https://gone.example/x", destination)
            self.assertNotIsInstance(raised.exception, UnavailableSource)
            self.assertEqual(urlopen.call_count, 1)

    def test_a_server_error_is_retried_and_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            busy = urllib.error.HTTPError("https://busy.example/x", 503, "Unavailable", {}, None)
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=busy) as urlopen, \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(UnavailableSource):
                    fetch("https://busy.example/x", destination)
            self.assertEqual(urlopen.call_count, FETCH_ATTEMPTS)

    def test_a_certificate_failure_is_fatal_not_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            bad_cert = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=bad_cert), \
                    patch("tools.source_pipeline.time.sleep"):
                with self.assertRaises(RuntimeError) as raised:
                    fetch("https://mitm.example/x", destination)
            self.assertNotIsInstance(raised.exception, UnavailableSource)

    def test_a_missing_primary_with_a_dead_mirror_fails_the_run(self) -> None:
        """A 404 is actionable even if the mirror is also down."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fake_urlopen(request, timeout=None):
                if "gone" in request.full_url:
                    raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
                raise urllib.error.URLError(ConnectionRefusedError("connection refused"))

            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [{
                    "name": "demo",
                    "url": "https://gone.example/demo.tar.gz",
                    "fallback_urls": ["https://dead.example/demo.tar.gz"],
                    "filename": "demo.tar.gz",
                    "sha512": "0" * 128,
                }])
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "rejected")

    @staticmethod
    def _dead_upstream():
        return patch(
            "tools.source_pipeline.urllib.request.urlopen",
            side_effect=urllib.error.URLError(ConnectionRefusedError("connection refused")),
        )

    def test_unavailable_upstream_is_tracked_and_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = {
                "name": "demo",
                "url": "https://dead.example/demo.tar.gz",
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            with self._dead_upstream(), patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [entry])
            self.assertEqual(code, 0, output)
            self.assertIn("unavailable", output)
            self.assertNotIn("rejected", output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "unavailable")
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz").exists())
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz.candidate").exists())
            durable = json.loads((root / "reports" / "unavailable.json").read_text())
            self.assertEqual([item["package"] for item in durable], ["demo"])
            self.assertEqual(durable[0]["url"], "https://dead.example/demo.tar.gz")

    def test_unavailable_is_written_to_the_job_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "summary.md"
            entry = {
                "name": "demo",
                "url": "https://dead.example/demo.tar.gz",
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            with self._dead_upstream(), patch("tools.source_pipeline.time.sleep"), \
                    patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
                code, output = self._run(root, [entry])
            self.assertEqual(code, 0, output)
            self.assertIn("audit incomplete", output)
            self.assertIn("`demo`", summary.read_text())

    def test_a_named_package_whose_upstream_is_down_fails(self) -> None:
        """A build fetching one package cannot proceed without its source."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = {
                "name": "demo",
                "url": "https://dead.example/demo.tar.gz",
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            with self._dead_upstream(), patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [entry], package="demo")
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "unavailable")

    def test_unreachable_verification_inputs_are_fatal(self) -> None:
        """A signature or checksum manifest that cannot be fetched is not 'unavailable'."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"real bytes"

            def fake_urlopen(request, timeout=None):
                if "SHA256SUMS" in request.full_url:
                    raise urllib.error.URLError(ConnectionRefusedError("connection refused"))
                return io.BytesIO(payload)

            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [{
                    "name": "demo",
                    "url": "https://good.example/demo.tar.gz",
                    "sha256_url": "https://good.example/SHA256SUMS",
                    "filename": "demo.tar.gz",
                    "sha512": hashlib.sha512(payload).hexdigest(),
                }])
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "rejected")
            self.assertIn("SHA-256 manifest could not be fetched", report["error"])
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz").exists())

    def test_unreachable_bundled_source_is_fatal_and_leaves_no_final_source0(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"real bytes"
            (root / "packages" / "demo").mkdir(parents=True)
            (root / "packages" / "demo" / "sources").write_text(
                f"SHA512 (extra.tar.gz) = {'1' * 128}\n"
            )

            def fake_urlopen(request, timeout=None):
                if "src.fedoraproject.org" in request.full_url:
                    raise urllib.error.URLError(ConnectionRefusedError("connection refused"))
                return io.BytesIO(payload)

            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [{
                    "name": "demo",
                    "url": "https://good.example/demo.tar.gz",
                    "filename": "demo.tar.gz",
                    "sha512": hashlib.sha512(payload).hexdigest(),
                }])
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "rejected")
            self.assertIn("bundled source extra.tar.gz could not be fetched", report["error"])
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz").exists())

    def test_unavailable_does_not_block_accepted_packages(self) -> None:
        """One dead upstream does not fail a run that also has good sources."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good_payload = b"real bytes"

            def fake_urlopen(request, timeout=None):
                url = getattr(request, "full_url", str(request))
                if "dead" in url:
                    raise urllib.error.URLError(ConnectionRefusedError("connection refused"))
                return io.BytesIO(good_payload)

            # demo is unavailable; good is accepted, in the same run.
            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [
                    {
                        "name": "demo",
                        "url": "https://dead.example/demo.tar.gz",
                        "filename": "demo.tar.gz",
                        "sha512": "0" * 128,
                    },
                    {
                        "name": "good",
                        "url": "https://good.example/good.tar.gz",
                        "filename": "good.tar.gz",
                        "sha512": hashlib.sha512(good_payload).hexdigest(),
                    },
                ])
            self.assertEqual(code, 0, output)
            demo = json.loads((root / "reports" / "demo.json").read_text())
            good = json.loads((root / "reports" / "good.json").read_text())
            self.assertEqual(demo["result"], "unavailable")
            self.assertEqual(good["result"], "accepted")

    def test_integrity_failure_fails_the_run_even_with_an_unavailable_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good_payload = b"real bytes"

            def fake_urlopen(request, timeout=None):
                url = getattr(request, "full_url", str(request))
                if "dead" in url:
                    raise urllib.error.URLError(ConnectionRefusedError("connection refused"))
                return io.BytesIO(good_payload)

            with patch("tools.source_pipeline.urllib.request.urlopen", side_effect=fake_urlopen), \
                    patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [
                    {
                        "name": "demo",
                        "url": "https://dead.example/demo.tar.gz",
                        "filename": "demo.tar.gz",
                        "sha512": "0" * 128,
                    },
                    {
                        "name": "bad",
                        "url": "https://bad.example/bad.tar.gz",
                        "filename": "bad.tar.gz",
                        "sha512": "ab" * 64,  # does not match good_payload
                    },
                ])
            # The integrity failure is fatal even though demo is only unavailable.
            self.assertEqual(code, 1, output)
            demo = json.loads((root / "reports" / "demo.json").read_text())
            bad = json.loads((root / "reports" / "bad.json").read_text())
            self.assertEqual(demo["result"], "unavailable")
            self.assertEqual(bad["result"], "rejected")

    def test_generate_timeout_is_fatal(self) -> None:
        """A wedged generator is not proven to be an outage, so it fails.

        The generator bounds its own network calls and reports an unreachable
        host with its dedicated exit; the outer timeout is only a backstop.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "gen.py"
            script.write_text("#!/usr/bin/env python3\n")
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            entry = {
                "name": "demo",
                "generate": {"script": str(script)},
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            with patch(
                "tools.source_pipeline.subprocess.run",
                side_effect=subprocess.TimeoutExpired(str(script), 600),
            ), patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [entry])
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "rejected")
            self.assertIn("did not finish", report["error"])

    def test_generator_unreachable_exit_is_unavailable(self) -> None:
        """Only the generator's dedicated exit maps to unavailable.

        This is the rtmpdump failure: git.ffmpeg.org is unreachable, the
        generator classifies git's transport error and exits
        EXIT_UPSTREAM_UNREACHABLE. The daily job must track this, not abort.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "gen.py"
            script.write_text("#!/usr/bin/env python3\n")
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            entry = {
                "name": "demo",
                "generate": {"script": str(script)},
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            with patch(
                "tools.source_pipeline.subprocess.run",
                side_effect=subprocess.CalledProcessError(EXIT_UPSTREAM_UNREACHABLE, [str(script)]),
            ), patch("tools.source_pipeline.time.sleep"):
                code, output = self._run(root, [entry])
            self.assertEqual(code, 0, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "unavailable")
            self.assertIn("could not reach its upstream", report["error"])

    def test_any_other_generator_exit_is_rejected(self) -> None:
        """A moved tag or input mismatch exits 1 from the generator; it stays fatal."""
        for returncode in (1, 128):
            with self.subTest(returncode=returncode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = root / "gen.py"
                script.write_text("#!/usr/bin/env python3\n")
                (root / "packages" / "demo").mkdir(parents=True)
                entry = {
                    "name": "demo",
                    "generate": {"script": str(script)},
                    "filename": "demo.tar.gz",
                    "sha512": "0" * 128,
                }
                with patch(
                    "tools.source_pipeline.subprocess.run",
                    side_effect=subprocess.CalledProcessError(returncode, [str(script)]),
                ):
                    code, output = self._run(root, [entry])
                self.assertEqual(code, 1, output)
                report = json.loads((root / "reports" / "demo.json").read_text())
                self.assertEqual(report["result"], "rejected")

    def test_real_generator_integrity_failure_is_rejected(self) -> None:
        """End to end: a generator raising 'tag ... moved' fails the run."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "gen.py"
            script.write_text(
                "raise RuntimeError('tag v1 moved: expected aaaa, got bbbb')\n"
            )
            (root / "packages" / "demo").mkdir(parents=True)
            entry = {
                "name": "demo",
                "generate": {"script": str(script)},
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            code, output = self._run(root, [entry])
            self.assertEqual(code, 1, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "rejected")
            self.assertNotIn("demo", [item["package"] for item in json.loads((root / "reports" / "unavailable.json").read_text())])

    def test_real_generator_unreachable_exit_is_unavailable(self) -> None:
        """End to end: the generator's dedicated exit code is honoured."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "gen.py"
            script.write_text(f"raise SystemExit({EXIT_UPSTREAM_UNREACHABLE})\n")
            (root / "packages" / "demo").mkdir(parents=True)
            entry = {
                "name": "demo",
                "generate": {"script": str(script)},
                "filename": "demo.tar.gz",
                "sha512": "0" * 128,
            }
            code, output = self._run(root, [entry])
            self.assertEqual(code, 0, output)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "unavailable")


class SignatureConfigurationTests(unittest.TestCase):
    """gpg_key and signature_url are a pair; half a pair is a silent no-op."""

    def test_key_without_signature_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "must be configured together"):
                verify_signature({"gpg_key": "keys/demo.asc"}, root / "target", root)

    def test_signature_url_without_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "must be configured together"):
                verify_signature({"signature_url": "https://example.org/x.asc"}, root / "target", root)

    def test_unsigned_package_verifies_without_fetching_anything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("tools.source_pipeline.fetch") as fetched:
                verify_signature({"name": "demo"}, root / "target", root)
            fetched.assert_not_called()

    def test_missing_key_file_is_rejected_before_gpg_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = {"gpg_key": str(root / "absent.asc"), "signature_url": "https://example.org/x.asc"}
            with patch("tools.source_pipeline.fetch"), patch("tools.source_pipeline.subprocess.run") as run:
                with self.assertRaisesRegex(ValueError, "configured GPG key does not exist"):
                    verify_signature(package, root / "target", root)
            run.assert_not_called()


class SourceManifestTests(unittest.TestCase):
    """The dist-git ``sources`` file is the record of the bundled tarballs."""

    def write_manifest(self, root: Path, name: str, text: str) -> None:
        package_dir = root / "packages" / name
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "sources").write_text(text)

    def test_absent_manifest_reports_no_bundled_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages" / "demo").mkdir(parents=True)
            with working_directory(root):
                self.assertEqual(source_manifest({"name": "demo"}), [])

    def test_rpmfusion_auxiliary_sources_keep_the_manifest_digest_gate(self) -> None:
        for payload in (b"verified test data", b"tampered test data"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                expected = hashlib.sha512(b"verified test data").hexdigest()
                self.write_manifest(root, "demo", f"SHA512 (tests.tar.xz) = {expected}\n")
                target = root / "download"
                target.mkdir()
                package = {"name": "demo", "lookaside": "rpmfusion-free"}
                with working_directory(root), patch("tools.source_pipeline.fetch") as fetched:
                    fetched.side_effect = lambda url, path: path.write_bytes(payload)
                    if payload == b"verified test data":
                        self.assertEqual(bundled_sources(package, target, "source.tar.gz"), ["tests.tar.xz"])
                        self.assertEqual((target / "tests.tar.xz").read_bytes(), payload)
                    else:
                        with self.assertRaisesRegex(ValueError, "SHA-512 mismatch"):
                            bundled_sources(package, target, "source.tar.gz")
                        self.assertFalse((target / "tests.tar.xz").exists())
                        self.assertFalse((target / "tests.tar.xz.candidate").exists())
                fetched.assert_called_once_with(
                    f"https://pkgs.rpmfusion.org/repo/pkgs/free/demo/tests.tar.xz/sha512/{expected}/tests.tar.xz",
                    target / "tests.tar.xz.candidate",
                )

    def test_only_well_formed_sha512_lines_are_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_manifest(
                root,
                "demo",
                "SHA512 (gvdb.tar.xz) = " + "a" * 128 + "\n"
                "MD5 (legacy.tar.gz) = " + "b" * 32 + "\n"
                "SHA512 (truncated.tar.xz) = " + "c" * 100 + "\n"
                "\n"
                "SHA512 (extra.tar.xz) = " + "d" * 128 + "\n",
            )
            with working_directory(root):
                self.assertEqual(
                    source_manifest({"name": "demo"}),
                    [("gvdb.tar.xz", "a" * 128), ("extra.tar.xz", "d" * 128)],
                )


class DigestTests(unittest.TestCase):
    """digest() compares a downloaded file against the value Fedora recorded.

    md5 is collision-broken; the pipeline accepts it only where the dist-git
    pin itself is md5, and such recipes are listed in factory_manifest under
    source_verification as the checksum-only class to shorten. On a FIPS-mode
    OpenSSL build, ``hashlib.new('md5')`` raises ``ValueError`` for security
    use; the call has to carry ``usedforsecurity=False`` so md5 verification
    works on a FIPS host. sha512 and sha256 keep the FIPS-strict default so a
    future algorithm addition cannot silently opt out of policy.
    """

    def test_digest_passes_usedforsecurity_false_only_for_md5(self) -> None:
        captured: list[tuple[str, dict]] = []
        real_new = hashlib.new

        def spy_new(name: str, *args: object, **kwargs: object):
            captured.append((name, dict(kwargs)))
            return real_new(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bytes"
            path.write_bytes(b"digest me")
            with patch("tools.source_pipeline.hashlib.new", side_effect=spy_new):
                for algorithm in ("sha512", "sha256", "md5"):
                    digest(path, algorithm)
        self.assertEqual([name for name, _ in captured], ["sha512", "sha256", "md5"])
        self.assertEqual(captured[0][1], {"usedforsecurity": True})
        self.assertEqual(captured[1][1], {"usedforsecurity": True})
        self.assertEqual(captured[2][1], {"usedforsecurity": False})

    def test_digest_matches_hashlib_for_md5(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bytes"
            path.write_bytes(b"digest me")
            self.assertEqual(digest(path, "md5"), hashlib.md5(b"digest me").hexdigest())


class BundledSourceTests(unittest.TestCase):
    """malcontent's Source2 is a gvdb snapshot with no upstream URL at all.

    Nothing fetched it, so ``%prep`` died in the buildroot. The lookaside is
    addressed by the recorded SHA-512, so these cases prove the digest is
    enforced and that a mismatch leaves nothing behind.
    """

    PAYLOAD = b"bundled gvdb snapshot"

    def manifest_entry(self, filename: str, payload: bytes) -> str:
        return f"SHA512 ({filename}) = {hashlib.sha512(payload).hexdigest()}\n"

    def test_source0_is_skipped_and_other_entries_are_fetched_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "malcontent"
            package_dir.mkdir(parents=True)
            (package_dir / "sources").write_text(
                self.manifest_entry("malcontent-0.11.tar.xz", b"source0 bytes")
                + self.manifest_entry("gvdb.tar.xz", self.PAYLOAD)
            )
            target_dir = root / "sources" / "malcontent"
            target_dir.mkdir(parents=True)

            requested: list[str] = []

            def fake_fetch(url: str, destination: Path) -> None:
                requested.append(url)
                destination.write_bytes(self.PAYLOAD)

            with working_directory(root), patch("tools.source_pipeline.fetch", side_effect=fake_fetch):
                fetched = bundled_sources(
                    {"name": "malcontent"}, target_dir, "malcontent-0.11.tar.xz"
                )

            self.assertEqual(fetched, ["gvdb.tar.xz"])
            self.assertEqual((target_dir / "gvdb.tar.xz").read_bytes(), self.PAYLOAD)
            self.assertFalse((target_dir / "gvdb.tar.xz.candidate").exists())
            self.assertEqual(
                requested,
                [LOOKASIDE.format(pkg="malcontent", name="gvdb.tar.xz",
                                  hash=hashlib.sha512(self.PAYLOAD).hexdigest())],
            )

    def test_lookaside_url_uses_the_dist_git_name_when_it_differs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            (package_dir / "sources").write_text(self.manifest_entry("extra.tar.xz", self.PAYLOAD))
            target_dir = root / "sources" / "demo"
            target_dir.mkdir(parents=True)

            requested: list[str] = []

            def fake_fetch(url: str, destination: Path) -> None:
                requested.append(url)
                destination.write_bytes(self.PAYLOAD)

            with working_directory(root), patch("tools.source_pipeline.fetch", side_effect=fake_fetch):
                bundled_sources({"name": "demo", "dist_git_name": "demo-upstream"}, target_dir, "demo.tar.xz")

            self.assertIn("/rpms/demo-upstream/", requested[0])

    def test_digest_mismatch_rejects_and_leaves_no_candidate_behind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            (package_dir / "sources").write_text(self.manifest_entry("extra.tar.xz", self.PAYLOAD))
            target_dir = root / "sources" / "demo"
            target_dir.mkdir(parents=True)

            def fake_fetch(url: str, destination: Path) -> None:
                destination.write_bytes(b"substituted bytes")

            with working_directory(root), patch("tools.source_pipeline.fetch", side_effect=fake_fetch):
                with self.assertRaisesRegex(ValueError, "SHA-512 mismatch for extra.tar.xz"):
                    bundled_sources({"name": "demo"}, target_dir, "demo.tar.xz")

            self.assertFalse((target_dir / "extra.tar.xz.candidate").exists())
            self.assertFalse((target_dir / "extra.tar.xz").exists())


class StagedVerificationTests(unittest.TestCase):
    def test_bundled_sources_are_verified_alongside_source0(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package_dir = root / "packages" / "demo"
            package_dir.mkdir(parents=True)
            (package_dir / "demo.tar.gz").write_bytes(b"source0")
            (package_dir / "extra.tar.xz").write_bytes(b"bundled")
            (package_dir / "sources").write_text(
                f"SHA512 (extra.tar.xz) = {hashlib.sha512(b'bundled').hexdigest()}\n"
            )
            package = {
                "name": "demo",
                "filename": "demo.tar.gz",
                "sha512": hashlib.sha512(b"source0").hexdigest(),
            }
            with working_directory(root):
                verified = verify_staged_sources(package, root / "packages")
            self.assertEqual(
                sorted(Path(item).name for item in verified),
                ["demo.tar.gz", "extra.tar.xz"],
            )

    def test_absent_staged_source_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages" / "demo").mkdir(parents=True)
            package = {"name": "demo", "filename": "demo.tar.gz", "sha512": "ab" * 64}
            with working_directory(root):
                with self.assertRaisesRegex(ValueError, "staged source does not exist"):
                    verify_staged_sources(package, root / "packages")


class StageForPackitTests(unittest.TestCase):
    def test_missing_recipe_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "packages").mkdir()
            with self.assertRaisesRegex(ValueError, "package recipe directory does not exist"):
                stage_for_packit({"name": "absent"}, [], root / "packages")


class SelectionTests(unittest.TestCase):
    def test_no_package_argument_selects_every_lock(self) -> None:
        locks = {"a": {"name": "a"}, "b": {"name": "b"}}
        self.assertEqual(selected(locks, None), [locks["a"], locks["b"]])

    def test_named_package_selects_only_that_lock(self) -> None:
        locks = {"a": {"name": "a"}, "b": {"name": "b"}}
        self.assertEqual(selected(locks, "b"), [locks["b"]])

    def test_unknown_package_exits_naming_the_package(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            selected({"a": {"name": "a"}}, "missing")
        self.assertIn("missing", str(raised.exception))


class EntryValidationTests(unittest.TestCase):
    """main() rejects lock entries that cannot be verified, before fetching."""

    def run_pipeline(self, root: Path, entry: dict, package: str = "demo"):
        (root / "packages" / package).mkdir(parents=True, exist_ok=True)
        config = root / "sources.json"
        config.write_text(json.dumps({"packages": [entry]}))
        return subprocess.run(
            [sys.executable, str(SOURCE_PIPELINE), package,
             "--config", str(config),
             "--output", str(root / "sources"),
             "--report-dir", str(root / "reports")],
            cwd=root, capture_output=True, text=True,
        )

    def test_entry_without_url_or_url_template_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, {"name": "demo", "sha512": "ab" * 64})
            self.assertEqual(result.returncode, 1)
            self.assertIn("require url or url_template", result.stderr + result.stdout)

    def test_entry_without_sha512_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, {"name": "demo", "url": "https://example.org/demo.tar.gz"})
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing sha512", result.stderr + result.stdout)

    def test_fallback_urls_must_be_a_list_of_non_empty_strings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(
                root,
                {"name": "demo", "url": "https://example.org/demo.tar.gz",
                 "sha512": "ab" * 64, "fallback_urls": ["", None]},
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("fallback_urls must be a list", result.stderr + result.stdout)

    def test_url_template_is_resolved_from_the_pinned_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"templated upstream archive"
            source = root / "demo-2.4.tar.gz"
            source.write_bytes(payload)
            template = source.as_uri().replace("demo-2.4", "demo-{version}")
            result = self.run_pipeline(
                root,
                {"name": "demo", "url_template": template, "version": "2.4",
                 "filename": "demo-2.4.tar.gz",
                 "sha512": hashlib.sha512(payload).hexdigest()},
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads((root / "reports" / "demo.json").read_text())
            self.assertEqual(report["result"], "accepted")
            self.assertEqual(report["url"], source.as_uri())


class UpstreamChecksumManifestTests(unittest.TestCase):
    """sha256_url proves the bytes are the ones upstream published."""

    def run_pipeline(self, root: Path, manifest_text: str):
        payload = b"archive covered by an upstream manifest"
        (root / "packages" / "demo").mkdir(parents=True)
        source = root / "demo.tar.gz"
        source.write_bytes(payload)
        manifest = root / "SHA256SUMS"
        manifest.write_text(manifest_text.format(sha256=hashlib.sha256(payload).hexdigest()))
        config = root / "sources.json"
        config.write_text(
            json.dumps(
                {
                    "packages": [
                        {
                            "name": "demo",
                            "url": source.as_uri(),
                            "filename": "demo.tar.gz",
                            "sha512": hashlib.sha512(payload).hexdigest(),
                            "sha256_url": manifest.as_uri(),
                        }
                    ]
                }
            )
        )
        return subprocess.run(
            [sys.executable, str(SOURCE_PIPELINE), "demo",
             "--config", str(config),
             "--output", str(root / "sources"),
             "--report-dir", str(root / "reports")],
            cwd=root, capture_output=True, text=True,
        )

    def test_download_listed_in_the_manifest_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, "{sha256}  demo.tar.gz\n")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((root / "sources" / "demo" / "demo.tar.gz").is_file())

    def test_download_absent_from_the_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_pipeline(root, "0" * 64 + "  demo.tar.gz\n")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("absent from the upstream SHA-256 manifest", result.stdout)
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz").exists())
            self.assertFalse((root / "sources" / "demo" / "demo.tar.gz.candidate").exists())


if __name__ == "__main__":
    unittest.main()
