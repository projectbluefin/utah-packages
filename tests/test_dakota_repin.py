"""Tests for tools/dakota_repin.py and refresh-dakota.yml.

The GitHub API is replaced by in-memory fixtures; nothing here touches the
network.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.dakota_repin import (
    DAKOTA_IMAGE,
    PROJECT_REMOTES,
    apply,
    candidate_runs,
    checkout_projects,
    compare_on_branch,
    has_artifacts,
    junction_pin,
    pin_changed,
    proposed_source,
    render_pr_body,
    resolve,
    select_run,
    verify_digest_record,
)

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "refresh-dakota.yml"

OLD_SHA = "bf271777da1808627f775f1d8816db2a89a931ea"
NEW_SHA = "b49af1221cb1c08dbf4821e52f08f0b6e6cf90b6"
NEW_DIGEST = "sha256:" + "4f" * 32

SOURCE = {
    "name": "dakota",
    "url": "https://github.com/projectbluefin/dakota",
    "branch": "testing",
    "revision": OLD_SHA,
    "publish_run": 1,
    "sbom": "projectbluefin/dakota publish.yml run 1, artifact sbom-dakota",
    "image": "ghcr.io/projectbluefin/dakota:testing",
    "image_digest": "sha256:" + "3f" * 32,
    "junctions": {
        "gnome-build-meta.bst": "gnome-51 51.1-36-g8a89846df11e86cee57c728a86a247e61d604b84",
        "freedesktop-sdk.bst": "freedesktop-sdk-26.08.4-0-g114ae909ec9881958bd507c8b4414aa33f758d2b",
    },
}

GBM_JUNCTION = """\
kind: junction
sources:
- kind: git_repo
  url: gnome:gnome-build-meta.git
  track: gnome-51
  ref: 51.1-40-gabcdef0123456789abcdef0123456789abcdef01
- kind: patch_queue
  path: patches/gnome-build-meta
"""
FDSDK_JUNCTION = """\
kind: junction
sources:
- kind: git_repo
  url: gitlab:freedesktop-sdk/freedesktop-sdk.git
  track: freedesktop-sdk-26.08*
  ref: freedesktop-sdk-26.08.5-0-g0123456789abcdef0123456789abcdef01234567
"""


def run(run_id: int, sha: str, created: str, **fields) -> dict:
    values = {"id": run_id, "head_sha": sha, "head_branch": "testing", "status": "completed",
              "conclusion": "success", "event": "workflow_run", "created_at": created,
              "html_url": f"https://github.com/projectbluefin/dakota/actions/runs/{run_id}"}
    values.update(fields)
    return values


def artifacts(*names: str, expired: tuple[str, ...] = ()) -> list[dict]:
    return [{"name": n, "expired": n in expired} for n in names]


BOTH = ("sbom-dakota", "digest-default", "digest-nvidia")


class RunSelectionTest(unittest.TestCase):
    def test_only_successful_testing_runs_newest_first(self) -> None:
        runs = [
            run(1, OLD_SHA, "2026-11-14T03:00:00Z"),
            run(2, NEW_SHA, "2026-11-17T06:00:00Z"),
            run(3, NEW_SHA, "2026-11-18T06:00:00Z", head_branch="gh-readonly-queue/testing/pr-9"),
            run(4, NEW_SHA, "2026-11-18T07:00:00Z", conclusion="failure"),
            run(5, NEW_SHA, "2026-11-18T08:00:00Z", event="pull_request"),
            run(6, NEW_SHA, "2026-11-18T09:00:00Z", status="in_progress", conclusion=None),
        ]
        self.assertEqual([r["id"] for r in candidate_runs(runs)], [2, 1])

    def test_needs_both_artifacts_unexpired(self) -> None:
        self.assertTrue(has_artifacts(artifacts(*BOTH)))
        self.assertFalse(has_artifacts(artifacts("sbom-dakota")))
        self.assertFalse(has_artifacts(artifacts(*BOTH, expired=("sbom-dakota",))))

    def test_skips_runs_without_artifacts_or_off_branch(self) -> None:
        runs = [run(1, OLD_SHA, "2026-11-14"), run(2, NEW_SHA, "2026-11-17"),
                run(3, "c" * 40, "2026-11-18")]
        lists = {1: artifacts(*BOTH), 2: artifacts(*BOTH), 3: artifacts("sbom-dakota")}
        chosen = select_run(runs, lists.__getitem__, lambda sha: True)
        self.assertEqual(chosen["id"], 2)
        # A force-pushed testing that dropped the newest commit falls back.
        chosen = select_run(runs, lists.__getitem__, lambda sha: sha != NEW_SHA)
        self.assertEqual(chosen["id"], 1)
        self.assertIsNone(select_run(runs, lambda _: [], lambda sha: True))

    def test_compare_status(self) -> None:
        self.assertTrue(compare_on_branch({"status": "identical"}))
        self.assertTrue(compare_on_branch({"status": "ahead"}))
        self.assertFalse(compare_on_branch({"status": "diverged"}))
        self.assertFalse(compare_on_branch({"status": "behind"}))


class DigestRecordTest(unittest.TestCase):
    RUN = run(2, NEW_SHA, "2026-11-17")
    RECORD = {"schema": 1, "variant": "default", "image": DAKOTA_IMAGE,
              "sha": NEW_SHA, "digest": NEW_DIGEST}

    def test_accepts_the_runs_default_image(self) -> None:
        self.assertEqual(verify_digest_record(self.RECORD, self.RUN), NEW_DIGEST)

    def test_refuses_another_commit_image_or_variant(self) -> None:
        for field, value in (("sha", OLD_SHA), ("image", DAKOTA_IMAGE + "-nvidia"),
                             ("variant", "nvidia"), ("digest", "sha256:abc"), ("schema", 2)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify_digest_record({**self.RECORD, field: value}, self.RUN)


class JunctionPinTest(unittest.TestCase):
    def test_keeps_the_committed_shape(self) -> None:
        self.assertEqual(junction_pin(GBM_JUNCTION),
                         "gnome-51 51.1-40-gabcdef0123456789abcdef0123456789abcdef01")
        self.assertEqual(junction_pin(FDSDK_JUNCTION),
                         "freedesktop-sdk-26.08.5-0-g0123456789abcdef0123456789abcdef01234567")

    def test_refuses_a_non_junction(self) -> None:
        with self.assertRaises(ValueError):
            junction_pin("kind: meson\nsources: []\n")
        with self.assertRaises(ValueError):
            junction_pin("kind: junction\nsources:\n- kind: local\n  path: x\n")


def fake_github(runs: list[dict], lists: dict[int, list[dict]], record: dict,
                on_branch: set[str]):
    def gh_json(path: str):
        if "/workflows/publish.yml/runs" in path:
            return {"workflow_runs": runs}
        if path.endswith("/artifacts?per_page=100"):
            return {"artifacts": lists[int(path.split("/runs/")[1].split("/")[0])]}
        if "/compare/" in path:
            sha = path.split("/compare/")[1].split("...")[0]
            return {"status": "identical" if sha in on_branch else "diverged"}
        raise AssertionError(path)

    def gh(*args: str) -> str:
        if args[0] == "run":
            Path(args[args.index("-D") + 1], "digest.json").write_text(json.dumps(record))
            return ""
        path = args[-1]
        if "gnome-build-meta.bst" in path:
            return GBM_JUNCTION
        if "freedesktop-sdk.bst" in path:
            return FDSDK_JUNCTION
        raise AssertionError(args)

    return gh_json, gh


class ResolveTest(unittest.TestCase):
    def test_moves_to_the_newest_run(self) -> None:
        record = {"schema": 1, "variant": "default", "image": DAKOTA_IMAGE,
                  "sha": NEW_SHA, "digest": NEW_DIGEST}
        gh_json, gh = fake_github([run(1, OLD_SHA, "2026-11-14"), run(2, NEW_SHA, "2026-11-17")],
                                  {1: artifacts(*BOTH), 2: artifacts(*BOTH)}, record,
                                  {OLD_SHA, NEW_SHA})
        result = resolve(SOURCE, gh_json=gh_json, gh=gh)
        self.assertTrue(result["changed"])
        self.assertEqual(result["run"], 2)
        source = result["source"]
        self.assertEqual(source["revision"], NEW_SHA)
        self.assertEqual(source["image_digest"], NEW_DIGEST)
        self.assertEqual(source["publish_run"], 2)
        self.assertEqual(source["sbom"], "projectbluefin/dakota publish.yml run 2, artifact sbom-dakota")
        self.assertEqual(source["junctions"]["freedesktop-sdk.bst"],
                         "freedesktop-sdk-26.08.5-0-g0123456789abcdef0123456789abcdef01234567")
        # Fields the re-pin does not own are carried over untouched.
        self.assertEqual(source["image"], SOURCE["image"])
        self.assertEqual(list(source), list(SOURCE))

    def test_unchanged_pin(self) -> None:
        record = {"schema": 1, "variant": "default", "image": DAKOTA_IMAGE,
                  "sha": OLD_SHA, "digest": SOURCE["image_digest"]}
        gh_json, gh = fake_github([run(1, OLD_SHA, "2026-11-14")], {1: artifacts(*BOTH)},
                                  record, {OLD_SHA})
        self.assertFalse(resolve(SOURCE, gh_json=gh_json, gh=gh)["changed"])

    def test_no_usable_run_fails(self) -> None:
        gh_json, gh = fake_github([run(1, OLD_SHA, "2026-11-14")], {1: artifacts("sbom-dakota")},
                                  {}, {OLD_SHA})
        with self.assertRaises(SystemExit):
            resolve(SOURCE, gh_json=gh_json, gh=gh)

    def test_pin_changed_on_revision_or_digest(self) -> None:
        self.assertFalse(pin_changed(SOURCE, dict(SOURCE)))
        self.assertTrue(pin_changed(SOURCE, {**SOURCE, "image_digest": NEW_DIGEST}))
        self.assertTrue(pin_changed(SOURCE, {**SOURCE, "revision": NEW_SHA}))


class ApplyTest(unittest.TestCase):
    def test_rewrites_only_the_source(self) -> None:
        pin = json.loads((REPO / "config" / "dakota.json").read_text())
        new = proposed_source(pin["source"], run(2, NEW_SHA, "x"), NEW_DIGEST,
                              {"gnome-build-meta.bst": "g", "freedesktop-sdk.bst": "f"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dakota.json"
            path.write_text(json.dumps(pin, indent=2) + "\n")
            apply(path, new)
            written = json.loads(path.read_text())
        self.assertEqual(written["source"], new)
        self.assertEqual({k: v for k, v in written.items() if k != "source"},
                         {k: v for k, v in pin.items() if k != "source"})
        self.assertEqual(list(written), list(pin))

    def test_refuses_a_malformed_digest(self) -> None:
        pin = json.loads((REPO / "config" / "dakota.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dakota.json"
            path.write_text(json.dumps(pin, indent=2) + "\n")
            with self.assertRaises(ValueError):
                apply(path, {**pin["source"], "image_digest": "latest"})


def report(counts: dict, drift: list[dict], stale: int = 0) -> dict:
    return {"counts": counts, "drift": drift, "stale_mappings": [{}] * stale,
            "import_queue": {"fedora-importable": [{}] * 3, "new-spec": [{}]}}


class PrBodyTest(unittest.TestCase):
    def test_counts_drift_and_contract(self) -> None:
        before = report({"factory": 468, "hummingbird": 237},
                        [{"classification": "aligned"}], stale=94)
        drift = [{"classification": "needs_review", "rpm": f"pkg{i}", "factory_version": "1",
                  "dakota_version": "2", "element": f"e{i}.bst"} for i in range(45)]
        after = report({"factory": 469, "hummingbird": 237}, drift)
        repin = {"source": {**SOURCE, "revision": NEW_SHA, "publish_run": 2,
                            "image_digest": NEW_DIGEST}}
        body = render_pr_body(before, after, SOURCE, repin, [])
        self.assertIn("| factory | 468 | 469 | +1 |", body)
        self.assertIn("Stale mappings: 94 -> 0.", body)
        self.assertIn("| needs_review | 0 | 45 |", body)
        self.assertIn("5 more in the report", body)
        self.assertIn(f"/compare/{OLD_SHA}...{NEW_SHA}", body)
        self.assertIn("every reviewer decision names one of them", body)
        self.assertNotIn("## Patches and build options", body)

        after["build_intent"] = [{"classification": "needs_review"}, {"classification": "aligned"}]
        body = render_pr_body(before, after, SOURCE, repin, [])
        self.assertIn("## Patches and build options of factory recipes", body)
        self.assertIn("| needs_review | 0 | 1 |", body)

        failing = render_pr_body(before, after, SOURCE, repin,
                                 ["overrides x.bst: not an element of the snapshot"])
        self.assertIn("`just dakota-audit` fails on this pin", failing)
        self.assertIn("- overrides x.bst: not an element of the snapshot", failing)


class CheckoutTest(unittest.TestCase):
    def test_fetches_each_project_at_its_pinned_commit(self) -> None:
        extra = "7825d44d436a51dcbf7d226904348e810c63bf75"
        calls = []

        def git(*args: str) -> None:
            calls.append(args)
            if args[2] == "checkout" and args[1].endswith("gnome-build-meta"):
                write_to = Path(args[1], "elements", "freedesktop-sdk-extra.bst")
                write_to.parent.mkdir(parents=True)
                write_to.write_text(
                    "kind: junction\nsources:\n- kind: git_repo\n  url: gitlab:x.git\n"
                    f"  ref: freedesktop-sdk-extra-26.08.3-0-g{extra}\n")

        with tempfile.TemporaryDirectory() as tmp:
            dirs = checkout_projects(SOURCE, Path(tmp), git)
        fetched = {Path(c[1]).name: (c[6], c[7]) for c in calls if c[2] == "fetch"}
        self.assertEqual(fetched, {
            "dakota": (PROJECT_REMOTES["dakota"], OLD_SHA),
            "gnome-build-meta": (PROJECT_REMOTES["gnome-build-meta"],
                                 "8a89846df11e86cee57c728a86a247e61d604b84"),
            "freedesktop-sdk": (PROJECT_REMOTES["freedesktop-sdk"],
                                "114ae909ec9881958bd507c8b4414aa33f758d2b"),
            "freedesktop-sdk-extra": (PROJECT_REMOTES["freedesktop-sdk-extra"], extra),
        })
        self.assertEqual(sorted(dirs), sorted(PROJECT_REMOTES))

    def test_refuses_a_junction_without_a_commit(self) -> None:
        source = {**SOURCE, "junctions": {**SOURCE["junctions"], "freedesktop-sdk.bst": "main"}}
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            checkout_projects(source, Path(tmp), lambda *args: None)


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text()
        self.workflow = yaml.safe_load(self.text)
        self.steps = self.workflow["jobs"]["repin"]["steps"]

    def test_never_merges(self) -> None:
        for forbidden in ("gh pr merge", "--auto", "enable-pull-request-automerge",
                          "--admin", "auto-merge"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.text.replace("never arms auto-merge", ""))

    def test_pull_request_carries_only_the_pin(self) -> None:
        open_pr = self.workflow["jobs"]["open-pr"]["steps"]
        pr = next(s for s in open_pr if "create-pull-request" in s.get("uses", ""))
        self.assertEqual(pr["with"]["add-paths"].split(),
                         ["config/dakota.json", "config/dakota-elements.tsv",
                          "config/dakota-build-facts.json"])
        self.assertEqual(pr["with"]["branch"], "chore/dakota-repin")

    def test_unchanged_pin_does_nothing(self) -> None:
        resolve_index = next(i for i, s in enumerate(self.steps) if s.get("id") == "resolve")
        for step in self.steps[resolve_index + 1:]:
            with self.subTest(step=step.get("name")):
                self.assertEqual(step.get("if"), "steps.resolve.outputs.changed == 'true'")

    def test_import_keeps_its_checks(self) -> None:
        # The new source is written before the import, so --import-sbom compares
        # the SBOM and the layout with the revision and digest Dakota recorded.
        script = "\n".join(s.get("run", "") for s in self.steps)
        self.assertLess(script.index("dakota_repin.py apply"), script.index("--import-sbom"))
        self.assertIn("--image-layout work/dakota-oci --refresh", script)
        # The build facts are rebuilt from checkouts at the new pin, after it is written.
        self.assertLess(script.index("dakota_repin.py apply"),
                        script.index("dakota_repin.py checkout"))
        self.assertIn("--import-build-facts", script)
        self.assertIn("--preserve-digests", script)
        self.assertIn('ghcr.io/projectbluefin/dakota@${DIGEST}', script)

    def test_only_trusted_main(self) -> None:
        self.assertIn("github.ref == 'refs/heads/main'", self.workflow["jobs"]["repin"]["if"])

    def test_the_job_that_fetches_third_party_content_holds_no_secret(self) -> None:
        # repin `git apply`s Dakota's patches from GitLab/GitHub checkouts; a
        # write token must not exist in that job (#1212 review).
        repin = yaml.safe_dump(self.workflow["jobs"]["repin"])
        self.assertNotIn("secrets.", repin)
        self.assertNotIn("create-github-app-token", repin)
        self.assertEqual(self.workflow["jobs"]["repin"]["permissions"],
                         {"contents": "read", "actions": "read"})
        open_pr = self.workflow["jobs"]["open-pr"]
        self.assertEqual(open_pr["needs"], "repin")
        script = "\n".join(s.get("run", "") for s in open_pr["steps"])
        self.assertNotIn("dakota_repin.py", script)
        self.assertNotIn("audit_dakota.py", script)


if __name__ == "__main__":
    unittest.main()
