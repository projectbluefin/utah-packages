#!/usr/bin/env python3
"""Pin the Koji gate in ``tools/dist_git.py``.

``dist_git.py`` decides whether a Fedora dist-git snapshot may become a
reviewable update branch.  It had no unit coverage at all, so the two rules
that make it a gate rather than a mirror -- ``nvr_from_spec`` refusing an
incomplete spec, and ``koji_complete`` accepting only Koji state 1 -- could
regress silently and promote a package that Fedora never finished building.

These tests exercise the pure helpers plus ``main``'s exit contract with the
network and git calls stubbed; nothing here touches Koji or src.fedoraproject.org.
"""

import io
import json
import unittest
from pathlib import Path
from unittest import mock

from tools import dist_git


class NvrFromSpecTests(unittest.TestCase):
    def spec(self, text: str) -> Path:
        import tempfile

        directory = tempfile.mkdtemp(prefix="distgit-test-")
        path = Path(directory) / "pkg.spec"
        path.write_text(text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_reads_name_version_release(self):
        path = self.spec("Name:    fish\nVersion: 4.0.2\nRelease: 3%{?dist}\n")
        self.assertEqual(dist_git.nvr_from_spec(path), "fish-4.0.2-3")

    def test_strips_dist_macro_only_from_release(self):
        path = self.spec("Name: grub2\nVersion: 2.12\nRelease: 1%{?dist}\n")
        self.assertNotIn("%{?dist}", dist_git.nvr_from_spec(path))

    def test_ignores_unrelated_and_indented_fields(self):
        path = self.spec(
            "Summary: a shell\n"
            "  Name: not-the-name\n"
            "Name: fish\n"
            "Version: 4.0.2\n"
            "Release: 1%{?dist}\n"
            "BuildRequires: gcc\n"
        )
        self.assertEqual(dist_git.nvr_from_spec(path), "fish-4.0.2-1")

    def test_first_match_wins_for_repeated_field(self):
        path = self.spec(
            "Name: fish\nVersion: 4.0.2\nRelease: 1%{?dist}\nVersion: 9.9.9\n"
        )
        # ``fields`` is overwritten by later lines, so a duplicate Version wins.
        # Pinning the observed behaviour keeps an accidental change visible.
        self.assertEqual(dist_git.nvr_from_spec(path), "fish-9.9.9-1")

    def test_missing_release_is_rejected(self):
        path = self.spec("Name: fish\nVersion: 4.0.2\n")
        with self.assertRaises(ValueError) as caught:
            dist_git.nvr_from_spec(path)
        self.assertIn("release", str(caught.exception))

    def test_missing_every_field_names_them_all(self):
        path = self.spec("Summary: nothing useful here\n")
        with self.assertRaises(ValueError) as caught:
            dist_git.nvr_from_spec(path)
        self.assertIn("name", str(caught.exception))
        self.assertIn("release", str(caught.exception))
        self.assertIn("version", str(caught.exception))

    def test_undecodable_bytes_do_not_abort_the_parse(self):
        import tempfile

        directory = tempfile.mkdtemp(prefix="distgit-test-")
        path = Path(directory) / "pkg.spec"
        path.write_bytes(b"Name: fish\n%changelog\n- \xff\xfe broken\nVersion: 4.0.2\nRelease: 1%{?dist}\n")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        self.assertEqual(dist_git.nvr_from_spec(path), "fish-4.0.2-1")


class KojiCompleteTests(unittest.TestCase):
    def urlopen(self, payload):
        context = mock.MagicMock()
        context.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        context.__exit__.return_value = False
        return context

    def test_state_one_is_complete(self):
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": {"state": 1}})):
            self.assertTrue(dist_git.koji_complete("fish-4.0.2-1.fc44"))

    def test_building_state_is_not_complete(self):
        # Koji state 0 is BUILDING: dist-git has advanced but the build has not
        # finished, which is exactly the case this gate exists to reject.
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": {"state": 0}})):
            self.assertFalse(dist_git.koji_complete("fish-4.0.2-1.fc44"))

    def test_failed_state_is_not_complete(self):
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": {"state": 3}})):
            self.assertFalse(dist_git.koji_complete("fish-4.0.2-1.fc44"))

    def test_unknown_nvr_is_not_complete(self):
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": None})):
            self.assertFalse(dist_git.koji_complete("fish-0.0.0-1.fc44"))

    def test_sends_getbuild_for_the_requested_nvr(self):
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": {"state": 1}})) as urlopen:
            dist_git.koji_complete("fish-4.0.2-1.fc44")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://koji.fedoraproject.org/kojihub")
        body = json.loads(request.data)
        self.assertEqual(body["method"], "getBuild")
        self.assertEqual(body["params"], ["fish-4.0.2-1.fc44"])
        self.assertEqual(request.get_header("Content-type"), "application/json")

    def test_request_carries_a_timeout(self):
        with mock.patch.object(dist_git.urllib.request, "urlopen",
                               return_value=self.urlopen({"result": {"state": 1}})) as urlopen:
            dist_git.koji_complete("fish-4.0.2-1.fc44")
        self.assertEqual(urlopen.call_args.kwargs.get("timeout"), 30)


class MainTests(unittest.TestCase):
    def run_main(self, argv, *, specs=("fish.spec",), koji=True):
        """Run ``main`` with git, the filesystem probe, and Koji stubbed out."""
        created: dict[str, object] = {}

        def fake_run(command, check=False, **kwargs):
            checkout = Path(command[-1])
            checkout.mkdir(parents=True, exist_ok=True)
            for name in specs:
                (checkout / name).write_text("Name: fish\nVersion: 4.0.2\nRelease: 1%{?dist}\n")
            created["clone"] = list(command)
            return mock.Mock(returncode=0)

        stdout = io.StringIO()
        with mock.patch.object(dist_git.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(dist_git, "command", return_value="c0ffee"), \
                mock.patch.object(dist_git, "koji_complete", return_value=koji) as gate, \
                mock.patch("sys.argv", ["dist_git.py", *argv]), \
                mock.patch("sys.stdout", stdout):
            code = dist_git.main()
        created["gate"] = gate
        payload = stdout.getvalue().strip()
        return code, (json.loads(payload) if payload else None), created

    def test_complete_build_exits_zero_and_reports(self):
        code, report, _ = self.run_main(["fish"])
        self.assertEqual(code, 0)
        self.assertEqual(report["package"], "fish")
        self.assertEqual(report["branch"], "rawhide")
        self.assertEqual(report["commit"], "c0ffee")
        self.assertEqual(report["nvr"], "fish-4.0.2-1")
        self.assertTrue(report["koji_complete"])
        self.assertEqual(report["remote"], "https://src.fedoraproject.org/rpms/fish.git")

    def test_incomplete_build_exits_two(self):
        # Exit 2 is the signal the workflow reads to decline the update branch.
        code, report, _ = self.run_main(["fish"], koji=False)
        self.assertEqual(code, 2)
        self.assertFalse(report["koji_complete"])

    def test_branch_and_remote_template_are_honoured(self):
        code, report, created = self.run_main(
            ["fish", "--branch", "f43", "--remote-template", "https://example.test/{package}.git"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["branch"], "f43")
        self.assertEqual(report["remote"], "https://example.test/fish.git")
        clone = created["clone"]
        self.assertIn("--branch", clone)
        self.assertEqual(clone[clone.index("--branch") + 1], "f43")
        self.assertIn("https://example.test/fish.git", clone)

    def test_ambiguous_spec_set_is_rejected_before_koji(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_main(["fish"], specs=("fish.spec", "fish-extra.spec"))
        self.assertIn("expected exactly one spec file", str(caught.exception))

    def test_missing_spec_is_rejected(self):
        with self.assertRaises(SystemExit) as caught:
            self.run_main(["fish"], specs=())
        self.assertIn("found 0", str(caught.exception))

    def test_checkout_is_removed_after_the_run(self):
        seen: list[Path] = []

        real_nvr_from_spec = dist_git.nvr_from_spec

        def capture(spec: Path) -> str:
            seen.append(spec.parent)
            return real_nvr_from_spec(spec)

        with mock.patch.object(dist_git, "nvr_from_spec", side_effect=capture):
            self.run_main(["fish"])
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())


class CommandTests(unittest.TestCase):
    def test_returns_stripped_stdout(self):
        with mock.patch.object(dist_git.subprocess, "check_output", return_value="c0ffee\n") as check:
            self.assertEqual(dist_git.command("git", "rev-parse", "HEAD", cwd=Path("/tmp")), "c0ffee")
        self.assertEqual(check.call_args.args[0], ("git", "rev-parse", "HEAD"))
        self.assertEqual(check.call_args.kwargs["cwd"], Path("/tmp"))
        self.assertTrue(check.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
