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
        import re

        script = SCRIPT.read_text()
        # The online retry wrapper must never enclose the offline build.
        self.assertEqual(re.findall(r"^ *online .+$", script, re.M), [
            '  online "lock resolve" clean_lock resolve_lock',
            '  online "lock fetch" true fetch_remote',
        ])

    def test_online_retries_then_gives_up_with_the_last_status(self) -> None:
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        start = script.index("NET_ATTEMPTS=")
        end = script.index("render_config() {")
        helper = script[start:end]
        self.assertIn('sleep "$delay"', helper)
        helper = helper.replace('sleep "$delay"', "true")
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
            self.assertIn("::warning title=probe retry::probe: probe failed (exit 1); attempt 2 of 4 in 5s", passes.stdout)
            counter.unlink()
            gives_up = subprocess.run(["bash", "-c", probe], env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"},
                                      capture_output=True, text=True)
            self.assertEqual(gives_up.returncode, 1, gives_up.stdout + gives_up.stderr)
            self.assertEqual(counter.read_text().strip(), "4")
            self.assertIn("::error title=probe failed::probe: probe failed 4 times (last exit 1)", gives_up.stdout)
            self.assertFalse((reports / "infra-failure").exists())
            counter.unlink()
            early_outage = (
                f"flaky() {{ if [ ! -f {counter} ]; then echo 'urllib3 MaxRetryError' >&2; "
                "else echo 'createrepo_c: not an RPM file (bad lead)' >&2; fi;"
            )
            outage = subprocess.run(
                ["bash", "-c", probe.replace("flaky() {", early_outage)],
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
            recovered = (
                f"flaky() {{ if [ ! -f {counter} ]; then echo 'Curl error (28)' >&2; "
                "else echo 'No match for argument: libfoo' >&2; fi;"
            )
            unsatisfiable_after_retry = subprocess.run(
                ["bash", "-c", probe.replace("flaky() {", recovered)],
                env={"PASS_ON": "9", "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
            self.assertEqual(unsatisfiable_after_retry.returncode, 1,
                             unsatisfiable_after_retry.stdout + unsatisfiable_after_retry.stderr)
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
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        self.assertNotRegex(script, r"(?i)fcix|servaxnet|mirror\.constant")
        start = script.index("redirect_fedora_urls() {")
        end = script.index("\n}\n", start) + 3
        helper = script[start:end]

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

    def test_each_retry_asks_hummingbird_for_a_different_spelling_of_the_same_file(self) -> None:
        # Akamai caches a bad answer per URL (run 44478890278: 48 of 52 failed
        # builds were one shadow-utils RPM). Each retry changes the cache key,
        # never the host, the file name, or a Fedora or file:// URL.
        import json
        import os
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        start = script.index("vary_hummingbird_urls() {")
        helper = script[start:script.index("\n}\n", start) + 3]
        self.assertIn('vary_hummingbird_urls "$H/lock/pending.json" "$attempt"', script)
        hb = "https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/Packages/s/shadow-utils-4.20.0-2.hum1.x86_64.rpm"
        others = ["file:///work/prior/x-1-1.x86_64.rpm",
                  "https://download.fedoraproject.org/pub/fedora/linux/updates/44/Everything/x86_64/Packages/f/f-1.noarch.rpm"]
        seen = []
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "pending.json"
            lock.write_text(json.dumps({"buildroot": {"rpms": [{"url": u} for u in [hb, *others]]}}))
            for attempt in (2, 3, 4, 5):
                subprocess.run(["bash", "-c", f"set -euo pipefail\n{helper}\nvary_hummingbird_urls {lock} {attempt}"],
                               check=True)
                urls = [r["url"] for r in json.loads(lock.read_text())["buildroot"]["rpms"]]
                self.assertEqual(urls[1:], others)
                self.assertTrue(urls[0].startswith("https://packages.redhat.com/api/"))
                self.assertEqual(os.path.basename(urls[0]), os.path.basename(hb))
                self.assertEqual(urls[0].replace("//", "/").replace("https:/", "https://"), hb)
                seen.append(urls[0])
        self.assertEqual(len(set(seen[:3])), 3)
        self.assertNotIn(hb, seen)
        self.assertEqual(seen[3], seen[0])

    def test_a_gzip_encoded_rpm_download_is_unwrapped_before_verification(self) -> None:
        # An Akamai edge answered with Content-Encoding: gzip and
        # mock-hermetic-repo kept the encoded body (run 44735693275: shadow-utils,
        # 1381217 bytes starting 1f8b). Only a gzip stream around an RPM lead is
        # unwrapped; SIGMD5 verification still decides whether it is the RPM.
        import gzip
        import subprocess
        import tempfile

        script = SCRIPT.read_text()
        start = script.index("unwrap_gzip_rpms() {")
        helper = script[start:script.index("\n}\n", start) + 3]
        fetch = script[script.index("mock-hermetic-repo --lockfile"):script.index("verify_hermetic_repo.py --lockfile")]
        self.assertIn('unwrap_gzip_rpms "$H/repo"', fetch)
        rpm = b"\xed\xab\xee\xdb" + b"rpm header and payload" * 64
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "encoded-1-1.x86_64.rpm").write_bytes(gzip.compress(rpm))
            (repo / "plain-1-1.x86_64.rpm").write_bytes(rpm)
            # Compressed once: gzip.compress stamps the current second into the
            # header, so compressing again for the comparison can differ by a tick.
            page = gzip.compress(b"<html>not an rpm</html>")
            truncated = gzip.compress(rpm)[:40]
            (repo / "page-1-1.x86_64.rpm").write_bytes(page)
            (repo / "truncated-1-1.x86_64.rpm").write_bytes(truncated)
            subprocess.run(["bash", "-c", f"set -euo pipefail\n{helper}\nunwrap_gzip_rpms {repo}"], check=True,
                           capture_output=True)
            self.assertEqual((repo / "encoded-1-1.x86_64.rpm").read_bytes(), rpm)
            self.assertEqual((repo / "plain-1-1.x86_64.rpm").read_bytes(), rpm)
            self.assertEqual((repo / "page-1-1.x86_64.rpm").read_bytes(), page)
            self.assertEqual((repo / "truncated-1-1.x86_64.rpm").read_bytes(), truncated)

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
