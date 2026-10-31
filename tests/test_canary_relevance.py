#!/usr/bin/env python3
"""Which pull requests the canary has anything to prove about (#369)."""

import json
import subprocess
import unittest
from unittest import mock

from tools import canary

SET = ["libical", "vulkan-headers", "vulkan-loader"]


def f(name, patch="@@ -1 +1 @@\n-x\n+y\n", **extra):
    return {"filename": name, "patch": patch, **extra}


def lock(*names, **top):
    rows = [{"name": n, "version": "1", "url": f"https://example.org/{n}", "sha512": "a" * 8} for n in names]
    return {"packages": rows, **top}


class PipelineRelevantTests(unittest.TestCase):
    def relevant(self, files, base=None, head=None):
        return canary.pipeline_relevant(files, SET, base, head)

    def test_files_the_pipeline_executes_always_count(self):
        for name in ("tools/publish_gate.py", ".github/workflows/canary.yml", ".github/actions/x/action.yml",
                     "Containerfile", "config/hummingbird.repo", "config/runtime-contract.toml",
                     "config/buildroot-lock.json", "config/bump-holds.json"):
            with self.subTest(name=name):
                self.assertTrue(self.relevant([f(name)]))

    def test_recipes_and_docs_never_count(self):
        self.assertFalse(self.relevant([f("packages/foo/foo.spec"), f("docs/x.md"), f("reports/r.json"), f(".packit.yaml")]))
        self.assertFalse(self.relevant([]))

    def test_a_rename_out_of_the_pipeline_still_counts(self):
        self.assertTrue(self.relevant([f("docs/old-tool.py", previous_filename="tools/tool.py")]))

    def test_new_lock_entries_are_inventory_not_pipeline(self):
        base, head = lock("libical", "foo"), lock("libical", "foo", "bar", "baz")
        self.assertFalse(self.relevant([f("config/upstream-sources.json")], base, head))

    def test_an_existing_entry_that_changes_counts(self):
        base = lock("libical", "foo")
        changed = lock("libical", "foo")
        changed["packages"][1]["sha512"] = "b" * 8
        self.assertTrue(self.relevant([f("config/upstream-sources.json")], base, changed))

    def test_a_canary_entry_that_changes_counts(self):
        base = lock("libical", "vulkan-loader")
        changed = lock("libical", "vulkan-loader")
        changed["packages"][0]["url"] = "https://evil.example/libical.tar.gz"
        self.assertTrue(self.relevant([f("config/upstream-sources.json")], base, changed))

    def test_a_removed_entry_counts(self):
        self.assertTrue(self.relevant([f("config/upstream-sources.json")], lock("a", "b"), lock("a")))

    def test_anything_outside_the_package_list_counts(self):
        self.assertTrue(self.relevant([f("config/upstream-sources.json")],
                                      lock("a", schema=1), lock("a", "b", schema=2)))

    def test_an_unreadable_or_ambiguous_lock_counts(self):
        files = [f("config/upstream-sources.json")]
        self.assertTrue(self.relevant(files, None, lock("a")))
        self.assertTrue(self.relevant(files, lock("a"), None))
        self.assertTrue(self.relevant(files, {"packages": "nope"}, lock("a")))
        self.assertTrue(self.relevant(files, lock("a"), {"no": "packages"}))
        duplicated = lock("a", "a")
        self.assertTrue(self.relevant(files, lock("a"), duplicated))

    def test_backlog_and_fedora_list_count_only_when_a_canary_package_changes(self):
        added = "@@ -1,2 +1,3 @@\n  keep\n+{ name = \"gnome-tour\", pr = 551 },\n  keep2\n"
        self.assertFalse(self.relevant([f("config/factory-build-backlog.toml", added)]))
        self.assertFalse(self.relevant([f("config/fedora-primary-sources.txt", "@@ -1 +1,2 @@\n a\n+zinnia\n")]))
        for name in ("libical", "vulkan-headers", "vulkan-loader", "python-typing-inspection"):
            patch = f"@@ -1,2 +1,1 @@\n-{name}\n keep\n"
            with self.subTest(name=name):
                self.assertTrue(self.relevant([f("config/fedora-primary-sources.txt", patch)]) if name in SET
                                else canary.pipeline_relevant(
                                    [f("config/fedora-primary-sources.txt", patch)],
                                    [*SET, *canary.PERTURBED]))

    def test_an_unchanged_line_that_names_a_canary_package_is_only_context(self):
        context = "@@ -1,3 +1,4 @@\n  libical\n+new-package\n  vulkan-loader\n"
        self.assertFalse(self.relevant([f("config/fedora-primary-sources.txt", context)]))

    def test_a_different_package_with_a_similar_name_does_not_count(self):
        patch = "@@ -1 +1,2 @@\n a\n+libical-glib\n+libicalss\n+vulkan-loader-devel\n"
        self.assertFalse(self.relevant([f("config/fedora-primary-sources.txt", patch)]))

    def test_a_diff_github_did_not_return_counts(self):
        # Binary or too large: it cannot be judged, so it is not waved through.
        self.assertTrue(self.relevant([{"filename": "config/factory-build-backlog.toml"}]))

    def test_a_pipeline_change_next_to_inventory_still_counts(self):
        self.assertTrue(self.relevant([f("config/factory-build-backlog.toml"), f("tools/x.py")],
                                      lock("a"), lock("a")))


class PullRequestFetchTests(unittest.TestCase):
    def fake_gh(self, files_pages, base, head, fail_contents=False):
        calls = []

        def gh(args):
            calls.append(list(args))
            url = args[-1]
            if url.endswith("/pulls/7/files"):
                return "\n".join(json.dumps(page) for page in files_pages)
            if url.endswith("/pulls/7"):
                return json.dumps({"head": {"sha": "h" * 40}, "base": {"sha": "b" * 40}})
            if "/compare/" in url:
                return json.dumps({"merge_base_commit": {"sha": "m" * 40}})
            if "/contents/" in url:
                if fail_contents:
                    raise subprocess.CalledProcessError(1, "gh")
                return json.dumps(base if url.endswith("m" * 40) else head)
            raise AssertionError(url)

        return gh, calls

    def test_files_are_read_across_pages_and_new_entries_are_inventory(self):
        pages = [[f("docs/a.md")], [f("config/upstream-sources.json"), f("packages/x/x.spec")]]
        gh, calls = self.fake_gh(pages, lock("libical"), lock("libical", "new"))
        self.assertFalse(canary.pr_relevant("o/r", 7, SET, gh))
        compare = next(c for c in calls if "/compare/" in c[-1])
        self.assertIn("b" * 40 + "..." + "h" * 40, compare[-1])  # merge base, not the moving tip

    def test_the_lock_is_compared_against_the_merge_base_not_the_branch_tip(self):
        pages = [[f("config/upstream-sources.json")]]
        gh, calls = self.fake_gh(pages, lock("a"), lock("a", "b"))
        canary.pr_relevant("o/r", 7, SET, gh)
        refs = [c[-1].rsplit("ref=", 1)[1] for c in calls if "/contents/" in c[-1]]
        self.assertEqual(refs, ["m" * 40, "h" * 40])

    def test_a_lock_that_cannot_be_fetched_counts(self):
        pages = [[f("config/upstream-sources.json")]]
        gh, _ = self.fake_gh(pages, lock("a"), lock("a", "b"), fail_contents=True)
        self.assertTrue(canary.pr_relevant("o/r", 7, SET, gh))

    def test_no_lock_means_no_extra_fetches(self):
        gh, calls = self.fake_gh([[f("docs/a.md")]], None, None)
        self.assertFalse(canary.pr_relevant("o/r", 7, SET, gh))
        self.assertEqual(len(calls), 1)

    def test_the_command_exits_zero_when_the_canary_must_run(self):
        for relevant, code in ((True, 0), (False, 1)):
            with self.subTest(relevant=relevant), \
                    mock.patch.object(canary, "pr_relevant", return_value=relevant) as pr:
                self.assertEqual(canary.main(["pr-relevant", "--repository", "o/r", "--pr", "7",
                                              "--set", json.dumps(SET)]), code)
                pr.assert_called_once_with("o/r", 7, SET)


QUEUE_REF = "refs/heads/gh-readonly-queue/main/pr-7-" + "c" * 40


class QueueRefTests(unittest.TestCase):
    def test_the_pull_request_number_comes_from_the_queue_ref(self):
        self.assertEqual(canary.queue_pr(QUEUE_REF), 7)
        self.assertEqual(canary.queue_pr("gh-readonly-queue/main/pr-801-" + "a" * 40), 801)
        self.assertEqual(canary.queue_pr("gh-readonly-queue/release/1.x/pr-3-" + "a" * 40), 3)

    def test_anything_else_names_no_pull_request(self):
        for ref in ("", "refs/heads/main", "refs/pull/7/merge", "gh-readonly-queue/main/pr-7",
                    "gh-readonly-queue/main/pr-7-abc", "gh-readonly-queue/main/pr-0-" + "a" * 40,
                    "refs/heads/feature/gh-readonly-queue/main/pr-7-" + "a" * 40):
            with self.subTest(ref=ref):
                self.assertIsNone(canary.queue_pr(ref))


class GitRepo:
    """A real repository with refs/pull/<n>/head, and a merge group checkout of it."""

    def __init__(self, root):
        self.origin, self.clone = root / "origin", root / "clone"
        self.origin.mkdir()
        self.run(self.origin, "init", "-q", "-b", "main")
        self.run(self.origin, "config", "user.email", "t@example.org")
        self.run(self.origin, "config", "user.name", "t")

    @staticmethod
    def run(where, *args):
        return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True,
                              check=True).stdout

    def commit(self, files, parent=None):
        if parent:
            self.run(self.origin, "checkout", "-q", "--detach", parent)
        for name, text in files.items():
            path = self.origin / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.run(self.origin, "add", "-A")
        self.run(self.origin, "commit", "-q", "--allow-empty", "-m", "c")
        return self.run(self.origin, "rev-parse", "HEAD").strip()

    def publish_pr(self, number, sha):
        self.run(self.origin, "update-ref", f"refs/pull/{number}/head", sha)

    def checkout_group(self, sha):
        """What actions/checkout leaves on a merge group run: one shallow commit."""
        self.run(self.origin, "update-ref", "refs/heads/gh-readonly-queue/main/pr-7", sha)
        self.clone.mkdir()
        self.run(self.clone, "init", "-q")
        self.run(self.clone, "remote", "add", "origin", self.origin.as_uri())
        self.run(self.clone, "fetch", "-q", "--depth=1", "origin", "refs/heads/gh-readonly-queue/main/pr-7")
        self.run(self.clone, "checkout", "-q", "--detach", sha)

    def git(self, args):
        return self.run(self.clone, *args)

    def origin_git(self, args):
        return self.run(self.origin, *args)


def sources(*names):
    return json.dumps(lock(*names), indent=2) + "\n"


class MergeGroupProofTests(unittest.TestCase):
    """The verdict a merge group gets without building anything."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        directory = tempfile.TemporaryDirectory(prefix="canary-queue-")
        self.addCleanup(directory.cleanup)
        self.repo = GitRepo(Path(directory.name))
        self.main = self.repo.commit({
            "config/upstream-sources.json": sources("libical", "foo"),
            "tools/tool.py": "x = 1\n",
            "docs/a.md": "a\n",
        })

    def prove(self, pr_head, group, relevant=True, api_head=None):
        self.repo.publish_pr(7, pr_head)
        self.repo.checkout_group(group)

        def gh(args):
            self.assertEqual(args, ["api", "repos/o/r/pulls/7"])
            return json.dumps({"head": {"sha": api_head or pr_head}})

        with mock.patch.object(canary, "pr_relevant", return_value=relevant) as judged:
            verdict = canary.merge_group_proof("o/r", QUEUE_REF, group, SET, gh=gh, git=self.repo.git)
        judged.assert_called_once_with("o/r", 7, SET, gh=gh)
        return verdict

    def test_a_pull_request_that_touches_no_pipeline_path_is_proven_without_a_fetch(self):
        def refuse(args):
            raise AssertionError(f"unexpected call {args}")

        with mock.patch.object(canary, "pr_relevant", return_value=False):
            proven, reason = canary.merge_group_proof("o/r", QUEUE_REF, "d" * 40, SET, gh=refuse, git=refuse)
        self.assertTrue(proven)
        self.assertIn("#7 touches no pipeline path", reason)

    def test_a_pipeline_change_is_proven_when_main_moved_only_in_recipes_docs_and_new_locks(self):
        pr_head = self.repo.commit({"tools/tool.py": "x = 2\n"})
        main = self.repo.commit({
            "packages/bar/bar.spec": "Name: bar\n",
            "docs/a.md": "b\n",
            "config/upstream-sources.json": sources("libical", "foo", "bar"),
        }, parent=self.main)
        group = self.repo.commit({"tools/tool.py": "x = 2\n"}, parent=main)
        proven, reason = self.prove(pr_head, group)
        self.assertTrue(proven, reason)

    def test_a_pipeline_change_is_unproven_when_the_pipeline_moved_under_it(self):
        pr_head = self.repo.commit({"tools/tool.py": "x = 2\n"})
        ahead = self.repo.commit({"tools/other.py": "y = 1\n"}, parent=self.main)
        group = self.repo.commit({"tools/tool.py": "x = 2\n"}, parent=ahead)
        proven, reason = self.prove(pr_head, group)
        self.assertFalse(proven)
        self.assertIn("Update the branch", reason)

    def test_an_existing_lock_entry_changed_under_it_is_pipeline_drift(self):
        pr_head = self.repo.commit({"tools/tool.py": "x = 2\n"})
        bumped = lock("libical", "foo")
        bumped["packages"][1]["version"] = "2"
        main = self.repo.commit({"config/upstream-sources.json": json.dumps(bumped)}, parent=self.main)
        group = self.repo.commit({"tools/tool.py": "x = 2\n"}, parent=main)
        self.assertFalse(self.prove(pr_head, group)[0])

    def test_a_head_that_moved_since_the_api_answered_is_unproven(self):
        api_head = self.repo.commit({"tools/tool.py": "x = 2\n"})
        moved = self.repo.commit({"tools/tool.py": "x = 3\n"})
        group = self.repo.commit({"tools/tool.py": "x = 2\n"}, parent=self.main)
        proven, reason = self.prove(moved, group, api_head=api_head)
        self.assertFalse(proven)
        self.assertIn("head moved", reason)

    def test_an_unreadable_queue_ref_or_sha_fails_closed_before_any_call(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("must not be called")

        with mock.patch.object(canary, "pr_relevant", side_effect=refuse):
            self.assertFalse(canary.merge_group_proof("o/r", "refs/heads/main", "d" * 40, SET,
                                                      gh=refuse, git=refuse)[0])
            self.assertFalse(canary.merge_group_proof("o/r", QUEUE_REF, "abc", SET, gh=refuse, git=refuse)[0])

    def test_a_range_is_judged_like_pull_request_files_renames_included(self):
        (self.repo.origin / "docs").mkdir(exist_ok=True)
        (self.repo.origin / "tools" / "tool.py").rename(self.repo.origin / "docs" / "moved.py")
        renamed = self.repo.commit({})
        files = canary.range_files(self.main, renamed, git=self.repo.origin_git)
        self.assertEqual(files, [{"filename": "docs/moved.py", "previous_filename": "tools/tool.py"}])
        self.assertTrue(canary.range_relevant(self.main, renamed, SET, git=self.repo.origin_git))
        docs_only = self.repo.commit({"docs/a.md": "c\n"})
        self.assertFalse(canary.range_relevant(renamed, docs_only, SET, git=self.repo.origin_git))

    def test_the_command_exits_zero_only_on_a_proof(self):
        argv = ["merge-group", "--repository", "o/r", "--head-ref", QUEUE_REF, "--head-sha", "d" * 40,
                "--set", json.dumps(SET)]
        for verdict, code in (((True, "ok"), 0), ((False, "no"), 1)):
            with self.subTest(verdict=verdict), \
                    mock.patch.object(canary, "merge_group_proof", return_value=verdict) as proof, \
                    mock.patch("builtins.print"):
                self.assertEqual(canary.main(argv), code)
                proof.assert_called_once_with("o/r", QUEUE_REF, "d" * 40, SET)


if __name__ == "__main__":
    unittest.main()
