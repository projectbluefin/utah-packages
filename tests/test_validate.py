#!/usr/bin/env python3
"""Coverage for tools/validate.py, the gate run by .github/workflows/validate.yml.

validate.py runs as a script, never imported, so every case drives it the way CI
does: a synthetic factory tree as the working directory, then an assertion on the
exit status and the message. The tree is deliberately minimal -- one package, one
source lock, one Packit entry -- so a failure names the rule that broke rather
than a fixture that drifted.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATE = ROOT / "tools" / "validate.py"

RAWHIDE_PROVENANCE = {
    "package": "example",
    "branch": "rawhide",
    "remote": "https://src.fedoraproject.org/rpms/example.git",
    "commit": "f" * 40,
    "tree": "e" * 40,
    "imported_at": "2026-08-30T15:46:53.402315+00:00",
}

UPSTREAM_PROVENANCE = {
    "package": "example",
    "branch": "upstream",
    "remote": "https://github.com/example/example.git",
    "commit": "",
    "tree": "",
    "imported_at": "2026-08-30T15:46:53.402315+00:00",
}

DEFAULT_BUILDROOT_LOCK = {
    "schema": 1,
    "buildroots": {
        "fedora-44": {
            "image": "quay.io/fedora/fedora:44@sha256:" + "0" * 64,
            "packages": [],
        }
    },
}


class ValidateScriptTests(unittest.TestCase):
    def build(
        self,
        root: Path,
        *,
        packages=("example",),
        provenance=RAWHIDE_PROVENANCE,
        locked=None,
        packit=None,
        buildroot_lock=DEFAULT_BUILDROOT_LOCK,
    ) -> None:
        """Write a factory tree validate.py accepts unless a case breaks one rule."""
        locked = packages if locked is None else locked
        packit = packages if packit is None else packit
        for name in packages:
            directory = root / "packages" / name
            directory.mkdir(parents=True)
            (directory / f"{name}.spec").write_text(f"Name: {name}\n")
            if provenance is not None:
                (directory / ".hummingbird-upstream.json").write_text(
                    json.dumps({**provenance, "package": name})
                )
        (root / "config").mkdir()
        (root / "config" / "upstream-sources.json").write_text(
            json.dumps({"packages": [{"name": name} for name in locked]})
        )
        if buildroot_lock is not None:
            (root / "config" / "buildroot-lock.json").write_text(
                json.dumps(buildroot_lock)
            )
        entries = "".join(
            f"  {name}:\n    specfile_path: {name}.spec\n" for name in packit
        )
        (root / ".packit.yaml").write_text("packages:\n" + entries)

    def run_validate(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(VALIDATE)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

    def check(self, **kwargs) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build(root, **kwargs)
            return self.run_validate(root)

    def test_accepts_a_rawhide_import_that_pins_commit_and_tree(self) -> None:
        result = self.check(provenance=RAWHIDE_PROVENANCE)
        assert result.returncode == 0, result.stderr
        assert "validated 1 source RPMs" in result.stdout

    def test_accepts_an_upstream_import_with_no_dist_git_snapshot(self) -> None:
        result = self.check(provenance=UPSTREAM_PROVENANCE)
        assert result.returncode == 0, result.stderr
        assert "validated 1 source RPMs" in result.stdout

    def test_rejects_a_package_that_carries_no_provenance_file(self) -> None:
        result = self.check(provenance=None)
        assert result.returncode != 0
        assert "missing upstream provenance" in result.stderr

    def test_rejects_provenance_missing_a_required_key(self) -> None:
        incomplete = {k: v for k, v in RAWHIDE_PROVENANCE.items() if k != "imported_at"}
        result = self.check(provenance=incomplete)
        assert result.returncode != 0
        assert "invalid upstream provenance" in result.stderr

    def test_rejects_provenance_carrying_an_unknown_key(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "signature": "x"})
        assert result.returncode != 0
        assert "invalid upstream provenance" in result.stderr

    def test_rejects_a_branch_that_is_neither_rawhide_nor_upstream(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "branch": "f43"})
        assert result.returncode != 0
        assert "only rawhide or upstream imports are supported" in result.stderr

    def test_rejects_an_upstream_import_that_carries_a_commit(self) -> None:
        result = self.check(provenance={**UPSTREAM_PROVENANCE, "commit": "a" * 40})
        assert result.returncode != 0
        assert "upstream import must not carry commit" in result.stderr

    def test_rejects_an_upstream_import_that_carries_a_tree(self) -> None:
        result = self.check(provenance={**UPSTREAM_PROVENANCE, "tree": "b" * 40})
        assert result.returncode != 0
        assert "upstream import must not carry tree" in result.stderr

    def test_rejects_an_upstream_import_with_an_empty_remote(self) -> None:
        result = self.check(provenance={**UPSTREAM_PROVENANCE, "remote": ""})
        assert result.returncode != 0
        assert "upstream import must name its upstream remote" in result.stderr

    def test_rejects_a_rawhide_import_with_an_empty_commit(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "commit": ""})
        assert result.returncode != 0
        assert "rawhide import must carry commit" in result.stderr

    def test_rejects_a_rawhide_import_with_a_short_commit(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "commit": "abc1234"})
        assert result.returncode != 0
        assert "rawhide import must carry a full commit SHA" in result.stderr

    def test_rejects_a_rawhide_import_with_an_empty_tree(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "tree": ""})
        assert result.returncode != 0
        assert "rawhide import must carry tree" in result.stderr

    def test_rejects_a_rawhide_import_with_a_short_tree(self) -> None:
        result = self.check(provenance={**RAWHIDE_PROVENANCE, "tree": "def5678"})
        assert result.returncode != 0
        assert "rawhide import must carry a full tree SHA" in result.stderr

    def test_rejects_missing_buildroot_lock(self) -> None:
        result = self.check(buildroot_lock=None)
        assert result.returncode != 0
        assert "missing buildroot lock" in result.stderr

    def test_rejects_unpinned_buildroot_image(self) -> None:
        unpinned = {
            "schema": 1,
            "buildroots": {
                "fedora-44": {
                    "image": "quay.io/fedora/fedora:44",
                    "packages": [],
                }
            },
        }
        result = self.check(buildroot_lock=unpinned)
        assert result.returncode != 0
        assert "image must be digest-pinned" in result.stderr

    def test_rejects_invalid_buildroot_lock_schema(self) -> None:
        invalid = {
            "schema": 2,
            "buildroots": {},
        }
        result = self.check(buildroot_lock=invalid)
        assert result.returncode != 0
        assert "invalid buildroot lock" in result.stderr

    def test_detects_drift_between_buildroot_lock_and_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.build(root)
            wf_dir = root / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            wf_file = wf_dir / "rebuild-rpms.yml"
            wf_file.write_text(
                "jobs:\n  prepare:\n    env:\n      BUILDROOT_IMAGE: quay.io/fedora/fedora:44@sha256:" + "1" * 64 + "\n"
            )
            result = self.run_validate(root)
            assert result.returncode != 0
            assert "buildroot drift" in result.stderr

    def test_reports_a_package_with_no_source_lock(self) -> None:
        result = self.check(provenance=RAWHIDE_PROVENANCE, locked=())
        assert result.returncode == 1
        assert "packages missing source locks: example" in result.stdout

    def test_reports_a_package_with_no_packit_entry(self) -> None:
        result = self.check(provenance=RAWHIDE_PROVENANCE, packit=())
        assert result.returncode == 1
        assert "packages missing Packit config: example" in result.stdout

    def test_reports_both_missing_locks_and_missing_packit_entries(self) -> None:
        result = self.check(
            packages=("one", "two"),
            provenance=RAWHIDE_PROVENANCE,
            locked=("two",),
            packit=("one",),
        )
        assert result.returncode == 1
        assert "packages missing source locks: one" in result.stdout
        assert "packages missing Packit config: two" in result.stdout

    def test_counts_every_recipe_it_validated(self) -> None:
        result = self.check(
            packages=("one", "two", "three"), provenance=RAWHIDE_PROVENANCE
        )
        assert result.returncode == 0, result.stderr
        assert "validated 3 source RPMs" in result.stdout

    def test_returns_zero_when_packages_directory_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_validate(root)
            assert result.returncode == 0, result.stderr

    def test_the_checked_in_factory_tree_passes_its_own_gate(self) -> None:
        result = self.run_validate(ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "validated" in result.stdout


if __name__ == "__main__":
    unittest.main()
