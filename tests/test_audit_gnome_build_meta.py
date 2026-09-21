#!/usr/bin/env python3

"""Unit tests for tools/audit_gnome_build_meta.py.

The audit tool must be deterministic and reason about BuildStream includes and
dependency composition deliberately (the issue explicitly rules out a
regex-only scan). These tests exercise the pieces that make it deterministic:
name mapping, secondary sources, dependency categories, includes, feature-option
extraction, release-line comparison and classification.
"""

from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

from tools.audit_gnome_build_meta import (
    ALIGNED,
    NEEDS_REVIEW,
    UNMAPPED,
    Loader,
    _aliases,
    _factory_rev,
    _secondary_sources,
    classify,
    element_patch_sources,
    meson_options,
    release_line,
    resolve_element,
    same_release_line,
    spec_dependencies,
    spec_patches,
    _rpm_base_name,
    build_report,
)

ALIASES = """\
aliases:
  gnome_downloads: https://download.gnome.org/sources/
  gnome: https://gitlab.gnome.org/GNOME/
"""

GCC_FOR_RECC = """\
filename:
- freedesktop-sdk.bst:components/gcc.bst
config:
  digest-environment: RECC_REMOTE_PLATFORM_chrootRootDigest
"""

MUTTER_BST = """\
kind: meson

sources:
- kind: tar
  url: gnome_downloads:mutter/51/mutter-51.0.tar.xz
  ref: 5d28f3ae225692428fcafb96500d673f34328b698b86960c9c1460d0b1d983b3
- kind: git_repo
  url: gnome:gvdb.git
  directory: subprojects/gvdb
  ref: b54bc5da25127ef416858a3ad92e57159ff565b3

build-depends:
- (@): include/gcc-for-recc.yml
- buildsystems/meson.bst
- core-deps/python-argcomplete.bst

runtime-depends:
- core/gnome-control-center.bst

depends:
- sdk/glib.bst
- sdk/gobject-introspection.bst
- core/gnome-desktop.bst

variables:
  meson-local: >-
    -Dxwayland_initfd=enabled
    -Dprofiler=true
"""

GVFS_DAEMON_BST = """\
kind: filter

build-depends:
- sdk-deps/gvfs.bst

runtime-depends:
- sdk/glib.bst
"""

MOZJS_BST = """\
kind: manual

sources:
- kind: tar
  url: gnome_downloads:mozjs/128/mozjs-128.0.tar.xz
  ref: 0d28f3ae225692428fcafb96500d673f34328b698b86960c9c1460d0b1d983b3
- kind: patch
  path: files/mozjs/fix-build.patch
"""

PIN = {
    "schema": 1,
    "source": {
        "name": "gnome-build-meta",
        "url": "https://gitlab.gnome.org/GNOME/gnome-build-meta.git",
        "release_tag": "51.0",
        "release_commit": "a50b8c9de35f51c6a646c8178cde3c2c176725b6",
    },
    "element_path": {"project_conf": "project.conf", "root": "elements"},
    "factory_alias": {},
    "mapping": {
        "mutter": "core/mutter.bst",
        "gvfs-daemon": "core/gvfs-daemon.bst",
    },
    "unmapped": [],
}


def write(root: Path, rel: str, content: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def make_gbm_tree(root: Path) -> Path:
    write(root, "include/aliases.yml", ALIASES)
    write(root, "include/gcc-for-recc.yml", GCC_FOR_RECC)
    write(root, "elements/core/mutter.bst", MUTTER_BST)
    write(root, "elements/core/gvfs-daemon.bst", GVFS_DAEMON_BST)
    write(root, "elements/sdk/mozjs.bst", MOZJS_BST)
    return root


class ReleaseLineTests(unittest.TestCase):
    def test_gnome_cycle_uses_single_major(self) -> None:
        self.assertEqual(release_line("51.0"), "51")
        self.assertEqual(release_line("51.beta"), "51")

    def test_library_uses_major_minor(self) -> None:
        self.assertEqual(release_line("1.10.beta.1"), "1.10")
        self.assertEqual(release_line("4.23.3"), "4.23")
        self.assertEqual(release_line("2.62.3"), "2.62")

    def test_same_release_line(self) -> None:
        self.assertTrue(same_release_line("51.beta", "51.0"))
        self.assertTrue(same_release_line("1.10.beta.1", "1.10.0"))
        self.assertTrue(same_release_line("3.12.beta", "3.12.0"))
        self.assertFalse(same_release_line("4.23.3", "4.24.0"))
        self.assertFalse(same_release_line("1.89.2", "1.90.0"))
        self.assertFalse(same_release_line("", "1.0"))

    def test_rpm_base_name_strips_trailing_digits(self) -> None:
        self.assertEqual(_rpm_base_name("gnome-desktop3"), "gnome-desktop")
        self.assertEqual(_rpm_base_name("gtk4"), "gtk")
        self.assertEqual(_rpm_base_name("gdk-pixbuf2"), "gdk-pixbuf")
        self.assertEqual(_rpm_base_name("librsvg2"), "librsvg")
        self.assertEqual(_rpm_base_name("nautilus"), "nautilus")


class ExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_name_mapping_from_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pin_path = write(Path(tmp), "pin.json", json.dumps(PIN))
            from tools.audit_gnome_build_meta import load_pin
            pin = load_pin(pin_path)
            self.assertEqual(pin["mapping"]["mutter"], "core/mutter.bst")

    def test_resolve_includes_and_kind(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(el.kind, "meson")
        # include/gcc-for-recc.yml is resolved and recorded, not treated as a dep.
        self.assertIn("include/gcc-for-recc.yml", el.includes)
        self.assertNotIn("freedesktop-sdk.bst:components/gcc.bst", el.build_depends)
        self.assertIn("buildsystems/meson.bst", el.build_depends)

    def test_primary_source_expands_alias(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(
            el.primary_source["url"],
            "https://download.gnome.org/sources/mutter/51/mutter-51.0.tar.xz",
        )

    def test_secondary_sources_captures_wrap(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        secondaries = el.sources[1:]
        self.assertEqual(len(secondaries), 1)
        self.assertEqual(secondaries[0]["directory"], "subprojects/gvdb")
        self.assertEqual(secondaries[0]["kind"], "git_repo")

    def test_dependency_categories_split(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertEqual(el.runtime_depends, ["core/gnome-control-center.bst"])
        self.assertIn("sdk/glib.bst", el.depends)
        self.assertIn("core/gnome-desktop.bst", el.depends)

    def test_feature_options_from_variables(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        self.assertIn("meson-local", el.variables)
        self.assertIn("profiler=true", el.variables["meson-local"])

    def test_filter_element_has_no_sources(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/gvfs-daemon.bst")
        self.assertEqual(el.kind, "filter")
        self.assertEqual(el.sources, [])

    def test_patch_source_uses_path_key(self) -> None:
        # BuildStream's patch plugin declares its file in `path:`, not
        # `local:`/`url:`; reading the wrong key recorded an empty patch name.
        el = resolve_element(self.loader, self.aliases, "elements/sdk/mozjs.bst")
        self.assertEqual(
            element_patch_sources(el, self.aliases),
            ["files/mozjs/fix-build.patch"],
        )

    def test_patch_source_is_not_a_secondary_source(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/sdk/mozjs.bst")
        self.assertEqual(_secondary_sources(el, self.aliases), [])

    def test_meson_options_ignore_cflags_defines_and_prose(self) -> None:
        # -D tokens outside a meson invocation are not feature flags.
        spec = (
            "Name: gtk4\nVersion: 4.20.0\n"
            "License: LGPL-2.1-or-later AND Unicode-DFS-2016\n"
            "export CFLAGS=\"$CFLAGS -DG_DISABLE_ASSERT -DG_DISABLE_CAST_CHECKS\"\n"
            "%meson \\\n"
            "  -Dbroadway-backend=true \\\n"
            "%if %{with wayland}\n"
            "  -Dwayland-backend=true \\\n"
            "%endif\n"
            "  %{nil}\n"
        )
        self.assertEqual(
            meson_options(spec),
            {"broadway-backend": "true", "wayland-backend": "true"},
        )

    def test_meson_options_strip_rpm_macro_closing_brace(self) -> None:
        spec = "Name: librsvg2\n%meson %{?rhel:-Davif=disabled}\n"
        self.assertEqual(meson_options(spec), {"avif": "disabled"})

    def test_cmake_flag_macros_are_expanded(self) -> None:
        # evolution-data-server builds CMake flags in %define macros and passes
        # them to %cmake; reading only the invocation block would drop them.
        spec = (
            "Name: evolution-data-server\n"
            "%if %{ldap_support}\n"
            "%define ldap_flags -DWITH_OPENLDAP=ON\n"
            "%else\n"
            "%define ldap_flags -DWITH_OPENLDAP=OFF\n"
            "%endif\n"
            "export CFLAGS=\"$RPM_OPT_FLAGS -DLDAP_DEPRECATED\"\n"
            "%cmake -DENABLE_SMIME=ON \\\n"
            "  %ldap_flags \\\n"
            "  %{nil}\n"
        )
        opts = meson_options(spec)
        self.assertEqual(opts.get("ENABLE_SMIME"), "ON")
        self.assertEqual(opts.get("WITH_OPENLDAP"), "ON")
        self.assertNotIn("LDAP_DEPRECATED", opts)

    def test_spec_dependency_edges_are_extracted(self) -> None:
        spec = (
            "Name: mutter\nVersion: 51.beta\n"
            "BuildRequires: meson >= 1.4.0\n"
            "BuildRequires: pkgconfig(glib-2.0), pkgconfig(gtk4)\n"
            "Requires: gsettings-desktop-schemas\n"
            "Requires(post): /sbin/ldconfig\n"
        )
        deps = spec_dependencies(spec)
        self.assertEqual(
            deps["build_requires"],
            ["meson", "pkgconfig(glib-2.0)", "pkgconfig(gtk4)"],
        )
        self.assertEqual(
            deps["requires"], ["/sbin/ldconfig", "gsettings-desktop-schemas"]
        )

    def test_spec_features_and_patches(self) -> None:
        spec = (
            "Name: mutter\nVersion: 51.beta\n"
            "Patch: linux-fix.patch\n"
            "%meson \\\n"
            "  -Dprofiler=true \\\n"
            "  -Dxwayland_initfd=enabled \\\n"
            "  %{nil}\n"
        )
        opts = meson_options(spec)
        self.assertEqual(opts.get("profiler"), "true")
        self.assertEqual(opts.get("xwayland_initfd"), "enabled")
        self.assertEqual(spec_patches(spec), ["linux-fix.patch"])


class ClassifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_aligned_same_line(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, reason = classify(
            el, {"name": "mutter", "patches": []}, "51.beta"
        )
        self.assertEqual(cls, ALIGNED)
        self.assertIn("51", reason)

    def test_patch_drift_is_needs_review(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, reason = classify(
            el, {"name": "mutter", "patches": ["local.patch"]}, "51.beta"
        )
        self.assertEqual(cls, NEEDS_REVIEW)
        self.assertIn("patch", reason)

    def test_line_mismatch_is_needs_review(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/mutter.bst")
        cls, _ = classify(el, {"name": "mutter", "patches": []}, "45.0")
        self.assertEqual(cls, NEEDS_REVIEW)

    def test_missing_element_is_unmapped(self) -> None:
        cls, _ = classify(None, {"name": "mutter", "patches": []}, "51.0")
        self.assertEqual(cls, UNMAPPED)

    def test_filter_element_aligned_membership(self) -> None:
        el = resolve_element(self.loader, self.aliases, "elements/core/gvfs-daemon.bst")
        cls, _ = classify(el, {"name": "gvfs", "patches": []}, "1.61.91")
        self.assertEqual(cls, ALIGNED)


class PatchDriftTests(unittest.TestCase):
    """Both sides carrying *different* patches is drift, not alignment."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)
        self.el = resolve_element(self.loader, self.aliases, "elements/sdk/mozjs.bst")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_differing_patch_sets_are_needs_review(self) -> None:
        cls, reason = classify(
            self.el, {"name": "mozjs", "patches": ["fedora-only.patch"]}, "128.0"
        )
        self.assertEqual(cls, NEEDS_REVIEW)
        self.assertIn("both sides carry patches", reason)

    def test_same_patch_basename_is_not_drift(self) -> None:
        # gbm names a project-relative path, the spec a bare Patch: filename.
        cls, _ = classify(
            self.el, {"name": "mozjs", "patches": ["fix-build.patch"]}, "128.0"
        )
        self.assertEqual(cls, ALIGNED)


class FactoryRevTests(unittest.TestCase):
    """Provenance must name the factory checkout, not the caller's CWD."""

    def test_rev_is_read_from_the_factory_checkout(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        if not (repo_root / ".git").exists():
            self.skipTest("factory checkout is not a git repository")
        expected = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        with tempfile.TemporaryDirectory() as outside:
            cwd = os.getcwd()
            os.chdir(outside)
            try:
                self.assertEqual(_factory_rev(), expected)
            finally:
                os.chdir(cwd)


class ReportTests(unittest.TestCase):
    def test_build_report_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_gbm_tree(root)
            pin_path = write(root, "pin.json", json.dumps(PIN))
            sources = {
                "mutter": {"name": "mutter", "version": "51.beta", "filename": "mutter-51.beta.tar.xz"},
                "gvfs": {"name": "gvfs", "version": "1.61.91", "filename": "gvfs-1.61.91.tar.xz"},
            }
            packages_dir = write(root, "packages/mutter/mutter.spec",
                                 "Name: mutter\nVersion: 51.beta\n%meson\n")

            loader = Loader(root)
            report = build_report(
                json.loads(pin_path.read_text()), loader,
                _aliases(loader), sources, packages_dir.parent,
            )
            self.assertEqual(len(report["packages"]), 2)
            classes = {p["rpm_name"]: p["classification"] for p in report["packages"]}
            self.assertEqual(classes["mutter"], ALIGNED)


class FailClosedTests(unittest.TestCase):
    """The audit must not write a plausible all-unmapped report when the checkout is unusable."""

    def test_non_git_checkout_requires_no_verify(self) -> None:
        from tools.audit_gnome_build_meta import _verify_checkout, Loader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No .git directory — not a git checkout.
            loader = Loader(root)
            with self.assertRaises(SystemExit) as cm:
                _verify_checkout(loader, "a50b8c9de35f51c6a646c8178cde3c2c176725b6")
            self.assertIn("not a git repository", str(cm.exception))

    def test_non_git_checkout_passes_with_no_verify(self) -> None:
        # main() with --no-verify should allow an exported snapshot.
        import json as _json
        from tools.audit_gnome_build_meta import main as audit_main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Build a minimal gbm tree that will resolve at least one element.
            make_gbm_tree(root)
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": "a50b8c9de35f51c6a646c8178cde3c2c176725b6"},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"mutter": "core/mutter.bst"},
                "factory_alias": {},
            }
            pin_path = root / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = root / "sources.json"
            sources_path.write_text(_json.dumps({"packages": [{"name": "mutter", "version": "51.beta"}]}))
            pkg = root / "packages" / "mutter"
            pkg.mkdir(parents=True)
            (pkg / "mutter.spec").write_text("Name: mutter\nVersion: 51.beta\n")
            json_out = Path(tmp) / "out.json"
            md_out = Path(tmp) / "out.md"
            rc = audit_main([
                "--gbm-dir", str(root),
                "--pin", str(pin_path),
                "--sources", str(sources_path),
                "--packages-dir", str(root / "packages"),
                "--json-out", str(json_out),
                "--markdown-out", str(md_out),
                "--no-verify",
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(json_out.exists())

    def test_missing_elements_root_fails(self) -> None:
        from tools.audit_gnome_build_meta import main as audit_main
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create a git repo but no elements/ directory
            import subprocess as _sp
            _sp.run(["git", "init", str(root)], capture_output=True, check=True)
            _sp.run(["git", "-C", str(root), "config", "user.email", "test@test"], capture_output=True)
            _sp.run(["git", "-C", str(root), "config", "user.name", "test"], capture_output=True)
            (root / "dummy").write_text("x")
            _sp.run(["git", "-C", str(root), "add", "."], capture_output=True)
            _sp.run(["git", "-C", str(root), "commit", "-m", "init"], capture_output=True)
            # Now init repo at the pinned commit would fail verification, so use --no-verify
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": _sp.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"mutter": "core/mutter.bst"},
                "factory_alias": {},
            }
            pin_path = root / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = root / "sources.json"
            sources_path.write_text(_json.dumps({"packages": [{"name": "mutter", "version": "51.beta"}]}))
            json_out = Path(tmp) / "out.json"
            md_out = Path(tmp) / "out.md"
            rc = audit_main([
                "--gbm-dir", str(root),
                "--pin", str(pin_path),
                "--sources", str(sources_path),
                "--packages-dir", str(root / "packages"),
                "--json-out", str(json_out),
                "--markdown-out", str(md_out),
                "--no-verify",
            ])
            self.assertEqual(rc, 2)
            self.assertFalse(json_out.exists())

    def test_zero_elements_resolved_fails(self) -> None:
        from tools.audit_gnome_build_meta import main as audit_main
        import json as _json, subprocess as _sp
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _sp.run(["git", "init", str(root)], capture_output=True, check=True)
            _sp.run(["git", "-C", str(root), "config", "user.email", "test@test"], capture_output=True)
            _sp.run(["git", "-C", str(root), "config", "user.name", "test"], capture_output=True)
            (root / "elements").mkdir(parents=True)
            (root / "dummy").write_text("x")
            _sp.run(["git", "-C", str(root), "add", "."], capture_output=True)
            _sp.run(["git", "-C", str(root), "commit", "-m", "init"], capture_output=True)
            head = _sp.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": head},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"mutter": "core/mutter.bst"},
                "factory_alias": {},
            }
            pin_path = root / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = root / "sources.json"
            sources_path.write_text(_json.dumps({"packages": [{"name": "mutter", "version": "51.beta"}]}))
            json_out = Path(tmp) / "out.json"
            md_out = Path(tmp) / "out.md"
            rc = audit_main([
                "--gbm-dir", str(root),
                "--pin", str(pin_path),
                "--sources", str(sources_path),
                "--packages-dir", str(root / "packages"),
                "--json-out", str(json_out),
                "--markdown-out", str(md_out),
                # not using --no-verify, so _verify_checkout will pass (git repo at right commit)
            ])
            self.assertEqual(rc, 2)
            self.assertFalse(json_out.exists())


class IncludeIsolationTests(unittest.TestCase):
    """Cross-element include contamination: Loader.seen must be per-element."""

    def test_includes_are_per_element(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Two elements each including a different file.
            write(root, "include/aliases.yml", ALIASES)
            write(root, "include/one.yml", "variables:\n  one: true\n")
            write(root, "include/two.yml", "variables:\n  two: true\n")
            write(root, "elements/core/a.bst", "kind: meson\n(@): include/one.yml\nvariables:\n  a: 1\n")
            write(root, "elements/core/b.bst", "kind: meson\n(@): include/two.yml\nvariables:\n  b: 1\n")
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": "a50b8c9de35f51c6a646c8178cde3c2c176725b6"},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"a": "core/a.bst", "b": "core/b.bst"},
                "factory_alias": {},
            }
            sources = {
                "a": {"name": "a", "version": "1.0"},
                "b": {"name": "b", "version": "1.0"},
            }
            loader = Loader(root)
            report = build_report(pin, loader, _aliases(loader), sources, root / "packages")
            by_name = {e["rpm_name"]: e for e in report["packages"]}
            # Each element should only report its own include, not the accumulated set.
            self.assertEqual(by_name["a"]["gnome_build_meta"]["includes"], ["include/one.yml"])
            self.assertEqual(by_name["b"]["gnome_build_meta"]["includes"], ["include/two.yml"])


class MergeTests(unittest.TestCase):
    def test_merge_handles_overlay_operator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loader = Loader(root)
            base = {"variables": {"a": "1"}, "depends": ["x.bst"]}
            over = {"(>)variables": {"b": "2"}, "(>)depends": ["y.bst"]}
            merged = loader._merge(base, over)
            # (>)variables should have been merged into variables, not dropped.
            self.assertIn("variables", merged)
            self.assertEqual(merged["variables"]["a"], "1")
            self.assertEqual(merged["variables"]["b"], "2")
            self.assertIn("y.bst", merged["depends"])
            self.assertIn("x.bst", merged["depends"])


if __name__ == "__main__":
    unittest.main()

