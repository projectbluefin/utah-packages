#!/usr/bin/env python3
"""What Utah installs is resolved against the candidate, and reported by name."""

from pathlib import Path
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
            (root / "bluefin.toml").write_text(
                '[fedora]\npackages = ["fish", "libgphoto2"]\n[fedora_v44]\npackages = ["ptyxis"]\n')
            (root / "utah.toml").write_text(
                '[gnome]\npackages = ["gnome-shell"]\n[parity]\npackages = ["fish"]\n'
                '[unavailable]\npackages = ["ptyxis"]\n[build]\npackages = ["meson"]\n')
            packages = uis.install_set(root / "install-packages.py", root / "bluefin.toml",
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
