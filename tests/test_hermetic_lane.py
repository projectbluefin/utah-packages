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

    def test_only_the_online_steps_are_retried(self) -> None:
        # Run 36286494799 (#287) lost mdadm and setxkbmap to a dropped
        # connection in mock-hermetic-repo and dmidecode to one in the lock's
        # repoquery. Both online steps go through `online`, which cleans the
        # partial result between attempts; the offline build never does --
        # its only retry is the deliberate %check one.
        script = SCRIPT.read_text()
        self.assertIn('online "lock resolve" clean_lock resolve_lock', script)
        self.assertIn('online "lock fetch" clean_repo fetch_remote', script)
        self.assertIn('clean_lock() { rm -rf "$H/lock"; }', script)
        self.assertIn('clean_repo() { rm -rf "$H/repo"; }', script)
        self.assertNotIn("online build_offline", script)
        self.assertNotIn("online runuser -u mockbuilder -- mock --hermetic-build", script)
        self.assertIn("NET_ATTEMPTS=${HERMETIC_NET_ATTEMPTS:-3}", script)

    def test_online_retries_then_gives_up_with_the_last_status(self) -> None:
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        start = script.index("NET_ATTEMPTS=")
        end = script.index("render_config() {")
        helper = script[start:end].replace("sleep \"$NET_RETRY_PAUSE\"", "true")
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "count"
            reports = Path(directory) / "reports"
            probe = f"""
set -euo pipefail
PACKAGE=probe
REPORT_DIR={reports}
{helper}
cleanups=0
cleanup() {{ cleanups=$((cleanups + 1)); }}
flaky() {{ n=$(cat {counter} 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > {counter}; [ "$n" -ge "$PASS_ON" ]; }}
online probe cleanup flaky
echo "attempts=$(cat {counter}) cleanups=$cleanups"
"""
            passes = subprocess.run(["bash", "-c", probe], env={"PASS_ON": "2", "PATH": "/usr/bin:/bin"},
                                    capture_output=True, text=True)
            self.assertEqual(passes.returncode, 0, passes.stdout + passes.stderr)
            self.assertIn("attempts=2 cleanups=1", passes.stdout)
            self.assertIn("::warning title=probe retry::probe: probe failed (exit 1); attempt 2 of 3", passes.stdout)
            counter.unlink()
            gives_up = subprocess.run(["bash", "-c", probe], env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"},
                                      capture_output=True, text=True)
            self.assertEqual(gives_up.returncode, 1, gives_up.stdout + gives_up.stderr)
            self.assertEqual(counter.read_text().strip(), "3")
            self.assertIn("::error title=probe failed::probe: probe failed 3 times (last exit 1)", gives_up.stdout)
            self.assertFalse((reports / "infra-failure").exists())
            counter.unlink()
            outage = subprocess.run(
                ["bash", "-c", probe.replace("flaky() {", "flaky() { echo 'urllib3 IncompleteRead' >&2;")],
                env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
            self.assertEqual(outage.returncode, 1, outage.stdout + outage.stderr)
            self.assertEqual((reports / "infra-failure").read_text().strip(), "probe")
            counter.unlink()
            (reports / "infra-failure").unlink()
            silent = "flaky() { echo 'ERROR: Command failed: # /usr/bin/dnf5 repoquery -q --location' >&2;"
            dropped = subprocess.run(["bash", "-c", probe.replace("flaky() {", silent)],
                                     env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
            self.assertEqual(dropped.returncode, 1, dropped.stdout + dropped.stderr)
            self.assertEqual((reports / "infra-failure").read_text().strip(), "probe")
            (reports / "infra-failure").unlink()
            counter.unlink()
            unsatisfiable = subprocess.run(
                ["bash", "-c", probe.replace("flaky() {", silent + " echo 'No match for argument: libfoo' >&2;")],
                env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
            self.assertEqual(unsatisfiable.returncode, 1, unsatisfiable.stdout + unsatisfiable.stderr)
            self.assertFalse((reports / "infra-failure").exists())
            counter.unlink()
            capped = subprocess.run(["bash", "-c", probe],
                                    env={"PASS_ON": "9", "HERMETIC_NET_ATTEMPTS": "1", "PATH": "/usr/bin:/bin"},
                                    capture_output=True, text=True)
            self.assertEqual(capped.returncode, 1)
            self.assertEqual(counter.read_text().strip(), "1")

    def test_fetch_retries_use_fedoras_redirector_not_a_mirror_list(self) -> None:
        # The first fetch uses the lock as resolved; retries send Fedora URLs to
        # download.fedoraproject.org, never to a host list of our own, and leave
        # Hummingbird and file:// URLs alone.
        import json
        import re
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        start = script.index("redirect_fedora_urls() {")
        end = script.index("\n}\n", start) + 3
        helper = script[start:end]
        fetch = script[script.index("  fetch_remote() {"):script.index("  clean_repo()")]
        self.assertLess(fetch.index('if [ -e "$H/fetch.attempted" ]'), fetch.index(': > "$H/fetch.attempted"'))
        self.assertIn('rm -f "$H/fetch.attempted"', script[:script.index("  fetch_remote() {")])
        self.assertNotRegex(script, re.compile(r"fcix|servaxnet|mirror\.constant", re.I))

        hummingbird = "https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/Packages/e/example-1.noarch.rpm"
        local = "file:///work/prior/local-stage-1-1.x86_64.rpm"
        fedora = [
            "https://mirror.acm.umn.edu/fedora/fedora/linux/updates/44/Everything/x86_64/Packages/f/f-1.noarch.rpm",
            "http://example.org/pub/fedora/linux/releases/44/Everything/x86_64/os/Packages/g/g-1.noarch.rpm",
        ]
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "remote.json"
            lock.write_text(json.dumps({"buildroot": {"rpms": [{"url": u} for u in [hummingbird, local, *fedora]]}}))
            subprocess.run(["bash", "-c", f"set -euo pipefail\n{helper}\nredirect_fedora_urls {lock}"], check=True)
            urls = [r["url"] for r in json.loads(lock.read_text())["buildroot"]["rpms"]]
        self.assertEqual(urls[:2], [hummingbird, local])
        self.assertEqual(urls[2:], [
            "https://download.fedoraproject.org/pub/fedora/linux/updates/44/Everything/x86_64/Packages/f/f-1.noarch.rpm",
            "https://download.fedoraproject.org/pub/fedora/linux/releases/44/Everything/x86_64/os/Packages/g/g-1.noarch.rpm",
        ])

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
