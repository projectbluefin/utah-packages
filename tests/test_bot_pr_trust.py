"""A dispatch must judge exactly the current allowed bot PR commit."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.bot_pr_trust import verify

REPO = Path(__file__).resolve().parent.parent
REPOSITORY = "projectbluefin/utah-packages"


class BotPrTrustTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.pr = {"state": "OPEN", "baseRefName": "main", "headRefName": "import/rawhide-demo",
                   "headRefOid": self.sha, "headRepository": {"nameWithOwner": "projectbluefin/utah-packages"},
                   "author": {"login": "app/github-actions"}}

    def check(self, pr=None, sha=None, branch=None):
        verify(pr or self.pr, "projectbluefin/utah-packages", sha or self.sha,
               branch or self.pr["headRefName"])

    def test_accepts_current_import_and_buildroot_heads(self):
        self.check()
        self.pr["headRefName"] = "chore/buildroot-mirror"
        self.check()

    def test_accepts_import_package_with_plus(self):
        self.pr["headRefName"] = "import/rawhide-libsigc++30"
        self.check()

    def test_rejects_foreign_closed_human_or_wrong_base_pull_requests(self):
        for key, value in (("state", "CLOSED"), ("baseRefName", "testing"),
                           ("headRepository", {"nameWithOwner": "someone/utah-packages"}),
                           ("author", {"login": "someone"})):
            with self.subTest(key=key):
                pr = copy.deepcopy(self.pr)
                pr[key] = value
                with self.assertRaises(ValueError):
                    self.check(pr)

    def test_rejects_moved_head_and_wrong_dispatch_branch(self):
        with self.assertRaises(ValueError):
            self.check(sha="b" * 40)
        with self.assertRaises(ValueError):
            self.check(branch="main")
        with self.assertRaises(ValueError):
            self.check(branch="import/rawhide-other")


class BotPrTrustCliTests(unittest.TestCase):
    """bot-pr-validate.yml gates on this command's exit status alone."""

    def setUp(self):
        self.sha = "a" * 40
        self.branch = "import/rawhide-demo"
        self.pr = {"state": "OPEN", "baseRefName": "main", "headRefName": self.branch,
                   "headRefOid": self.sha, "headRepository": {"nameWithOwner": REPOSITORY},
                   "author": {"login": "app/github-actions"}}
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.metadata = Path(scratch.name) / "pr.json"

    def run_cli(self, metadata_text=None, sha=None, branch=None):
        self.metadata.write_text(json.dumps(self.pr) if metadata_text is None else metadata_text)
        return subprocess.run(
            [sys.executable, "-m", "tools.bot_pr_trust", str(self.metadata), REPOSITORY,
             sha or self.sha, branch or self.branch],
            cwd=REPO, capture_output=True, text=True, check=False,
        )

    def test_current_bot_head_exits_zero(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_untrusted_dispatch_exits_nonzero_with_reason(self):
        cases = {
            "moved head": dict(sha="b" * 40),
            "branch outside the bot allow-list": dict(branch="main"),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                result = self.run_cli(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ValueError", result.stderr)

    def test_human_or_fork_pull_request_exits_nonzero(self):
        for key, value in (("author", {"login": "someone"}),
                           ("headRepository", {"nameWithOwner": "someone/utah-packages"}),
                           ("state", "MERGED")):
            with self.subTest(key=key):
                result = self.run_cli(metadata_text=json.dumps({**self.pr, key: value}))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("is not the open same-repository bot PR", result.stderr)

    def test_incomplete_or_unreadable_metadata_exits_nonzero(self):
        for label, text in (("null head repository", json.dumps({**self.pr, "headRepository": None})),
                            ("empty object", "{}"),
                            ("truncated JSON", '{"state": "OPEN"')):
            with self.subTest(label):
                self.assertNotEqual(self.run_cli(metadata_text=text).returncode, 0)

    def test_missing_arguments_exit_nonzero(self):
        result = subprocess.run([sys.executable, "-m", "tools.bot_pr_trust", str(self.metadata)],
                                cwd=REPO, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
