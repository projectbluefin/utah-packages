"""Check that parsing the recipe does not inject prep commands into the build."""

from pathlib import Path
import shutil
import subprocess
import unittest


class LinuxAtmSpecTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rpmspec"), "rpmspec is not installed")
    def test_build_section_does_not_run_setup(self):
        spec = Path(__file__).resolve().parent.parent / "packages/linux-atm/linux-atm.spec"
        parsed = subprocess.run(
            ["rpmspec", "--parse", str(spec)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        build = parsed.split("%build\n", 1)[1].split("%install\n", 1)[0]
        self.assertNotRegex(build, r"(?m)^\s*%setup\b")
        self.assertIn("autoreconf -fi", build)
