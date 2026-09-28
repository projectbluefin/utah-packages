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
    ACTIONABLE,
    ALIGNED,
    INTENTIONAL_FEDORA,
    NEEDS_REVIEW,
    UNMAPPED,
    Loader,
    _aliases,
    _factory_rev,
    _gbm_version,
    _secondary_sources,
    _unaccounted_gnome_sources,
    classify,
    dependency_comparison,
    element_patch_sources,
    feature_comparison,
    gbm_feature_options,
    load_pin,
    meson_options,
    release_line,
    render_markdown,
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

    def test_missing_git_binary_fails_closed(self) -> None:
        from tools.audit_gnome_build_meta import _verify_checkout, Loader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loader = Loader(root)
            original_run = subprocess.run

            def no_git(*args, **kwargs):
                raise FileNotFoundError(2, "No such file or directory: 'git'")

            subprocess.run = no_git
            try:
                with self.assertRaises(SystemExit) as cm:
                    _verify_checkout(loader, "a50b8c9de35f51c6a646c8178cde3c2c176725b6")
            finally:
                subprocess.run = original_run
            self.assertIn("--no-verify", str(cm.exception))

    def test_dirty_checkout_fails_closed(self) -> None:
        from tools.audit_gnome_build_meta import _verify_checkout, Loader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "a@b.c"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
            (root / "element.bst").write_text("kind: meson\n")
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "--no-verify", "-qm", "pin"], check=True)
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            loader = Loader(root)
            self.assertEqual(_verify_checkout(loader, head), head)

            # A local modification means the tree is no longer the pinned commit.
            (root / "element.bst").write_text("kind: autotools\n")
            with self.assertRaises(SystemExit) as cm:
                _verify_checkout(loader, head)
            self.assertIn("local modifications", str(cm.exception))
            self.assertIn("element.bst", str(cm.exception))

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
            pin_path = Path(tmp) / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = Path(tmp) / "sources.json"
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
            _sp.run(["git", "-C", str(root), "commit", "--no-verify", "-m", "init"], capture_output=True, check=True)
            # Now init repo at the pinned commit would fail verification, so use --no-verify
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": _sp.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"mutter": "core/mutter.bst"},
                "factory_alias": {},
            }
            pin_path = Path(tmp) / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = Path(tmp) / "sources.json"
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
            # The pin/sources files live outside the checkout: an untracked file
            # inside it would (correctly) be reported as a dirty working tree.
            root = Path(tmp) / "gbm"
            root.mkdir()
            _sp.run(["git", "init", str(root)], capture_output=True, check=True)
            _sp.run(["git", "-C", str(root), "config", "user.email", "test@test"], capture_output=True)
            _sp.run(["git", "-C", str(root), "config", "user.name", "test"], capture_output=True)
            (root / "elements").mkdir(parents=True)
            (root / "dummy").write_text("x")
            _sp.run(["git", "-C", str(root), "add", "."], capture_output=True)
            _sp.run(["git", "-C", str(root), "commit", "--no-verify", "-m", "init"], capture_output=True, check=True)
            head = _sp.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": head},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"mutter": "core/mutter.bst"},
                "factory_alias": {},
            }
            pin_path = Path(tmp) / "pin.json"
            pin_path.write_text(_json.dumps(pin))
            sources_path = Path(tmp) / "sources.json"
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

    def test_shared_include_is_reported_for_every_element(self) -> None:
        # A include both elements pull in must appear on both, not only on the
        # first element that happened to resolve it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "include/aliases.yml", ALIASES)
            write(root, "include/gcc-for-recc.yml", GCC_FOR_RECC)
            for name in ("a", "b"):
                write(root, f"elements/core/{name}.bst",
                      "kind: meson\nbuild-depends:\n- (@): include/gcc-for-recc.yml\n")
            pin = {
                "schema": 1,
                "source": {"release_tag": "51.0", "release_commit": "a50b8c9"},
                "element_path": {"project_conf": "project.conf", "root": "elements"},
                "mapping": {"a": "core/a.bst", "b": "core/b.bst"},
                "factory_alias": {},
            }
            sources = {"a": {"name": "a", "version": "1.0"},
                       "b": {"name": "b", "version": "1.0"}}
            loader = Loader(root)
            report = build_report(pin, loader, _aliases(loader), sources, root / "packages")
            by_name = {e["rpm_name"]: e for e in report["packages"]}
            for name in ("a", "b"):
                self.assertEqual(
                    by_name[name]["gnome_build_meta"]["includes"],
                    ["include/gcc-for-recc.yml"],
                )


class GitRefVersionTests(unittest.TestCase):
    """git_repo elements must not skip the release-line comparison silently."""

    def test_version_read_from_git_describe_ref(self) -> None:
        primary = {
            "kind": "git_repo",
            "url": "https://gitlab.freedesktop.org/cairo/cairo.git",
            "ref": "1.18.4-0-g4541e0cd3a751b85e52e2a83d02ac6145a5efa85",
        }
        self.assertEqual(_gbm_version(primary), "1.18.4")

    def test_version_read_from_plain_tag_ref(self) -> None:
        primary = {"kind": "git_repo", "url": "gnome:gvdb.git", "ref": "v4.23.0"}
        self.assertEqual(_gbm_version(primary), "4.23.0")

    def test_bare_commit_sha_is_not_a_version(self) -> None:
        primary = {
            "kind": "git_repo",
            "url": "gnome:gvdb.git",
            "ref": "b54bc5da25127ef416858a3ad92e57159ff565b3",
        }
        self.assertIsNone(_gbm_version(primary))

    def test_git_repo_line_mismatch_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "include/aliases.yml", ALIASES)
            write(
                root, "elements/sdk/cairo.bst",
                "kind: meson\n"
                "sources:\n"
                "- kind: git_repo\n"
                "  url: https://gitlab.freedesktop.org/cairo/cairo.git\n"
                "  ref: 1.18.4-0-g4541e0cd3a751b85e52e2a83d02ac6145a5efa85\n",
            )
            loader = Loader(root)
            el = resolve_element(loader, _aliases(loader), "elements/sdk/cairo.bst")
            cls, reason = classify(el, {"name": "cairo", "patches": []}, "1.20.0")
            self.assertEqual(cls, NEEDS_REVIEW)
            self.assertIn("release line", reason)

    def test_unversioned_source_says_not_compared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "include/aliases.yml", ALIASES)
            write(
                root, "elements/sdk/gvdb.bst",
                "kind: meson\n"
                "sources:\n"
                "- kind: git_repo\n"
                "  url: gnome:gvdb.git\n"
                "  ref: b54bc5da25127ef416858a3ad92e57159ff565b3\n",
            )
            loader = Loader(root)
            el = resolve_element(loader, _aliases(loader), "elements/sdk/gvdb.bst")
            cls, reason = classify(el, {"name": "gvdb", "patches": []}, "0.9")
            self.assertEqual(cls, ALIGNED)
            self.assertIn("NOT compared", reason)


class GnomeOwnershipTests(unittest.TestCase):
    """Every GNOME-owned factory source is mapped or explicitly unmapped."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_gbm_tree(self.root)
        # A Fedora-mirrored but GNOME-owned module: the factory url points at
        # the lookaside, the gbm element pulls from download.gnome.org.
        write(
            self.root, "elements/sdk/libsecret.bst",
            "kind: meson\nsources:\n- kind: tar\n"
            "  url: gnome_downloads:libsecret/0.21/libsecret-0.21.7.tar.xz\n"
            "  ref: deadbeef\n",
        )
        self.loader = Loader(self.root)
        self.aliases = _aliases(self.loader)
        self.sources = {
            "mutter": {"name": "mutter", "version": "51.beta"},
            "gdm": {
                "name": "gdm", "version": "51.beta",
                "url": "https://download.gnome.org/sources/gdm/51/gdm-51.beta.tar.xz",
            },
            "libsecret": {
                "name": "libsecret", "version": "0.21.7",
                "url": "https://src.fedoraproject.org/repo/pkgs/rpms/libsecret/x.tar.xz",
            },
            "fish": {
                "name": "fish", "version": "4.6.0",
                "url": "https://github.com/fish-shell/fish-shell/releases/4.6.0.tar.xz",
            },
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gnome_sources_missing_from_both_lists_are_reported(self) -> None:
        found = _unaccounted_gnome_sources(
            PIN, self.sources, self.loader, self.aliases
        )
        names = {item["name"] for item in found}
        self.assertIn("gdm", names)            # gnome.org url in the factory lock
        self.assertIn("libsecret", names)      # Fedora-mirrored, gbm builds from gnome.org
        self.assertNotIn("mutter", names)      # mapped
        self.assertNotIn("fish", names)        # not GNOME-owned

    def test_explicitly_unmapped_sources_are_accounted_for(self) -> None:
        pin = dict(PIN)
        pin["unmapped"] = [
            {"name": "gdm", "reason": "outside the initial mapping scope"},
            {"name": "libsecret", "reason": "outside the initial mapping scope"},
        ]
        found = _unaccounted_gnome_sources(
            pin, self.sources, self.loader, self.aliases
        )
        self.assertEqual(found, [])

    def test_committed_pin_accounts_for_every_listed_gnome_source(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        pin = json.loads((repo_root / "config" / "gnome-build-meta.json").read_text())
        accounted = set(pin["mapping"]) | {u["name"] for u in pin["unmapped"]}
        for name in ("adwaita-fonts", "gdm", "gnome-tweaks", "zenity",
                     "libcloudproviders", "libgexiv2", "gnome-ponytail-daemon",
                     "gcr", "gnome-keyring", "libsecret", "libsoup3", "json-glib",
                     "graphene", "adwaita-icon-theme", "gobject-introspection",
                     "tecla", "libgweather"):
            self.assertIn(name, accounted)
        for entry in pin["unmapped"]:
            self.assertTrue(entry.get("reason"), entry["name"])


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


class PinConfigTests(unittest.TestCase):
    """config/gnome-build-meta.json must map distinct GNOME modules distinctly."""

    def test_tinysparql_is_not_aliased_to_localsearch(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        pin = json.loads((repo_root / "config/gnome-build-meta.json").read_text())
        # tinysparql (ex-tracker) and localsearch (ex-tracker-miners) are
        # separate modules; aliasing them would compare localsearch against
        # itself and report a comparison that never happened.
        self.assertNotIn("tinysparql", pin.get("factory_alias", {}))
        self.assertEqual(pin["mapping"]["tinysparql"], "sdk/tinysparql.bst")
        self.assertEqual(pin["mapping"]["localsearch"], "core-deps/localsearch.bst")


class FeatureComparisonTests(unittest.TestCase):
    """Feature options must be diffed, not dumped side by side in two shapes."""

    def test_gbm_variable_string_is_parsed_into_options(self) -> None:
        options = gbm_feature_options(
            {"meson-local": "-Dxwayland_initfd=enabled -Dprofiler=true"}
        )
        self.assertEqual(
            options, {"xwayland_initfd": "enabled", "profiler": "true"}
        )

    def test_conflicting_option_value_is_reported(self) -> None:
        diff = feature_comparison(
            {"meson-local": "-Dprofiler=false"}, {"profiler": "true"}
        )
        self.assertEqual(
            diff["conflicting"],
            [{
                "option": "profiler",
                "gbm_option": "profiler",
                "gbm_value": "false",
                "factory_value": "true",
            }],
        )

    def test_true_and_enabled_are_not_a_conflict(self) -> None:
        diff = feature_comparison({"meson-local": "-Dprofiler=true"}, {"profiler": "enabled"})
        self.assertEqual(diff["conflicting"], [])
        self.assertEqual(len(diff["same_value"]), 1)

    def test_subproject_qualifier_is_ignored_when_matching(self) -> None:
        diff = feature_comparison(
            {"meson-local": "-Dextensions-tool:bash_completion=disabled"},
            {"bash_completion": "enabled"},
        )
        self.assertEqual(
            [item["gbm_option"] for item in diff["conflicting"]],
            ["extensions-tool:bash_completion"],
        )

    def test_one_sided_options_are_listed_per_side(self) -> None:
        diff = feature_comparison(
            {"meson-local": "-Dprofiler=true"}, {"documentation": "true"}
        )
        self.assertEqual(diff["only_in_gbm"], ["profiler"])
        self.assertEqual(diff["only_in_factory"], ["documentation"])

    def test_conflicting_option_makes_the_entry_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_gbm_tree(Path(tmp))
            loader = Loader(root)
            el = resolve_element(loader, _aliases(loader), "elements/core/mutter.bst")
            cls, reason = classify(
                el, {"name": "mutter", "patches": []}, "51.0", {"profiler": "false"}
            )
            self.assertEqual(cls, NEEDS_REVIEW)
            self.assertIn("-Dprofiler", reason)


def _StubElement(build_depends: list[str]):
    """A resolved element carrying only the dependency edges under test."""
    from tools.audit_gnome_build_meta import Element

    return Element(
        path="stub.bst", kind="meson", sources=[], variables={},
        build_depends=list(build_depends), runtime_depends=[], depends=[],
        includes=[], extensions=[], primary_source=None,
    )


class DependencyComparisonTests(unittest.TestCase):
    def test_gbm_edges_match_pkgconfig_and_devel_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_gbm_tree(Path(tmp))
            loader = Loader(root)
            el = resolve_element(loader, _aliases(loader), "elements/core/mutter.bst")
            result = dependency_comparison(
                el,
                {
                    "build_requires": ["pkgconfig(glib-2.0)", "gobject-introspection-devel"],
                    "requires": ["gnome-desktop3"],
                },
            )
            self.assertIn("sdk/glib.bst", result["matched_in_factory"])
            self.assertIn("sdk/gobject-introspection.bst", result["matched_in_factory"])
            self.assertIn("core/gnome-desktop.bst", result["matched_in_factory"])
            self.assertIn("core/gnome-control-center.bst", result["gbm_only"])

    def test_no_element_yields_empty_comparison(self) -> None:
        result = dependency_comparison(None, {"build_requires": ["glib2-devel"]})
        self.assertEqual(result["gbm_edges"], 0)
        self.assertEqual(result["gbm_only"], [])

    def test_split_api_dependency_is_not_collapsed(self) -> None:
        from tools.audit_gnome_build_meta import _gbm_dep_key, _rpm_dep_key

        self.assertEqual(_gbm_dep_key("sdk/gtk+-3.bst"), ("gtk", "3"))
        self.assertEqual(_gbm_dep_key("sdk/gtk.bst"), ("gtk", ""))
        self.assertEqual(_rpm_dep_key("gtk3-devel"), ("gtk", "3"))
        self.assertEqual(_rpm_dep_key("pkgconfig(gtk4)"), ("gtk", "4"))
        self.assertEqual(_rpm_dep_key("pkgconfig(libsoup-3.0)"), ("libsoup", "3"))

        gtk3_only = dependency_comparison(
            _StubElement(["sdk/gtk+-3.bst", "sdk/libsoup2.bst"]),
            {"build_requires": ["pkgconfig(gtk4)", "pkgconfig(libsoup-3.0)"]},
        )
        self.assertEqual(gtk3_only["matched_in_factory"], [])
        self.assertEqual(
            gtk3_only["gbm_only"], ["sdk/gtk+-3.bst", "sdk/libsoup2.bst"]
        )

        gtk3_match = dependency_comparison(
            _StubElement(["sdk/gtk+-3.bst"]),
            {"build_requires": ["gtk3-devel"]},
        )
        self.assertEqual(gtk3_match["matched_in_factory"], ["sdk/gtk+-3.bst"])

    def test_api_stated_on_one_side_still_matches(self) -> None:
        # glib2-devel vs the gbm element glib, gnome-desktop3 vs gnome-desktop.
        result = dependency_comparison(
            _StubElement(["sdk/glib.bst", "core/gnome-desktop.bst"]),
            {"build_requires": ["glib2-devel"], "requires": ["gnome-desktop3"]},
        )
        self.assertEqual(
            result["matched_in_factory"],
            ["core/gnome-desktop.bst", "sdk/glib.bst"],
        )


class SecondarySourceAliasTests(unittest.TestCase):
    def test_secondary_source_url_is_alias_expanded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_gbm_tree(Path(tmp))
            loader = Loader(root)
            aliases = _aliases(loader)
            el = resolve_element(loader, aliases, "elements/core/mutter.bst")
            secondaries = _secondary_sources(el, aliases)
            self.assertEqual(len(secondaries), 1)
            self.assertEqual(
                secondaries[0]["url"], "https://gitlab.gnome.org/GNOME/gvdb.git"
            )


class ClassificationOverrideTests(unittest.TestCase):
    """A reviewer decision must survive a re-run, and must not mask new drift."""

    def _pin_with_override(self, override: dict) -> dict:
        pin = json.loads(json.dumps(PIN))
        pin["classification_overrides"] = {"mutter": override}
        return pin

    def _report(self, root: Path, pin: dict, spec: str) -> dict:
        make_gbm_tree(root)
        sources = {
            "mutter": {"name": "mutter", "version": "51.0", "filename": "mutter-51.0.tar.xz"},
            "gvfs": {"name": "gvfs", "version": "1.61.91", "filename": "gvfs-1.61.91.tar.xz"},
        }
        packages_dir = write(root, "packages/mutter/mutter.spec", spec)
        loader = Loader(root)
        return build_report(
            pin, loader, _aliases(loader), sources, packages_dir.parents[1]
        )

    def test_override_applies_to_a_needs_review_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pin = self._pin_with_override({
                "classification": INTENTIONAL_FEDORA,
                "reason": "Fedora keeps the profiler enabled",
            })
            report = self._report(
                Path(tmp), pin,
                "Name: mutter\nVersion: 51.0\n%meson -Dprofiler=false\n",
            )
            entry = next(e for e in report["packages"] if e["rpm_name"] == "mutter")
            self.assertEqual(entry["auto_classification"], NEEDS_REVIEW)
            self.assertEqual(entry["classification"], INTENTIONAL_FEDORA)
            self.assertEqual(entry["reason"], "Fedora keeps the profiler enabled")
            self.assertIn("-Dprofiler", entry["auto_reason"])

    def test_stale_override_is_ignored_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pin = self._pin_with_override({
                "classification": ACTIONABLE,
                "reason": "recorded when mutter still drifted",
            })
            report = self._report(
                Path(tmp), pin, "Name: mutter\nVersion: 51.0\n%meson\n"
            )
            entry = next(e for e in report["packages"] if e["rpm_name"] == "mutter")
            self.assertEqual(entry["classification"], ALIGNED)
            self.assertIsNone(entry["classification_override"])
            self.assertTrue(
                any("ignored" in note for note in entry["notes"]), entry["notes"]
            )

    def test_override_is_rendered_in_the_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pin = self._pin_with_override({
                "classification": INTENTIONAL_FEDORA,
                "reason": "Fedora keeps the profiler enabled",
            })
            report = self._report(
                Path(tmp), pin,
                "Name: mutter\nVersion: 51.0\n%meson -Dprofiler=false\n",
            )
            text = render_markdown(report)
            self.assertIn("Reviewer override", text)
            self.assertIn("Fedora keeps the profiler enabled", text)
            self.assertIn("Feature option conflict", text)
            self.assertNotIn("see JSON report for the full diff", text)

    def test_invalid_override_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for override, field in (
                ({"classification": "aligned", "reason": "x"}, "classification"),
                ({"classification": INTENTIONAL_FEDORA, "reason": ""}, "reason"),
            ):
                pin = self._pin_with_override(override)
                path = write(root, "pin.json", json.dumps(pin))
                with self.assertRaises(ValueError):
                    load_pin(path)
            pin = json.loads(json.dumps(PIN))
            pin["classification_overrides"] = {
                "not-mapped": {"classification": ACTIONABLE, "reason": "x"}
            }
            path = write(root, "pin.json", json.dumps(pin))
            with self.assertRaises(ValueError):
                load_pin(path)

    def test_committed_pin_overrides_are_valid(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        pin = load_pin(repo_root / "config/gnome-build-meta.json")
        self.assertIsInstance(pin.get("classification_overrides", {}), dict)


if __name__ == "__main__":
    unittest.main()

