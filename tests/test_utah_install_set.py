#!/usr/bin/env python3
"""What Utah installs is resolved against the candidate, and reported by name."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import yaml

from tools import utah_install_set as uis

ROOT = Path(__file__).resolve().parent.parent
REBUILD = ROOT / ".github" / "workflows" / "rebuild-rpms.yml"

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
        self.assertIn("utah_install_set.py fetch", step["run"])

    def test_one_issue_per_package_on_main_only(self) -> None:
        step = next(s for s in self.jobs["report"]["steps"]
                    if s.get("name") == "Track each package Utah cannot install")
        for clause in ("refs/heads/main", "inputs.publish_tag == ''",
                       "inputs.artifact_prefix == ''", "needs.publish.outputs.utah_report != ''"):
            self.assertIn(clause, step["if"])
        self.assertIn('prefix="Utah install set: "', step["run"])
        self.assertIn("gh issue close", step["run"])


if __name__ == "__main__":
    unittest.main()
