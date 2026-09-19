#!/usr/bin/env python3

import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.package_inventory import source_locks
from tools.upstream_bump import (
    apply,
    cycle_final,
    release_cycle,
    gnome_module,
    is_prerelease,
    major,
    newest_stable,
    plan,
    planned_entry,
    rewrite_spec,
    rewrite_sources,
    rpm_version,
    tarball_version,
    version_key,
    forge_feed,
    forge_label,
    forge_planned_entry,
    forge_proposal,
    forge_versions,
    strip_tag_prefix,
    substituted,
    candidates,
    parse_feed,
    resolve_feed,
    anitya_versions,
    anitya_proposal,
    audit_inventory,
    is_url_pollable,
)

ROOT = Path(__file__).resolve().parent.parent

# The real gnome-shell index, trimmed: alpha, beta and rc all precede 51.0.
GNOME_SHELL_CACHE = [4, {}, {"gnome-shell": ["50.5", "51.alpha", "51.beta", "51.rc", "51.0"]}, {}]


class VersionSpellingTests(unittest.TestCase):
    """RPM and the tarball spell a prerelease differently; both come from one string."""

    def test_recognises_every_prerelease_spelling_gnome_uses(self) -> None:
        for version in ("51.beta", "51~rc", "51.alpha", "1.10.beta.1", "3.12~beta"):
            self.assertTrue(is_prerelease(version), version)

    def test_a_final_release_is_not_a_prerelease(self) -> None:
        for version in ("51.0", "4.23.3", "1.58.2", "49.0"):
            self.assertFalse(is_prerelease(version), version)

    def test_does_not_mistake_a_digit_run_for_a_prerelease(self) -> None:
        # "rc" inside a word is not a prerelease marker; the separator matters.
        self.assertFalse(is_prerelease("1.2.3"))
        self.assertFalse(is_prerelease("51.0"))

    def test_rpm_sorts_a_prerelease_below_its_final_with_a_tilde(self) -> None:
        self.assertEqual(rpm_version("51.beta"), "51~beta")
        self.assertEqual(rpm_version("51.alpha"), "51~alpha")
        self.assertEqual(rpm_version("1.10.beta.1"), "1.10~beta.1")

    def test_a_final_release_needs_no_tilde(self) -> None:
        self.assertEqual(rpm_version("51.0"), "51.0")

    def test_the_tarball_spells_a_prerelease_with_a_dot(self) -> None:
        self.assertEqual(tarball_version("51~beta"), "51.beta")
        self.assertEqual(tarball_version("51.0"), "51.0")

    def test_the_two_spellings_round_trip(self) -> None:
        for version in ("51.beta", "51.0", "1.10.beta.1"):
            self.assertEqual(tarball_version(rpm_version(version)), version)

    def test_a_release_is_filed_under_its_leading_component(self) -> None:
        self.assertEqual(major("51.0"), "51")
        self.assertEqual(major("1.10.beta.1"), "1")


class ReleaseSelectionTests(unittest.TestCase):
    def test_picks_the_final_over_every_prerelease_of_the_same_cycle(self) -> None:
        self.assertEqual(newest_stable(["51.alpha", "51.beta", "51.rc", "51.0"]), "51.0")

    def test_orders_numerically_not_lexically(self) -> None:
        # "9" > "10" as strings; the whole point of the key.
        self.assertEqual(newest_stable(["1.9.0", "1.10.0"]), "1.10.0")
        self.assertEqual(newest_stable(["49.0", "50.5", "51.0"]), "51.0")

    def test_returns_none_when_a_module_has_only_prereleases(self) -> None:
        self.assertIsNone(newest_stable(["51.alpha", "51.beta"]))

    def test_a_malformed_component_does_not_raise(self) -> None:
        self.assertEqual(version_key("51.x")[1], -1)


class ReleaseCycleTests(unittest.TestCase):
    """GNOME uses two numbering schemes; the cycle sits in a different place."""

    def test_the_app_scheme_puts_the_cycle_in_the_leading_number(self) -> None:
        for version in ("51.beta", "51.0", "51.alpha", "49.0"):
            self.assertEqual(release_cycle(version), version.split(".")[0])

    def test_the_library_scheme_puts_the_cycle_in_major_minor(self) -> None:
        self.assertEqual(release_cycle("1.58.2"), "1.58")
        self.assertEqual(release_cycle("4.23.3"), "4.23")
        self.assertEqual(release_cycle("1.61.91"), "1.61")

    def test_a_library_prerelease_keeps_its_numeric_prefix(self) -> None:
        self.assertEqual(release_cycle("1.10.beta.1"), "1.10")


class CycleScopeTests(unittest.TestCase):
    """A cross-cycle jump is never applied; the number cannot decide it."""

    PANGO = ["1.56.4", "1.57.0", "1.57.1", "1.58.0", "1.58.2", "1.90.0"]

    def test_stays_inside_the_cycle_the_lock_names(self) -> None:
        self.assertEqual(cycle_final(self.PANGO, "1.58"), "1.58.2")

    def test_does_not_treat_a_development_series_as_an_in_cycle_successor(self) -> None:
        # The regression this guards: an earlier draft read pango's cycle as
        # "1", so 1.90.0 -- the development series toward 2.0 -- looked like the
        # newest release in the same cycle as the stable 1.58.2, and the tool
        # proposed 1.58.2 -> 1.90.0. Neither "highest" nor "even minor" rejects
        # it: 90 is even and it sorts above everything.
        self.assertNotEqual(cycle_final(self.PANGO, release_cycle("1.58.2")), "1.90.0")

    def test_finds_the_release_that_ends_a_prerelease_cycle(self) -> None:
        self.assertEqual(cycle_final(["51.alpha", "51.beta", "51.rc", "51.0"], "51"), "51.0")

    def test_a_cycle_with_nothing_released_yet_yields_none(self) -> None:
        self.assertIsNone(cycle_final(["51.alpha", "51.beta"], "51"))

    def test_ignores_releases_from_other_cycles(self) -> None:
        self.assertIsNone(cycle_final(["50.5", "52.0"], "51"))


class ModuleDetectionTests(unittest.TestCase):
    def test_reads_the_module_out_of_a_gnome_source_url(self) -> None:
        entry = {"url": "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.beta.tar.xz"}
        self.assertEqual(gnome_module(entry), "gnome-shell")

    def test_ignores_a_lock_hosted_anywhere_else(self) -> None:
        for url in (
            "https://src.fedoraproject.org/repo/pkgs/rpms/nautilus/nautilus-51.tar.xz",
            "https://github.com/tailscale/tailscale/archive/v1.98.8.tar.gz",
        ):
            self.assertIsNone(gnome_module({"url": url}))

    def test_an_entry_with_no_url_is_not_a_gnome_module(self) -> None:
        self.assertIsNone(gnome_module({}))


class EntryRewriteTests(unittest.TestCase):
    """Every URL is rebuilt from the release, so no field keeps the old tarball."""

    def setUp(self) -> None:
        self.entry = {
            "name": "gnome-shell",
            "version": "51.beta",
            "url": "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.beta.tar.xz",
            "filename": "gnome-shell-51.beta.tar.xz",
            "sha512": "old" * 42 + "aa",
            "sha256_url": "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.beta.sha256sum",
            "stage": 10,
            "fallback_urls": [
                "https://src.fedoraproject.org/repo/pkgs/rpms/gnome-shell/"
                "gnome-shell-51.beta.tar.xz/sha512/" + "old" * 42 + "aa/gnome-shell-51.beta.tar.xz"
            ],
        }

    def test_rewrites_every_field_that_names_the_release(self) -> None:
        new = planned_entry(self.entry, "51.0", "f" * 128)
        self.assertEqual(new["version"], "51.0")
        self.assertEqual(new["filename"], "gnome-shell-51.0.tar.xz")
        self.assertEqual(
            new["url"], "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.0.tar.xz"
        )
        self.assertEqual(
            new["sha256_url"],
            "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.0.sha256sum",
        )
        self.assertEqual(new["sha512"], "f" * 128)

    def test_no_field_keeps_the_superseded_version_or_digest(self) -> None:
        new = planned_entry(self.entry, "51.0", "f" * 128)
        rendered = json.dumps(new)
        self.assertNotIn("51.beta", rendered)
        self.assertNotIn("old" * 42, rendered)

    def test_the_lookaside_fallback_carries_the_new_digest_and_name(self) -> None:
        new = planned_entry(self.entry, "51.0", "f" * 128)
        self.assertEqual(
            new["fallback_urls"],
            [
                "https://src.fedoraproject.org/repo/pkgs/rpms/gnome-shell/"
                "gnome-shell-51.0.tar.xz/sha512/" + "f" * 128 + "/gnome-shell-51.0.tar.xz"
            ],
        )

    def test_keeps_the_fields_a_bump_must_not_touch(self) -> None:
        new = planned_entry(self.entry, "51.0", "f" * 128)
        self.assertEqual(new["stage"], 10)
        self.assertEqual(new["name"], "gnome-shell")

    def test_does_not_invent_optional_fields_the_entry_lacks(self) -> None:
        bare = {k: v for k, v in self.entry.items() if k not in ("sha256_url", "fallback_urls")}
        new = planned_entry(bare, "51.0", "f" * 128)
        self.assertNotIn("sha256_url", new)
        self.assertNotIn("fallback_urls", new)


class SpecRewriteTests(unittest.TestCase):
    def test_writes_the_rpm_spelling_not_the_tarball_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "gnome-shell.spec"
            spec.write_text("Name:           gnome-shell\nVersion:        51~beta\nRelease:  1\n")
            self.assertTrue(rewrite_spec(spec, "51.0"))
            self.assertIn("Version:        51.0", spec.read_text())

    def test_leaves_the_rest_of_the_spec_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "x.spec"
            body = "Name:  x\nVersion:        51~beta\n%description\nVersion: not a field\n"
            spec.write_text(body)
            rewrite_spec(spec, "51.0")
            # Only the real Version: field moves; the prose line is untouched.
            self.assertIn("Version: not a field", spec.read_text())

    def test_reports_no_change_when_already_at_the_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "x.spec"
            spec.write_text("Version:        51.0\n")
            self.assertFalse(rewrite_spec(spec, "51.0"))

    def test_refuses_a_spec_with_no_version_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "x.spec"
            spec.write_text("Name: x\n")
            with self.assertRaises(ValueError):
                rewrite_spec(spec, "51.0")


class SourcesManifestTests(unittest.TestCase):
    def test_writes_the_format_fedora_dist_git_uses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "sources"
            rewrite_sources(manifest, "gnome-shell-51.0.tar.xz", "f" * 128)
            self.assertEqual(
                manifest.read_text(), f"SHA512 (gnome-shell-51.0.tar.xz) = {'f' * 128}\n"
            )


def fake_opener(payloads: dict):
    """Serve canned bytes per URL so no test reaches the network."""

    def opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url not in payloads:
            raise OSError(f"unexpected request: {url}")
        return io.BytesIO(payloads[url])

    return opener


class PlanTests(unittest.TestCase):
    """plan() reads the real inventory but never the network."""

    def test_proposes_the_final_for_a_locked_prerelease(self) -> None:
        opener = fake_opener(
            {
                "https://download.gnome.org/sources/gnome-shell/cache.json": json.dumps(
                    GNOME_SHELL_CACHE
                ).encode()
            }
        )
        proposals = plan(ROOT, only="gnome-shell", opener=opener)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "final")
        self.assertEqual(proposals[0]["current"], "51.beta")
        self.assertEqual(proposals[0]["latest"], "51.0")

    def test_a_cross_cycle_candidate_is_flagged_for_review_not_applied(self) -> None:
        cache = [4, {}, {"pango": CycleScopeTests.PANGO}, {}]
        opener = fake_opener(
            {"https://download.gnome.org/sources/pango/cache.json": json.dumps(cache).encode()}
        )
        proposals = plan(ROOT, only="pango", opener=opener)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "review")
        self.assertEqual(proposals[0]["latest"], "1.90.0")

    def test_proposes_nothing_while_the_cycle_is_still_in_prerelease(self) -> None:
        # 51 has not shipped yet: there is nothing to bump to, which is not an
        # error. The lock stays on the prerelease it already names.
        cache = [4, {}, {"gnome-shell": ["50.5", "51.alpha", "51.beta"]}, {}]
        opener = fake_opener(
            {
                "https://download.gnome.org/sources/gnome-shell/cache.json": json.dumps(
                    cache
                ).encode()
            }
        )
        self.assertEqual(plan(ROOT, only="gnome-shell", opener=opener), [])

    def test_proposes_nothing_when_the_lock_is_already_the_cycle_final(self) -> None:
        cache = [4, {}, {"pango": ["1.58.0", "1.58.2"]}, {}]
        opener = fake_opener(
            {"https://download.gnome.org/sources/pango/cache.json": json.dumps(cache).encode()}
        )
        self.assertEqual(plan(ROOT, only="pango", opener=opener), [])

    def test_an_unreachable_module_is_reported_not_raised(self) -> None:
        proposals = plan(ROOT, only="gnome-shell", opener=fake_opener({}))
        self.assertEqual(len(proposals), 1)
        self.assertIn("error", proposals[0])

    def test_skips_pinned_packages(self) -> None:
        # color-filesystem is pinned (recipe file only), so it is out of scope for bumps.
        self.assertEqual(plan(ROOT, only="color-filesystem", opener=fake_opener({})), [])


class ApplyTests(unittest.TestCase):
    """apply() moves all three files together, against a scratch tree."""

    def test_writes_inventory_spec_and_manifest_from_the_fetched_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            package = root / "packages" / "gnome-shell"
            package.mkdir(parents=True)
            entry = {
                "name": "gnome-shell",
                "version": "51.beta",
                "url": "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.beta.tar.xz",
                "filename": "gnome-shell-51.beta.tar.xz",
                "sha512": "0" * 128,
                "stage": 10,
            }
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [entry]}, indent=2) + "\n"
            )
            (package / "gnome-shell.spec").write_text("Version:        51~beta\n")
            (package / "sources").write_text(
                f"SHA512 (gnome-shell-51.beta.tar.xz) = {'0' * 128}\n"
            )

            payload = b"a plausible tarball"
            import hashlib

            expected = hashlib.sha512(payload).hexdigest()
            opener = fake_opener(
                {
                    "https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.0.tar.xz": payload
                }
            )
            apply(root, {"name": "gnome-shell", "latest": "51.0"}, opener=opener)

            written = json.loads((root / "config" / "upstream-sources.json").read_text())
            self.assertEqual(written["packages"][0]["version"], "51.0")
            self.assertEqual(written["packages"][0]["sha512"], expected)
            self.assertIn("Version:        51.0", (package / "gnome-shell.spec").read_text())
            self.assertEqual(
                (package / "sources").read_text(),
                f"SHA512 (gnome-shell-51.0.tar.xz) = {expected}\n",
            )

    def test_the_digest_is_the_real_one_not_the_one_it_replaced(self) -> None:
        # The failure this guards against is a bump that moves the version and
        # keeps the old checksum: source_pipeline.py would reject it, and the
        # bump would look done while being unusable.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "packages" / "pango").mkdir(parents=True)
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "pango",
                                "version": "1.58.2",
                                "url": "https://download.gnome.org/sources/pango/1/pango-1.58.2.tar.xz",
                                "filename": "pango-1.58.2.tar.xz",
                                "sha512": "d" * 128,
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n"
            )
            opener = fake_opener(
                {"https://download.gnome.org/sources/pango/1/pango-1.59.0.tar.xz": b"bytes"}
            )
            updated = apply(root, {"name": "pango", "latest": "1.59.0"}, opener=opener)
            self.assertNotEqual(updated["sha512"], "d" * 128)




class ForgeFeedDetectionTests(unittest.TestCase):
    """Which locks this tool can poll, and which it must leave alone."""

    def feed(self, url):
        return forge_feed({"name": "x", "url": url})

    def test_github_archive_and_release_shapes_are_distinguished(self):
        archive = self.feed(
            "https://github.com/rockowitz/ddcutil/archive/v2.2.1/ddcutil-2.2.1.tar.gz"
        )
        self.assertEqual(
            (archive["forge"], archive["endpoint"], archive["owner"], archive["repo"]),
            ("github", "tags", "rockowitz", "ddcutil"),
        )
        release = self.feed(
            "https://github.com/lassekongo83/adw-gtk3/releases/download/v6.4/adw-gtk3v6.4.tar.xz"
        )
        self.assertEqual(
            (release["forge"], release["endpoint"], release["repo"]),
            ("github", "releases", "adw-gtk3"),
        )

    def test_gitlab_archive_release_and_plain_http_all_resolve(self):
        for url, path in (
            ("https://gitlab.freedesktop.org/camera/libcamera/-/archive/0.6.0/x.tar.bz2",
             "camera/libcamera"),
            ("https://gitlab.freedesktop.org/wayland/wayland-protocols/-/releases/1.49/downloads/x.tar.xz",
             "wayland/wayland-protocols"),
            ("http://gitlab.freedesktop.org/libevdev/evtest/-/archive/evtest-1.36/x.tar.bz2",
             "libevdev/evtest"),
        ):
            with self.subTest(url=url):
                feed = self.feed(url)
                self.assertEqual(feed["forge"], "gitlab")
                self.assertEqual(feed["path"], path)

    def test_sources_without_a_release_feed_are_not_claimed(self):
        for url in (
            "https://src.fedoraproject.org/repo/pkgs/rpms/speex/speex-1.2.0.tar.gz/sha512/7fe/speex-1.2.0.tar.gz",
            "https://xorg.freedesktop.org/archive/individual/app/igt-gpu-tools-2.5.tar.xz",
            "https://download.gnome.org/sources/gtk4/4.23/gtk4-4.23.3.tar.xz",
        ):
            with self.subTest(url=url):
                self.assertIsNone(self.feed(url))

    def test_candidates_claim_all_automatable_locks(self):
        locks = source_locks(ROOT)
        found = candidates(locks)
        names = [name for name, _, _ in found]
        self.assertEqual(len(names), len(set(names)), "a lock was claimed twice")
        for name, entry, feed in found:
            with self.subTest(package=name):
                if entry.get("feed") and "download.gnome.org" in entry["feed"]:
                    self.assertEqual(feed["forge"], "gnome")
                elif entry.get("url", "").startswith("https://download.gnome.org/sources/"):
                    self.assertEqual(feed["forge"], "gnome")


class TagParsingTests(unittest.TestCase):
    def test_version_is_recovered_from_common_tag_spellings(self):
        for tag, expected in (
            ("v2.2.1", "2.2.1"),
            ("2.2.1", "2.2.1"),
            ("release-1.4", "1.4"),
            ("V3.0", "3.0"),
            ("evtest-1.36", "1.36"),
            ("xdg-desktop-portal-1.20.0", "1.20.0"),
        ):
            with self.subTest(tag=tag):
                self.assertEqual(strip_tag_prefix(tag), expected)

    def test_tags_that_are_not_versions_are_dropped(self):
        for tag in ("main", "stable", "v", "", "HEAD"):
            with self.subTest(tag=tag):
                self.assertEqual(strip_tag_prefix(tag), "")


class ForgeVersionListingTests(unittest.TestCase):
    def test_github_tags_are_read_and_stripped(self):
        feed = {"forge": "github", "endpoint": "tags", "owner": "o", "repo": "r"}
        opener = fake_opener(
            {
                "https://api.github.com/repos/o/r/tags?per_page=100": json.dumps(
                    [{"name": "v2.3.0"}, {"name": "v2.2.1"}, {"name": "main"}]
                ).encode()
            }
        )
        self.assertEqual(forge_versions(feed, opener=opener), ["2.3.0", "2.2.1"])

    def test_github_draft_and_prerelease_flags_are_honoured(self):
        feed = {"forge": "github", "endpoint": "releases", "owner": "o", "repo": "r"}
        opener = fake_opener(
            {
                "https://api.github.com/repos/o/r/releases?per_page=100": json.dumps(
                    [
                        {"tag_name": "v9.0", "draft": True},
                        {"tag_name": "v8.0", "prerelease": True},
                        {"tag_name": "v7.1"},
                    ]
                ).encode()
            }
        )
        self.assertEqual(forge_versions(feed, opener=opener), ["7.1"])

    def test_gitlab_project_path_is_url_encoded(self):
        feed = {
            "forge": "gitlab",
            "endpoint": "tags",
            "host": "gitlab.freedesktop.org",
            "path": "camera/libcamera",
        }
        url = (
            "https://gitlab.freedesktop.org/api/v4/projects/"
            "camera%2Flibcamera/repository/tags?per_page=100"
        )
        opener = fake_opener({url: json.dumps([{"name": "v0.6.0"}]).encode()})
        self.assertEqual(forge_versions(feed, opener=opener), ["0.6.0"])

    def test_a_non_list_response_is_an_error_not_an_empty_feed(self):
        feed = {"forge": "github", "endpoint": "tags", "owner": "o", "repo": "r"}
        opener = fake_opener(
            {
                "https://api.github.com/repos/o/r/tags?per_page=100": b'{"message": "API rate limit exceeded"}'
            }
        )
        with self.assertRaises(ValueError):
            forge_versions(feed, opener=opener)

    def test_github_tags_pagination(self):
        feed = {"forge": "github", "endpoint": "tags", "owner": "o", "repo": "r"}
        page1 = [{"name": f"v1.{i}"} for i in range(100)]
        page2 = [{"name": "v0.9"}]
        opener = fake_opener(
            {
                "https://api.github.com/repos/o/r/tags?per_page=100": json.dumps(page1).encode(),
                "https://api.github.com/repos/o/r/tags?per_page=100&page=2": json.dumps(page2).encode(),
            }
        )
        versions = forge_versions(feed, opener=opener)
        self.assertEqual(len(versions), 101)
        self.assertIn("0.9", versions)


class ForgeProposalTests(unittest.TestCase):
    ENTRY = {
        "name": "ddcutil",
        "version": "2.2.1",
        "url": "https://github.com/rockowitz/ddcutil/archive/v2.2.1/ddcutil-2.2.1.tar.gz",
    }
    FEED = {"forge": "github", "endpoint": "tags", "owner": "rockowitz", "repo": "ddcutil"}

    def propose(self, tags):
        opener = fake_opener(
            {
                "https://api.github.com/repos/rockowitz/ddcutil/tags?per_page=100": json.dumps(
                    [{"name": t} for t in tags]
                ).encode()
            }
        )
        return forge_proposal("ddcutil", self.ENTRY, self.FEED, opener=opener)

    def test_a_newer_release_in_the_same_major_is_an_update(self):
        p = self.propose(["v2.3.0", "v2.2.1"])
        self.assertEqual((p["kind"], p["latest"]), ("update", "2.3.0"))

    def test_crossing_a_major_is_review_only(self):
        p = self.propose(["v3.0.0", "v2.2.1"])
        self.assertEqual((p["kind"], p["latest"]), ("review", "3.0.0"))

    def test_the_newest_in_major_wins_even_when_a_major_also_exists(self):
        p = self.propose(["v3.0.0", "v2.4.0", "v2.3.0", "v2.2.1"])
        self.assertEqual((p["kind"], p["latest"]), ("update", "2.4.0"))

    def test_prereleases_are_never_proposed(self):
        p = self.propose(["v2.3.0-rc1", "v2.2.1"])
        self.assertIsNone(p["latest"])

    def test_nothing_newer_proposes_nothing(self):
        p = self.propose(["v2.2.1", "v2.1.0"])
        self.assertIsNone(p["latest"])
        self.assertNotIn("kind", p)

    def test_an_unreachable_forge_is_reported_and_not_fatal(self):
        def broken(request, timeout=None):
            raise OSError("connection reset")

        p = forge_proposal("ddcutil", self.ENTRY, self.FEED, opener=broken)
        self.assertIn("error", p)
        self.assertIn("ddcutil", p["error"])


class ForgeEntryRewriteTests(unittest.TestCase):
    def test_every_url_field_moves_together(self):
        entry = {
            "name": "ddcutil",
            "version": "2.2.1",
            "url": "https://github.com/rockowitz/ddcutil/archive/v2.2.1/ddcutil-2.2.1.tar.gz",
            "filename": "ddcutil-2.2.1.tar.gz",
            "sha512": "old" * 10,
            "fallback_urls": [
                "https://src.fedoraproject.org/repo/pkgs/rpms/ddcutil/"
                "ddcutil-2.2.1.tar.gz/sha512/"
                + "old" * 10
                + "/ddcutil-2.2.1.tar.gz"
            ],
        }
        updated = forge_planned_entry(entry, "2.3.0", "new" * 10)
        self.assertEqual(updated["version"], "2.3.0")
        self.assertEqual(updated["sha512"], "new" * 10)
        self.assertIn("/archive/v2.3.0/", updated["url"])
        self.assertEqual(updated["filename"], "ddcutil-2.3.0.tar.gz")
        fallback = updated["fallback_urls"][0]
        self.assertNotIn("2.2.1", fallback)
        self.assertNotIn("old" * 10, fallback)
        self.assertIn("new" * 10, fallback)

    def test_a_version_absent_from_the_url_refuses_to_substitute(self):
        entry = {
            "name": "odd",
            "version": "1.0",
            "url": "https://example.invalid/odd/latest.tar.gz",
            "sha512": "x" * 8,
        }
        with self.assertRaises(ValueError):
            forge_planned_entry(entry, "1.1", "y" * 8)

    def test_substituted_handles_strings_and_lists(self):
        self.assertEqual(substituted("a-1.0", [("1.0", "2.0")]), "a-2.0")
        self.assertEqual(
            substituted(["a-1.0", "b-1.0"], [("1.0", "2.0")]),
            ["a-2.0", "b-2.0"],
        )


class ForgeLabelTests(unittest.TestCase):
    def test_labels_name_the_project_for_a_report(self):
        self.assertEqual(
            forge_label({"forge": "github", "owner": "o", "repo": "r"}),
            "github.com/o/r",
        )
        self.assertEqual(
            forge_label({"forge": "gitlab", "host": "h", "path": "a/b"}),
            "h/a/b",
        )
        self.assertEqual(
            forge_label({"type": "anitya", "project_id": 14498}),
            "anitya:14498",
        )


class FeedResolutionTests(unittest.TestCase):
    def test_parse_feed_strings(self):
        self.assertEqual(
            parse_feed("https://github.com/libsdl-org/SDL"),
            {
                "type": "forge",
                "forge": "github",
                "owner": "libsdl-org",
                "repo": "SDL",
                "endpoint": "tags",
            },
        )
        self.assertEqual(
            parse_feed("https://gitlab.freedesktop.org/mesa/mesa"),
            {
                "type": "forge",
                "forge": "gitlab",
                "host": "gitlab.freedesktop.org",
                "path": "mesa/mesa",
                "endpoint": "tags",
            },
        )
        self.assertEqual(
            parse_feed("https://download.gnome.org/sources/nautilus"),
            {"type": "gnome", "forge": "gnome", "module": "nautilus"},
        )
        self.assertEqual(
            parse_feed("anitya:14498"),
            {"type": "anitya", "project_id": 14498},
        )
        self.assertEqual(
            parse_feed("pinned: xorg directory listing"),
            {"type": "pinned", "reason": "xorg directory listing"},
        )

    def test_parse_feed_dict(self):
        self.assertEqual(
            parse_feed({"pinned": True, "reason": "vendored go"}),
            {"type": "pinned", "reason": "vendored go"},
        )
        self.assertEqual(
            parse_feed({"type": "anitya", "project_id": 123}),
            {"type": "anitya", "project_id": 123},
        )

    def test_resolve_feed_prefers_explicit_feed_field(self):
        entry = {
            "name": "colord",
            "url": "https://src.fedoraproject.org/repo/pkgs/rpms/colord/colord-1.4.7.tar.xz/sha512/abc/colord-1.4.7.tar.xz",
            "feed": "https://github.com/hughsie/colord",
        }
        resolved = resolve_feed(entry)
        self.assertEqual(resolved["forge"], "github")
        self.assertEqual(resolved["owner"], "hughsie")
        self.assertEqual(resolved["repo"], "colord")

    def test_resolve_feed_falls_back_to_url(self):
        entry = {
            "name": "ddcutil",
            "url": "https://github.com/rockowitz/ddcutil/archive/v2.2.1/ddcutil-2.2.1.tar.gz",
        }
        resolved = resolve_feed(entry)
        self.assertEqual(resolved["forge"], "github")
        self.assertEqual(resolved["owner"], "rockowitz")


class AnityaTests(unittest.TestCase):
    def test_anitya_versions(self):
        feed = {"type": "anitya", "project_id": 14498}
        url = "https://release-monitoring.org/api/v2/versions/?project_id=14498"
        opener = fake_opener(
            {url: json.dumps({"versions": ["1.2.0", "1.1.0"]}).encode()}
        )
        self.assertEqual(anitya_versions(feed, opener=opener), ["1.2.0", "1.1.0"])

    def test_anitya_proposal(self):
        feed = {"type": "anitya", "project_id": 14498}
        entry = {"name": "foo", "version": "1.1.0", "url": "https://example.com/foo-1.1.0.tar.gz"}
        url = "https://release-monitoring.org/api/v2/versions/?project_id=14498"
        opener = fake_opener(
            {url: json.dumps({"versions": ["1.2.0", "1.1.0"]}).encode()}
        )
        p = anitya_proposal("foo", entry, feed, opener=opener)
        self.assertEqual((p["kind"], p["latest"]), ("update", "1.2.0"))


class LookasideSafetyTests(unittest.TestCase):
    def test_lookaside_url_refuses_rewrite_without_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "packages" / "foo").mkdir(parents=True)
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "foo",
                                "version": "1.0",
                                "url": "https://src.fedoraproject.org/repo/pkgs/rpms/foo/foo-1.0.tar.gz/sha512/abc/foo-1.0.tar.gz",
                                "filename": "foo-1.0.tar.gz",
                                "sha512": "a" * 128,
                            }
                        ]
                    }
                )
            )
            with self.assertRaises(ValueError) as ctx:
                apply(root, {"name": "foo", "latest": "1.1"}, opener=fake_opener({}))
            self.assertIn("lookaside", str(ctx.exception).lower())

    def test_main_apply_continues_past_lookaside_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "packages" / "foo").mkdir(parents=True)
            (root / "packages" / "bar").mkdir(parents=True)
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "foo",
                                "version": "1.0",
                                "url": "https://src.fedoraproject.org/repo/pkgs/rpms/foo/foo-1.0.tar.gz/sha512/abc/foo-1.0.tar.gz",
                                "filename": "foo-1.0.tar.gz",
                                "sha512": "a" * 128,
                            },
                            {
                                "name": "bar",
                                "version": "1.0",
                                "url": "https://download.gnome.org/sources/bar/1/bar-1.0.tar.xz",
                                "filename": "bar-1.0.tar.xz",
                                "sha512": "b" * 128,
                            },
                        ]
                    }
                )
            )
            finals = [
                {"name": "foo", "current": "1.0", "latest": "1.1", "kind": "final"},
                {"name": "bar", "current": "1.0", "latest": "1.1", "kind": "final"},
            ]
            opener = fake_opener(
                {"https://download.gnome.org/sources/bar/1/bar-1.1.tar.xz": b"content"}
            )
            applied = []
            for bump in finals:
                try:
                    res = apply(root, bump, opener=opener)
                    applied.append(res["name"])
                except ValueError:
                    pass
            self.assertEqual(applied, ["bar"])


class AuditInventoryTests(unittest.TestCase):
    def test_audit_inventory_finds_zero_unclassified_gaps(self):
        locks = source_locks(ROOT)
        report = audit_inventory(locks)
        self.assertEqual(report["total"], 340)
        self.assertEqual(report["pollable_url"], 63)
        self.assertEqual(report["pollable_feed"], 197)
        self.assertEqual(report["pinned"], 80)
        self.assertEqual(report["gap"], 0)


if __name__ == "__main__":
    unittest.main()
