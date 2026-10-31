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
import os
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
    LOCK,
    REVIEW_ONLY,
    already_posted,
    bumped,
    comment,
    disallowed,
    dump_holds,
    holdable,
    holds_only_verdict,
    load_review_only,
    locks_by_name,
    marker,
    parse_holds,
    parse_review_only,
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
                "reports/multimedia-closure.json",
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


class ReviewOnlyFileTests(unittest.TestCase):
    def test_missing_or_empty_is_nothing_guarded(self) -> None:
        self.assertEqual(parse_review_only(None), set())
        self.assertEqual(parse_review_only("# only a comment\n\n"), set())

    def test_names_are_read_with_comments_stripped(self) -> None:
        self.assertEqual(parse_review_only("gdm  # display manager\n ppp\n"), {"gdm", "ppp"})

    def test_the_committed_list_names_only_locked_packages(self) -> None:
        lock = json.loads((bump_gate.ROOT / LOCK).read_text())
        locked = {entry["name"] for entry in lock["packages"]}
        listed = load_review_only(bump_gate.ROOT)
        self.assertTrue(listed, "the committed list guards nothing")
        self.assertEqual(sorted(listed - locked), [])


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

    def guard(self, *names: str) -> None:
        (self.tmp / REVIEW_ONLY).write_text("# root daemons\n" + "".join(f"{n}\n" for n in names))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "guard")
        self.base = self.git("rev-parse", "HEAD").strip()

    def test_plan_refuses_to_move_a_review_only_lock_entry(self) -> None:
        self.guard("gtk4")
        self.write_lock({"glib2": "2.86.0", "gtk4": "4.20.1"})
        code, out, err = self.plan(self.commit())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("gtk4", err)
        self.assertIn(REVIEW_ONLY, err)

    def test_plan_still_gates_other_bumps_beside_a_guarded_package(self) -> None:
        self.guard("gtk4")
        self.write_lock({"glib2": "2.86.1", "gtk4": "4.20.0"})
        code, out, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["packages"], ["glib2"])

    def test_plan_lets_a_guarded_recipe_move_when_its_lock_does_not(self) -> None:
        # A Rawhide recipe re-import touches packages/<name>/ but moves no
        # bytes; the guard is about the upstream payload, not the recipe.
        self.guard("glib2")
        (self.tmp / "packages" / "glib2" / "glib2.spec").write_text("Version: 2.86.0\n# fedora\n")
        code, out, _ = self.plan(self.commit())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["packages"], ["glib2"])

    def test_plan_refuses_a_bump_that_edits_the_review_only_list(self) -> None:
        self.guard("gtk4")
        self.write_lock({"glib2": "2.86.0", "gtk4": "4.20.1"})
        (self.tmp / REVIEW_ONLY).write_text("")
        code, _, err = self.plan(self.commit())
        self.assertEqual(code, 1)
        self.assertIn(REVIEW_ONLY, err)

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

    def test_the_required_canary_is_dispatched_for_the_pull_request(self) -> None:
        run = "\n".join(s.get("run", "") for s in self.jobs["plan"]["steps"])
        self.assertIn('gh workflow run canary.yml', run)
        self.assertIn('-f pr="$PR"', run)
        canary = yaml.safe_load((WORKFLOWS / "canary.yml").read_text())
        self.assertIn("pr", on(canary)["workflow_dispatch"]["inputs"])


class EnqueueBehaviorTests(unittest.TestCase):
    """Run the actual trusted shell and plan tool against real Git history.

    Only GitHub's remote API/CLI responses are fixtures. Candidate tools are
    deliberately never checked out or executed by the credentialed handoff.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.origin = self.root / "origin"
        self.origin.mkdir()
        self.git(self.origin, "init", "-q", "-b", "main")
        self.git(self.origin, "config", "user.email", "gate@example.invalid")
        self.git(self.origin, "config", "user.name", "gate")
        for path, text in {
            "tools/bump_gate.py": (ROOT / "tools/bump_gate.py").read_text(),
            LOCK: json.dumps({"packages": [{"name": "glib2", "version": "1"},
                                           {"name": "guarded", "version": "1"}]}),
            REVIEW_ONLY: "guarded\n",
            HOLDS: '{"holds": {}}\n',
            "packages/glib2/glib2.spec": "Version: 1\n",
        }.items():
            self.put(path, text)
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-qm", "trusted main")
        self.git(self.origin, "checkout", "-qb", "bump/upstream-sources")
        self.put("packages/glib2/glib2.spec", "Version: 2\n")
        self.commit_candidate()
        self.workspace = self.root / "workspace"
        subprocess.run(["git", "clone", "-q", "--branch", "main",
                        str(self.origin), str(self.workspace)], check=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "root = pathlib.Path(os.environ['FIXTURES'])\n"
            "args = sys.argv[1:]\n"
            "with (root / 'calls.jsonl').open('a') as f:\n"
            "    f.write(json.dumps({'args': args, 'token': os.environ.get('GH_TOKEN')}) + '\\n')\n"
            "if args[:2] == ['pr', 'checks']:\n"
            "    sys.exit(int(os.environ.get('CHECKS_EXIT', '0')))\n"
            "if args[:2] == ['pr', 'view']:\n"
            "    print(os.environ['CURRENT_HEAD'])\n"
            "    sys.exit(0)\n"
            "if any(arg.endswith('/dispatches') for arg in args):\n"
            "    (root / 'dispatch.json').write_text(sys.stdin.read())\n"
            "    sys.exit(0)\n"
            "if args[:2] == ['pr', 'list']:\n"
            "    name = 'prs.json'\n"
            "elif any('/jobs?' in arg for arg in args):\n"
            "    name = 'jobs.json'\n"
            "elif args[:2] == ['api', 'graphql']:\n"
            "    if any('enqueuePullRequest' in arg for arg in args):\n"
            "        if os.environ.get('ENQUEUE_EXIT'):\n"
            "            sys.exit(int(os.environ['ENQUEUE_EXIT']))\n"
            "        name = 'enqueue.json'\n"
            "    else:\n"
            "        if os.environ.get('DISCOVERY_EXIT'):\n"
            "            sys.exit(int(os.environ['DISCOVERY_EXIT']))\n"
            "        name = 'landing.json'\n"
            "elif any(arg.endswith('/merge') for arg in args):\n"
            "    name = 'merged.json'\n"
            "elif args[0] == 'api':\n"
            "    name = 'gate.json'\n"
            "else:\n"
            "    sys.exit('unexpected gh command: ' + repr(args))\n"
            "print((root / name).read_text())\n")
        gh.chmod(0o755)
        workflow = yaml.safe_load((WORKFLOWS / "bump-upstream-enqueue.yml").read_text())
        self.validate = workflow["jobs"]["validate"]["steps"][1]["run"]
        self.merge = workflow["jobs"]["enqueue"]["steps"][1]["run"]
        gate_workflow = yaml.safe_load((WORKFLOWS / "bump-upstream-gate.yml").read_text())
        self.handoff = gate_workflow["jobs"]["merge"]["steps"][-1]["run"]
        self.gate = {
            "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
            "path": ".github/workflows/bump-upstream-gate.yml",
            "head_repository": {"full_name": "projectbluefin/utah-packages"},
            "head_branch": "bump/upstream-sources", "head_sha": self.sha, "run_attempt": 2,
        }
        self.jobs = [{"jobs": []}, {"jobs": [{
            "name": "merge", "head_sha": self.sha, "conclusion": "success",
            "steps": [{"name": "Ready to land the commit that built",
                       "conclusion": "success"}],
        }]}]
        self.prs = [{"number": 42, "state": "OPEN", "baseRefName": "main",
                     "headRefName": "bump/upstream-sources", "headRefOid": self.sha,
                     "isCrossRepository": False}]
        self.landing = {"data": {"repository": {
            "mergeQueue": {"id": "MQ_main"},
            "pullRequest": {"id": "PR_42", "state": "OPEN", "baseRefName": "main",
                            "headRefOid": self.sha, "isCrossRepository": False},
        }}}
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}",
                    "GH_TOKEN": "read-only-github-token", "REPOSITORY": "projectbluefin/utah-packages",
                    "RUN_ID": "123", "GITHUB_OUTPUT": str(self.root / "outputs"),
                    "FIXTURES": str(self.root)}

    @staticmethod
    def git(root: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                              text=True).stdout.strip()

    def put(self, path: str, text: str) -> None:
        dest = self.origin / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)

    def commit_candidate(self) -> None:
        self.git(self.origin, "add", ".")
        self.git(self.origin, "commit", "-qm", "candidate")
        self.sha = self.git(self.origin, "rev-parse", "HEAD")

    def refresh_head(self) -> None:
        self.commit_candidate()
        self.gate["head_sha"] = self.sha
        self.jobs[1]["jobs"][0]["head_sha"] = self.sha
        self.prs[0]["headRefOid"] = self.sha

    def run_validation(self) -> subprocess.CompletedProcess:
        for name, data in (("gate.json", self.gate), ("jobs.json", self.jobs), ("prs.json", self.prs)):
            (self.root / name).write_text(json.dumps(data))
        return subprocess.run(["bash", "-c", self.validate], cwd=self.workspace, env=self.env,
                              capture_output=True, text=True)

    def run_landing(self) -> subprocess.CompletedProcess:
        for name, data in (
            ("landing.json", self.landing),
            ("enqueue.json", {"data": {"enqueuePullRequest": {"mergeQueueEntry": {"id": "MQE_42"}}}}),
            ("merged.json", {"merged": True}),
        ):
            (self.root / name).write_text(json.dumps(data))
        return subprocess.run(["bash", "-c", self.merge], cwd=self.workspace,
                              env={**self.env, "PR": "42", "SHA": self.sha,
                                   "GH_TOKEN": "repo-scoped-app-token"},
                              capture_output=True, text=True)

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def assert_rejected(self) -> None:
        result = self.run_validation()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "outputs").exists())

    def test_successful_gate_dispatches_only_its_run_id(self) -> None:
        result = subprocess.run(["bash", "-c", self.handoff], cwd=self.workspace,
                                env={**self.env, "SHA": self.sha, "PR": "42",
                                     "CURRENT_HEAD": self.sha},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "dispatch.json").read_text()),
                         {"event_type": "bump-gate-built", "client_payload": {"run_id": "123"}})

    def test_stale_gate_does_not_dispatch(self) -> None:
        result = subprocess.run(["bash", "-c", self.handoff], cwd=self.workspace,
                                env={**self.env, "SHA": self.sha, "PR": "42",
                                     "CURRENT_HEAD": "f" * 40},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "dispatch.json").exists())

    def test_invalid_run_id_is_rejected_before_api_access(self) -> None:
        self.env["RUN_ID"] = "../other"
        self.assert_rejected()
        self.assertFalse((self.root / "calls.jsonl").exists())

    def test_success_hands_exact_head_to_queue_without_persistent_auto_merge(self) -> None:
        result = self.run_validation()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "outputs").read_text(), f"pr=42\nsha={self.sha}\n")
        result = self.run_landing()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(all(call["token"] == "read-only-github-token" for call in calls[:-2]))
        self.assertTrue(all(call["token"] == "repo-scoped-app-token" for call in calls[-2:]))
        enqueue_args = calls[-1]["args"]
        self.assertEqual(enqueue_args[:2], ["api", "graphql"])
        self.assertIn("pr=PR_42", enqueue_args)
        self.assertIn(f"sha={self.sha}", enqueue_args)
        self.assertIn("expectedHeadOid: $sha", " ".join(enqueue_args))
        self.assertFalse(any("pulls/42/merge" in arg for call in calls for arg in call["args"]))
        self.assertFalse(any("--auto" in call["args"] for call in calls))
        jobs_call = next(call for call in calls if any("/jobs?" in arg for arg in call["args"]))
        self.assertIn("--paginate", jobs_call["args"])
        self.assertIn("--slurp", jobs_call["args"])
        self.assertIn("/attempts/2/jobs?", " ".join(jobs_call["args"]))

    def test_confirmed_no_queue_waits_checks_then_merges_once_at_built_sha(self) -> None:
        self.landing["data"]["repository"]["mergeQueue"] = None
        result = self.run_landing()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls()
        self.assertEqual(calls[-2]["args"],
                         ["pr", "checks", "42", "-R", "projectbluefin/utah-packages",
                          "--required", "--watch"])
        self.assertEqual(calls[-1]["args"],
                         ["api", "--method", "PUT", "repos/projectbluefin/utah-packages/pulls/42/merge",
                          "-f", f"sha={self.sha}", "-f", "merge_method=squash"])
        self.assertFalse(any("--auto" in call["args"] for call in calls))

    def test_queue_discovery_error_never_falls_back_to_direct_merge(self) -> None:
        self.env["DISCOVERY_EXIT"] = "1"
        result = self.run_landing()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 1)

    def test_malformed_or_graphql_error_discovery_never_merges(self) -> None:
        for response in ({"errors": [{"message": "forbidden"}]},
                         {"data": {"repository": None}},
                         {"data": {"repository": {"pullRequest": {}}}},
                         {"data": {"repository": {"mergeQueue": {}, "pullRequest": {}}}}):
            with self.subTest(response=response):
                self.landing = response
                result = self.run_landing()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(all(call["args"][:2] == ["api", "graphql"] for call in self.calls()))

    def test_later_branch_head_cannot_reuse_built_verdict(self) -> None:
        self.landing["data"]["repository"]["pullRequest"]["headRefOid"] = "f" * 40
        result = self.run_landing()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 1)

    def test_failed_required_checks_prevent_non_queue_merge(self) -> None:
        self.landing["data"]["repository"]["mergeQueue"] = None
        self.env["CHECKS_EXIT"] = "1"
        result = self.run_landing()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls()[-1]["args"][:2], ["pr", "checks"])

    def test_queue_head_race_failure_never_falls_back_to_merge(self) -> None:
        self.env["ENQUEUE_EXIT"] = "1"
        result = self.run_landing()
        self.assertNotEqual(result.returncode, 0)
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call["args"][:2] == ["api", "graphql"] for call in calls))
        self.assertIn(f"sha={self.sha}", calls[-1]["args"])

    def test_both_daily_branches_are_supported(self) -> None:
        self.gate["head_branch"] = self.prs[0]["headRefName"] = "bump/rawhide-imports"
        result = self.run_validation()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_moved_pr_is_not_armed(self) -> None:
        self.prs[0]["headRefOid"] = "f" * 40
        self.assert_rejected()

    def test_duplicate_or_foreign_pr_is_not_armed(self) -> None:
        self.prs.append(dict(self.prs[0]))
        self.assert_rejected()
        self.prs = self.prs[:1]
        self.prs[0]["isCrossRepository"] = True
        self.assert_rejected()

    def test_failed_cancelled_or_wrong_source_gate_is_not_armed(self) -> None:
        for key, value in (("conclusion", "failure"), ("conclusion", "cancelled"),
                           ("event", "pull_request"), ("path", ".github/workflows/other.yml"),
                           ("head_branch", "target-cycle"), ("head_sha", "not-a-sha")):
            with self.subTest(key=key, value=value):
                original = self.gate[key]
                self.gate[key] = value
                self.assert_rejected()
                self.gate[key] = original
        self.gate["head_repository"]["full_name"] = "someone/fork"
        self.assert_rejected()

    def test_missing_skipped_failed_or_wrong_head_handoff_is_not_armed(self) -> None:
        job = self.jobs[1]["jobs"][0]
        for key, value in (("conclusion", "skipped"), ("conclusion", "failure"),
                           ("head_sha", "f" * 40), ("steps", []),
                           ("steps", [{"name": "Ready to land the commit that built",
                                       "conclusion": "skipped"}])):
            with self.subTest(key=key, value=value):
                original = job[key]
                job[key] = value
                self.assert_rejected()
                job[key] = original

    def test_changed_branch_tools_are_rejected_without_execution(self) -> None:
        self.put("tools/bump_gate.py", "raise SystemExit('UNTRUSTED TOOL EXECUTED')\n")
        self.refresh_head()
        self.assert_rejected()
        self.assertEqual(self.git(self.workspace, "branch", "--show-current"), "main")
        self.assertNotIn("UNTRUSTED TOOL", (self.workspace / "tools/bump_gate.py").read_text())

    def test_changed_workflow_is_rejected(self) -> None:
        self.put(".github/workflows/bump-upstream-gate.yml", "untrusted workflow\n")
        self.refresh_head()
        self.assert_rejected()

    def test_review_only_lock_change_is_rejected(self) -> None:
        self.put(LOCK, json.dumps({"packages": [{"name": "glib2", "version": "1"},
                                              {"name": "guarded", "version": "2"}]}))
        self.refresh_head()
        self.assert_rejected()

    def test_holds_only_still_enqueues_without_a_build(self) -> None:
        self.git(self.origin, "checkout", "main", "--", "packages/glib2/glib2.spec")
        self.put(HOLDS, '{"holds": {"glib2": {"version": "2", "run": "gate-url"}}}\n')
        self.refresh_head()
        result = self.run_validation()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


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
