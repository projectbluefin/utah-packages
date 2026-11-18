"""Tests for the build-intent half of tools/audit_dakota.py: each factory
element's patches and configure options against its recipe.

Every project checkout is a fixture in a temporary directory; nothing here
touches the network.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_dakota import (
    ALIGNED,
    FACTORY,
    NEEDS_REVIEW,
    NOT_COMPARED,
    ElementRecord,
    apply_junction_queues,
    build_intent,
    build_report,
    compare_options,
    compare_patches,
    configure_switches,
    element_facts,
    element_options,
    expected_build_refs,
    import_build_facts,
    junction_commit,
    main,
    patch_identity,
    render_markdown,
    spec_configure_switches,
    verify_build_roots,
)

GBM_SHA = "8a89846df11e86cee57c728a86a247e61d604b84"
FDSDK_SHA = "114ae909ec9881958bd507c8b4414aa33f758d2b"
EXTRA_SHA = "7825d44d436a51dcbf7d226904348e810c63bf75"
DAKOTA_SHA = "bf271777da1808627f775f1d8816db2a89a931ea"

PIN = {
    "schema": 1,
    "source": {
        "revision": DAKOTA_SHA,
        "sbom": "publish run 1, artifact sbom-dakota",
        "image": "ghcr.io/projectbluefin/dakota:testing",
        "image_digest": "sha256:" + "3f" * 32,
        "junctions": {
            "gnome-build-meta.bst": f"gnome-51 51.1-36-g{GBM_SHA}",
            "freedesktop-sdk.bst": f"freedesktop-sdk-26.08.4-0-g{FDSDK_SHA}",
        },
    },
    "config_packages": {"dakota": "dakota-config", "gnome-build-meta": "gnome-os-config"},
    "aliases": {},
    "overrides": {},
    "elements": {},
}

PATCH = """\
From 1 Mon Sep 17 00:00:00 2001
Subject: [PATCH 1/2] Fix the build with GCC 16

--- a/src/x.c
+++ b/src/x.c
@@ -1 +1 @@
-int x;
+static int x;
"""


def record(element: str, **fields) -> ElementRecord:
    values = {"name": element.rsplit("/", 1)[-1].removesuffix(".bst"), "in_image": True,
              "sources": ("tar",), "version": "", "url": "", "patches": 0}
    values.update(fields)
    return ElementRecord(element=element, **values)


def write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def projects(tmp: Path) -> dict[str, Path]:
    """Four small projects: a Dakota junction queue, a cross-junction include,
    a patch_queue, a filter, and a gnome-build-meta junction to fdsdk-extra."""
    roots = {name: tmp / name for name in
             ("dakota", "gnome-build-meta", "freedesktop-sdk", "freedesktop-sdk-extra")}
    write(roots["dakota"], {
        "elements/gnome-build-meta.bst": (
            "kind: junction\nsources:\n- kind: git_repo\n  url: gnome:gnome-build-meta.git\n"
            f"  track: gnome-51\n  ref: 51.1-36-g{GBM_SHA}\n"),
        "elements/freedesktop-sdk.bst": (
            "kind: junction\nsources:\n- kind: git_repo\n  url: gitlab:fdsdk.git\n"
            f"  ref: freedesktop-sdk-26.08.4-0-g{FDSDK_SHA}\n"
            "- kind: patch_queue\n  path: patches/freedesktop-sdk-dakota\n"),
        "patches/freedesktop-sdk-dakota/0001-ffmpeg-all-codecs.patch": (
            "--- a/elements/components/ffmpeg.bst\n+++ b/elements/components/ffmpeg.bst\n"
            "@@ -3,2 +3,2 @@ variables:\n   conf-local: >-\n"
            "-    --disable-decoder=h264 --enable-openal\n"
            "+    --enable-decoders --enable-openal\n"),
        "elements/bluefin/nicstat.bst": (
            "kind: make\nsources:\n- kind: git_repo\n  url: github:x/nicstat.git\n"
            "- kind: patch_queue\n  path: patches/nicstat\n"),
        "patches/nicstat/0001-fix-speed.patch": PATCH,
    })
    write(roots["freedesktop-sdk"], {
        "elements/components/ffmpeg.bst": (
            "kind: make\n(@):\n- elements/include/ffmpeg.yml\nvariables:\n"
            "  conf-local: >-\n    --disable-decoder=h264 --enable-openal\n"),
        "elements/include/ffmpeg.yml": "variables:\n  conf-extra: --enable-gpl\n",
        "elements/components/bluez.bst": (
            "kind: filter\nbuild-depends:\n- components/_private/bluez-base.bst\n"),
        "elements/components/_private/bluez-base.bst": (
            "kind: autotools\nsources:\n- kind: tar\n  url: kernel:bluez.tar.xz\n"
            "- kind: patch\n  path: patches/bluez/no-obex.patch\nvariables:\n"
            "  conf-local: --disable-obex --with-udevdir=%{indep-libdir}/udev\n"),
        "patches/bluez/no-obex.patch": PATCH.replace("GCC 16", "obex"),
        "include/meson-vars.yml": "variables:\n  meson-extra: -Dintrospection=enabled\n",
    })
    write(roots["gnome-build-meta"], {
        "elements/freedesktop-sdk-extra.bst": (
            "kind: junction\nsources:\n- kind: git_repo\n  url: gitlab:extra.git\n"
            f"  track: freedesktop-sdk-extra-26.08*\n  ref: freedesktop-sdk-extra-26.08.3-0-g{EXTRA_SHA}\n"),
        "elements/core/gdm.bst": (
            "kind: meson\n(@): freedesktop-sdk.bst:include/meson-vars.yml\nsources:\n"
            "- kind: tar\n  url: gnome_downloads:gdm/51/gdm-51.0.tar.xz\nvariables:\n"
            "  meson-local: >-\n    -Ddefault-pam-config=none -Dplymouth=enabled\n"
            "  (?):\n  - arch == 'x86_64':\n      meson-local: -Dx=1\n"),
    })
    write(roots["freedesktop-sdk-extra"], {
        "elements/components/fish.bst": "kind: cmake\nvariables:\n  cmake-local: -DWITH_GETTEXT=ON\n",
    })
    return roots


class ParserTests(unittest.TestCase):
    def test_configure_switches_normalize_disable_and_without(self) -> None:
        self.assertEqual(
            configure_switches("--enable-gtk --disable-docs --with-x=yes --without-ldap "
                               "--enable-encoder=a,b --libdir=/usr/lib64 --prefix=/usr"),
            {"enable-gtk": "yes", "enable-docs": "no", "with-x": "yes", "with-ldap": "no",
             "enable-encoder": "a,b"})

    def test_spec_configure_blocks_only(self) -> None:
        spec = (
            "%build\n"
            "%configure \\\n"
            "  --disable-static \\\n"
            "%if %{with obex}\n"
            "  --enable-obex \\\n"
            "%endif\n"
            "  --with-udevdir=%{_udevdir}\n"
            "echo --enable-not-an-option\n"
            "./configure --enable-openal\n"
        )
        self.assertEqual(spec_configure_switches(spec), {
            "enable-static": "no", "enable-obex": "yes", "with-udevdir": "%{_udevdir}",
            "enable-openal": "yes"})

    def test_element_options_by_variable(self) -> None:
        facts = {"options": {"meson-local": "-Dprofiler=false -Dx11=enabled",
                             "conf-local": "--disable-obex"}}
        self.assertEqual(element_options(facts),
                         {"profiler": "false", "x11": "enabled", "enable-obex": "no"})

    def test_junction_commit(self) -> None:
        self.assertEqual(junction_commit(f"gnome-51 51.1-36-g{GBM_SHA}"), GBM_SHA)
        self.assertEqual(junction_commit(f"freedesktop-sdk-26.08.4-0-g{FDSDK_SHA}"), FDSDK_SHA)
        self.assertIsNone(junction_commit("gnome-51"))


class PatchTests(unittest.TestCase):
    def test_identity_is_subject_and_changed_lines(self) -> None:
        identity = patch_identity(PATCH)
        self.assertEqual(identity["subject"], "Fix the build with GCC 16")
        renamed = PATCH.replace("From 1", "From 2").replace("[PATCH 1/2] ", "")
        self.assertEqual(patch_identity(renamed)["hunks"], identity["hunks"])
        self.assertNotEqual(patch_identity(PATCH.replace("static", "extern"))["hunks"],
                            identity["hunks"])

    def test_matches_by_name_subject_or_hunks(self) -> None:
        dakota = [
            {"path": "patches/x/0002-Fix-Build.patch", "subject": "", "hunks": "aa"},
            {"path": "patches/x/cve.patch", "subject": "src/ogg: better checks", "hunks": "bb"},
            {"path": "patches/x/svn-r6564.patch", "subject": "", "hunks": "cc"},
            {"path": "patches/x/dakota-only.patch", "subject": "Dakota only", "hunks": "dd"},
        ]
        factory = [
            {"path": "fix-build.patch", "subject": "", "hunks": "zz"},
            {"path": "x-1.2-cve-2024-1.patch", "subject": "src/ogg: better checks", "hunks": "yy"},
            {"path": "x-symbols.patch", "subject": "", "hunks": "cc"},
            {"path": "fedora-only.patch", "subject": "", "hunks": "ee"},
        ]
        result = compare_patches(dakota, factory)
        self.assertEqual([m["factory"] for m in result["matched"]],
                         ["fix-build.patch", "x-1.2-cve-2024-1.patch", "x-symbols.patch"])
        self.assertEqual(result["only_in_dakota"], ["patches/x/dakota-only.patch"])
        self.assertEqual(result["only_in_factory"], ["fedora-only.patch"])


class OptionTests(unittest.TestCase):
    def test_conflicts_normalize_and_skip_macros(self) -> None:
        result = compare_options(
            {"profiler": "false", "x11": "true", "docs": "false", "udev": "%{indep-libdir}",
             "extensions-tool:bash_completion": "disabled", "only-dakota": "1"},
            {"profiler": "true", "x11": "enabled", "udev": "/usr/lib/udev",
             "bash_completion": "enabled", "only-fedora": "1", "docs": "%{?with_docs}"})
        self.assertEqual(result["conflicting"], [
            {"option": "extensions-tool:bash_completion", "dakota": "disabled", "factory": "enabled"},
            {"option": "profiler", "dakota": "false", "factory": "true"}])
        self.assertEqual(result["only_in_dakota"], ["only-dakota"])
        self.assertEqual(result["only_in_factory"], ["only-fedora"])
        self.assertEqual(result["same"], 3)


def fake_head(refs: dict[str, str]):
    return lambda path: {"dakota": DAKOTA_SHA, "gnome-build-meta": GBM_SHA,
                         "freedesktop-sdk": FDSDK_SHA, "freedesktop-sdk-extra": EXTRA_SHA}[path.name]


class ImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.roots = projects(self.tmp)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_expected_refs_read_fdsdk_extra_from_gbm(self) -> None:
        self.assertEqual(expected_build_refs(PIN, self.roots["gnome-build-meta"]), {
            "dakota": DAKOTA_SHA, "gnome-build-meta": GBM_SHA,
            "freedesktop-sdk": FDSDK_SHA, "freedesktop-sdk-extra": EXTRA_SHA})

    def test_refuses_a_checkout_at_another_commit(self) -> None:
        refs = expected_build_refs(PIN, self.roots["gnome-build-meta"])
        heads = verify_build_roots(refs, self.roots, fake_head(refs))
        self.assertEqual(heads["freedesktop-sdk"], FDSDK_SHA)
        with self.assertRaises(SystemExit):
            verify_build_roots(refs, self.roots, lambda path: "0" * 40)

    def test_junction_queue_is_applied_to_a_copy(self) -> None:
        roots, queues = apply_junction_queues(self.roots, self.tmp / "work")
        self.assertIn("--enable-decoders",
                      (roots["freedesktop-sdk"] / "elements/components/ffmpeg.bst").read_text())
        # The checkout itself is untouched.
        self.assertIn("--disable-decoder=h264",
                      (self.roots["freedesktop-sdk"] / "elements/components/ffmpeg.bst").read_text())
        self.assertEqual(queues["freedesktop-sdk"], [{
            "patch": "patches/freedesktop-sdk-dakota/0001-ffmpeg-all-codecs.patch",
            "files": ["elements/components/ffmpeg.bst"]}])
        self.assertNotIn("gnome-build-meta", queues)

    def test_element_facts(self) -> None:
        gdm = element_facts(record("gnome-build-meta.bst:core/gdm.bst"), self.roots)
        self.assertEqual(gdm["kind"], "meson")
        # The cross-junction include resolves in freedesktop-sdk's checkout.
        self.assertEqual(gdm["options"], {
            "meson-local": "-Ddefault-pam-config=none -Dplymouth=enabled",
            "meson-extra": "-Dintrospection=enabled"})
        self.assertTrue(gdm["conditional_variables"])

        nicstat = element_facts(record("bluefin/nicstat.bst"), self.roots)
        self.assertEqual([p["path"] for p in nicstat["patches"]],
                         ["patches/nicstat/0001-fix-speed.patch"])
        self.assertEqual(nicstat["patches"][0]["subject"], "Fix the build with GCC 16")

        bluez = element_facts(record("freedesktop-sdk.bst:components/bluez.bst"), self.roots)
        self.assertEqual(bluez["kind"], "filter")
        self.assertEqual(bluez["build"]["element"],
                         "freedesktop-sdk.bst:components/_private/bluez-base.bst")
        self.assertEqual(bluez["build"]["options"]["conf-local"],
                         "--disable-obex --with-udevdir=%{indep-libdir}/udev")

        missing = element_facts(record("bluefin/gone.bst"), self.roots)
        self.assertIn("not found", missing["error"])

    def test_import_is_deterministic_and_marks_queue_patched_elements(self) -> None:
        records = [record("freedesktop-sdk.bst:components/ffmpeg.bst"),
                   record("gnome-build-meta.bst:core/gdm.bst"),
                   record("bluefin/nicstat.bst"),
                   record("gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/fish.bst"),
                   record("bluefin/build-only.bst", in_image=False)]
        head = fake_head({})
        first = import_build_facts(PIN, records, self.roots, head)
        second = import_build_facts(PIN, records, self.roots, head)
        self.assertEqual(json.dumps(first), json.dumps(second))
        self.assertEqual(list(first["elements"]), sorted(r.element for r in records[:4]))
        ffmpeg = first["elements"]["freedesktop-sdk.bst:components/ffmpeg.bst"]
        self.assertEqual(ffmpeg["dakota_junction_patches"], ["0001-ffmpeg-all-codecs.patch"])
        self.assertIn("--enable-decoders", ffmpeg["options"]["conf-local"])
        self.assertEqual(ffmpeg["options"]["conf-extra"], "--enable-gpl")
        self.assertEqual(first["refs"]["freedesktop-sdk-extra"], EXTRA_SHA)
        fish = first["elements"]["gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/fish.bst"]
        self.assertEqual(fish["options"], {"cmake-local": "-DWITH_GETTEXT=ON"})


SPEC = """\
Name: gdm
Version: 51.0
Patch0: 0001-fix-build.patch
Patch1: fedora-only.patch
%build
%meson \\
  -Ddefault-pam-config=redhat \\
  -Dplymouth=enabled
"""


class BuildIntentTests(unittest.TestCase):
    FACTS = {"schema": 1, "dakota_revision": DAKOTA_SHA, "elements": {
        "gnome-build-meta.bst:core/gdm.bst": {
            "kind": "meson",
            "options": {"meson-local": "-Ddefault-pam-config=none -Dplymouth=enabled"},
            "patches": [{"path": "patches/gdm/0001-Fix-build.patch", "subject": "", "hunks": "a"},
                        {"path": "patches/gdm/dakota-only.patch", "subject": "", "hunks": "b"}]},
        "freedesktop-sdk.bst:components/jq.bst": {"kind": "autotools",
                                                  "options": {"conf-local": "--disable-docs"}},
        "freedesktop-sdk.bst:components/bluez-libs.bst": {
            "kind": "filter",
            "build": {"element": "freedesktop-sdk.bst:components/_private/bluez-base.bst",
                      "kind": "autotools", "options": {"conf-local": "--disable-obex"}}},
        "freedesktop-sdk.bst:components/bluez.bst": {
            "kind": "filter",
            "build": {"element": "freedesktop-sdk.bst:components/_private/bluez-base.bst",
                      "kind": "autotools", "options": {"conf-local": "--disable-obex"}}},
        "freedesktop-sdk.bst:components/split.bst": {"kind": "filter"},
        "freedesktop-sdk.bst:components/broken.bst": {"error": "ScannerError: bad"},
    }}

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.packages = Path(self._tmp.name)
        write(self.packages, {
            "gdm/gdm.spec": SPEC, "gdm/0001-fix-build.patch": PATCH,
            "gdm/fedora-only.patch": PATCH.replace("static", "const"),
            "jq/jq.spec": "%configure --disable-docs\n",
            "bluez/bluez.spec": "%configure --enable-obex\n",
            "split/split.spec": "",
            "broken/broken.spec": "",
        })

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def entries(self) -> list[dict]:
        rows = [("gnome-build-meta.bst:core/gdm.bst", "gdm"),
                ("freedesktop-sdk.bst:components/jq.bst", "jq"),
                ("freedesktop-sdk.bst:components/bluez-libs.bst", "bluez"),
                ("freedesktop-sdk.bst:components/bluez.bst", "bluez"),
                ("freedesktop-sdk.bst:components/split.bst", "split"),
                ("freedesktop-sdk.bst:components/broken.bst", "broken"),
                ("freedesktop-sdk.bst:components/nofacts.bst", "nofacts"),
                ("freedesktop-sdk.bst:components/hb.bst", "hb")]
        out = [{"element": e, "rpm": r, "disposition": FACTORY} for e, r in rows]
        out[-1]["disposition"] = "hummingbird"
        return out

    def locks(self) -> dict:
        return {name: {"version": "1"} for name in
                ("gdm", "jq", "bluez", "split", "broken", "nofacts", "hb")}

    def test_classifications(self) -> None:
        rows = {r["element"]: r for r in build_intent(self.entries(), self.FACTS, self.locks(),
                                                      self.packages)}
        gdm = rows["gnome-build-meta.bst:core/gdm.bst"]
        self.assertEqual(gdm["classification"], NEEDS_REVIEW)
        self.assertEqual(gdm["patches"]["only_in_dakota"], ["patches/gdm/dakota-only.patch"])
        self.assertEqual(gdm["patches"]["only_in_factory"], ["fedora-only.patch"])
        self.assertEqual(gdm["options"]["conflicting"], [
            {"option": "default-pam-config", "dakota": "none", "factory": "redhat"}])
        self.assertIn("1 Dakota patch(es) not in the recipe", gdm["reason"])

        self.assertEqual(rows["freedesktop-sdk.bst:components/jq.bst"]["classification"], ALIGNED)

        # Two filters of one build compare it once, against the RPM's recipe.
        bluez = [r for r in rows.values() if r["rpm"] == "bluez"]
        self.assertEqual(len(bluez), 1)
        self.assertEqual(bluez[0]["built_by"], "freedesktop-sdk.bst:components/_private/bluez-base.bst")
        self.assertEqual(bluez[0]["classification"], NEEDS_REVIEW)

        for element, reason in (("split", "builds nothing itself"),
                                ("broken", "could not be read"),
                                ("nofacts", "no build facts")):
            row = rows[f"freedesktop-sdk.bst:components/{element}.bst"]
            self.assertEqual(row["classification"], NOT_COMPARED)
            self.assertIn(reason, row["reason"])
        self.assertNotIn("freedesktop-sdk.bst:components/hb.bst", rows)

    def test_missing_spec_is_not_compared(self) -> None:
        (self.packages / "jq" / "jq.spec").unlink()
        rows = {r["element"]: r for r in build_intent(self.entries(), self.FACTS, self.locks(),
                                                      self.packages)}
        self.assertIn("no spec", rows["freedesktop-sdk.bst:components/jq.bst"]["reason"])

    def test_report_section_is_report_only(self) -> None:
        pin = copy.deepcopy(PIN)
        records = [record("gnome-build-meta.bst:core/gdm.bst", name="gdm")]
        pin["elements"] = {records[0].element: {"disposition": FACTORY, "rpm": "gdm",
                                                "fedora": "gdm", "hummingbird": False}}
        report = build_report(pin, records, {"gdm": {"version": "51.0"}}, self.packages,
                              self.FACTS)
        self.assertEqual(report["build_intent"][0]["classification"], NEEDS_REVIEW)
        markdown = render_markdown(report)
        self.assertIn("## Patches and build options of factory recipes", markdown)
        self.assertIn("| gdm | meson | `dakota-only.patch` | "
                      "`default-pam-config=none / redhat` | `gnome-build-meta.bst:core/gdm.bst` |",
                      markdown)
        self.assertNotIn("not the pinned revision", markdown)

        stale = dict(self.FACTS, dakota_revision="0" * 40)
        markdown = render_markdown(build_report(pin, records, {"gdm": {"version": "51.0"}},
                                                self.packages, stale))
        self.assertIn("not the pinned revision", markdown)

        markdown = render_markdown(build_report(pin, records, {"gdm": {"version": "51.0"}},
                                                self.packages, None))
        self.assertIn("no build facts", markdown)


class CommittedFactsTests(unittest.TestCase):
    def test_check_passes_with_the_committed_facts(self) -> None:
        # Review findings in the section never fail the gate.
        self.assertEqual(main(["--check"]), 0)

    def test_import_needs_every_checkout(self) -> None:
        self.assertEqual(main(["--import-build-facts", "--dakota-dir", "/nonexistent"]), 2)
        self.assertEqual(main(["--check", "--import-build-facts"]), 2)


if __name__ == "__main__":
    unittest.main()
