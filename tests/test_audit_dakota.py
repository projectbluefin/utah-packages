"""Tests for tools/audit_dakota.py: snapshot, name resolution, dispositions, drift.

Every fixture is built in memory or in a temporary directory; nothing here
touches the network.
"""

from __future__ import annotations

import copy
import gzip
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.audit_dakota import (
    ALIGNED,
    BUILD_ONLY_REASON,
    DAKOTA_CONFIG,
    FACTORY,
    FEDORA_IMPORTABLE,
    GNOMEOS_CONFIG,
    HUMMINGBIRD,
    NEEDS_REVIEW,
    NEW_SPEC,
    NOT_APPLICABLE,
    NOT_COMPARED,
    STRUCTURAL,
    ElementRecord,
    FedoraIndex,
    build_report,
    build_snapshot,
    candidate_names,
    classify_element,
    contract_problems,
    gnome_build_meta_aliases,
    image_ownership,
    load_pin,
    main,
    parse_primary,
    project_of,
    read_snapshot,
    refresh_mapping,
    render_markdown,
    sbom_version,
    scan_image_layout,
    spec_subpackages,
    validate_pin,
    version_drift,
    write_snapshot,
)

REPO = Path(__file__).resolve().parents[1]

PIN = {
    "schema": 1,
    "source": {
        "revision": "bf271777da1808627f775f1d8816db2a89a931ea",
        "sbom": "publish run 1, artifact sbom-dakota",
        "image": "ghcr.io/projectbluefin/dakota:testing",
        "image_digest": "sha256:" + "3f" * 32,
    },
    "config_packages": {"dakota": "dakota-config", "gnome-build-meta": "gnome-os-config"},
    "aliases": {},
    "overrides": {},
    "elements": {},
}


def record(element: str, **fields) -> ElementRecord:
    values = {
        "name": element.rsplit("/", 1)[-1].removesuffix(".bst"),
        "in_image": True,
        "sources": ("tar",),
        "version": "",
        "url": "",
        "patches": 0,
    }
    values.update(fields)
    return ElementRecord(element=element, **values)


def resolution(rpm=None, hummingbird=False, evidence=None) -> dict:
    return {"rpm": rpm, "hummingbird": hummingbird, "evidence": evidence}


class ElementRecordTests(unittest.TestCase):
    def test_project_follows_the_junction_prefix(self) -> None:
        self.assertEqual(project_of("bluefin/alsa-utils.bst"), "dakota")
        self.assertEqual(project_of("gnome-build-meta.bst:core/gdm.bst"), "gnome-build-meta")
        self.assertEqual(project_of("freedesktop-sdk.bst:components/jq.bst"), "freedesktop-sdk")
        self.assertEqual(
            project_of("gnome-build-meta.bst:freedesktop-sdk-extra.bst:components/fish.bst"),
            "freedesktop-sdk-extra",
        )
        with self.assertRaises(ValueError):
            project_of("unknown.bst:components/x.bst")

    def test_config_only_ignores_local_files_and_patches(self) -> None:
        self.assertTrue(record("bluefin/x.bst", sources=("local",)).config_only)
        self.assertTrue(record("bluefin/x.bst", sources=()).config_only)
        self.assertTrue(record("bluefin/x.bst", sources=("local", "patch")).config_only)
        self.assertFalse(record("bluefin/x.bst", sources=("git_repo", "local")).config_only)

    def test_visibility_prefers_apps_then_daemons_then_commands(self) -> None:
        self.assertEqual(record("a.bst", apps=1, units=3).visibility, "apps")
        self.assertEqual(record("a.bst", units=1, commands=4).visibility, "daemons")
        self.assertEqual(record("a.bst", commands=1).visibility, "commands")
        self.assertEqual(record("a.bst", files=9).visibility, "libraries-and-data")


class SbomVersionTests(unittest.TestCase):
    def test_tags_and_describe_refs_carry_a_version(self) -> None:
        self.assertEqual(sbom_version("1.2.14"), "1.2.14")
        self.assertEqual(sbom_version("v4.23.0"), "4.23.0")
        self.assertEqual(sbom_version("51.1-36-g8a89846df11e86cee57c728a86a247e61d604b84"), "51.1")
        self.assertEqual(sbom_version("freedesktop-sdk-26.08.4"), "26.08.4")
        self.assertEqual(sbom_version("release_2_4_1"), "2.4.1")

    def test_commits_checksums_and_local_digests_do_not(self) -> None:
        self.assertIsNone(sbom_version("550a03e3d5f600282c8b4c73060bb830c91c1f74"))
        self.assertIsNone(sbom_version("sha256:" + "ab" * 32))
        self.assertIsNone(sbom_version("34f60d698e4042d4057b979d9ab3680385496f6c4d714a8455a11f74ecf26f2a/84"))
        self.assertIsNone(sbom_version(""))
        self.assertIsNone(sbom_version("main"))


class VersionDriftTests(unittest.TestCase):
    def test_same_version_is_aligned(self) -> None:
        self.assertEqual(version_drift("1.2.14", "1.2.14")[0], ALIGNED)

    def test_same_release_line_is_aligned_with_both_versions(self) -> None:
        classification, reason = version_drift("2.62.3", "2.62.4")
        self.assertEqual(classification, ALIGNED)
        self.assertIn("2.62.4", reason)

    def test_gnome_cycle_compares_the_major_only(self) -> None:
        self.assertEqual(version_drift("51.1", "51.2")[0], ALIGNED)
        self.assertEqual(version_drift("50.3", "51.0")[0], NEEDS_REVIEW)

    def test_other_line_needs_review_and_says_which_side_leads(self) -> None:
        classification, reason = version_drift("2.63.2", "2.62.3")
        self.assertEqual(classification, NEEDS_REVIEW)
        self.assertIn("behind", reason)
        self.assertIn("ahead of", version_drift("8.1.3", "9.0.1")[1])

    def test_missing_versions_are_not_compared(self) -> None:
        self.assertEqual(version_drift(None, "1.0")[0], NOT_COMPARED)
        self.assertEqual(version_drift("1.0", None)[0], NOT_COMPARED)


class CandidateNameTests(unittest.TestCase):
    def test_aliases_come_first(self) -> None:
        names = candidate_names(record("gnome-build-meta.bst:sdk/glib.bst"),
                                {"gnome-build-meta.bst:sdk/glib.bst": ["glib2"]})
        self.assertEqual(names[0], "glib2")

    def test_fedora_spellings_of_the_element_name(self) -> None:
        names = candidate_names(record("freedesktop-sdk.bst:components/xorg-lib-xft.bst"), {})
        self.assertIn("libxft", names)
        names = candidate_names(record("bluefin/lm-sensors.bst"), {})
        self.assertIn("lm_sensors", names)
        names = candidate_names(record("freedesktop-sdk.bst:components/avahi-libs.bst"), {})
        self.assertIn("avahi", names)
        names = candidate_names(record("freedesktop-sdk.bst:components/gstreamer-plugins-good.bst"), {})
        self.assertIn("gstreamer1-plugins-good", names)

    def test_element_name_beats_the_repository_name(self) -> None:
        # Every gstreamer-plugins-* element builds from gstreamer.git.
        names = candidate_names(record(
            "freedesktop-sdk.bst:components/gstreamer-plugins-base.bst",
            url="https://gitlab.freedesktop.org/gstreamer/gstreamer.git"), {})
        self.assertLess(names.index("gstreamer1-plugins-base"), names.index("gstreamer"))

    def test_language_ecosystem_names_come_from_the_url(self) -> None:
        names = candidate_names(record(
            "freedesktop-sdk.bst:components/perl-ssl.bst",
            url="https://cpan.metacpan.org/authors/id/S/SU/SULLR/IO-Socket-SSL-2.089.tar.gz"), {})
        self.assertIn("perl-IO-Socket-SSL", names)
        names = candidate_names(record(
            "freedesktop-sdk.bst:components/python3-pil.bst",
            url="https://github.com/python-pillow/Pillow.git"), {})
        self.assertIn("python-pillow", names)

    def test_shell_extensions_try_the_fedora_prefix(self) -> None:
        names = candidate_names(record("bluefin/shell-extensions/caffeine.bst"), {})
        self.assertEqual(names[0], "gnome-shell-extension-caffeine")


class FedoraIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        binaries = {"pulseaudio-libs": "pulseaudio", "NetworkManager": "NetworkManager",
                    "python3-six": "python-six", "pulseaudio": "pulseaudio"}
        self.index = FedoraIndex(set(binaries.values()), binaries)

    def test_source_name_wins(self) -> None:
        self.assertEqual(self.index.resolve(["pulseaudio"])[0], "pulseaudio")

    def test_case_is_folded(self) -> None:
        rpm, evidence = self.index.resolve(["networkmanager"])
        self.assertEqual(rpm, "NetworkManager")
        self.assertIn("case-folded", evidence)

    def test_binary_resolves_to_its_source(self) -> None:
        self.assertEqual(self.index.resolve(["pulseaudio-libs"]),
                         ("pulseaudio", "rawhide binary pulseaudio-libs"))
        self.assertEqual(self.index.resolve(["python3-six"])[0], "python-six")

    def test_first_matching_candidate_wins(self) -> None:
        self.assertEqual(self.index.resolve(["nope", "python3-six", "pulseaudio"])[0], "python-six")
        self.assertEqual(self.index.resolve(["nope"]), (None, None))


class ClassifyTests(unittest.TestCase):
    def classify(self, rec, res=None, factory=(), pin=None):
        return classify_element(rec, pin or PIN, res or resolution(), set(factory))

    def test_build_only_element_needs_no_rpm(self) -> None:
        decision = self.classify(record("freedesktop-sdk.bst:components/meson.bst", in_image=False),
                                 resolution("meson"))
        self.assertEqual(decision["disposition"], NOT_APPLICABLE)
        self.assertEqual(decision["reason"], BUILD_ONLY_REASON)

    def test_dakota_config_element(self) -> None:
        decision = self.classify(record("bluefin/udev-groups.bst", sources=("local",)))
        self.assertEqual(decision["disposition"], DAKOTA_CONFIG)
        self.assertEqual(decision["rpm"], "dakota-config")
        self.assertEqual(decision["subpackage"], "dakota-config-udev-groups")

    def test_gbm_config_element_needs_local_sources(self) -> None:
        decision = self.classify(record("gnome-build-meta.bst:gnomeos-deps/uinput.bst", sources=("local",)))
        self.assertEqual(decision["disposition"], GNOMEOS_CONFIG)
        self.assertEqual(decision["subpackage"], "gnome-os-config-uinput")
        # A gbm element with no source at all is a filter of a component.
        decision = self.classify(record("gnome-build-meta.bst:core-deps/systemd.bst", sources=()),
                                 resolution("systemd", hummingbird=True))
        self.assertEqual(decision["disposition"], HUMMINGBIRD)

    def test_fdsdk_local_element_is_not_a_config_package(self) -> None:
        decision = self.classify(record("freedesktop-sdk.bst:components/bash-config.bst", sources=("local",)),
                                 resolution("bash", hummingbird=True))
        self.assertEqual(decision["disposition"], HUMMINGBIRD)

    def test_availability_precedence(self) -> None:
        rec = record("freedesktop-sdk.bst:components/jq.bst")
        self.assertEqual(self.classify(rec, resolution("jq", True), {"jq"})["disposition"], FACTORY)
        self.assertEqual(self.classify(rec, resolution("jq", True))["disposition"], HUMMINGBIRD)
        self.assertEqual(self.classify(rec, resolution("jq"))["disposition"], FEDORA_IMPORTABLE)
        decision = self.classify(rec)
        self.assertEqual(decision["disposition"], NEW_SPEC)
        self.assertIsNone(decision["rpm"])

    def test_factory_authored_recipe_without_fedora_source(self) -> None:
        decision = self.classify(record("bluefin/uupd.bst"), factory={"uupd"})
        self.assertEqual((decision["disposition"], decision["rpm"]), (FACTORY, "uupd"))

    def test_override_wins_and_carries_the_issue(self) -> None:
        pin = copy.deepcopy(PIN)
        pin["overrides"]["bluefin/kanata.bst"] = {
            "disposition": STRUCTURAL, "issue": "#1222", "reason": "kanata vs input-remapper"}
        decision = self.classify(record("bluefin/kanata.bst"), resolution("kanata"), pin=pin)
        self.assertEqual((decision["disposition"], decision["issue"]), (STRUCTURAL, "#1222"))
        self.assertTrue(decision["override"])

    def test_new_spec_override_becomes_factory_once_the_recipe_lands(self) -> None:
        pin = copy.deepcopy(PIN)
        pin["overrides"]["bluefin/x.bst"] = {
            "disposition": NEW_SPEC, "rpm": "x", "reason": "Fedora's x is another project"}
        self.assertEqual(self.classify(record("bluefin/x.bst"), pin=pin)["disposition"], NEW_SPEC)
        self.assertEqual(self.classify(record("bluefin/x.bst"), pin=pin, factory={"x"})["disposition"],
                         FACTORY)

    def test_config_override_names_the_subpackage(self) -> None:
        pin = copy.deepcopy(PIN)
        pin["overrides"]["gnome-build-meta.bst:gnomeos-deps/ld-config.bst"] = {
            "disposition": GNOMEOS_CONFIG, "reason": "written inline"}
        decision = self.classify(record("gnome-build-meta.bst:gnomeos-deps/ld-config.bst", sources=()),
                                 pin=pin)
        self.assertEqual(decision["subpackage"], "gnome-os-config-ld-config")


class PinValidationTests(unittest.TestCase):
    def assert_rejected(self, mutate) -> None:
        pin = copy.deepcopy(PIN)
        mutate(pin)
        with self.assertRaises(ValueError):
            validate_pin(pin)

    def test_measured_dispositions_cannot_be_asserted(self) -> None:
        self.assert_rejected(lambda p: p["overrides"].update(
            {"a.bst": {"disposition": FEDORA_IMPORTABLE, "reason": "x"}}))

    def test_override_needs_a_reason(self) -> None:
        self.assert_rejected(lambda p: p["overrides"].update(
            {"a.bst": {"disposition": NOT_APPLICABLE, "reason": " "}}))

    def test_structural_needs_a_parity_issue(self) -> None:
        self.assert_rejected(lambda p: p["overrides"].update(
            {"a.bst": {"disposition": STRUCTURAL, "reason": "x"}}))
        self.assert_rejected(lambda p: p["overrides"].update(
            {"a.bst": {"disposition": STRUCTURAL, "issue": "#999", "reason": "x"}}))

    def test_pins_are_full_identities(self) -> None:
        self.assert_rejected(lambda p: p["source"].update({"revision": "bf27177"}))
        self.assert_rejected(lambda p: p["source"].update({"image_digest": "testing"}))

    def test_config_subpackage_belongs_to_a_config_package(self) -> None:
        self.assert_rejected(lambda p: p.update(
            {"config_subpackages": {"bluefin/rpcbind.bst": ["rpcbind-preset"]}}))

    def test_committed_pin_is_valid_and_maps_every_snapshot_element(self) -> None:
        pin = load_pin(REPO / "config" / "dakota.json")
        records = read_snapshot(REPO / "config" / "dakota-elements.tsv")
        self.assertEqual(sorted(pin["elements"]), [r.element for r in records])
        self.assertTrue(pin["source"]["sbom"])


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            record("freedesktop-sdk.bst:components/bluez.bst", sources=(), units=2),
            record("freedesktop-sdk.bst:components/_private/bluez-base.bst", in_image=False,
                   sources=("git_repo",), version="5.87"),
            record("gnome-build-meta.bst:core/baobab.bst", version="50.0", apps=1),
            record("freedesktop-sdk.bst:components/libfoo.bst", version="1.0"),
            record("freedesktop-sdk.bst:components/libfoo-tools.bst", commands=1),
            record("bluefin/nerd-fonts-symbols.bst", version="v3.5.1"),
        ]
        self.pin = copy.deepcopy(PIN)
        self.pin["elements"] = {
            "freedesktop-sdk.bst:components/bluez.bst":
                {"disposition": FEDORA_IMPORTABLE, "fedora": "bluez", "hummingbird": False},
            "freedesktop-sdk.bst:components/_private/bluez-base.bst":
                {"disposition": NOT_APPLICABLE, "fedora": "bluez", "hummingbird": False},
            "gnome-build-meta.bst:core/baobab.bst":
                {"disposition": FEDORA_IMPORTABLE, "fedora": "baobab", "hummingbird": False},
            "freedesktop-sdk.bst:components/libfoo.bst":
                {"disposition": FEDORA_IMPORTABLE, "fedora": "foo", "hummingbird": False},
            "freedesktop-sdk.bst:components/libfoo-tools.bst":
                {"disposition": FEDORA_IMPORTABLE, "fedora": "foo", "hummingbird": False},
            "bluefin/nerd-fonts-symbols.bst":
                {"disposition": NEW_SPEC, "fedora": None, "hummingbird": False},
        }
        self.locks = {"bluez": {"name": "bluez", "version": "5.87"}}
        self.report = build_report(self.pin, self.records, self.locks)

    def test_counts_cover_every_element(self) -> None:
        self.assertEqual(sum(self.report["counts"].values()), len(self.records))
        self.assertEqual(self.report["counts"][FACTORY], 1)

    def test_a_landed_recipe_makes_the_recorded_mapping_stale(self) -> None:
        self.assertEqual(self.report["stale_mappings"], [{
            "element": "freedesktop-sdk.bst:components/bluez.bst",
            "recorded": FEDORA_IMPORTABLE, "now": FACTORY, "rpm": "bluez"}])

    def test_split_element_takes_the_version_of_its_sibling(self) -> None:
        (drift,) = self.report["drift"]
        self.assertEqual(drift["dakota_version"], "5.87")
        self.assertEqual(drift["classification"], ALIGNED)
        self.assertIn("_private/bluez-base.bst", drift["reason"])

    def test_import_queue_is_one_row_per_rpm_user_visible_first(self) -> None:
        queue = self.report["import_queue"][FEDORA_IMPORTABLE]
        self.assertEqual([row["name"] for row in queue], ["baobab", "foo"])
        self.assertEqual(queue[1]["visibility"], "commands")
        self.assertEqual(len(queue[1]["elements"]), 2)
        self.assertEqual(self.report["import_queue"][NEW_SPEC][0]["dakota_versions"], ["3.5.1"])

    def test_build_only_elements_are_listed_by_name(self) -> None:
        self.assertEqual(self.report["build_only"],
                         ["freedesktop-sdk.bst:components/_private/bluez-base.bst"])
        self.assertNotIn("freedesktop-sdk.bst:components/_private/bluez-base.bst",
                         [e["element"] for e in self.report["elements"]])

    def test_markdown_has_every_section(self) -> None:
        text = render_markdown(self.report)
        for heading in ("## Dispositions", "Fedora-importable, no factory recipe",
                        "new spec from the .bst", "## Version drift", "## Structural",
                        "## Config packages", "## Stale mappings"):
            self.assertIn(heading, text)
        self.assertIn("| apps | baobab | 50.0 |", text)


class ConfigGapTests(unittest.TestCase):
    def test_missing_subpackages_are_reported_against_the_recipe(self) -> None:
        pin = copy.deepcopy(PIN)
        pin["config_subpackages"] = {"bluefin/rpcbind.bst": ["dakota-config-rpcbind-preset"]}
        records = [record("bluefin/udev-groups.bst", sources=("local",)),
                   record("bluefin/network.bst", sources=()),
                   record("bluefin/rpcbind.bst")]
        with tempfile.TemporaryDirectory() as tmp:
            packages = Path(tmp)
            report = build_report(pin, records, {}, packages)
            self.assertFalse(report["config_gaps"]["dakota-config"]["recipe"])
            spec = packages / "dakota-config" / "dakota-config.spec"
            spec.parent.mkdir()
            spec.write_text("Name: dakota-config\n%package udev-groups\n"
                            "%package -n dakota-config-rpcbind-preset\n")
            self.assertEqual(spec_subpackages(spec),
                             {"dakota-config-udev-groups", "dakota-config-rpcbind-preset"})
            report = build_report(pin, records, {}, packages)
            self.assertEqual(report["config_gaps"]["dakota-config"],
                             {"recipe": True, "missing": ["dakota-config-network"]})


SBOM = {
    "documentNamespace": "https://github.com/projectbluefin/dakota/sbom/" + "b" * 40,
    "packages": [
        {"name": "ghostty", "SPDXID": "SPDXRef-bluefin-ghostty.bst",
         "externalRefs": [{"referenceType": "bst-element", "referenceLocator": "bluefin/ghostty.bst"}]},
        {"name": "ghostty", "SPDXID": "SPDXRef-bluefin-ghostty.bst-1", "sourceInfo": "patch",
         "versionInfo": "db92", "downloadLocation": "patches/ghostty/0001.patch"},
        {"name": "ghostty", "SPDXID": "SPDXRef-bluefin-ghostty.bst-0", "sourceInfo": "tar",
         "versionInfo": "1.4.0", "downloadLocation": "https://release.files.ghostty.org/1.4.0/ghostty-1.4.0.tar.gz"},
        {"name": "zig-dep", "SPDXID": "SPDXRef-bluefin-ghostty.bst-2", "sourceInfo": "remote",
         "versionInfo": "0.1", "downloadLocation": "https://deps/zig-dep-0.1.tar.gz"},
        {"name": "meson", "SPDXID": "SPDXRef-freedesktop-sdk.bst-components-meson.bst",
         "externalRefs": [{"referenceType": "bst-element",
                           "referenceLocator": "freedesktop-sdk.bst:components/meson.bst"}]},
    ],
    "relationships": [
        {"spdxElementId": "SPDXRef-bluefin-ghostty.bst", "relationshipType": "GENERATED_FROM",
         "relatedSpdxElement": f"SPDXRef-bluefin-ghostty.bst-{n}"} for n in (2, 1, 0)
    ],
}


def _layer(members: list[tuple[str, str | None]]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path, owner in members:
            info = tarfile.TarInfo(path)
            if owner:
                info.pax_headers = {"SCHILY.xattr.user.component": owner}
            tar.addfile(info, io.BytesIO(b""))
    return gzip.compress(raw.getvalue())


class SnapshotTests(unittest.TestCase):
    def test_image_ownership_counts_user_visible_files(self) -> None:
        stats = image_ownership([
            ("usr/bin/ghostty", "bluefin/ghostty.bst"),
            ("./usr/share/applications/com.mitchellh.ghostty.desktop", "bluefin/ghostty.bst"),
            ("usr/lib/systemd/user/app-ghostty.service", "bluefin/ghostty.bst"),
            ("usr/share/ghostty/themes/x", "bluefin/ghostty.bst"),
            ("etc/unowned", None),
        ])
        self.assertEqual(stats, {"bluefin/ghostty.bst":
                                 {"files": 4, "apps": 1, "units": 1, "commands": 1}})

    def test_snapshot_joins_sbom_and_ownership(self) -> None:
        records = build_snapshot(SBOM, {"bluefin/ghostty.bst": {"files": 3, "apps": 1}})
        ghostty, meson = records
        self.assertEqual(ghostty.element, "bluefin/ghostty.bst")
        self.assertTrue(ghostty.in_image)
        self.assertEqual((ghostty.version, ghostty.patches), ("1.4.0", 1))
        self.assertEqual(ghostty.sources, ("patch", "remote", "tar"))
        self.assertFalse(meson.in_image)

    def test_snapshot_round_trips(self) -> None:
        records = build_snapshot(SBOM, {"bluefin/ghostty.bst": {"files": 3, "apps": 1}})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "elements.tsv"
            write_snapshot(path, records)
            self.assertEqual(read_snapshot(path), records)

    def test_layout_scan_reads_chunkah_xattrs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            layout = Path(tmp)
            blobs = layout / "blobs" / "sha256"
            blobs.mkdir(parents=True)
            layer = _layer([("usr/bin/jq", "components/jq.bst"), ("usr/share/doc/x", None)])
            (blobs / "11").write_bytes(layer)
            manifest = {"layers": [{"digest": "sha256:11"}]}
            (blobs / "22").write_text(json.dumps(manifest))
            stats = scan_image_layout(layout, "sha256:22")
            self.assertEqual(stats, {"components/jq.bst":
                                     {"files": 1, "apps": 0, "units": 0, "commands": 1}})
            with self.assertRaises(SystemExit):
                scan_image_layout(layout, "sha256:33")


PRIMARY = b"""<?xml version="1.0"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm">
<package type="rpm"><name>pulseaudio-libs</name>
<format><rpm:sourcerpm>pulseaudio-17.0-5.fc45.src.rpm</rpm:sourcerpm></format></package>
<package type="rpm"><name>python3-six</name>
<format><rpm:sourcerpm>python-six-1.17.0-10.fc45.src.rpm</rpm:sourcerpm></format></package>
</metadata>
"""


class RefreshTests(unittest.TestCase):
    def test_primary_maps_binaries_to_sources(self) -> None:
        self.assertEqual(parse_primary(PRIMARY),
                         {"pulseaudio-libs": "pulseaudio", "python3-six": "python-six"})

    def test_refresh_resolves_and_records_evidence(self) -> None:
        binaries = parse_primary(PRIMARY)
        index = FedoraIndex(set(binaries.values()), binaries)
        records = [
            record("freedesktop-sdk.bst:components/libpulse.bst", name="libpulse"),
            record("freedesktop-sdk.bst:components/python3-six.bst"),
            record("freedesktop-sdk.bst:components/gnupg.bst"),
        ]
        pin = copy.deepcopy(PIN)
        pin["aliases"] = {"freedesktop-sdk.bst:components/libpulse.bst": ["pulseaudio-libs"]}
        heads = {"pulseaudio": True, "python-six": None, "gnupg": True}
        elements = refresh_mapping(pin, records, index, {"pulseaudio"}, set(),
                                   head=lambda name: heads.get(name, False))
        pulse = elements["freedesktop-sdk.bst:components/libpulse.bst"]
        self.assertEqual((pulse["disposition"], pulse["fedora"]), (HUMMINGBIRD, "pulseaudio"))
        self.assertIn("dist-git rpms/pulseaudio exists", pulse["evidence"])
        six = elements["freedesktop-sdk.bst:components/python3-six.bst"]
        self.assertEqual(six["disposition"], FEDORA_IMPORTABLE)
        self.assertIn("unreachable", six["evidence"])
        gnupg = elements["freedesktop-sdk.bst:components/gnupg.bst"]
        self.assertEqual(gnupg["disposition"], NEW_SPEC)
        self.assertIn("retired", gnupg["evidence"])

    def test_gnome_build_meta_mapping_is_reused(self) -> None:
        aliases = gnome_build_meta_aliases({
            "mapping": {"gtk4": "sdk/gtk.bst", "gvfs-client": "sdk/gvfs-client.bst"},
            "factory_alias": {"gvfs-client": "gvfs"},
        })
        self.assertEqual(aliases, {"gnome-build-meta.bst:sdk/gtk.bst": ["gtk4"],
                                   "gnome-build-meta.bst:sdk/gvfs-client.bst": ["gvfs"]})


class CheckTests(unittest.TestCase):
    """--check: the gate CI runs instead of diffing a committed report (#309)."""

    def setUp(self) -> None:
        self.records = [record("bluefin/a.bst"), record("bluefin/b.bst")]
        self.pin = copy.deepcopy(PIN)
        self.pin["elements"] = {"bluefin/a.bst": {"disposition": NEW_SPEC},
                                "bluefin/b.bst": {"disposition": NEW_SPEC}}

    def test_a_mapping_of_exactly_the_snapshot_passes(self) -> None:
        self.assertEqual(contract_problems(self.pin, self.records), [])

    def test_an_element_missing_from_either_side_fails(self) -> None:
        del self.pin["elements"]["bluefin/b.bst"]
        self.pin["elements"]["bluefin/gone.bst"] = {"disposition": NEW_SPEC}
        problems = contract_problems(self.pin, self.records)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("bluefin/b.bst: in the snapshot"))
        self.assertTrue(problems[1].startswith("bluefin/gone.bst: in the mapping"))

    def test_a_decision_about_an_unknown_element_fails(self) -> None:
        self.pin["overrides"]["bluefin/typo.bst"] = {"disposition": NOT_APPLICABLE, "reason": "x"}
        self.pin["aliases"]["bluefin/typo2.bst"] = ["x"]
        self.pin["config_subpackages"] = {"bluefin/typo3.bst": ["dakota-config-x"]}
        self.assertEqual(contract_problems(self.pin, self.records), [
            "overrides bluefin/typo.bst: not an element of the snapshot",
            "aliases bluefin/typo2.bst: not an element of the snapshot",
            "config_subpackages bluefin/typo3.bst: not an element of the snapshot",
        ])

    def test_a_stale_disposition_is_not_a_problem(self) -> None:
        # Importing a recipe makes the recorded disposition stale; an import
        # PR must pass the gate without touching config/dakota.json.
        self.pin["elements"]["bluefin/a.bst"]["disposition"] = FEDORA_IMPORTABLE
        self.assertEqual(contract_problems(self.pin, self.records), [])

    def test_check_writes_nothing_and_passes_on_the_committed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            code = main(["--check", "--json-out", str(out / "a.json"),
                         "--markdown-out", str(out / "a.md")])
            self.assertEqual(code, 0)
            self.assertEqual(list(out.iterdir()), [])

    def test_check_fails_on_a_broken_pin(self) -> None:
        pin = json.loads((REPO / "config" / "dakota.json").read_text())
        pin["overrides"]["bluefin/not-an-element.bst"] = {"disposition": NOT_APPLICABLE,
                                                          "reason": "x"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dakota.json"
            path.write_text(json.dumps(pin))
            self.assertEqual(main(["--check", "--pin", str(path)]), 1)

    def test_check_refuses_to_write(self) -> None:
        self.assertEqual(main(["--check", "--refresh"]), 2)

    def test_the_report_is_ignored_not_committed(self) -> None:
        ignored = (REPO / ".gitignore").read_text().splitlines()
        self.assertIn("reports/audit-dakota.json", ignored)
        self.assertIn("reports/audit-dakota.md", ignored)


if __name__ == "__main__":
    unittest.main()
