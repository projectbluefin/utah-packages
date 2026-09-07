#!/usr/bin/env python3
"""Cover ``tools/dist_git.py``, which had no unit tests.

``nvr_from_spec`` decides which name-version-release is asked of Koji, and
``koji_complete`` decides whether that build counts as a candidate. A silent
mistake in either promotes a package Koji never built, so both are pinned here
against the real parsing and the real JSON-RPC response shape.
"""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.dist_git import command, koji_complete, nvr_from_spec


class NvrFromSpecTests(unittest.TestCase):
    def spec(self, body: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "demo.spec"
        path.write_text(body)
        return path

    def test_joins_name_version_release(self) -> None:
        nvr = nvr_from_spec(self.spec("Name: demo\nVersion: 1.2.3\nRelease: 4\n"))
        self.assertEqual(nvr, "demo-1.2.3-4")

    def test_strips_dist_macro_from_release(self) -> None:
        nvr = nvr_from_spec(self.spec("Name: demo\nVersion: 1.0\nRelease: 2%{?dist}\n"))
        self.assertEqual(nvr, "demo-1.0-2")

    def test_name_may_contain_hyphens(self) -> None:
        nvr = nvr_from_spec(self.spec("Name: adw-gtk3-theme\nVersion: 5.7\nRelease: 1%{?dist}\n"))
        self.assertEqual(nvr, "adw-gtk3-theme-5.7-1")

    def test_ignores_unrelated_and_indented_fields(self) -> None:
        body = (
            "Summary: Name: not-the-name\n"
            "  Name: indented-is-not-a-field\n"
            "Name: demo\n"
            "Version: 1.0\n"
            "Release: 1\n"
            "Requires: other\n"
        )
        self.assertEqual(nvr_from_spec(self.spec(body)), "demo-1.0-1")

    def test_last_definition_wins(self) -> None:
        body = "Name: demo\nVersion: 1.0\nVersion: 2.0\nRelease: 1\n"
        self.assertEqual(nvr_from_spec(self.spec(body)), "demo-2.0-1")

    def test_missing_fields_are_named_in_the_error(self) -> None:
        with self.assertRaises(ValueError) as raised:
            nvr_from_spec(self.spec("Name: demo\n"))
        message = str(raised.exception)
        self.assertIn("release", message)
        self.assertIn("version", message)
        self.assertNotIn("name", message.split(":", 1)[1])

    def test_undecodable_bytes_do_not_abort_parsing(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "demo.spec"
        path.write_bytes(b"Name: demo\n%description\n\xff\xfe\nVersion: 1.0\nRelease: 1\n")
        self.assertEqual(nvr_from_spec(path), "demo-1.0-1")


class KojiCompleteTests(unittest.TestCase):
    def urlopen(self, payload: object):
        captured = {}

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()
                return False

        def fake(request, timeout=None):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response(json.dumps({"id": 1, "result": payload}).encode())

        return fake, captured

    def test_state_one_is_complete(self) -> None:
        fake, _ = self.urlopen({"nvr": "demo-1.0-1", "state": 1})
        with patch("tools.dist_git.urllib.request.urlopen", fake):
            self.assertTrue(koji_complete("demo-1.0-1"))

    def test_other_states_are_not_complete(self) -> None:
        for state in (0, 2, 3, 4):
            fake, _ = self.urlopen({"nvr": "demo-1.0-1", "state": state})
            with patch("tools.dist_git.urllib.request.urlopen", fake):
                self.assertFalse(koji_complete("demo-1.0-1"), f"state {state}")

    def test_unknown_build_is_not_complete(self) -> None:
        fake, _ = self.urlopen(None)
        with patch("tools.dist_git.urllib.request.urlopen", fake):
            self.assertFalse(koji_complete("demo-1.0-1"))

    def test_queries_getbuild_for_the_requested_nvr(self) -> None:
        fake, captured = self.urlopen({"state": 1})
        with patch("tools.dist_git.urllib.request.urlopen", fake):
            koji_complete("demo-1.0-1")
        request = captured["request"]
        self.assertEqual(request.full_url, "https://koji.fedoraproject.org/kojihub")
        body = json.loads(request.data)
        self.assertEqual(body["method"], "getBuild")
        self.assertEqual(body["params"], ["demo-1.0-1"])
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(captured["timeout"], 30)


class CommandTests(unittest.TestCase):
    def test_returns_stripped_stdout_from_the_given_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "marker").write_text("")
            self.assertEqual(command("ls", cwd=root), "marker")


if __name__ == "__main__":
    unittest.main()
