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


if __name__ == "__main__":
    unittest.main()
