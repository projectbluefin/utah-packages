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
    HOLDS,
    already_posted,
    bumped,
    comment,
    disallowed,
    dump_holds,
    holdable,
    holds_only_verdict,
    locks_by_name,
    marker,
    parse_holds,
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
                "config/bump-holds.json",
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


class HoldableTests(unittest.TestCase):
    """Which failures may be held so the rest of the bump merges.

    Run 37129679613 failed 12 of 22 bumped packages and merged none of the
    10 that built. Holding is the way forward, but only for a verdict the gate
    fully accounts for; everything else keeps failing closed for a human.
    """

    def test_the_failed_bumped_packages_are_held(self) -> None:
        self.assertEqual(
            holdable('["fish","glib2","gtk4"]', '["fish","glib2","gtk4"]', '["gtk4","fish"]', "failure"),
            ["fish", "gtk4"],
        )

    def test_every_bumped_package_failing_is_still_held(self) -> None:
        # What is left is the holds file alone; the plan merges that.
        self.assertEqual(holdable('["gtk4"]', '["gtk4"]', '["gtk4"]', "failure"), ["gtk4"])

    def test_nothing_failed_holds_nothing(self) -> None:
        self.assertEqual(holdable('["gtk4"]', '["gtk4"]', "[]", "success"), [])

    def test_a_cancelled_or_skipped_build_holds_nothing(self) -> None:
        for outcome in ("cancelled", "skipped", ""):
            with self.subTest(outcome=outcome):
                self.assertEqual(holdable('["gtk4"]', '["gtk4"]', '["gtk4"]', outcome), [])

    def test_missing_outputs_hold_nothing(self) -> None:
        self.assertEqual(holdable('["gtk4"]', "", '["gtk4"]', "failure"), [])
        self.assertEqual(holdable('["gtk4"]', '["gtk4"]', "", "failure"), [])
        self.assertEqual(holdable("", '["gtk4"]', '["gtk4"]', "failure"), [])

    def test_an_unselected_bumped_package_holds_nothing(self) -> None:
        self.assertEqual(holdable('["glib2","gtk4"]', '["gtk4"]', '["gtk4"]', "failure"), [])

    def test_a_failure_outside_the_bump_holds_nothing(self) -> None:
        self.assertEqual(
            holdable('["glib2","gtk4"]', '["glib2","gtk4","pango"]', '["gtk4","pango"]', "failure"), []
        )


class HoldsFileTests(unittest.TestCase):
    def test_missing_or_empty_is_no_holds(self) -> None:
        self.assertEqual(parse_holds(None), {})
        self.assertEqual(parse_holds(""), {})

    def test_round_trips_sorted(self) -> None:
        holds = {"gtk4": {"version": "4.20.1", "run": "u"}, "fish": {"version": "4.9.3", "run": "u"}}
        text = dump_holds(holds)
        self.assertEqual(parse_holds(text), holds)
        self.assertLess(text.index('"fish"'), text.index('"gtk4"'))

    def test_a_malformed_file_raises_rather_than_releasing_every_hold(self) -> None:
        for text in ('[]', '{"holds": []}', '{"holds": {"fish": {}}}',
                     '{"holds": {"fish": {"version": ""}}}', '{"holds": {"fish": "4.9.3"}}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_holds(text)

    def test_the_committed_holds_file_parses(self) -> None:
        path = ROOT / HOLDS
        if path.is_file():
            parse_holds(path.read_text())


class HoldsOnlyVerdictTests(unittest.TestCase):
    def test_merges_when_nothing_was_bumped_or_built(self) -> None:
        self.assertTrue(holds_only_verdict("[]", "skipped").ok)

    def test_refuses_when_a_package_was_named_or_something_built(self) -> None:
        self.assertFalse(holds_only_verdict('["gtk4"]', "skipped").ok)
        self.assertFalse(holds_only_verdict("[]", "success").ok)
        self.assertFalse(holds_only_verdict("", "skipped").ok)


class CommentTests(unittest.TestCase):
    def test_the_comment_names_failures_and_carries_its_marker(self) -> None:
        result = verdict('["gtk4"]', '["gtk4"]', '["gtk4"]', "failure")
        text = comment(result, SHA, "https://example.invalid/run/1")
        self.assertIn("`gtk4`", text)
        self.assertIn("https://example.invalid/run/1", text)
        self.assertIn(marker(SHA, ["gtk4"]), text)

    def test_a_holding_comment_says_what_is_held_and_how_to_release_it(self) -> None:
        result = verdict('["glib2","gtk4"]', '["glib2","gtk4"]', '["gtk4"]', "failure")
        text = comment(result, SHA, "u", held=["gtk4"])
        self.assertIn("holding `gtk4`", text)
        self.assertIn(HOLDS, text)
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
        self.assertEqual(json.loads(out), {"packages": ["glib2"], "holds_only": False})

    def test_plan_lets_the_holds_file_ride_along(self) -> None:
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        (self.tmp / HOLDS).write_text(dump_holds({"gtk4": {"version": "4.20.1", "run": "u"}}))
        code, out, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["packages"], ["glib2"])

    def test_plan_names_a_holds_only_diff(self) -> None:
        (self.tmp / HOLDS).write_text(dump_holds({"gtk4": {"version": "4.20.1", "run": "u"}}))
        code, out, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"packages": [], "holds_only": True})

    def test_a_holds_only_diff_may_not_change_the_lock_content(self) -> None:
        (self.tmp / HOLDS).write_text(dump_holds({"gtk4": {"version": "4.20.1", "run": "u"}}))
        lock = self.tmp / "config" / "upstream-sources.json"
        document = json.loads(lock.read_text())
        document["schema"] = 2
        lock.write_text(json.dumps(document))
        self.assertEqual(self.plan(self.commit())[0], 1)

    def test_plan_refuses_a_holds_file_it_cannot_read(self) -> None:
        (self.tmp / HOLDS).write_text('{"holds": {"gtk4": {}}}')
        code, out, err = self.plan(self.commit())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("holds file", err)

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

    def decide(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = bump_gate.main([
                "decide", *args, "--sha", SHA, "--run-url", "u",
                "--comment", str(self.tmp / "c.md"),
                "--failed-output", str(self.tmp / "f.json"),
                "--hold-output", str(self.tmp / "h.json"),
            ])
        return code, out.getvalue()

    def test_decide_passes_and_writes_nothing(self) -> None:
        code, _ = self.decide("--bumped", '["glib2"]', "--build-list", '["glib2"]',
                              "--failed", "[]", "--result", "success")
        self.assertEqual(code, 0)
        self.assertFalse((self.tmp / "c.md").exists())
        self.assertFalse((self.tmp / "h.json").exists())

    def test_decide_fails_and_writes_the_comment_and_failed_list(self) -> None:
        code, out = self.decide("--bumped", '["glib2"]', "--build-list", '["glib2"]',
                                "--failed", '["glib2"]', "--result", "failure")
        self.assertEqual(code, 1)
        self.assertIn("::error title=bump gate::", out)
        self.assertIn(marker(SHA, ["glib2"]), (self.tmp / "c.md").read_text())
        self.assertEqual(json.loads((self.tmp / "f.json").read_text()), ["glib2"])
        self.assertEqual(json.loads((self.tmp / "h.json").read_text()), ["glib2"])

    def test_decide_holds_nothing_for_a_verdict_it_cannot_account_for(self) -> None:
        code, _ = self.decide("--bumped", '["glib2"]', "--build-list", '["glib2"]',
                              "--failed", '["glib2"]', "--result", "cancelled")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((self.tmp / "h.json").read_text()), [])

    def test_decide_passes_a_holds_only_change_that_built_nothing(self) -> None:
        code, _ = self.decide("--bumped", "[]", "--holds-only", "--result", "skipped")
        self.assertEqual(code, 0)
        code, _ = self.decide("--bumped", "[]", "--holds-only", "--result", "success")
        self.assertEqual(code, 1)

    def trim(self, head: str, hold: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(bump_gate, "ROOT", self.tmp), \
                redirect_stdout(out), redirect_stderr(err):
            code = bump_gate.main(["trim", "--base", self.base, "--head", head,
                                   "--hold", hold, "--run-url", "https://example.invalid/run/9"])
        return code, out.getvalue(), err.getvalue()

    def test_trim_takes_held_packages_back_to_base_and_records_them(self) -> None:
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.1", "fish": "4.9.3"})
        (self.tmp / "packages" / "glib2" / "glib2.spec").write_text("Version: 2.86.1\n")
        (self.tmp / "packages" / "glib2" / "new.patch").write_text("+\n")
        (self.tmp / "packages" / "gtk4").mkdir()
        (self.tmp / "packages" / "gtk4" / "gtk4.spec").write_text("Version: 4.20.1\n")
        head = self.commit()
        code, out, err = self.trim(head, '["glib2","fish"]')
        self.assertEqual(code, 0, err)
        self.assertIn("held glib2 at 2.86.1", out)
        self.assertEqual(
            {e["name"]: e["version"] for e in json.loads((self.tmp / bump_gate.LOCK).read_text())["packages"]},
            {"glib2": "2.86.0", "gtk4": "4.20.1"},
        )
        # The recipe directory is exactly the base one: changed file restored,
        # added file gone.
        self.assertEqual((self.tmp / "packages" / "glib2" / "glib2.spec").read_text(), "Version: 2.86.0\n")
        self.assertFalse((self.tmp / "packages" / "glib2" / "new.patch").exists())
        self.assertTrue((self.tmp / "packages" / "gtk4" / "gtk4.spec").exists())
        holds = parse_holds((self.tmp / HOLDS).read_text())
        self.assertEqual(holds["glib2"], {"version": "2.86.1", "run": "https://example.invalid/run/9"})
        self.assertEqual(holds["fish"]["version"], "4.9.3")
        # What is left plans as exactly the packages that built, plus holds.
        trimmed = self.commit()
        code, planned, _ = self.plan(trimmed)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(planned)["packages"], ["gtk4"])

    def test_trim_of_every_package_leaves_a_holds_only_change(self) -> None:
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        (self.tmp / "packages" / "glib2" / "glib2.spec").write_text("Version: 2.86.1\n")
        head = self.commit()
        self.assertEqual(self.trim(head, '["glib2"]')[0], 0)
        code, planned, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(planned), {"packages": [], "holds_only": True})

    def test_trim_keeps_existing_holds(self) -> None:
        (self.tmp / HOLDS).write_text(dump_holds({"pango": {"version": "1.60.0", "run": "old"}}))
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        head = self.commit()
        self.assertEqual(self.trim(head, '["glib2"]')[0], 0)
        self.assertEqual(set(parse_holds((self.tmp / HOLDS).read_text())), {"glib2", "pango"})

    def test_trim_refuses_nothing_or_an_unknown_package(self) -> None:
        self.assertEqual(self.trim(self.base, "[]")[0], 1)
        code, _, err = self.trim(self.base, '["stray"]')
        self.assertEqual(code, 1)
        self.assertIn("stray", err)

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
        # Every later step but the hold runs only on success, so the failed
        # step above keeps them from merging.
        report_at = steps.index(report)
        for step in steps[report_at + 1:]:
            if step.get("name") == "Hold the failed packages and gate the rest":
                continue
            self.assertNotIn("failure()", step.get("if", ""), step.get("name"))
            self.assertNotIn("always()", step.get("if", ""), step.get("name"))

    def test_a_partial_failure_holds_and_regates_without_merging(self) -> None:
        steps = self.jobs["merge"]["steps"]
        hold = next(s for s in steps if s.get("name") == "Hold the failed packages and gate the rest")
        self.assertIn("failure()", hold["if"])
        self.assertIn("steps.verdict.outputs.hold != '[]'", hold["if"])
        run = hold["run"]
        self.assertIn("tools/bump_gate.py trim", run)
        # Fast-forward only: never a force push over a branch that moved.
        self.assertIn('git push origin "HEAD:refs/heads/bump/upstream-sources"', run)
        self.assertNotIn("--force", run)
        self.assertNotIn("gh pr merge", run)
        self.assertIn("gh workflow run bump-upstream-gate.yml", run)
        self.assertIn('"$head" != "$SHA"', run)
        self.assertEqual(self.jobs["merge"]["permissions"]["contents"], "write")

    def test_a_holds_only_change_builds_nothing(self) -> None:
        self.assertIn("needs.plan.outputs.holds_only != 'true'", self.jobs["build"]["if"])
        verdict_step = next(s for s in self.jobs["merge"]["steps"]
                            if s.get("name") == "Every bumped package built")
        self.assertIn("--holds-only", verdict_step["run"])

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

    def test_the_bump_commits_the_holds_it_retires(self) -> None:
        workflow = yaml.safe_load((WORKFLOWS / "bump-upstream-sources.yml").read_text())
        cpr = next(s for s in workflow["jobs"]["bump"]["steps"] if s.get("id") == "cpr")
        paths = cpr["with"]["add-paths"].split()
        self.assertIn(HOLDS, paths)
        # config/fedora-primary-sources.txt changes only when a dispatched
        # --package run relocks a source off the Fedora lookaside. The gate
        # deliberately refuses that diff: moving a source's origin is a
        # human merge, never an automatic one.
        self.assertEqual(disallowed(paths), ["config/fedora-primary-sources.txt"])



class ParkedRunTests(unittest.TestCase):
    """Bot-triggered pull_request runs wait in action_required, and their
    pending Canary blocks the merge; the gate approves them on its commit."""

    def test_merge_job_approves_parked_runs_before_waiting_for_canary(self):
        workflow = yaml.safe_load((WORKFLOWS / "bump-upstream-gate.yml").read_text())
        steps = [step.get("name", "") for step in workflow["jobs"]["merge"]["steps"]]
        release = steps.index("Release pull_request runs parked for approval on this commit")
        wait = steps.index("Wait for the Canary check on this commit")
        self.assertLess(release, wait)
        run = workflow["jobs"]["merge"]["steps"][release]["run"]
        self.assertIn("head_sha=$SHA&status=action_required", run)
        self.assertIn('select(.event == "pull_request")', run)
        self.assertEqual(workflow["jobs"]["merge"]["permissions"]["actions"], "write")

class AddPathsExistTests(unittest.TestCase):
    """create-pull-request runs `git add` on every add-paths entry, and a
    missing path is fatal: the first bump after the holds file was introduced
    died on "pathspec 'config/bump-holds.json' did not match any files"."""

    def test_every_bump_add_path_exists_in_the_repository(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("bump-upstream-sources.yml", "detect-rawhide-updates.yml"):
            workflow = yaml.safe_load((WORKFLOWS / name).read_text())
            for job in workflow["jobs"].values():
                for step in job.get("steps", []):
                    paths = (step.get("with") or {}).get("add-paths", "")
                    for path in paths.split():
                        with self.subTest(workflow=name, path=path):
                            self.assertTrue((root / path).exists(), path)

if __name__ == "__main__":
    unittest.main()
