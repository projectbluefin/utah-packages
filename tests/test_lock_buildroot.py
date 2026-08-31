#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.lock_buildroot import split_pinned, load_lock, _pick_digest


class LockBuildrootTests(unittest.TestCase):
    def test_pick_digest_prefers_non_fedora_registry(self) -> None:
        digests = [
            "registry.fedoraproject.org/fedora@sha256:aaa",
            "quay.io/fedora/fedora@sha256:bbb",
        ]
        self.assertEqual(_pick_digest(digests), "quay.io/fedora/fedora@sha256:bbb")

    def test_pick_digest_falls_back_to_first_when_all_fedora(self) -> None:
        digests = [
            "registry.fedoraproject.org/fedora@sha256:aaa",
        ]
        self.assertEqual(_pick_digest(digests), "registry.fedoraproject.org/fedora@sha256:aaa")

    def test_split_pinned_returns_reference_without_digest(self) -> None:
        pinned = "quay.io/fedora/fedora:44@sha256:" + "0" * 64
        result = split_pinned(pinned)
        self.assertEqual(result, "quay.io/fedora/fedora:44")

    def test_split_pinned_rejects_unpinned(self) -> None:
        with self.assertRaises(ValueError):
            split_pinned("quay.io/fedora/fedora:44")

    def test_load_lock_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                load_lock(Path(directory) / "nonexistent.json")

    def test_load_lock_rejects_missing_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps({"schema": 1, "image": {}}))
            with self.assertRaisesRegex(ValueError, "image.pinned"):
                load_lock(lock)

    def test_load_lock_validates_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps({"schema": 2, "image": {"pinned": "x"}}))
            with self.assertRaisesRegex(ValueError, "schema"):
                load_lock(lock)

    def test_load_lock_returns_valid_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps({
                "schema": 1,
                "image": {"reference": "quay.io/fedora/fedora:44", "pinned": "quay.io/fedora/fedora:44@sha256:abc"},
                "release": "44",
            }))
            data = load_lock(lock)
            self.assertEqual(data["image"]["pinned"], "quay.io/fedora/fedora:44@sha256:abc")
            self.assertEqual(data["release"], "44")


class ResolveTests(unittest.TestCase):
    @patch("tools.lock_buildroot.subprocess.run")
    def test_resolve_pulls_when_image_not_present(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.side_effect = [
            unittest.mock.Mock(returncode=1, stdout="", stderr=""),  # inspect fails
            unittest.mock.Mock(returncode=0, stdout=""),            # pull succeeds
            unittest.mock.Mock(returncode=0, stdout=json.dumps([  # second inspect
                {"RepoDigests": ["registry.fedoraproject.org/fedora@sha256:aaa",
                                 "quay.io/fedora/fedora@sha256:bbb"]}
            ])),
        ]
        from tools.lock_buildroot import resolve
        result = resolve("quay.io/fedora/fedora:44")
        self.assertEqual(result, "quay.io/fedora/fedora:44@sha256:bbb")

    @patch("tools.lock_buildroot.subprocess.run")
    def test_resolve_uses_tag_from_input(self, mock_run: unittest.mock.MagicMock) -> None:
        mock_run.return_value = unittest.mock.Mock(returncode=0, stdout=json.dumps([
            {"RepoDigests": ["quay.io/fedora/fedora@sha256:bbb"]}
        ]))
        from tools.lock_buildroot import resolve
        result = resolve("quay.io/fedora/fedora:44")
        self.assertTrue(result.startswith("quay.io/fedora/fedora:44@sha256:"))


if __name__ == "__main__":
    unittest.main()
