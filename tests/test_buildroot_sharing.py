#!/usr/bin/env python3
"""The build root is pulled once per run and shared, never pulled per job.

quay.io/fedora/fedora:44 is republished several times a day and each previous
digest is garbage-collected. Three digests died in five days, the last inside
four hours, and Fedora publishes no immutable tag to pin instead. Pinning a
digest and pulling it in every job is therefore a race the factory loses:

  run 34801488576  every job, exit 125, pin written 09-12 and dead by 09-17
  run 35186196830  stages 0-3 pulled at 06:01, stages 4-10 exit 125 at 07:13,
                   from a pin that was correct when the run started

So prepare pulls the tag once, records what it resolved to, and shares the
bytes. These tests hold that shape: nothing may reintroduce a per-job pull, and
a job that runs the image must load it first.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
LOAD_ACTION = ROOT / ".github" / "actions" / "load-buildroot" / "action.yml"
REBUILD = WORKFLOWS / "rebuild-rpms.yml"
BUILD_STAGE = WORKFLOWS / "build-stage.yml"

LOCAL_IMAGE = "utah-buildroot:run"


def jobs(path: Path) -> dict[str, str]:
    """Crude but sufficient split of a workflow into its job bodies.

    Deliberately textual rather than a YAML walk: what these tests assert is
    about the text a maintainer edits, and a job body is unambiguous at this
    indentation.
    """
    text = path.read_text()
    starts = [(m.start(), m.group(1)) for m in re.finditer(r"(?m)^  ([a-z0-9_-]+):$", text)]
    found = {}
    for index, (offset, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        found[name] = text[offset:end]
    return found


class BuildRootSharingTests(unittest.TestCase):
    def test_every_job_that_runs_the_build_root_loads_it_first(self) -> None:
        offenders = []
        for path in (REBUILD, BUILD_STAGE):
            for name, body in jobs(path).items():
                # A job that RUNS the image, not one that merely names it:
                # prepare builds and tags it, and has nothing to load.
                if f"{LOCAL_IMAGE} bash -exc" not in body:
                    continue
                if "./.github/actions/load-buildroot" not in body:
                    offenders.append(f"{path.name}:{name}")
        self.assertEqual(
            offenders,
            [],
            "these jobs run the shared build root without loading it, so the "
            "image will be absent and docker will fail on an unqualified name",
        )

    def test_no_job_pulls_the_build_root_from_a_registry(self) -> None:
        # The whole point. A digest here is dead within hours, and a per-job
        # pull is what put thirty-seven jobs on exit 125 mid-run.
        pulls = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"quay\.io/fedora/fedora\S*\s+bash", stripped):
                    pulls.append(f"{path.name}: {stripped[:70]}")
        self.assertEqual(pulls, [], "run the shared utah-buildroot:run instead")

    def test_the_image_is_named_without_a_registry(self) -> None:
        # An unqualified name cannot be silently fetched: docker refuses it
        # rather than substituting a fresh pull for the bytes prepare shared,
        # which is what makes a failed load loud instead of invisible.
        self.assertNotIn("/", LOCAL_IMAGE.split(":")[0])
        self.assertIn(LOCAL_IMAGE, BUILD_STAGE.read_text())

    def test_prepare_pulls_by_tag_and_records_the_digest(self) -> None:
        prepare = jobs(REBUILD)["prepare"]
        # By tag, because a recorded digest may already be collected.
        self.assertIn('docker pull "$tag"', prepare)
        # And the digest it actually got is recorded as a job output, so the
        # run says which bytes it used even though the tag is mutable.
        self.assertIn('digest=$actual', prepare)
        self.assertIn("buildroot_digest", REBUILD.read_text())

    def test_a_moved_build_root_warns_and_does_not_fail_the_run(self) -> None:
        # Failing here would recreate the outage this design exists to remove:
        # the recorded digest is expected to go stale, by design.
        prepare = jobs(REBUILD)["prepare"]
        self.assertIn("::warning title=build root moved::", prepare)
        self.assertNotIn("exit 1", prepare.split("docker pull")[1].split("digest=")[0])

    def test_the_shared_image_is_uploaded_and_downloaded_under_one_name(self) -> None:
        self.assertIn("name: buildroot-image", jobs(REBUILD)["prepare"])
        self.assertIn("name: buildroot-image", LOAD_ACTION.read_text())

    def test_the_load_action_asserts_the_image_arrived(self) -> None:
        # Without this, a failed download surfaces as a confusing docker error
        # inside the build step instead of a clear one here.
        self.assertIn("docker image inspect utah-buildroot:run", LOAD_ACTION.read_text())

    def test_a_mirror_pin_is_pulled_by_its_exact_digest(self) -> None:
        # The factory mirror is never pruned, so its digest is the pull
        # target; only the legacy quay.io form pulls a moving tag.
        prepare = jobs(REBUILD)["prepare"]
        self.assertIn("ghcr.io/projectbluefin/utah-buildroot:*@sha256:*)", prepare)
        self.assertIn('docker pull "${tag%:*}@${expected}"', prepare)


class BuildRootPinTests(unittest.TestCase):
    PIN = "ghcr.io/projectbluefin/utah-buildroot:44-20260925-94e175d9796d@sha256:" + "a" * 64

    def test_the_workflow_has_exactly_one_readable_pin(self) -> None:
        from tools import buildroot_pin

        self.assertTrue(buildroot_pin.get(REBUILD.read_text()))

    def test_set_moves_only_the_pin(self) -> None:
        from tools import buildroot_pin

        text = REBUILD.read_text()
        moved = buildroot_pin.set_pin(text, self.PIN)
        self.assertEqual(buildroot_pin.get(moved), self.PIN)
        self.assertEqual(
            [line for line in moved.splitlines() if "BUILDROOT_IMAGE:" not in line],
            [line for line in text.splitlines() if "BUILDROOT_IMAGE:" not in line],
        )

    def test_set_refuses_anything_but_a_mirror_digest_pin(self) -> None:
        from tools import buildroot_pin

        text = REBUILD.read_text()
        for bad in (
            "quay.io/fedora/fedora:44@sha256:" + "a" * 64,  # prunable upstream
            "ghcr.io/projectbluefin/utah-buildroot:44",  # no digest
            "ghcr.io/projectbluefin/utah-buildroot@sha256:" + "a" * 64,  # no tag
        ):
            with self.assertRaises(ValueError):
                buildroot_pin.set_pin(text, bad)

    def test_the_refresh_workflow_writes_the_pin_through_the_tool(self) -> None:
        refresh = (WORKFLOWS / "refresh-buildroot.yml").read_text()
        self.assertIn("python3 tools/buildroot_pin.py set", refresh)
        self.assertIn("ghcr.io/projectbluefin/utah-buildroot", refresh)
        self.assertIn("schedule:", refresh)


if __name__ == "__main__":
    unittest.main()
