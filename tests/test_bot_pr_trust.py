"""A dispatch must judge exactly the current allowed bot PR commit."""
import copy
import unittest
from tools.bot_pr_trust import verify


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
