"""Check that parsing the recipe does not inject prep commands into the build."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class LinuxAtmSpecTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("rpmspec"), "rpmspec is not installed")
    def test_build_section_does_not_run_setup(self):
        spec = Path(__file__).resolve().parent.parent / "packages/linux-atm/linux-atm.spec"
        source = spec.read_text()
        source = source.replace("%build\n", "%build\n# BEGIN BUILD REGRESSION TEST\n", 1)
        source = source.replace("%install\n", "# END BUILD REGRESSION TEST\n%install\n", 1)
        with tempfile.TemporaryDirectory() as directory:
            test_spec = Path(directory) / spec.name
            test_spec.write_text(source)
            parsed = subprocess.run(
                ["rpmspec", "--parse", str(test_spec)],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        build = parsed.split("# BEGIN BUILD REGRESSION TEST\n", 1)[1].split(
            "# END BUILD REGRESSION TEST\n", 1
        )[0]
        self.assertNotRegex(build, r"(?m)^\s*%setup\b")
        self.assertIn("autoreconf -fi", build)
