#!/usr/bin/env python3
"""The hermetic lane: lock the root from BuildRequires, build offline from it.

Hummingbird's mechanism (ci/build_rpms.sh --hermetic): mock resolves the
root and writes buildroot_lock.json, the lock is materialized into a local
repository, and the build runs with no network. These tests hold the order
of those steps in build-stage.yml and the properties the script relies on.
"""

from pathlib import Path
import unittest

import yaml

from tools.mock_config import render

ROOT = Path(__file__).resolve().parent.parent
BUILD_STAGE = ROOT / ".github" / "workflows" / "build-stage.yml"
SCRIPT = ROOT / "tools" / "hermetic_build.sh"


def steps() -> list[dict]:
    workflow = yaml.safe_load(BUILD_STAGE.read_text())
    return workflow["jobs"]["build"]["steps"]


def index(name: str) -> int:
    return next(i for i, step in enumerate(steps()) if step.get("name") == name)


class LaneChoiceTests(unittest.TestCase):
    """hermetic is the default; build_lane container is the declared exception."""

    def test_hermetic_is_the_default_everywhere(self) -> None:
        stage = yaml.safe_load(BUILD_STAGE.read_text())
        inputs = stage.get("on", stage.get(True))["workflow_call"]["inputs"]
        self.assertEqual(inputs["backend"]["default"], "hermetic")
        rebuild = (ROOT / ".github" / "workflows" / "rebuild-rpms.yml").read_text()
        self.assertEqual(rebuild.count("backend: ${{ inputs.backend || 'hermetic' }}"), 14)
        self.assertNotIn("inputs.backend || 'container'", rebuild)
        workflow = yaml.safe_load(rebuild)
        triggers = workflow.get("on", workflow.get(True))
        self.assertEqual(triggers["workflow_dispatch"]["inputs"]["backend"]["default"], "hermetic")

    def test_every_step_follows_the_chosen_lane(self) -> None:
        for step in steps():
            condition = str(step.get("if", ""))
            self.assertNotIn("inputs.backend", condition, step.get("name"))
        lane = steps()[index("Choose the build lane")]
        self.assertIn('if [ "$BACKEND" = hermetic ] && [ -n "$EXCEPTION" ]; then', lane["run"])

    def test_an_exception_needs_a_reason(self) -> None:
        import json
        import tempfile

        from tools.package_inventory import load_source_locks

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "upstream-sources.json"
            config.write_text(json.dumps({"packages": [{"name": "libratbag", "build_lane": "container"}]}))
            with self.assertRaises(ValueError):
                load_source_locks(config)
            config.write_text(json.dumps({"packages": [
                {"name": "libratbag", "build_lane": "container",
                 "build_lane_reason": "%check needs a system bus"}]}))
            self.assertIn("libratbag", load_source_locks(config))
            config.write_text(json.dumps({"packages": [
                {"name": "x", "build_lane": "hermetic", "build_lane_reason": "r"}]}))
            with self.assertRaises(ValueError):
                load_source_locks(config)


class HermeticLaneTests(unittest.TestCase):
    LOCK = "Lock the build root from its BuildRequires (hermetic)"
    KEY = "Key the package cache from the lock (hermetic)"
    RESTORE = "Restore package RPM cache"
    BUILD = "Build offline from the lock (hermetic)"
    UPLOAD = "Upload the build-root lock (hermetic)"

    def test_lock_then_key_then_restore_then_offline_build(self) -> None:
        self.assertLess(index(self.LOCK), index(self.KEY))
        self.assertLess(index(self.KEY), index(self.RESTORE))
        self.assertLess(index(self.RESTORE), index(self.BUILD))
        self.assertIn("hermetic_build.sh lock", steps()[index(self.LOCK)]["run"])
        self.assertIn("hermetic_build.sh build", steps()[index(self.BUILD)]["run"])
        self.assertEqual(
            steps()[index(self.BUILD)]["if"],
            "steps.lane.outputs.backend == 'hermetic' && steps.package_cache_restore.outputs.hit != 'true'",
        )

    def test_the_offline_build_runs_before_its_result_is_cached(self) -> None:
        # The first canary run published the cache before the hermetic build
        # step had produced anything, and failed on an empty work/result.
        self.assertLess(index(self.BUILD), index("Publish package RPM cache"))
        self.assertLess(index("Build the verified source with its RPM recipe"),
                        index("Publish package RPM cache"))

    def test_the_workspace_is_handed_back_after_each_container(self) -> None:
        # A cache hit writes work/result from the host; the container had
        # given it to its mockbuilder user.
        for name in (self.LOCK, self.BUILD):
            self.assertIn('sudo chown -R "$(id -u):$(id -g)" work', steps()[index(name)]["run"])

    def test_mock_runs_as_an_unprivileged_user(self) -> None:
        script = SCRIPT.read_text()
        self.assertIn("runuser -u mockbuilder -- mock -r", script)
        self.assertIn("offline runuser -u mockbuilder -- mock --hermetic-build", script)

    def test_the_cache_key_comes_from_the_lock_in_its_own_namespace(self) -> None:
        run = steps()[index(self.KEY)]["run"]
        self.assertIn("--resolved-root work/cache/root", run)
        self.assertIn('--salt "hermetic${CACHE_SALT:+-$CACHE_SALT}"', run)
        restore = steps()[index(self.RESTORE)]
        self.assertIn("steps.package_cache_lock.outputs.key", restore["env"]["KEY"])

    def test_only_the_container_lane_runs_the_hand_built_root(self) -> None:
        container = steps()[index("Build the verified source with its RPM recipe")]
        self.assertTrue(container["if"].startswith("steps.lane.outputs.backend == 'container'"))

    def test_the_lock_is_kept_as_an_artifact(self) -> None:
        upload = steps()[index(self.UPLOAD)]
        self.assertIn("buildroot_lock.json", upload["with"]["path"])
        self.assertIn("mock.cfg.sha256", upload["with"]["path"])
        self.assertIn("always()", upload["if"])

    def test_the_bootstrap_image_is_the_pinned_build_root(self) -> None:
        run = steps()[index(self.LOCK)]["run"]
        self.assertIn("config/buildroot-image", run)

    def test_the_build_has_no_network(self) -> None:
        script = SCRIPT.read_text()
        self.assertIn("unshare --net -- bash -c 'ip link set lo up && exec \"$@\"'", script)
        self.assertIn("offline runuser -u mockbuilder -- mock --hermetic-build", script)
        # Materializing the lock is the last thing allowed to reach out.
        self.assertLess(script.index("  materialize\n"), script.index("build_offline 1"))

    def test_local_stage_rpms_are_materialized_by_copy(self) -> None:
        # mock-hermetic-repo cannot read file:// URLs; earlier stages and the
        # published factory are file:// repositories.
        script = SCRIPT.read_text()
        self.assertIn('startswith("file://")', script)
        self.assertIn("mock-hermetic-repo --lockfile", script)

    def test_mock_config_carries_a_ready_bootstrap_image_only_when_asked(self) -> None:
        plain = render()
        self.assertNotIn("bootstrap_image", plain)
        hermetic = render(bootstrap_image="ghcr.io/projectbluefin/utah-buildroot:44@sha256:" + "a" * 64,
                          hummingbird_extra_excludes=("libicu-77.*-*hum1",))
        self.assertIn("config_opts['use_bootstrap_image'] = True", hermetic)
        self.assertIn("config_opts['bootstrap_image_ready'] = True", hermetic)
        self.assertIn("excludepkgs=ruby3.3-default-gems,ruby3.4-default-gems,libicu-77.*-*hum1", hermetic)


if __name__ == "__main__":
    unittest.main()
