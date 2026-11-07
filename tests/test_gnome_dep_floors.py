#!/usr/bin/env python3
"""tools/gnome_dep_floors.py: GNOME modules' declared floors against the locks (D9).

Offline: tarballs are built from meson/configure/CMake snippets here and
served by a fake opener, repodata is a minimal primary.xml, and
tools/upstream_bump.py is replaced by a recorder that rewrites the lock the
way --apply would.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
from pathlib import Path

from tools import gnome_dep_floors as floors
from tools.gnome_dep_floors import Floor

GNOME = floors.GNOME_SOURCES
COMMON = "http://linux.duke.edu/metadata/common"
RPM = "http://linux.duke.edu/metadata/rpm"


def tarball(top: str, files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz") as archive:
        for path, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"{top}/{path}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def primary(packages: list[tuple[str, str, list[tuple[str, str]]]]) -> bytes:
    """A primary.xml: (binary name, source rpm, [(provide, version)])."""
    body = []
    for name, source, provides in packages:
        entries = "".join(
            f'<rpm:entry name="{cap}" flags="EQ" epoch="0" ver="{ver}" rel="1"/>'
            for cap, ver in provides
        )
        body.append(
            f'<package type="rpm"><name>{name}</name>'
            '<version epoch="0" ver="1" rel="1"/><format>'
            f"<rpm:sourcerpm>{source}</rpm:sourcerpm>"
            f"<rpm:provides>{entries}</rpm:provides>"
            # A requirement is not a provide: this must not count.
            '<rpm:requires><rpm:entry name="pkgconfig(decoy)" flags="GE" ver="99"/></rpm:requires>'
            "</format></package>"
        )
    return (
        f'<?xml version="1.0"?><metadata xmlns="{COMMON}" xmlns:rpm="{RPM}" '
        f'packages="{len(packages)}">{"".join(body)}</metadata>'
    ).encode()


class Served:
    """urlopen stand-in: fixed bytes per URL, URLError for anything else."""

    def __init__(self, pages: dict[str, bytes]):
        self.pages = pages
        self.requested: list[str] = []

    def __call__(self, request, timeout=None):
        url = getattr(request, "full_url", request)
        self.requested.append(url)
        if url not in self.pages:
            raise urllib.error.URLError(f"no route to {url}")
        return io.BytesIO(self.pages[url])


GTK_RELEASES = ["4.22.5", "4.23.4", "4.24.0", "4.24.1", "4.24.90", "4.25.0", "4.26.beta"]
GTK_CACHE = json.dumps([
    4,
    {"gtk": {v: {"tar.xz": f"{'.'.join(v.split('.')[:2])}/gtk-{v}.tar.xz",
                 "sha256sum": f"{'.'.join(v.split('.')[:2])}/gtk-{v}.sha256sum"}
             for v in GTK_RELEASES}},
    {"gtk": GTK_RELEASES},
    {},
]).encode()

NAUTILUS_MESON = """\
project('nautilus', 'c', version: '51.1')
gtk_req = '>= 4.24.0'   # a floor kept in a variable
glib_min = '2.86.0'
gtk = dependency('gtk4', version: gtk_req)
glib = dependency('glib-2.0', version: '>= @0@'.format(glib_min))
subdir('src')
"""
NAUTILUS_SRC = "libportal = dependency('libportal', version: ['>= 0.7', '< 1.0'])\n"


class Fixture:
    """A factory root with a nautilus module lock and a gtk4 dependency lock."""

    def __init__(self, test: unittest.TestCase, gtk4: str = "4.23.4",
                 meson: str = NAUTILUS_MESON, glib: str = "2.86.3", extra_locks=()):
        scratch = tempfile.TemporaryDirectory()
        test.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / "config").mkdir()
        self.nautilus = tarball("nautilus-51.1", {"meson.build": meson,
                                                  "src/meson.build": NAUTILUS_SRC})
        self.nautilus_url = f"{GNOME}nautilus/51/nautilus-51.1.tar.xz"
        self.locks = [
            {"name": "nautilus", "version": "51.1", "url": self.nautilus_url,
             "filename": "nautilus-51.1.tar.xz",
             "sha512": hashlib.sha512(self.nautilus).hexdigest()},
            {"name": "gtk4", "version": gtk4,
             "url": f"{GNOME}gtk/{'.'.join(gtk4.split('.')[:2])}/gtk-{gtk4}.tar.xz",
             "filename": f"gtk-{gtk4}.tar.xz", "sha512": "0" * 128},
            {"name": "libportal", "version": "0.11.0",
             "url": "https://github.com/flatpak/libportal/releases/download/0.11.0/libportal-0.11.0.tar.xz",
             "filename": "libportal-0.11.0.tar.xz", "sha512": "1" * 128},
            *extra_locks,
        ]
        self.write_locks()
        (self.root / "factory.xml").write_bytes(primary([
            ("gtk4-devel", f"gtk4-{gtk4}-1.src.rpm", [("pkgconfig(gtk4)", gtk4)]),
            ("libportal-devel", "libportal-0.11.0-1.src.rpm", [("pkgconfig(libportal)", "0.11.0")]),
        ]))
        (self.root / "hummingbird.xml").write_bytes(primary([
            ("glib2-devel", "glib2-2.84.0-1.src.rpm", [("pkgconfig(glib-2.0)", "2.84.0")]),
            ("glib2-devel", f"glib2-{glib}-1.src.rpm", [("pkgconfig(glib-2.0)", glib)]),
        ]))
        self.opener = Served({self.nautilus_url: self.nautilus,
                              f"{GNOME}gtk/cache.json": GTK_CACHE})
        self.calls: list[list[str]] = []
        self.proposal = "gtk4: {current} -> 4.24.1\n"
        self.applied_version = "4.24.1"

    def write_locks(self) -> None:
        (self.root / "config" / "upstream-sources.json").write_text(
            json.dumps({"schema": 1, "packages": self.locks}, indent=2)
        )

    def lock(self, name: str) -> dict:
        data = json.loads((self.root / "config" / "upstream-sources.json").read_text())
        return next(entry for entry in data["packages"] if entry["name"] == name)

    def run(self, command, **kwargs):
        """tools/upstream_bump.py stand-in: report, and on --apply rewrite the lock."""
        self.calls.append(list(command))
        package = command[command.index("--package") + 1]
        current = self.lock(package)["version"]
        stdout = self.proposal.format(current=current)
        if "--apply" in command:
            for entry in self.locks:
                if entry["name"] == package:
                    entry["version"] = self.applied_version
            self.write_locks()
        return subprocess.CompletedProcess(command, 0, stdout, "")

    def main(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        argv = ["--root", str(self.root), "--module", "nautilus",
                "--primary", str(self.root / "factory.xml"),
                "--hummingbird-primary", str(self.root / "hummingbird.xml"), *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = floors.main(argv, opener=self.opener, run=self.run)
        return code, out.getvalue(), err.getvalue()


class MesonFloorTests(unittest.TestCase):
    def floors(self, files: dict[str, str]) -> list[Floor]:
        return floors.meson_floors(files)

    def test_a_literal_floor(self):
        found = self.floors({"meson.build": "gtk = dependency('gtk4', version: '>= 4.24.0')\n"})
        self.assertEqual(found, [Floor("gtk4", ">=", "4.24.0", "'>= 4.24.0'", "meson.build")])

    def test_a_floor_stored_in_a_variable(self):
        found = self.floors({"meson.build": "glib_req = '>= 2.86'\n"
                             "glib = dependency('glib-2.0', version: glib_req)\n"})
        self.assertEqual([(f.dependency, f.op, f.version) for f in found],
                         [("glib-2.0", ">=", "2.86")])

    def test_concatenation_format_and_f_strings_are_evaluated(self):
        found = self.floors({"meson.build": (
            "glib_version = '2.86.0'\n"
            "a = dependency('gio-2.0', version: '>= ' + glib_version)\n"
            "b = dependency('gobject-2.0', version: '>= @0@'.format(glib_version))\n"
            "c = dependency('gmodule-2.0', version: f'>= @glib_version@')\n"
            "reqs = ['>= 1.2', '< 2']\n"
            "reqs += ['!= 1.3']\n"
            "d = dependency('json-glib-1.0', version: reqs)\n"
        )})
        self.assertEqual(
            [(f.dependency, f.op, f.version) for f in found],
            [("gio-2.0", ">=", "2.86.0"), ("gobject-2.0", ">=", "2.86.0"),
             ("gmodule-2.0", ">=", "2.86.0"), ("json-glib-1.0", ">=", "1.2")],
        )

    def test_subdir_files_see_variables_their_parent_set(self):
        found = self.floors({
            "meson.build": "pango_req = '>= 1.58'\nsubdir('src')\nsubdir('missing')\n",
            "src/meson.build": "dep = dependency('pango',\n  version: pango_req,\n  required: true)\n",
            # Never reached through subdir(): a subproject's own floors.
            "subprojects/x/meson.build": "dep = dependency('pango', version: '>= 9')\n",
        })
        self.assertEqual([(f.dependency, f.version, f.path) for f in found],
                         [("pango", "1.58", "src/meson.build")])

    def test_strict_and_exact_floors_and_no_ceiling(self):
        found = self.floors({"meson.build": (
            "a = dependency('qt5', version: '> 5.0.0')\n"
            "b = dependency('exact', version: '==1.2')\n"
            "c = dependency('ceiling', version: '< 3')\n"
            "d = dependency('none', version: '')\n"
            "e = dependency('unversioned')\n"
            "f = meson.get_compiler('c').dependency('m', version: '>= 1')\n"
        )})
        self.assertEqual([(f.dependency, f.op, f.version) for f in found],
                         [("qt5", ">", "5.0.0"), ("exact", ">=", "1.2")])

    def test_an_unevaluable_version_is_reported_not_guessed(self):
        found = self.floors({"meson.build": (
            "x = run_command('v').stdout()\n"
            "a = dependency('libfoo', version: '>= ' + x)\n"
            "b = dependency('libbar', version: '>= ' + undefined)\n"
        )})
        self.assertEqual([(f.dependency, f.op) for f in found], [("libfoo", None), ("libbar", None)])
        self.assertEqual(found[0].required, "? ('>= ' + x)")

    def test_comments_and_escapes(self):
        found = self.floors({"meson.build": (
            "# dependency('commented', version: '>= 9')\n"
            "v = '''>= 1.0'''\n"
            "a = dependency('it\\'s', version: v) # trailing\n"
            "items = ['>= 0.1', '>= 0.2']\n"
            "b = dependency('indexed', version: items[1])\n"
        )})
        self.assertEqual([(f.dependency, f.version) for f in found],
                         [("it's", "1.0"), ("indexed", "0.2")])


class ExpressionTests(unittest.TestCase):
    def evaluate(self, text: str, env=None):
        tokens = floors.meson_statements(text)[0]
        return floors.Expression(tokens, env or {}).evaluate()

    def test_supported_values(self):
        self.assertEqual(self.evaluate("('a' + 'b')"), "ab")
        self.assertEqual(self.evaluate("[true, false, 3]"), [True, False, 3])

    def test_unsupported_values_raise(self):
        for text in ("'a' + 1", "'@1@'.format('x')", "'a'.strip()", "x[0]", "'a' 'b'",
                     "[1, 2][5]", "'a'[0]", "[1 2]", "f(", "'a'.format(", ")"):
            with self.subTest(text=text), self.assertRaises(floors.Unsupported):
                self.evaluate(text, {"x": "s"})


class OtherBuildSystemTests(unittest.TestCase):
    def test_configure_ac_with_shell_and_m4_variables(self):
        text = (
            "m4_define([gtk_required], [3.22.0])\n"
            "GLIB_REQUIRED=2.40\n"
            "PKG_CHECK_MODULES(GTK, [gtk+-3.0 >= gtk_required glib-2.0>=$GLIB_REQUIRED\n"
            "                        libsecret-1 >= ${UNSET}])\n"
            "PKG_CHECK_EXISTS([libnm >= 1.2.0 x11], [have=yes])\n"
            "PKG_CHECK_MODULES(EMPTY)\n"
        )
        found = floors.autotools_floors("configure.ac", text)
        self.assertEqual(
            [(f.dependency, f.op, f.version) for f in found],
            [("gtk+-3.0", ">=", "3.22.0"), ("glib-2.0", ">=", "2.40"),
             ("libsecret-1", None, None), ("libnm", ">=", "1.2.0")],
        )

    def test_cmake_pkg_check_modules(self):
        found = floors.cmake_floors({
            "CMakeLists.txt": "set(glib_minimum_version 2.68)\n",
            "src/CMakeLists.txt": (
                "pkg_check_modules(GNOME_PLATFORM REQUIRED IMPORTED_TARGET "
                "gio-2.0>=${glib_minimum_version} \"libsoup-3.0 >= 3.1.1\" uuid)\n"
            ),
        })
        self.assertEqual([(f.dependency, f.version, f.path) for f in found],
                         [("gio-2.0", "2.68", "src/CMakeLists.txt"),
                          ("libsoup-3.0", "3.1.1", "src/CMakeLists.txt")])

    def test_tarball_prefers_meson_then_configure_then_cmake(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        cases = {
            "meson": ({"meson.build": "a = dependency('m', version: '>= 1')\n",
                       "configure.ac": "PKG_CHECK_MODULES(X, [c >= 1])\n"}, ["m"]),
            "autotools": ({"configure.ac": "PKG_CHECK_MODULES(X, [c >= 1])\n",
                           "CMakeLists.txt": "pkg_check_modules(X k>=1)\n"}, ["c"]),
            "cmake": ({"CMakeLists.txt": "pkg_check_modules(X k>=1)\n"}, ["k"]),
            "none": ({"README": "hello\n"}, []),
        }
        for name, (files, expected) in cases.items():
            with self.subTest(name=name):
                path = Path(scratch.name) / f"{name}.tar.xz"
                path.write_bytes(tarball(f"{name}-1", files))
                self.assertEqual([f.dependency for f in floors.tarball_floors(path)], expected)


class VersionTests(unittest.TestCase):
    def test_vercmp_orders_like_rpm(self):
        for left, right, expected in [
            ("4.24.1", "4.24.1", 0), ("4.23.4", "4.24.0", -1), ("4.24.10", "4.24.9", 1),
            ("51~beta", "51", -1), ("51", "51~beta", 1), ("1.0^git1", "1.0", 1),
            ("1.0", "1.0^git1", -1), ("1.0a", "1.0", 1), ("1.0", "1.0.1", -1),
            ("2.0", "2.a", 1), ("2.a", "2.0", -1), ("1.01", "1.1", 0), ("1_2", "1.2", 0),
            ("1.0^", "1.0^", 0), ("1.0^a", "1.0~a", 1), ("1.0~a", "1.0^a", -1),
            ("1.0^a", "1.0.1", -1), ("1.0", "1.0^", -1), ("1.0^", "1.0", 1),
        ]:
            with self.subTest(left=left, right=right):
                self.assertEqual(floors.vercmp(left, right), expected)

    def test_prerelease_spelling_does_not_decide_the_order(self):
        # gdk-pixbuf asks for glycin >= 2.2.alpha.7; the lock says 2.2~beta.
        self.assertTrue(floors.satisfies("2.2~beta", ">=", "2.2.alpha.7"))
        self.assertTrue(floors.satisfies("51.0", ">=", "51.rc"))
        self.assertFalse(floors.satisfies("51~beta", ">=", "51.rc"))
        self.assertFalse(floors.satisfies("5.0.0", ">", "5.0.0"))

    def test_prereleases_of_the_gnome_feed(self):
        for version, expected in [("51.beta", True), ("1.89.90", True), ("1.25.95-dev", True),
                                  ("4.24.1", False), ("51.0.90", False), ("1.90.0", False)]:
            with self.subTest(version=version):
                self.assertEqual(floors.is_prerelease(version), expected)

    def test_choose_release_takes_the_lowest_series_that_meets_the_floor(self):
        releases = {v: ".".join(v.split(".")[:2]) for v in GTK_RELEASES}
        self.assertEqual(floors.choose_release(releases, ">=", "4.24.0"), ("4.24", "4.24.1"))
        self.assertEqual(floors.choose_release(releases, ">", "4.24.1"), ("4.25", "4.25.0"))
        self.assertIsNone(floors.choose_release(releases, ">=", "4.26"))


class ProviderTests(unittest.TestCase):
    def test_pkgconfig_versions_reads_provides_only_and_keeps_the_highest(self):
        versions = floors.pkgconfig_versions(primary([
            ("a", "a-1-1.src.rpm", [("pkgconfig(glib-2.0)", "2.84.0"), ("libglib.so", "2")]),
            ("b", "b-1-1.src.rpm", [("pkgconfig(glib-2.0)", "2.86.3")]),
            ("c", "c-1-1.src.rpm", [("pkgconfig(glib-2.0)", "2.85.0")]),
        ]))
        self.assertEqual(versions, {"glib-2.0": "2.86.3"})

    def test_spec_pkgconfig_reads_provides_and_files(self):
        spec = (
            "%global api 4\n"
            "Name: gtk%{api}\n"
            "Version: 4.24.1\n"
            "Provides: pkgconfig(explicit) = %{version}\n"
            "%files devel\n"
            "%{_libdir}/pkgconfig/%{name}.pc\n"
            "%{_libdir}/pkgconfig/gtk4-wayland.pc\n"
            "%{_libdir}/pkgconfig/%{undefined}.pc\n"
        )
        self.assertEqual(floors.spec_pkgconfig(spec), {"explicit", "gtk4", "gtk4-wayland"})
        self.assertEqual(floors.spec_pkgconfig("Provides: pkgconfig(%{x})\n"), set())

    def test_factory_providers_merge_published_and_spec(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        (root / "packages" / "newlib").mkdir(parents=True)
        (root / "packages" / "newlib" / "newlib.spec").write_text(
            "Name: newlib\n%files devel\n/usr/lib64/pkgconfig/newlib-1.pc\n")
        providers = floors.factory_providers(root, {"gtk4": {"pkgconfig(gtk4)", "gtk4"}})
        self.assertEqual(providers, {"gtk4": {"gtk4"}, "newlib-1": {"newlib"}})

    def test_gnome_modules_are_gnome_primaries_and_mapped_packages(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        (root / "config").mkdir()
        (root / "config" / "gnome-build-meta.json").write_text(json.dumps({
            "factory_alias": {"gvfs-client": "gvfs"},
            "mapping": {"cairo": "sdk/cairo.bst", "gvfs-client": "core/gvfs.bst"},
        }))
        locks = {"nautilus": {"url": f"{GNOME}nautilus/51/x.tar.xz"},
                 "cairo": {"url": "https://cairographics.org/releases/cairo.tar.xz"},
                 "gvfs": {"url": "https://example.org/gvfs.tar.xz"},
                 "wayland": {"url": "https://gitlab.freedesktop.org/x.tar.xz"}}
        self.assertEqual(floors.gnome_modules(root, locks), ["cairo", "gvfs", "nautilus"])

    def test_gnome_module_reads_the_primary_or_an_explicit_feed(self):
        self.assertEqual(floors.gnome_module({"url": f"{GNOME}gtk/4.24/gtk-4.24.1.tar.xz"}), "gtk")
        self.assertEqual(floors.gnome_module({"url": "https://src.fedoraproject.org/x",
                                              "feed": f"{GNOME}gjs/1.89/gjs-1.89.2.tar.xz"}), "gjs")
        self.assertIsNone(floors.gnome_module({"url": "https://example.org/x.tar.xz"}))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.dir = Path(scratch.name)
        self.data = b"tarball bytes"
        self.entry = {"url": "https://primary.example/x.tar.xz",
                      "fallback_urls": ["https://mirror.example/x.tar.xz"],
                      "sha512": hashlib.sha512(self.data).hexdigest()}

    def test_a_transport_failure_falls_back(self):
        opener = Served({"https://mirror.example/x.tar.xz": self.data})
        path = floors.download(self.entry, self.dir / "x.tar.xz", opener=opener)
        self.assertEqual(path.read_bytes(), self.data)
        # A verified file already in the cache is not fetched again.
        floors.download(self.entry, path, opener=opener)
        self.assertEqual(len(opener.requested), 2)

    def test_a_digest_mismatch_stops_without_trying_a_mirror(self):
        opener = Served({"https://primary.example/x.tar.xz": b"other bytes",
                         "https://mirror.example/x.tar.xz": self.data})
        with self.assertRaisesRegex(floors.FetchError, "SHA-512 does not match"):
            floors.download(self.entry, self.dir / "x.tar.xz", opener=opener)
        self.assertEqual(opener.requested, ["https://primary.example/x.tar.xz"])
        self.assertFalse((self.dir / "x.tar.xz.part").exists())

    def test_no_reachable_url(self):
        with self.assertRaisesRegex(floors.FetchError, "no route"):
            floors.download(self.entry, self.dir / "x.tar.xz", opener=Served({}))


class CheckTests(unittest.TestCase):
    def test_an_already_satisfied_floor(self):
        fixture = Fixture(self, gtk4="4.24.1")
        code, out, err = fixture.main()
        self.assertEqual(code, 0, out + err)
        self.assertIn("| nautilus 51.1 | gtk4 | >= 4.24.0 | gtk4 4.24.1 | yes |", out)
        self.assertIn("| nautilus 51.1 | glib-2.0 | >= 2.86.0 | Hummingbird 2.86.3 | yes |", out)
        self.assertIn("| nautilus 51.1 | libportal | >= 0.7 | libportal 0.11.0 | yes |", out)
        self.assertIn("every declared floor is met", out)
        self.assertEqual(fixture.calls, [])

    def test_an_unmet_floor_fails_the_check_and_names_the_move(self):
        fixture = Fixture(self)
        code, out, err = fixture.main()
        self.assertEqual(code, 1)
        self.assertIn("| nautilus 51.1 | gtk4 | >= 4.24.0 | gtk4 4.23.4 | **no** |", out)
        self.assertIn("unmet: gtk4 4.23.4 < >= 4.24.0 (needed by nautilus): --apply moves it "
                      "to 4.24.1 with `upstream_bump.py --package gtk4 --cycle 4.24 --apply`", out)
        self.assertIn("::error title=GNOME dependency floor::nautilus needs gtk4 >= 4.24.0", err)
        # Check mode dry-runs the bump and writes nothing.
        self.assertEqual(len(fixture.calls), 1)
        self.assertNotIn("--apply", fixture.calls[0])
        self.assertEqual(fixture.lock("gtk4")["version"], "4.23.4")

    def test_apply_bumps_the_dependency_onto_the_series_that_meets_the_floor(self):
        fixture = Fixture(self)
        code, out, err = fixture.main("--apply")
        self.assertEqual(code, 0, out + err)
        bump = [str(floors.UPSTREAM_BUMP), "--root", str(fixture.root),
                "--package", "gtk4", "--cycle", "4.24"]
        self.assertEqual([call[1:] for call in fixture.calls], [bump, bump + ["--apply"]])
        self.assertEqual(fixture.lock("gtk4")["version"], "4.24.1")
        self.assertIn("- gtk4 -> 4.24.1 (>= 4.24.0, for nautilus)", out)
        self.assertIn("every declared floor is met", out)

    def test_apply_refuses_a_bump_that_stays_below_the_floor(self):
        fixture = Fixture(self)
        fixture.applied_version = "4.23.5"
        code, out, _ = fixture.main("--apply")
        self.assertEqual(code, 1)
        self.assertIn("gtk4 is at 4.23.5 after the bump, still below >= 4.24.0", out)

    def test_apply_reports_a_failed_bump(self):
        fixture = Fixture(self)

        def failing(command, **kwargs):
            fixture.calls.append(list(command))
            code = 1 if "--apply" in command else 0
            return subprocess.CompletedProcess(command, code, "gtk4: 4.23.4 -> 4.24.1\n", "boom\n")

        fixture.run = failing
        code, out, err = fixture.main("--apply")
        self.assertEqual(code, 1)
        self.assertIn("upstream_bump.py exited 1", out)
        self.assertIn("boom", err)

    def test_an_unmapped_pkgconfig_name_gets_a_specific_reason(self):
        meson = NAUTILUS_MESON.replace("subdir('src')", "x = dependency('libfoo-9', version: '>= 1.0')")
        fixture = Fixture(self, gtk4="4.24.1", meson=meson)
        code, out, _ = fixture.main()
        self.assertEqual(code, 0)
        self.assertIn("| nautilus 51.1 | libfoo-9 | >= 1.0 | — | unknown |", out)
        self.assertIn("unmapped: nautilus needs libfoo-9 >= 1.0: neither a factory recipe nor "
                      "Hummingbird provides pkgconfig(libfoo-9)", out)

    def test_a_floor_on_a_dependency_the_factory_does_not_build(self):
        fixture = Fixture(self, gtk4="4.24.1", glib="2.84.9")
        code, out, _ = fixture.main()
        self.assertEqual(code, 1)
        self.assertIn("external: nautilus needs glib-2.0 >= 2.86.0: pkgconfig(glib-2.0) is not "
                      "built by the factory; Hummingbird ships 2.84.9, so --apply cannot move it", out)
        self.assertEqual(fixture.calls, [])

    def test_no_stable_release_meets_the_floor(self):
        meson = NAUTILUS_MESON.replace("'>= 4.24.0'", "'>= 4.26.0'")
        fixture = Fixture(self, meson=meson)
        code, out, _ = fixture.main("--apply")
        self.assertEqual(code, 1)
        self.assertIn("no stable gtk release satisfies >= 4.26.0 (newest stable: 4.25.0)", out)
        self.assertEqual(fixture.calls, [])

    def test_an_unreadable_release_index(self):
        fixture = Fixture(self)
        del fixture.opener.pages[f"{GNOME}gtk/cache.json"]
        code, out, _ = fixture.main()
        self.assertEqual(code, 1)
        self.assertIn("cannot read gtk's release index", out)

    def test_a_forge_dependency_takes_what_upstream_bump_proposes(self):
        meson = NAUTILUS_MESON.replace("subdir('src')", "subdir('src')\nsubdir('forge')")
        fixture = Fixture(self, gtk4="4.24.1", meson=meson)
        fixture.nautilus = tarball("nautilus-51.1", {
            "meson.build": meson, "src/meson.build": NAUTILUS_SRC,
            "forge/meson.build": "libportal2 = dependency('libportal', version: '>= 0.12')\n",
        })
        fixture.opener.pages[fixture.nautilus_url] = fixture.nautilus
        fixture.locks[0]["sha512"] = hashlib.sha512(fixture.nautilus).hexdigest()
        fixture.write_locks()
        for proposal, expected in [
            ("libportal: {current} -> 0.11.1\n",
             "upstream_bump.py would move libportal only to 0.11.1, which does not satisfy >= 0.12"),
            ("", "proposes no move (nothing newer it may take)"),
            ("libportal: {current} -> 0.12.0\n",
             "--apply moves it to 0.12.0 with `upstream_bump.py --package libportal --cycle 0.12 --apply`"),
        ]:
            with self.subTest(proposal=proposal):
                fixture.proposal = proposal
                fixture.calls.clear()
                code, out, _ = fixture.main()
                self.assertEqual(code, 1)
                self.assertIn(expected, out)
                self.assertEqual(fixture.calls[0][-2:], ["--cycle", "0.12"])

    def test_upstream_bump_review_output_becomes_the_reason(self):
        fixture = Fixture(self)

        def review(command, **kwargs):
            fixture.calls.append(list(command))
            return subprocess.CompletedProcess(
                command, 0, "no lock is behind the newest release it may move to\n",
                "needs review  gtk4: 4.23.4 -> 4.24.1 (listed in config/bump-review-only.txt)\n",
            )

        fixture.run = review
        code, out, _ = fixture.main("--apply")
        self.assertEqual(code, 1)
        self.assertIn("upstream_bump.py --package gtk4 --cycle 4.24 proposes no move (needs review"
                      "  gtk4: 4.23.4 -> 4.24.1 (listed in config/bump-review-only.txt))", out)

    def test_an_unreadable_module_fails_the_check(self):
        fixture = Fixture(self, gtk4="4.24.1")
        del fixture.opener.pages[fixture.nautilus_url]
        code, out, err = fixture.main()
        self.assertEqual(code, 1)
        self.assertIn("unread: nautilus:", out)
        self.assertIn("::error title=GNOME dependency floor::nautilus:", err)

    def test_unlocked_unparsed_and_self_provided_floors(self):
        meson = NAUTILUS_MESON.replace("subdir('src')", (
            "a = dependency('orphan-1', version: '>= 1')\n"
            "b = dependency('libnautilus-extension-4', version: '>= 51')\n"
            "c = dependency('odd', version: '>= ' + run_command('x').stdout())\n"
        ))
        fixture = Fixture(self, gtk4="4.24.1", meson=meson)
        (fixture.root / "factory.xml").write_bytes(primary([
            ("gtk4-devel", "gtk4-4.24.1-1.src.rpm", [("pkgconfig(gtk4)", "4.24.1")]),
            ("orphan-devel", "orphan-1-1.src.rpm", [("pkgconfig(orphan-1)", "1")]),
            ("nautilus-devel", "nautilus-51.1-1.src.rpm",
             [("pkgconfig(libnautilus-extension-4)", "51.1")]),
        ]))
        summary = fixture.root / "summary.md"
        code, out, _ = fixture.main("--summary", str(summary))
        self.assertEqual(code, 0)
        self.assertIn("unlocked: nautilus needs orphan-1 >= 1: factory recipe orphan ships "
                      "pkgconfig(orphan-1) but has no source lock", out)
        self.assertIn("unparsed: nautilus needs odd ? ('>= ' + run_command ( 'x' ) . stdout ( ))"
                      ": meson.build: version", out)
        self.assertNotIn("libnautilus-extension-4", out)
        text = summary.read_text()
        self.assertIn("## GNOME dependency floors (D9)", text)
        self.assertIn("| nautilus 51.1 | orphan-1 | >= 1 | — | unknown |", text)

    def test_without_hummingbird_a_non_factory_name_is_unmapped(self):
        fixture = Fixture(self, gtk4="4.24.1")
        (fixture.root / "hummingbird.xml").write_bytes(b"<not xml")
        code, out, err = fixture.main()
        self.assertEqual(code, 0)
        self.assertIn("Hummingbird's repository could not be read", err)
        self.assertIn("no factory recipe provides pkgconfig(glib-2.0), and Hummingbird's "
                      "repository could not be read", out)

    def test_an_unknown_module_is_refused(self):
        fixture = Fixture(self)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            floors.main(["--root", str(fixture.root), "--module", "gtk-doc",
                         "--primary", str(fixture.root / "factory.xml")])


class StrongestFloorTests(unittest.TestCase):
    def test_needed_keeps_the_strongest_floor_per_dependency(self):
        def row(module, op, version):
            return floors.Row(module, Floor("gtk4", op, version, "", "meson.build"),
                              "unmet", "gtk4", "4.20.0")

        moves = floors.needed([row("a", ">=", "4.22"), row("b", ">=", "4.24.0"),
                               row("c", ">", "4.24.0"), row("c", ">=", "4.23"),
                               floors.Row("d", Floor("x", ">=", "1", "", ""), "ok")])
        self.assertEqual(len(moves), 1)
        self.assertEqual((moves[0].op, moves[0].version, moves[0].modules),
                         (">", "4.24.0", ["a", "b", "c"]))


if __name__ == "__main__":
    unittest.main()
