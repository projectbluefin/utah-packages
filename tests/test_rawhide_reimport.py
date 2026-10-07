#!/usr/bin/env python3
"""Pin the safety classifier that decides which Rawhide moves import unattended.

``tools/rawhide_reimport.py`` re-imports a carried recipe without a human only
when :func:`classify` returns no reasons. Each rule below is one way a
wholesale re-import could ship something nobody reviewed: dropping a
Utah-local patch, moving the payload under an unchanged source lock, or adding
a build dependency the factory never resolved. Nothing here touches Koji or
src.fedoraproject.org; the dist-git checks run against a local repository.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import xmlrpc.client
from pathlib import Path
from unittest import mock

from tools import import_rawhide, rawhide_reimport as reimport

SPEC = """\
Name:           demo
Version:        1.2.3
Release:        %autorelease
Source0:        https://example.org/demo-%{version}.tar.xz
Patch0:         fix.patch

BuildRequires:  gcc, meson >= 1.0
BuildRequires:  pkgconfig(glib-2.0) >= 2.80

%build
%meson_build
"""
SOURCES = b"SHA512 (demo-1.2.3.tar.xz) = " + b"a" * 128 + b"\n"
PROVENANCE = {
    "package": "demo",
    "branch": "rawhide",
    "remote": "https://src.fedoraproject.org/rpms/demo.git",
    "commit": "0" * 40,
}
LOCK = {
    "name": "demo", "version": "1.2.3", "url": "https://example.org/demo-1.2.3.tar.xz",
    "filename": "demo-1.2.3.tar.xz", "sha512": "a" * 128, "stage": 2,
}


def tree(spec: str = SPEC, **extra: bytes) -> dict[str, bytes]:
    files = {"demo.spec": spec.encode(), "sources": SOURCES, "fix.patch": b"--- a\n+++ b\n"}
    files.update(extra)
    return files


def local(files: dict[str, bytes]) -> dict[str, bytes]:
    return {**files, ".hummingbird-upstream.json": b"{}"}


def classify(local_tree=None, pinned=None, target=None, *, lock=LOCK, provenance=PROVENANCE,
             fast_forward=True) -> list[str]:
    pinned = tree() if pinned is None else pinned
    return reimport.classify(
        "demo", provenance, lock, local(pinned) if local_tree is None else local_tree,
        pinned, target if target is not None else pinned,
        fast_forward=fast_forward,
    )


class ClassifierTests(unittest.TestCase):
    def test_noop_target_is_safe(self) -> None:
        # `classify()`'s default target equals the pinned tree, so a recipe that
        # Koji has not moved past is reported as safe. The legacy
        # `test_release_only_move_on_a_clean_recipe_is_safe` swapped the spec's
        # `Release:` between pinned and target; that swap is exactly what the
        # classifier now rejects (see #382).
        self.assertEqual(classify(), [])

    def test_literal_to_autorelease_blocks(self) -> None:
        # The libnma case from issue #382: the local copy held `12%{?dist}`
        # at the pinned commit, then Koji's newer commit swapped to `%autorelease`,
        # which would resolve to 1 in the factory's build tag (was 14 in Koji's).
        pinned = tree(SPEC.replace("Release:        %autorelease", "Release:        12%{?dist}"))
        target = tree(SPEC)
        reasons = classify(local_tree=local(pinned), pinned=pinned, target=target)
        self.assertIn(
            "Release: changed ['12%{?dist}'] -> ['%autorelease']", reasons,
        )

    def test_autorelease_to_literal_blocks(self) -> None:
        # The mirror direction: the spec dropped `%autorelease` in favour of a
        # literal. The literal might be smaller than what %autorelease would
        # have produced (14 -> 2 here), and the classifier cannot tell.
        pinned = tree(SPEC)
        target = tree(SPEC.replace("Release:        %autorelease", "Release:        2%{?dist}"))
        reasons = classify(target=target)
        self.assertIn(
            "Release: changed ['%autorelease'] -> ['2%{?dist}']", reasons,
        )

    def test_literal_value_bump_blocks(self) -> None:
        # A literal-to-literal move is the same case the libnma re-import
        # missed: the new value can be smaller than the published NVR (down-
        # grade) or just be a mass-rebuild bump nobody cross-checked.
        pinned = tree(SPEC.replace("Release:        %autorelease", "Release:        12%{?dist}"))
        target = tree(SPEC.replace("Release:        %autorelease", "Release:        13%{?dist}"))
        reasons = classify(local_tree=local(pinned), pinned=pinned, target=target)
        self.assertIn(
            "Release: changed ['12%{?dist}'] -> ['13%{?dist}']", reasons,
        )

    def test_new_patch_and_dropped_build_requires_are_safe(self) -> None:
        target = tree(SPEC.replace("BuildRequires:  gcc, ", "BuildRequires:  ")
                      .replace("Patch0:", "Patch1: cve.patch\nPatch0:"))
        target["cve.patch"] = b"x"
        self.assertEqual(classify(target=target), [])

    def test_utah_local_spec_edit_blocks(self) -> None:
        ours = local(tree(SPEC + "# utah: disable docs\n"))
        self.assertIn("recipe diverges from Fedora: factory edited demo.spec", classify(local_tree=ours))

    def test_utah_local_patch_blocks(self) -> None:
        ours = local({**tree(), "utah.patch": b"x"})
        self.assertIn("recipe diverges from Fedora: factory added utah.patch", classify(local_tree=ours))

    def test_dropped_fedora_patch_blocks(self) -> None:
        ours = local({path: data for path, data in tree().items() if path != "fix.patch"})
        self.assertIn("recipe diverges from Fedora: factory dropped fix.patch", classify(local_tree=ours))

    def test_absent_inert_metadata_is_not_divergence(self) -> None:
        pinned = {**tree(), ".packit.yaml": b"x", "gating.yaml": b"x", "tests/main.fmf": b"x",
                  ".fmf/version": b"1\n"}
        self.assertEqual(classify(local_tree=local(tree()), pinned=pinned), [])

    def test_inert_name_the_spec_uses_is_a_source(self) -> None:
        spec = SPEC.replace("Patch0:", "Source1: README.md\nPatch0:")
        pinned = {**tree(spec), "README.md": b"x"}
        reasons = classify(local_tree=local(tree(spec)), pinned=pinned, target=pinned)
        self.assertIn("recipe diverges from Fedora: factory dropped README.md", reasons)

    def test_changed_sources_blocks(self) -> None:
        target = tree()
        target["sources"] = SOURCES.replace(b"a" * 128, b"b" * 128)
        self.assertIn("Fedora changed `sources`: the source lock would have to move",
                      classify(target=target))

    def test_version_move_blocks(self) -> None:
        reasons = classify(target=tree(SPEC.replace("1.2.3", "1.2.4")))
        self.assertIn("Version: changed ['1.2.3'] -> ['1.2.4']", reasons)

    def test_epoch_appearing_blocks(self) -> None:
        reasons = classify(target=tree(SPEC.replace("Version:", "Epoch: 1\nVersion:")))
        self.assertIn("Epoch: changed [] -> ['1']", reasons)

    def test_added_build_requires_blocks(self) -> None:
        reasons = classify(target=tree(SPEC + "BuildRequires: pkgconfig(libacl), fdupes\n"))
        self.assertIn("adds BuildRequires: fdupes, pkgconfig(libacl)", reasons)

    def test_tightened_version_constraint_is_a_new_requirement(self) -> None:
        reasons = classify(target=tree(SPEC.replace("meson >= 1.0", "meson >= 1.4")))
        self.assertIn("adds BuildRequires: meson >= 1.4", reasons)

    def test_generate_buildrequires_appearing_blocks(self) -> None:
        reasons = classify(target=tree(SPEC + "%generate_buildrequires\n%pyproject_buildrequires\n"))
        self.assertIn("adds %generate_buildrequires", reasons)

    def test_lock_with_local_decision_blocks(self) -> None:
        for key in ("dist_bump", "rebuild_reason", "generate", "dist_git_name", "buildroot_icu77"):
            with self.subTest(key=key):
                reasons = classify(lock={**LOCK, key: True})
                self.assertIn(f"source lock carries Utah-local decisions: {key}", reasons)

    def test_missing_lock_blocks(self) -> None:
        self.assertIn("no source lock", classify(lock=None))

    def test_non_fast_forward_blocks(self) -> None:
        self.assertIn("Koji's commit does not descend from the pinned commit",
                      classify(fast_forward=False))

    def test_non_fedora_provenance_blocks(self) -> None:
        for provenance in ({**PROVENANCE, "branch": "upstream"},
                           {**PROVENANCE, "remote": "https://example.org/demo.git"},
                           {**PROVENANCE, "package": "other"}):
            with self.subTest(provenance=provenance):
                self.assertIn("recipe is not a plain Fedora Rawhide import",
                              classify(provenance=provenance))

    def test_spec_rename_blocks(self) -> None:
        target = tree()
        target["demo2.spec"] = target.pop("demo.spec")
        self.assertIn("spec renamed demo.spec -> demo2.spec", classify(target=target))

    def test_two_specs_block(self) -> None:
        target = {**tree(), "other.spec": b"Name: other\n"}
        self.assertIn("expected exactly one spec file on both commits", classify(target=target))


class HelperTests(unittest.TestCase):
    def test_dependency_items_follow_rpm_grammar(self) -> None:
        self.assertEqual(
            reimport.dependency_items("gcc, meson >= 0.60 pkgconfig(glib-2.0) >= 2.80 (a if b) python3"),
            ["gcc", "meson >= 0.60", "pkgconfig(glib-2.0) >= 2.80", "(a if b)", "python3"],
        )

    def test_build_requires_ignores_trailing_comments(self) -> None:
        self.assertEqual(reimport.build_requires("BuildRequires: gcc # for the C bits\n"), {"gcc"})

    def test_metadata_only_move_is_not_build_relevant(self) -> None:
        pinned = {**tree(), "gating.yaml": b"old"}
        self.assertFalse(reimport.build_relevant(pinned, {**tree(), "gating.yaml": b"new"}))
        self.assertFalse(reimport.build_relevant(pinned, tree()))
        self.assertTrue(reimport.build_relevant(pinned, {**tree(), "new.patch": b"x"}))

    def test_koji_source_parses_the_built_commit(self) -> None:
        match = reimport.KOJI_SOURCE.match("git+https://src.fedoraproject.org/rpms/vid.stab.git#" + "f" * 40)
        self.assertEqual((match.group("package"), match.group("commit")), ("vid.stab", "f" * 40))
        self.assertIsNone(reimport.KOJI_SOURCE.match("git+https://example.org/demo.git#" + "f" * 40))

    def test_one_koji_fault_does_not_cost_the_batch(self) -> None:
        class Answers:
            def __getitem__(self, index):
                if index == 1:
                    raise xmlrpc.client.Fault(1000, "No such entry in table package")
                return [index]

        class Batch:
            def __init__(self, proxy):
                pass

            def __getattr__(self, name):
                return lambda *args: None

            def __call__(self):
                return Answers()

        with mock.patch.object(xmlrpc.client, "MultiCall", Batch):
            results = reimport.multicall(object(), "getLatestBuilds", [("a",), ("b",), ("c",)])
        self.assertEqual(results, [[0], None, [2]])


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, text=True,
    ).strip()


class ReimportSnapshotTests(unittest.TestCase):
    """``import_snapshot`` against a local repository standing in for dist-git."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="reimport-test-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.root)], check=False)
        self.repo = self.root / "dist-git"
        self.repo.mkdir()
        git("init", "-q", "-b", "rawhide", cwd=self.repo)
        (self.repo / "demo.spec").write_text(SPEC)
        (self.repo / "old.patch").write_text("x")
        git("add", "-A", cwd=self.repo)
        git("commit", "-qm", "one", cwd=self.repo)
        self.first = git("rev-parse", "HEAD", cwd=self.repo)
        (self.repo / "old.patch").unlink()
        (self.repo / "new.patch").write_text("y")
        git("add", "-A", cwd=self.repo)
        git("commit", "-qm", "two", cwd=self.repo)
        self.second = git("rev-parse", "HEAD", cwd=self.repo)

    def test_replace_writes_exactly_the_new_tree(self) -> None:
        destination = self.root / "packages" / "demo"
        import_rawhide.import_snapshot(self.repo, "demo", "rawhide", "remote", self.first, destination)
        record = import_rawhide.import_snapshot(
            self.repo, "demo", "rawhide", "remote", self.second, destination, replace=True,
        )
        self.assertEqual(sorted(p.name for p in destination.iterdir()),
                         [".hummingbird-upstream.json", "demo.spec", "new.patch"])
        self.assertEqual(record["commit"], self.second)
        self.assertEqual(json.loads((destination / ".hummingbird-upstream.json").read_text())["tree"],
                         git("rev-parse", f"{self.second}^{{tree}}", cwd=self.repo))

    def test_existing_recipe_is_refused_without_replace(self) -> None:
        destination = self.root / "packages" / "demo"
        import_rawhide.import_snapshot(self.repo, "demo", "rawhide", "remote", self.first, destination)
        with self.assertRaises(SystemExit):
            import_rawhide.import_snapshot(self.repo, "demo", "rawhide", "remote", self.second, destination)

    def test_fast_forward_check(self) -> None:
        self.assertTrue(reimport.is_ancestor(self.repo, self.first, self.second))
        self.assertFalse(reimport.is_ancestor(self.repo, self.second, self.first))

    def test_validate_ref_wants_a_full_commit(self) -> None:
        import_rawhide.validate_ref(self.first)
        for ref in ("HEAD", "rawhide", self.first[:12], self.first.upper(), "--upload-pack=x"):
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    import_rawhide.validate_ref(ref)


if __name__ == "__main__":
    unittest.main()
