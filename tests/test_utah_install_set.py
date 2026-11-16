#!/usr/bin/env python3
"""What Utah installs is resolved against the candidate, and reported by name."""

import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import yaml

from tools import utah_install_set as uis

ROOT = Path(__file__).resolve().parent.parent
REBUILD = ROOT / ".github" / "workflows" / "publish-repository.yml"

INSTALLER = '''
import tomllib
from pathlib import Path
def section(path, name):
    return list(tomllib.loads(Path(path).read_text()).get(name, {}).get("packages", []))
def contract(base, overlay, major):
    packages = section(base, "fedora") + section(base, f"fedora_v{major}")
    for name in ("gnome", "parity", "hardware", "services"):
        packages += section(overlay, name)
    unavailable = set(section(overlay, "unavailable"))
    return list(dict.fromkeys(p for p in packages if p not in unavailable))
'''


class InstallSetTests(unittest.TestCase):
    def test_utahs_own_code_decides_the_set_plus_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "install-packages.py").write_text(INSTALLER)
            (root / "base.toml").write_text(
                '[fedora]\npackages = ["fish", "libgphoto2"]\n[fedora_v44]\npackages = ["ptyxis"]\n')
            (root / "utah.toml").write_text(
                '[gnome]\npackages = ["gnome-shell"]\n[parity]\npackages = ["fish"]\n'
                '[unavailable]\npackages = ["ptyxis"]\n[build]\npackages = ["meson"]\n')
            packages = uis.install_set(root / "install-packages.py", root / "base.toml",
                                       root / "utah.toml")
        self.assertEqual(packages, ["fish", "libgphoto2", "gnome-shell", "meson"])


class BaseImageTests(unittest.TestCase):
    """Regression: the check resolved in the factory's older base image.

    bootc-os@c5539f9e still carried Fedora fuse3-libs 3.16 and a
    grub2-tools-minimal requiring libfuse3.so.3, so Hummingbird's
    fuse3-libs 3.18 (libfuse3.so.4) could not be installed beside it and
    flatpak, gnome-shell and xdg-desktop-portal were reported as gaps. Utah's
    base, bootc-os@7ea73596, ships fuse3-libs 3.18.3 and installed them.
    """

    UTAH = ("ARG BASE_IMAGE=quay.io/hummingbird-community/bootc-os:latest@sha256:"
            "7ea735968c2543f51a975474b13b17bb8e110852045fd99bd13066179bf775f2\n")

    def test_the_base_is_utahs_pinned_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            containerfile = Path(directory) / "Containerfile"
            containerfile.write_text("FROM x\n" + self.UTAH)
            self.assertTrue(uis.base_image(containerfile).endswith("7ea735968c2543f51a975474b13b17bb8e110852045fd99bd13066179bf775f2"))
            containerfile.write_text("ARG BASE_IMAGE=quay.io/hummingbird-community/bootc-os:latest\n")
            with self.assertRaises(ValueError):
                uis.base_image(containerfile)

    def test_the_workflow_resolves_in_utahs_base_not_the_contracts(self) -> None:
        step = next(s for s in yaml.safe_load(REBUILD.read_text())["jobs"]["publish"]["steps"]
                    if s.get("name") == "Resolve what Utah installs (advisory)")
        self.assertIn("BASE_IMAGE=$(cat work/utah/base-image)", step["run"])
        self.assertNotIn("runtime_contract.py", step["run"])
        self.assertIn("Containerfile", uis.FILES.values())

    def test_the_blocking_transaction_resolves_in_utahs_base_with_a_loud_fallback(self) -> None:
        steps = yaml.safe_load(REBUILD.read_text())["jobs"]["publish"]["steps"]
        names = [s.get("name") for s in steps]
        fetch = names.index("Fetch what Utah installs, and its base image")
        validate = names.index("Validate Hummingbird-only consumer transaction")
        self.assertLess(fetch, validate)
        self.assertTrue(steps[fetch]["continue-on-error"])
        run = steps[validate]["run"]
        self.assertIn("BASE_IMAGE=$(cat work/utah/base-image)", run)
        # The factory base only as a fallback, and never silently.
        fallback = run.split("else", 1)[1]
        self.assertIn("--base-image", fallback)
        self.assertIn("::warning title=transaction not in Utah's base::", fallback)
        self.assertIn("GITHUB_STEP_SUMMARY", fallback)

    def test_an_rpmdb_conflict_is_reported_by_its_own_line(self) -> None:
        output = (
            "Problem: package xdg-desktop-portal-1.22.1-1.hum1.bfin.x86_64 from utah-packages "
            "requires libfuse3.so.4()(64bit), but none of the providers can be installed\n"
            "  - cannot install both fuse3-libs-3.18.3-1.hum1.x86_64 from public-hummingbird-x86_64-rpms "
            "and fuse3-libs-3.16.2-6.fc43.x86_64 from @System\n")
        self.assertIn("requires libfuse3.so.4", uis.first_problem(output))


class VerdictTests(unittest.TestCase):
    NOTHING = ("Failed to resolve the transaction:\n"
               "Problem: conflicting requests\n"
               "  - nothing provides libexif.so.12()(64bit) needed by libgphoto2-2.5.33-1.hum1.bfin.x86_64 from utah-packages\n")

    def test_the_problem_line_is_the_reason(self) -> None:
        self.assertIn("nothing provides libexif.so.12", uis.first_problem(self.NOTHING))

    def test_each_failing_package_is_named(self) -> None:
        def attempt(packages, repos):
            if len(packages) > 1:
                return False, self.NOTHING
            return (packages != ["libgphoto2"]), self.NOTHING
        with mock.patch.object(uis, "attempt", side_effect=attempt):
            report = uis.resolve(["fish", "libgphoto2", "gnome-shell"], ("utah-packages",))
        self.assertFalse(report["resolved"])
        self.assertEqual(list(report["unresolved"]), ["libgphoto2"])
        self.assertIn("| `libgphoto2` |", uis.summary(report))

    def test_a_clean_set_resolves_in_one_transaction(self) -> None:
        with mock.patch.object(uis, "attempt", return_value=(True, "Transaction Summary:\n")) as call:
            report = uis.resolve(["fish", "gnome-shell"], ("utah-packages",))
        self.assertTrue(report["resolved"])
        self.assertEqual(call.call_count, 1)

    def test_a_conflict_only_the_set_has_is_still_reported(self) -> None:
        def attempt(packages, repos):
            return len(packages) == 1, "Problem: cannot install both a and b"
        with mock.patch.object(uis, "attempt", side_effect=attempt):
            report = uis.resolve(["a", "b"], ("utah-packages",))
        self.assertEqual(list(report["unresolved"]), ["(the set together)"])


class AttemptTests(unittest.TestCase):
    """attempt() is the verdict: dnf --assumeno exits 1 on a valid transaction."""

    SUMMARY = "Transaction Summary:\n Installing: 3 packages\nOperation aborted by the user.\n"

    def run_attempt(self, returncode: int, stdout: str):
        completed = subprocess.CompletedProcess([], returncode, stdout=stdout)
        with mock.patch.object(uis, "dnf", return_value="/usr/bin/dnf5"), \
                mock.patch.object(uis.subprocess, "run", return_value=completed) as run:
            ok, output = uis.attempt(["fish", "libgphoto2"], ("utah-packages", "hummingbird"))
        return ok, output, run

    def test_assumeno_exit_one_with_a_summary_is_a_valid_transaction(self) -> None:
        ok, output, _ = self.run_attempt(1, self.SUMMARY)
        self.assertTrue(ok)
        self.assertEqual(output, self.SUMMARY)

    def test_nothing_to_do_is_a_valid_transaction(self) -> None:
        self.assertTrue(self.run_attempt(0, "Nothing to do.\n")[0])

    def test_an_error_line_fails_even_beside_a_summary(self) -> None:
        for line in ("No match for argument: ptyxis", "nothing provides libexif.so.12",
                     "Error: Unable to find a match", "Failed to resolve the transaction:",
                     "Problem: cannot install both a and b"):
            with self.subTest(line=line):
                self.assertFalse(self.run_attempt(1, self.SUMMARY + line + "\n")[0])

    def test_no_summary_is_not_a_success(self) -> None:
        self.assertFalse(self.run_attempt(0, "Updating and loading repositories:\n")[0])
        self.assertFalse(self.run_attempt(0, "")[0])

    def test_any_other_exit_code_fails(self) -> None:
        self.assertFalse(self.run_attempt(2, self.SUMMARY)[0])

    def test_only_the_named_repositories_are_enabled_in_the_c_locale(self) -> None:
        _, _, run = self.run_attempt(1, self.SUMMARY)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/dnf5", "--assumeno", "--disablerepo=*"])
        self.assertEqual([c for c in command if c.startswith("--enablerepo=")],
                         ["--enablerepo=utah-packages", "--enablerepo=hummingbird"])
        self.assertEqual(command[-5:], ["-x", "PackageKit*", "install", "fish", "libgphoto2"])
        self.assertEqual(run.call_args.kwargs["env"]["LC_ALL"], "C")
        self.assertIs(run.call_args.kwargs["stderr"], subprocess.STDOUT)
        self.assertFalse(run.call_args.kwargs["check"])


class DnfTests(unittest.TestCase):
    def test_dnf5_is_preferred(self) -> None:
        found = {"dnf5": "/usr/bin/dnf5", "dnf": "/usr/bin/dnf"}
        with mock.patch.object(uis.shutil, "which", side_effect=found.get):
            self.assertEqual(uis.dnf(), "/usr/bin/dnf5")

    def test_dnf_is_the_fallback(self) -> None:
        with mock.patch.object(uis.shutil, "which", side_effect={"dnf": "/usr/bin/dnf"}.get):
            self.assertEqual(uis.dnf(), "/usr/bin/dnf")

    def test_no_dnf_is_an_error_not_a_pass(self) -> None:
        with mock.patch.object(uis.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "no dnf"):
                uis.dnf()


class FirstProblemFallbackTests(unittest.TestCase):
    def test_without_a_problem_line_the_line_after_the_error_is_the_reason(self) -> None:
        output = "Updating repositories\nError: \n - package foo is filtered out by exclude\n"
        self.assertEqual(uis.first_problem(output), "package foo is filtered out by exclude")

    def test_an_error_on_the_last_line_reports_that_line(self) -> None:
        self.assertEqual(uis.first_problem("loading\nError: repo down\n"), "Error: repo down")

    def test_empty_output_says_so(self) -> None:
        self.assertEqual(uis.first_problem("\n  \n"), "no output")

    def test_the_reason_is_capped(self) -> None:
        self.assertEqual(len(uis.first_problem("nothing provides " + "x" * 500)), 300)


class SummaryTests(unittest.TestCase):
    def test_an_unchecked_run_says_why(self) -> None:
        text = uis.summary({"error": "fetch failed", "resolved": False, "unresolved": {}})
        self.assertIn("**Not checked:** fetch failed", text)
        self.assertNotIn("All ", text)

    def test_a_clean_run_counts_what_resolved(self) -> None:
        text = uis.summary({"requested": 412, "resolved": True, "unresolved": {}})
        self.assertIn("All 412 packages Utah installs resolve", text)

    def test_pipes_in_a_reason_cannot_break_the_table(self) -> None:
        text = uis.summary({"requested": 2, "resolved": False,
                            "unresolved": {"b": "x | y", "a": "why"}})
        self.assertIn("**2 of 2 packages", text)
        rows = [line for line in text.splitlines() if line.startswith("| `")]
        self.assertEqual(rows, ["| `a` | `why` |", "| `b` | `x / y` |"])


class FetchTests(unittest.TestCase):
    def test_every_file_comes_from_the_requested_ref_by_its_basename(self) -> None:
        requested = []

        def urlopen(url, timeout):
            requested.append((url, timeout))
            return contextlib.nullcontext(io.BytesIO(url.encode()))

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=urlopen):
            paths = uis.fetch("abc123", Path(directory))
            self.assertEqual(set(paths), set(uis.FILES))
            for key, path in uis.FILES.items():
                url = f"https://raw.githubusercontent.com/projectbluefin/utah/abc123/{path}"
                self.assertEqual(paths[key], Path(directory) / Path(path).name)
                self.assertEqual(paths[key].read_text(), url)
        self.assertEqual(len(requested), len(uis.FILES))
        self.assertTrue(all(timeout == 60 for _, timeout in requested))

    def test_a_failed_download_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=OSError("404")):
            with self.assertRaises(OSError):
                uis.fetch("main", Path(directory))

    @staticmethod
    def missing(paths):
        def urlopen(url, timeout):
            if any(url.endswith("/" + path) for path in paths):
                raise uis.urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return contextlib.nullcontext(io.BytesIO(url.encode()))
        return urlopen

    def test_a_ref_before_the_rename_fetches_bluefin_toml(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen",
                                  side_effect=self.missing(["packages/base.toml"])):
            paths = uis.fetch("old", Path(directory))
            self.assertEqual(paths["manifest"], Path(directory) / "bluefin.toml")
            self.assertTrue(paths["manifest"].read_text().endswith("/old/packages/bluefin.toml"))
            self.assertFalse((Path(directory) / "base.toml").exists())

    def test_base_toml_wins_when_both_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=self.missing([])):
            paths = uis.fetch("new", Path(directory))
            self.assertEqual(paths["manifest"], Path(directory) / "base.toml")
            self.assertFalse((Path(directory) / "bluefin.toml").exists())

    def test_a_missing_manifest_under_both_names_fails(self) -> None:
        missing = self.missing(["packages/base.toml", "packages/bluefin.toml"])
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=missing):
            with self.assertRaises(uis.urllib.error.HTTPError):
                uis.fetch("main", Path(directory))

    def test_only_a_404_on_the_manifest_falls_back(self) -> None:
        def urlopen(url, timeout):
            if url.endswith("/packages/base.toml"):
                raise uis.urllib.error.HTTPError(url, 500, "Server Error", {}, None)
            return contextlib.nullcontext(io.BytesIO(url.encode()))
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=urlopen):
            with self.assertRaises(uis.urllib.error.HTTPError):
                uis.fetch("main", Path(directory))
        missing = self.missing(["packages/utah.toml"])
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(uis.urllib.request, "urlopen", side_effect=missing):
            with self.assertRaises(uis.urllib.error.HTTPError):
                uis.fetch("main", Path(directory))

    def test_resolve_reads_the_names_fetch_writes(self) -> None:
        # main(resolve) opens the installer and key by these names, inside the
        # base image, from what fetch wrote on the host.
        names = {Path(path).name for path in uis.FILES.values()}
        self.assertIn("install-packages.py", names)
        self.assertIn("RPM-GPG-KEY-redhat-release-2", names)
        self.assertIn("utah-packages.repo", names)


class MainTests(unittest.TestCase):
    PINNED = ("quay.io/hummingbird-community/bootc-os:latest@sha256:"
              "7ea735968c2543f51a975474b13b17bb8e110852045fd99bd13066179bf775f2")

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = uis.main(argv)
        return code, out.getvalue()

    def test_fetch_writes_the_package_set_and_the_base_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "utah"

            def fetch(ref, target):
                self.assertEqual(ref, "feature")
                (target / "install-packages.py").write_text(INSTALLER)
                (target / "base.toml").write_text(
                    '[fedora]\npackages = ["fish"]\n[fedora_v44]\npackages = ["ptyxis"]\n')
                (target / "utah.toml").write_text(
                    '[gnome]\npackages = ["fish", "gnome-shell"]\n[build]\npackages = ["meson"]\n')
                (target / "Containerfile").write_text(f"ARG BASE_IMAGE={self.PINNED}\n")
                return {"installer": target / "install-packages.py",
                        "manifest": target / "base.toml", "overlay": target / "utah.toml",
                        "containerfile": target / "Containerfile"}

            with mock.patch.object(uis, "fetch", side_effect=fetch):
                code, out = self.run_main(["fetch", "--dir", str(root), "--ref", "feature"])
            self.assertEqual(code, 0)
            self.assertEqual((root / "packages.txt").read_text(),
                             "fish\nptyxis\ngnome-shell\nmeson\n")
            self.assertEqual((root / "base-image").read_text(), self.PINNED + "\n")
        self.assertIn("Utah installs 4 packages (projectbluefin/utah@feature)", out)

    def test_fetch_refuses_an_unpinned_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fetch(ref, target):
                (target / "install-packages.py").write_text(INSTALLER)
                for name in ("base.toml", "utah.toml"):
                    (target / name).write_text("")
                (target / "Containerfile").write_text("ARG BASE_IMAGE=quay.io/x/y:latest\n")
                return {"installer": target / "install-packages.py",
                        "manifest": target / "base.toml", "overlay": target / "utah.toml",
                        "containerfile": target / "Containerfile"}

            with mock.patch.object(uis, "fetch", side_effect=fetch), \
                    self.assertRaises(ValueError):
                self.run_main(["fetch", "--dir", str(root)])
            self.assertFalse((root / "base-image").exists())

    def test_resolve_installs_utahs_repositories_and_writes_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            utah, system = root / "utah", root / "system"
            utah.mkdir()
            (utah / "packages.txt").write_text("fish\n\n  libgphoto2  \n")
            (utah / "utah-packages.repo").write_text("[utah-packages]\n")
            (utah / "hummingbird.repo").write_text("[hummingbird]\n")
            (utah / "RPM-GPG-KEY-redhat-release-2").write_text("KEY\n")
            (utah / "install-packages.py").write_text(
                "def install_repos(repos_dir):\n"
                "    return sorted(p.stem for p in repos_dir.glob('*.repo'))\n")
            (system / "etc" / "yum.repos.d").mkdir(parents=True)
            real_path, real_copy = uis.Path, shutil.copy

            def rooted(path):
                path = str(path)
                return system / path.lstrip("/") if path.startswith("/etc/") else path

            calls = []

            def resolve(packages, repos):
                calls.append((packages, repos))
                return {"requested": 2, "resolved": False, "unresolved": {"libgphoto2": "why"}}

            with mock.patch.object(uis, "Path", side_effect=lambda p: real_path(rooted(p))), \
                    mock.patch.object(uis.shutil, "copy",
                                      side_effect=lambda s, d: real_copy(s, rooted(d))), \
                    mock.patch.object(uis, "resolve", side_effect=resolve):
                code, out = self.run_main(["resolve", "--dir", str(utah),
                                           "--report", str(root / "report.json")])
            self.assertEqual(code, 0)
            self.assertEqual(calls, [(["fish", "libgphoto2"], ("hummingbird", "utah-packages"))])
            self.assertEqual(sorted(p.name for p in (system / "etc" / "yum.repos.d").iterdir()),
                             ["hummingbird.repo", "utah-packages.repo"])
            self.assertEqual(
                (system / "etc" / "pki" / "rpm-gpg" / "RPM-GPG-KEY-redhat-release-2").read_text(),
                "KEY\n")
            report = json.loads((root / "report.json").read_text())
        self.assertEqual(report["unresolved"], {"libgphoto2": "why"})
        self.assertIn("resolving 2 packages from hummingbird, utah-packages", out)
        self.assertIn("| `libgphoto2` | `why` |", out)

    def test_summary_renders_a_written_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text(json.dumps({"requested": 5, "resolved": True, "unresolved": {}}))
            code, out = self.run_main(["summary", str(report)])
        self.assertEqual(code, 0)
        self.assertIn("### Utah install set", out)
        self.assertIn("All 5 packages", out)

    def test_a_command_is_required(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            uis.main([])


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workflow = yaml.safe_load(REBUILD.read_text())
        cls.jobs = workflow["jobs"]

    def test_advisory_after_the_blocking_transaction_before_publication(self) -> None:
        names = [s.get("name") for s in self.jobs["publish"]["steps"]]
        utah = names.index("Resolve what Utah installs (advisory)")
        self.assertLess(names.index("Validate Hummingbird-only consumer transaction"), utah)
        self.assertLess(utah, names.index("Publish the repository as an OCI image"))
        step = self.jobs["publish"]["steps"][utah]
        self.assertTrue(step["continue-on-error"])
        self.assertIn("/etc/utah-packages", step["run"])
        self.assertIn("steps.utah_inputs.outcome", step["run"])

    def test_one_issue_per_package_on_main_only(self) -> None:
        factory = yaml.safe_load((ROOT / ".github" / "workflows" / "rebuild-rpms.yml").read_text())
        step = next(s for s in factory["jobs"]["report"]["steps"]
                    if s.get("name") == "Track each package Utah cannot install")
        for clause in ("refs/heads/main", "inputs.publish_tag == ''",
                       "inputs.artifact_prefix == ''", "needs.publish.outputs.utah_report != ''"):
            self.assertIn(clause, step["if"])
        self.assertIn('prefix="Utah install set: "', step["run"])
        self.assertIn("gh issue close", step["run"])


if __name__ == "__main__":
    unittest.main()
