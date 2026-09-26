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

DEFAULT_BUILDROOT_PIN = (
    "ghcr.io/projectbluefin/utah-buildroot:44-20260925-000000000000@sha256:" + "0" * 64
)

DEFAULT_BUILDROOT_LOCK = {
    "schema": 1,
    "buildroots": {
        "fedora-44": {
            "image": DEFAULT_BUILDROOT_PIN,
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
        buildroot_pin=DEFAULT_BUILDROOT_PIN,
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
        if buildroot_pin is not None:
            (root / "config" / "buildroot-image").write_text(buildroot_pin + "\n")
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

    def test_detects_a_lock_that_names_a_different_root_from_the_pin(self) -> None:
        # The lock and config/buildroot-image name one root twice. The weekly
        # refresh moves both through buildroot_pin.py set; a hand edit to
        # either one is what this catches.
        moved = DEFAULT_BUILDROOT_PIN.rsplit("@", 1)[0] + "@sha256:" + "1" * 64
        result = self.check(buildroot_pin=moved)
        assert result.returncode != 0
        assert "buildroot drift" in result.stderr
        assert moved in result.stderr

    def test_detects_a_lock_with_no_pin_behind_it(self) -> None:
        # prepare pulls nothing but the pin, so a lock without one describes a
        # root no run can have built in.
        result = self.check(buildroot_pin=None)
        assert result.returncode != 0
        assert "buildroot drift" in result.stderr
        assert "no pin" in result.stderr

    def test_buildroot_drift_is_reported_even_when_a_recipe_is_unlocked(self) -> None:
        # Drift used to hide behind the recipe tally: validate returned 1 for a
        # missing Packit entry before it ever looked at the buildroot.
        moved = DEFAULT_BUILDROOT_PIN.rsplit("@", 1)[0] + "@sha256:" + "1" * 64
        result = self.check(packit=(), buildroot_pin=moved)
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

    def test_reports_the_provenance_form_every_recipe_carries(self) -> None:
        # Direct-upstream recipes are the form that was easiest to leave
        # unvalidated, so the count says how many of each kind passed rather
        # than only how many there were.
        result = self.check(packages=("one", "two"), provenance=RAWHIDE_PROVENANCE)
        assert result.returncode == 0, result.stderr
        assert "validated 2 source RPMs (2 rawhide)" in result.stdout
        result = self.check(packages=("one",), provenance=UPSTREAM_PROVENANCE)
        assert result.returncode == 0, result.stderr
        assert "validated 1 source RPMs (1 upstream)" in result.stdout

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
