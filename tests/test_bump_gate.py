#!/usr/bin/env python3
"""The daily bump merges itself only when the packages it bumps build.

tools/bump_gate.py decides; .github/workflows/bump-upstream-gate.yml acts.
A wrong decision is silent in the worst direction -- a broken bump merged and
published to latest -- so every way to fail closed is covered here, along
with the workflow shape that keeps the gate from publishing, from merging a
commit it did not build, and from carrying anything but locks and recipes.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from tools import bump_gate
from tools.bump_gate import (
    already_posted,
    bumped,
    comment,
    disallowed,
    locks_by_name,
    marker,
    verdict,
)

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
SHA = "0123456789abcdef0123456789abcdef01234567"


def on(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


class PathTests(unittest.TestCase):
    def test_only_the_lock_and_recipes_are_allowed(self) -> None:
        self.assertEqual(
            disallowed([
                "config/upstream-sources.json",
                "packages/glib2/glib2.spec",
                "packages/glib2/sources",
            ]),
            [],
        )

    def test_anything_else_is_named(self) -> None:
        self.assertEqual(
            disallowed([
                "packages/glib2/sources",
                ".github/workflows/rebuild-rpms.yml",
                "tools/upstream_bump.py",
                "config/buildroot-image",
            ]),
            [".github/workflows/rebuild-rpms.yml", "config/buildroot-image",
             "tools/upstream_bump.py"],
        )


class BumpedTests(unittest.TestCase):
    base = {"glib2": {"name": "glib2", "version": "2.86.0"},
            "gtk4": {"name": "gtk4", "version": "4.20.0"}}

    def test_a_changed_lock_entry_is_bumped(self) -> None:
        head = {**self.base, "glib2": {"name": "glib2", "version": "2.86.1"}}
        self.assertEqual(bumped(self.base, head, []), ["glib2"])

    def test_a_changed_recipe_directory_is_bumped(self) -> None:
        self.assertEqual(
            bumped(self.base, self.base, ["packages/gtk4/gtk4.spec", "config/upstream-sources.json"]),
            ["gtk4"],
        )

    def test_a_removed_entry_is_named_so_the_plan_can_refuse_it(self) -> None:
        head = {"gtk4": self.base["gtk4"]}
        self.assertEqual(bumped(self.base, head, []), ["glib2"])

    def test_nothing_changed_is_empty(self) -> None:
        self.assertEqual(bumped(self.base, self.base, []), [])

    def test_locks_by_name_tolerates_a_missing_file(self) -> None:
        self.assertEqual(locks_by_name(None), {})


class VerdictTests(unittest.TestCase):
    def test_every_bumped_package_built(self) -> None:
        result = verdict('["glib2","gtk4"]', '["glib2","gtk4"]', "[]", "success")
        self.assertTrue(result.ok, result.reasons)

    def test_a_failed_bumped_package_blocks_and_is_named(self) -> None:
        result = verdict('["glib2","gtk4"]', '["glib2","gtk4"]', '["gtk4"]', "failure")
        self.assertFalse(result.ok)
        self.assertEqual(result.failed, ["gtk4"])
        self.assertTrue(any("`gtk4`" in reason for reason in result.reasons))

    def test_a_failed_run_with_no_named_failure_still_blocks(self) -> None:
        result = verdict('["glib2"]', '["glib2"]', "[]", "failure")
        self.assertFalse(result.ok)

    def test_a_cancelled_or_skipped_build_blocks(self) -> None:
        for outcome in ("cancelled", "skipped", ""):
            with self.subTest(outcome=outcome):
                self.assertFalse(verdict('["glib2"]', '["glib2"]', "[]", outcome).ok)

    def test_missing_outputs_block(self) -> None:
        self.assertFalse(verdict('["glib2"]', "", "[]", "success").ok)
        self.assertFalse(verdict('["glib2"]', '["glib2"]', "", "success").ok)
        self.assertFalse(verdict('["glib2"]', "not json", "[]", "success").ok)

    def test_a_bumped_package_nothing_built_blocks(self) -> None:
        result = verdict('["glib2","gtk4"]', '["glib2"]', "[]", "success")
        self.assertFalse(result.ok)
        self.assertTrue(any("not selected" in reason and "`gtk4`" in reason
                            for reason in result.reasons))

    def test_no_bumped_packages_blocks(self) -> None:
        self.assertFalse(verdict("[]", "[]", "[]", "success").ok)
        self.assertFalse(verdict("", "[]", "[]", "success").ok)

    def test_an_unrelated_failure_blocks_too(self) -> None:
        result = verdict('["glib2"]', '["glib2","pango"]', '["pango"]', "failure")
        self.assertFalse(result.ok)
        self.assertTrue(any("other packages" in reason for reason in result.reasons))


class CommentTests(unittest.TestCase):
    def test_the_comment_names_failures_and_carries_its_marker(self) -> None:
        result = verdict('["gtk4"]', '["gtk4"]', '["gtk4"]', "failure")
        text = comment(result, SHA, "https://example.invalid/run/1")
        self.assertIn("`gtk4`", text)
        self.assertIn("https://example.invalid/run/1", text)
        self.assertIn(marker(SHA, ["gtk4"]), text)

    def test_the_same_verdict_on_the_same_commit_is_posted_once(self) -> None:
        earlier = "first\n" + marker(SHA, ["gtk4", "glib2"]) + "\nsecond"
        self.assertTrue(already_posted(earlier, SHA, ["glib2", "gtk4"]))
        self.assertFalse(already_posted(earlier, SHA, ["gtk4"]))
        self.assertFalse(already_posted(earlier, "f" * 40, ["glib2", "gtk4"]))
        self.assertFalse(already_posted("", SHA, []))


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.tmp)], check=False))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate@example.invalid")
        self.git("config", "user.name", "gate")
        self.write_lock({"glib2": "2.86.0", "gtk4": "4.20.0"})
        (self.tmp / "packages" / "glib2").mkdir(parents=True)
        (self.tmp / "packages" / "glib2" / "glib2.spec").write_text("Version: 2.86.0\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.tmp, check=True,
                              capture_output=True, text=True).stdout

    def write_lock(self, versions: dict[str, str]) -> None:
        (self.tmp / "config").mkdir(exist_ok=True)
        (self.tmp / "config" / "upstream-sources.json").write_text(json.dumps({
            "schema": 1,
            "packages": [{"name": n, "version": v} for n, v in versions.items()],
        }))

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "bump")
        return self.git("rev-parse", "HEAD").strip()

    def plan(self, head: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(bump_gate, "ROOT", self.tmp), \
                redirect_stdout(out), redirect_stderr(err):
            code = bump_gate.main(["plan", "--base", self.base, "--head", head])
        return code, out.getvalue(), err.getvalue()

    def test_plan_names_the_bumped_packages(self) -> None:
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        (self.tmp / "packages" / "glib2" / "glib2.spec").write_text("Version: 2.86.1\n")
        code, out, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"packages": ["glib2"]})

    def test_plan_refuses_a_change_outside_the_lock_and_recipes(self) -> None:
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        (self.tmp / "tools").mkdir()
        (self.tmp / "tools" / "evil.py").write_text("")
        code, out, err = self.plan(self.commit())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("tools/evil.py", err)

    def test_plan_refuses_a_recipe_the_inventory_does_not_know(self) -> None:
        (self.tmp / "packages" / "stray").mkdir()
        (self.tmp / "packages" / "stray" / "stray.spec").write_text("")
        code, _, err = self.plan(self.commit())
        self.assertEqual(code, 1)
        self.assertIn("stray", err)

    def test_plan_refuses_a_diff_with_no_recipe(self) -> None:
        self.assertEqual(self.plan(self.base)[0], 1)

    def test_decide_passes_and_writes_nothing(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = bump_gate.main([
                "decide", "--bumped", '["glib2"]', "--build-list", '["glib2"]',
                "--failed", "[]", "--result", "success", "--sha", SHA,
                "--run-url", "u", "--comment", str(self.tmp / "c.md"),
                "--failed-output", str(self.tmp / "f.json"),
            ])
        self.assertEqual(code, 0)
        self.assertFalse((self.tmp / "c.md").exists())

    def test_decide_fails_and_writes_the_comment_and_failed_list(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = bump_gate.main([
                "decide", "--bumped", '["glib2"]', "--build-list", '["glib2"]',
                "--failed", '["glib2"]', "--result", "failure", "--sha", SHA,
                "--run-url", "u", "--comment", str(self.tmp / "c.md"),
                "--failed-output", str(self.tmp / "f.json"),
            ])
        self.assertEqual(code, 1)
        self.assertIn("::error title=bump gate::", out.getvalue())
        self.assertIn(marker(SHA, ["glib2"]), (self.tmp / "c.md").read_text())
        self.assertEqual(json.loads((self.tmp / "f.json").read_text()), ["glib2"])

    def test_seen_reads_comment_bodies_from_stdin(self) -> None:
        for text, expected in ((marker(SHA, ["glib2"]), 0), ("nothing", 1)):
            with self.subTest(expected=expected), \
                    mock.patch("sys.stdin", io.StringIO(text)):
                self.assertEqual(
                    bump_gate.main(["seen", "--sha", SHA, "--failed", '["glib2"]']), expected
                )


class GateWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = (WORKFLOWS / "bump-upstream-gate.yml").read_text()
        cls.workflow = yaml.safe_load(cls.text)
        cls.jobs = cls.workflow["jobs"]

    def test_dispatch_only_and_only_for_the_daily_branches(self) -> None:
        # The upstream bump and the Rawhide re-import; nothing else, and never
        # a GNOME-next target-cycle branch.
        self.assertEqual(set(on(self.workflow)), {"workflow_dispatch"})
        self.assertEqual(
            self.jobs["plan"]["if"],
            "github.ref == 'refs/heads/bump/upstream-sources' "
            "|| github.ref == 'refs/heads/bump/rawhide-imports'")
        self.assertNotIn("cycle", self.jobs["plan"]["if"])

    def test_a_newer_gate_cancels_an_older_one(self) -> None:
        self.assertTrue(self.workflow["concurrency"]["cancel-in-progress"])
        self.assertIn("github.ref", self.workflow["concurrency"]["group"])

    def test_the_build_is_the_factory_restricted_to_the_bump_and_publishes_nothing(self) -> None:
        build = self.jobs["build"]
        self.assertEqual(build["uses"], "./.github/workflows/rebuild-rpms.yml")
        self.assertIs(build["with"]["skip_publish"], True)
        self.assertEqual(build["with"]["factory_tag"], "latest")
        self.assertNotIn("publish_tag", build["with"])
        self.assertEqual(build["with"]["packages"], "${{ needs.plan.outputs.packages }}")

    def test_the_merge_names_the_commit_that_built(self) -> None:
        steps = self.jobs["merge"]["steps"]
        merge = next(s for s in steps if "gh pr merge" in s.get("run", ""))
        self.assertIn('--match-head-commit "$SHA"', merge["run"])
        self.assertEqual(merge["env"]["SHA"], "${{ github.sha }}")
        names = [s.get("name", "") for s in steps]
        # Judge, then wait for Canary, then merge, then publish -- in that order.
        verdict_at = names.index("Every bumped package built")
        canary_at = names.index("Wait for the Canary check on this commit")
        merge_at = names.index("Merge, only at the commit that built")
        publish_at = names.index("Publish the merged bump to latest")
        self.assertLess(verdict_at, canary_at)
        self.assertLess(canary_at, merge_at)
        self.assertLess(merge_at, publish_at)

    def test_a_failed_verdict_never_reaches_the_merge(self) -> None:
        steps = self.jobs["merge"]["steps"]
        report = next(s for s in steps if s.get("name") == "Say why on the pull request")
        self.assertEqual(report["if"], "steps.verdict.outputs.ok != 'true'")
        self.assertTrue(report["run"].rstrip().endswith("exit 1"))

    def test_latest_is_published_by_dispatching_the_factory_on_main_after_a_merge(self) -> None:
        publish = next(s for s in self.jobs["merge"]["steps"]
                       if s.get("name") == "Publish the merged bump to latest")
        self.assertEqual(publish["if"], "env.merged == 'true'")
        self.assertIn("gh workflow run rebuild-rpms.yml", publish["run"])
        self.assertIn("--ref main", publish["run"])

    def test_the_required_canary_is_dispatched_for_the_pull_request(self) -> None:
        run = "\n".join(s.get("run", "") for s in self.jobs["plan"]["steps"])
        self.assertIn('gh workflow run canary.yml', run)
        self.assertIn('-f pr="$PR"', run)
        canary = yaml.safe_load((WORKFLOWS / "canary.yml").read_text())
        self.assertIn("pr", on(canary)["workflow_dispatch"]["inputs"])


class BumpWorkflowTests(unittest.TestCase):
    def test_only_the_in_cycle_run_dispatches_the_gate(self) -> None:
        workflow = yaml.safe_load((WORKFLOWS / "bump-upstream-sources.yml").read_text())
        job = workflow["jobs"]["bump"]
        self.assertEqual(job["permissions"]["actions"], "write")
        step = next(s for s in job["steps"] if s.get("name") == "Gate the update on its own build")
        self.assertIn("inputs.target-cycle == ''", step["if"])
        self.assertIn("gh workflow run bump-upstream-gate.yml", step["run"])
        self.assertIn("--ref bump/upstream-sources", step["run"])


if __name__ == "__main__":
    unittest.main()
