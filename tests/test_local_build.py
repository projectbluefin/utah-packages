"""Exercise the local/CI driver's failure and locking boundaries without RPM tools."""
import fcntl
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalBuildTests(unittest.TestCase):
    def test_container_failure_preserves_log_and_does_not_claim_old_rpm(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / "work"
            (work / "result").mkdir(parents=True)
            (work / "result" / "old.rpm").write_bytes(b"previous build")
            engine = Path(directory) / "engine"
            engine.write_text("#!/bin/sh\necho 'deliberate container failure'\nexit 42\n")
            engine.chmod(0o755)
            result = subprocess.run(
                ["bash", "tools/build-package.sh", "python-argcomplete", "--no-fetch",
                 "--work", str(work), "--engine", str(engine)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 42, result.stdout + result.stderr)
            self.assertEqual(list((work / "result").iterdir()), [])
            self.assertEqual(len(list(work.glob("previous.*/result/old.rpm"))), 1)
            logs = list((work / "logs").glob("*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("deliberate container failure", logs[0].read_text())

    def test_busy_work_directory_fails_before_mutating_results(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            with (work / ".build.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(
                    ["bash", "tools/build-package.sh", "python-argcomplete", "--no-fetch",
                     "--work", str(work)], cwd=ROOT, capture_output=True, text=True,
                )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Another build owns", result.stderr)
            self.assertFalse((work / "result").exists())
