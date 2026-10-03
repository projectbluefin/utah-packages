#!/usr/bin/env python3

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

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
    check_bumpable,
    version_bound,
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

    def test_major_is_the_leading_component(self) -> None:
        self.assertEqual(major("51.0"), "51")
        self.assertEqual(major("1.10.beta.1"), "1")

    def test_a_library_scheme_release_is_filed_under_major_minor(self) -> None:
        self.assertEqual(release_cycle("4.23.4"), "4.23")
        self.assertEqual(release_cycle("1.10.0"), "1.10")
        self.assertEqual(release_cycle("51.0"), "51")

    def test_an_app_scheme_point_release_stays_in_its_gnome_cycle(self) -> None:
        # nautilus 51.0.1 is a point release of GNOME 51, not a new cycle;
        # without this the tool would file it under 51.0/ and flag it review.
        self.assertEqual(release_cycle("51.0.1"), "51")
        self.assertEqual(release_cycle("1.90.0"), "1.90")


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


class FallbackFeedTests(unittest.TestCase):
    """A lock whose primary moved to the lookaside still tracks its mirror's feed.

    GitHub archive tarballs can be regenerated upstream (srt 1.5.7 was), so
    the stable primary is the Fedora lookaside URL and the forge archive
    stays only as an availability fallback. The bumper must keep watching
    the feed the fallback names, but must never auto-apply from it: the new
    bytes are not in the lookaside until Fedora uploads them, so apply()
    would 404 fetching the digest or write a half-substituted lock.
    """

    SRT = {
        "name": "srt",
        "version": "1.5.7",
        "url": "https://src.fedoraproject.org/repo/pkgs/rpms/srt/srt-1.5.7.tar.gz/"
        "sha512/" + "8" * 128 + "/srt-1.5.7.tar.gz",
        "filename": "srt-1.5.7.tar.gz",
        "sha512": "8" * 128,
        "fallback_urls": [
            "https://github.com/Haivision/srt/archive/v1.5.7/srt-1.5.7.tar.gz"
        ],
    }

    def test_finds_the_forge_feed_named_by_a_fallback_mirror(self) -> None:
        self.assertEqual(
            forge_feed(self.SRT),
            {"forge": "github", "endpoint": "tags", "owner": "Haivision", "repo": "srt"},
        )

    def test_the_primary_feed_wins_over_a_fallback(self) -> None:
        entry = {
            "url": "https://github.com/a/b/archive/v1.tar.gz",
            "fallback_urls": ["https://github.com/c/d/archive/v2.tar.gz"],
        }
        feed = forge_feed(entry)
        assert feed is not None
        self.assertEqual(feed["repo"], "b")

    def test_no_feed_when_no_locked_url_is_forge_shaped(self) -> None:
        entry = {k: v for k, v in self.SRT.items() if k != "fallback_urls"}
        self.assertIsNone(forge_feed(entry))

    def test_finds_the_forge_feed_named_by_an_explicit_feed(self) -> None:
        entry = {k: v for k, v in self.SRT.items() if k != "fallback_urls"}
        entry["feed"] = "https://github.com/Haivision/srt/archive/v1.5.7/srt-1.5.7.tar.gz"
        found = candidates({"srt": entry}, only=None)
        self.assertEqual(len(found), 1)
        self.assertEqual(
            found[0][2],
            {"forge": "github", "endpoint": "tags", "owner": "Haivision", "repo": "srt"},
        )

    def test_a_proposal_from_an_explicit_feed_is_review_only(self) -> None:
        # The primary still points at the lookaside, so the new bytes are not
        # where the lock points: reported for a human, never applied.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            entry = {k: v for k, v in self.SRT.items() if k != "fallback_urls"}
            entry["feed"] = "https://github.com/Haivision/srt/archive/v1.5.7/srt-1.5.7.tar.gz"
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [entry]}, indent=2) + "\n"
            )
            opener = fake_opener(
                {
                    "https://api.github.com/repos/Haivision/srt/tags?per_page=100": json.dumps(
                        [{"name": "v1.5.7"}, {"name": "v1.5.8"}]
                    ).encode()
                }
            )
            proposals = plan(root, only="srt", opener=opener)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "review")
        self.assertEqual(proposals[0]["latest"], "1.5.8")
        self.assertIn("explicit feed", proposals[0]["reason"])

    def test_a_same_major_release_is_review_only_while_the_primary_is_lookaside(self) -> None:
        opener = fake_opener(
            {
                "https://api.github.com/repos/Haivision/srt/tags?per_page=100": json.dumps(
                    [{"name": "v1.5.7"}, {"name": "v1.5.8"}]
                ).encode()
            }
        )
        proposals = plan(ROOT, only="srt", opener=opener)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "review")
        self.assertEqual(proposals[0]["latest"], "1.5.8")
        self.assertIn("reason", proposals[0])


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

    def test_a_library_scheme_bump_files_under_major_minor(self) -> None:
        entry = dict(
            self.entry,
            name="gtk4",
            version="4.23.3",
            url="https://download.gnome.org/sources/gtk/4.23/gtk-4.23.3.tar.xz",
            filename="gtk-4.23.3.tar.xz",
        )
        new = planned_entry(entry, "4.23.4", "f" * 128)
        self.assertEqual(
            new["url"], "https://download.gnome.org/sources/gtk/4.23/gtk-4.23.4.tar.xz"
        )
        self.assertEqual(new["filename"], "gtk-4.23.4.tar.xz")

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


class BundledSourcesTests(unittest.TestCase):
    """A bump moves the primary pin and keeps every bundled lookaside file.

    PR #323 rewrote ppp's manifest to the tarball alone, dropping
    ppp-watch.tar.xz; adw-gtk3-theme lost its README and LICENSE copies, and
    both died in `rpmbuild -bs` before the gate could build anything.
    """

    DIGEST = "a" * 128

    def test_keeps_bundled_entries_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "sources"
            manifest.write_text(
                f"SHA512 (ppp-2.5.3.tar.gz) = {'0' * 128}\n"
                f"SHA512 (ppp-watch.tar.xz) = {'1' * 128}\n"
            )
            rewrite_sources(manifest, "ppp-2.5.4.tar.gz", self.DIGEST, previous="ppp-2.5.3.tar.gz")
            self.assertEqual(
                manifest.read_text(),
                f"SHA512 (ppp-2.5.4.tar.gz) = {self.DIGEST}\n"
                f"SHA512 (ppp-watch.tar.xz) = {'1' * 128}\n",
            )

    def test_a_manifest_naming_the_new_file_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "sources"
            manifest.write_text(f"SHA512 (x-1.1.tar.gz) = {'0' * 128}\n")
            rewrite_sources(manifest, "x-1.1.tar.gz", self.DIGEST, previous="x-1.0.tar.gz")
            self.assertEqual(manifest.read_text(), f"SHA512 (x-1.1.tar.gz) = {self.DIGEST}\n")

    def test_version_bound_names(self) -> None:
        self.assertTrue(version_bound("gum-2.0.0-vendor.tar.bz2", "2.0.0"))
        self.assertTrue(version_bound("fish-4.6.0.tar.xz.asc", "4.6.0"))
        self.assertFalse(version_bound("rust-pcre2-0.2.9-utf32.tar.gz", "4.6.0"))
        self.assertFalse(version_bound("ppp-watch.tar.xz", "2.5.3"))
        self.assertFalse(version_bound("x-1.2.3.tar.gz", "1.2"))
        self.assertFalse(version_bound("x-11.2.tar.gz", "1.2"))

    def scratch(self, tmp: str, name: str, spec: str, manifest: str) -> tuple[Path, dict]:
        root = Path(tmp)
        package = root / "packages" / name
        package.mkdir(parents=True)
        (package / f"{name}.spec").write_text(spec)
        (package / "sources").write_text(manifest)
        return root, {"name": name, "version": "2.0.0", "filename": f"{name}-2.0.0.tar.gz"}

    def test_refuses_a_bundled_source_bound_to_the_old_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, entry = self.scratch(
                tmp, "gum", "Version: 2.0.0\n",
                f"SHA512 (gum-2.0.0.tar.gz) = {'0' * 128}\n"
                f"SHA512 (gum-2.0.0-vendor.tar.bz2) = {'1' * 128}\n",
            )
            with self.assertRaisesRegex(ValueError, "gum-2.0.0-vendor.tar.bz2"):
                check_bumpable(root, entry)

    def test_refuses_a_version_computed_from_macros(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, entry = self.scratch(
                tmp, "fish", "%global version_base 2.0.0\nVersion: %{version_base}%{?version_pre:~%{version_pre}}\n",
                f"SHA512 (fish-2.0.0.tar.gz) = {'0' * 128}\n",
            )
            with self.assertRaisesRegex(ValueError, "macros"):
                check_bumpable(root, entry)
            with self.assertRaises(ValueError):
                rewrite_spec(root / "packages" / "fish" / "fish.spec", "2.0.1")

    def test_a_version_free_bundle_is_bumpable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, entry = self.scratch(
                tmp, "ppp", "Version: 2.0.0\n",
                f"SHA512 (ppp-2.0.0.tar.gz) = {'0' * 128}\n"
                f"SHA512 (ppp-watch.tar.xz) = {'1' * 128}\n",
            )
            check_bumpable(root, entry)

    def test_apply_refuses_before_fetching_or_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, entry = self.scratch(
                tmp, "gum", "Version: 2.0.0\n",
                f"SHA512 (gum-2.0.0.tar.gz) = {'0' * 128}\n"
                f"SHA512 (gum-2.0.0-vendor.tar.bz2) = {'1' * 128}\n",
            )
            entry.update(url="https://github.com/charmbracelet/gum/archive/v2.0.0/gum-2.0.0.tar.gz",
                         sha512="0" * 128)
            (root / "config").mkdir()
            config = root / "config" / "upstream-sources.json"
            config.write_text(json.dumps({"packages": [entry]}, indent=2) + "\n")
            before = config.read_text()
            with self.assertRaises(ValueError):
                apply(root, {"kind": "update", "name": "gum", "latest": "2.0.2"},
                      opener=fake_opener({}))
            self.assertEqual(config.read_text(), before)
            self.assertIn("Version: 2.0.0", (root / "packages" / "gum" / "gum.spec").read_text())


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
        # Hermetic: the real inventory moves as bumps land, so the fixture
        # carries its own prerelease lock instead of reading the worktree.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "gnome-shell",
                                "version": "51.beta",
                                "url": "https://download.gnome.org/sources/gnome-shell/51/"
                                "gnome-shell-51.beta.tar.xz",
                                "filename": "gnome-shell-51.beta.tar.xz",
                                "sha512": "d" * 128,
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n"
            )
            opener = fake_opener(
                {
                    "https://download.gnome.org/sources/gnome-shell/cache.json": json.dumps(
                        GNOME_SHELL_CACHE
                    ).encode()
                }
            )
            proposals = plan(root, only="gnome-shell", opener=opener)
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

    def test_full_runs_skip_lookaside_locks_but_package_runs_surface_them(self) -> None:
        # A lock on Fedora's lookaside is out of scope for a full scan even
        # though nautilus is a GNOME module sitting on a prerelease; naming
        # it explicitly offers the GNOME relock instead (and an unreachable
        # module reports an error rather than vanishing).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [LOOKASIDE_NAUTILUS]}, indent=2) + "\n"
            )
            self.assertEqual(plan(root, None, opener=fake_opener({})), [])
            proposals = plan(root, only="nautilus", opener=fake_opener({}))
            self.assertEqual(len(proposals), 1)
            self.assertIn("error", proposals[0])


GNOME_52_CACHE = [4, {}, {"gnome-shell": ["51.0", "51.1", "52.alpha", "52.beta", "52.0"]}, {}]
GNOME_52_ALPHA_ONLY_CACHE = [4, {}, {"gnome-shell": ["51.0", "51.1", "52.alpha"]}, {}]


def gnome_lock_root(version: str) -> tuple[Path, object]:
    """A temp tree with one GNOME-primary gnome-shell lock at `version`."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "config").mkdir()
    (root / "config" / "upstream-sources.json").write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": "gnome-shell",
                        "version": version,
                        "url": f"https://download.gnome.org/sources/gnome-shell/51/"
                        f"gnome-shell-{version}.tar.xz",
                        "filename": f"gnome-shell-{version}.tar.xz",
                        "sha512": "d" * 128,
                    }
                ]
            },
            indent=2,
        )
        + "\n"
    )
    return root, tmp


class CyclePolicyTests(unittest.TestCase):
    """Scheduled runs stay on their GNOME cycle; --cycle moves branches."""

    def cache_opener(self, cache):
        return fake_opener(
            {
                "https://download.gnome.org/sources/gnome-shell/cache.json": json.dumps(
                    cache
                ).encode()
            }
        )

    def test_a_newer_cycle_is_review_only_without_an_override(self) -> None:
        # At the head of cycle 51 with 52.0 shipped, the scheduled run flags
        # the jump for a human instead of applying it.
        root, tmp = gnome_lock_root("51.1")
        try:
            proposals = plan(root, only="gnome-shell", opener=self.cache_opener(GNOME_52_CACHE))
        finally:
            tmp.cleanup()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "review")
        self.assertEqual(proposals[0]["latest"], "52.0")

    def test_point_releases_still_apply_inside_the_current_cycle(self) -> None:
        root, tmp = gnome_lock_root("51.0")
        try:
            proposals = plan(root, only="gnome-shell", opener=self.cache_opener(GNOME_52_CACHE))
        finally:
            tmp.cleanup()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "final")
        self.assertEqual(proposals[0]["latest"], "51.1")

    def test_an_explicit_cycle_moves_a_next_branch_to_the_new_final(self) -> None:
        root, tmp = gnome_lock_root("51.0")
        try:
            proposals = plan(
                root, only="gnome-shell", opener=self.cache_opener(GNOME_52_CACHE), cycle="52"
            )
        finally:
            tmp.cleanup()
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "final")
        self.assertEqual(proposals[0]["latest"], "52.0")

    def test_even_an_explicit_cycle_cannot_land_on_an_alpha(self) -> None:
        # With 52 still prerelease, --cycle 52 applies nothing: whatever is
        # proposed is review-only, and no latest is a prerelease.
        root, tmp = gnome_lock_root("51.0")
        try:
            proposals = plan(
                root,
                only="gnome-shell",
                opener=self.cache_opener(GNOME_52_ALPHA_ONLY_CACHE),
                cycle="52",
            )
        finally:
            tmp.cleanup()
        self.assertTrue(proposals, "the 51.1 point release is still reported")
        for proposal in proposals:
            self.assertNotIn(proposal.get("kind"), ("final", "update", "relock"))
            self.assertFalse(is_prerelease(proposal["latest"]))


class ReleaseResetTests(unittest.TestCase):
    def test_version_bump_resets_only_literal_releases(self):
        for old, expected in (
            ("3%{?dist}", "1%{?dist}"),
            ("3.2%{?dist}", "1%{?dist}"),
            ("5%{?gitdate:.%{gitdate}git%{gitversion}}%{?dist}",
             "1%{?gitdate:.%{gitdate}git%{gitversion}}%{?dist}"),
            ("2%{?pre_tag}%{?dist} # comment", "1%{?pre_tag}%{?dist} # comment"),
            ("7", "1"),
            ("0.bootstrap%{?dist}", "1.bootstrap%{?dist}"),
            ("%autorelease", "%autorelease"),
            ("%{baserelease}%{?dist}", "%{baserelease}%{?dist}"),
            ("%{samba_release}%{?dist}", "%{samba_release}%{?dist}"),
        ):
            with self.subTest(release=old), tempfile.TemporaryDirectory() as tmp:
                spec = Path(tmp) / "test.spec"
                spec.write_text(f"Version: 1.0\nRelease:        {old}\n")
                self.assertTrue(rewrite_spec(spec, "1.1"))
                self.assertEqual(spec.read_text(),
                                 f"Version: 1.1\nRelease:        {expected}\n")

    def test_same_version_preserves_release_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "test.spec"
            original = "Version: 51~beta\nRelease: 3.2%{?dist}\n"
            spec.write_text(original)
            self.assertFalse(rewrite_spec(spec, "51.beta"))
            self.assertEqual(spec.read_text(), original)

    def test_apply_retires_counter_only_for_new_versions_on_every_feed(self):
        for url in (
            "https://download.gnome.org/sources/test/1/test-1.0.tar.xz",
            "https://github.com/o/test/archive/v1.0/test-1.0.tar.xz",
        ):
            for version in ("1.0", "1.1"):
                with self.subTest(url=url, version=version), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "config").mkdir()
                    package = root / "packages" / "test"
                    package.mkdir(parents=True)
                    spec = package / "test.spec"
                    spec.write_text("Version: 1.0\nRelease: 1%{?dist}\n")
                    counter = {"count": 2, "baseline": "1"}
                    entry = {"name": "test", "version": "1.0", "url": url,
                             "filename": "test-1.0.tar.xz", "dist_bump": counter}
                    config = root / "config" / "upstream-sources.json"
                    config.write_text(json.dumps({"packages": [entry]}))
                    updated = apply(root, {"name": "test", "latest": version},
                                    opener=fake_opener({url.replace("1.0", version): b"tarball"}))
                    written = json.loads(config.read_text())["packages"][0]
                    self.assertEqual(written, updated)
                    if version == "1.0":
                        self.assertEqual(written["dist_bump"], counter)
                    else:
                        self.assertNotIn("dist_bump", written)
                    self.assertIn("Release: 1%{?dist}", spec.read_text())


NAUTILUS_CACHE = [4, {}, {"nautilus": ["51.alpha", "51.beta", "51.rc", "51.0", "51.0.1"]}, {}]

LOOKASIDE_NAUTILUS = {
    "name": "nautilus",
    "version": "51~beta",
    "url": "https://src.fedoraproject.org/repo/pkgs/rpms/nautilus/nautilus-51.beta.tar.xz/"
    "sha512/" + "d" * 128 + "/nautilus-51.beta.tar.xz",
    "filename": "nautilus-51.beta.tar.xz",
    "sha512": "d" * 128,
    "stage": 6,
}


class RelockTests(unittest.TestCase):
    """A --package run may move a GNOME lock off the Fedora lookaside."""

    def locks(self) -> dict:
        return {"nautilus": dict(LOOKASIDE_NAUTILUS)}

    def test_package_mode_offers_the_gnome_module_but_full_runs_do_not(self) -> None:
        singled = candidates(self.locks(), only="nautilus")
        self.assertEqual(
            singled, [("nautilus", self.locks()["nautilus"], {"forge": "gnome", "module": "nautilus", "relock": True})]
        )
        self.assertEqual(candidates(self.locks(), None), [])

    def test_proposes_a_relock_when_gnome_is_newer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [LOOKASIDE_NAUTILUS]}, indent=2) + "\n"
            )
            opener = fake_opener(
                {
                    "https://download.gnome.org/sources/nautilus/cache.json": json.dumps(
                        NAUTILUS_CACHE
                    ).encode()
                }
            )
            proposals = plan(root, only="nautilus", opener=opener)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "relock")
        self.assertEqual(proposals[0]["current"], "51~beta")
        self.assertEqual(proposals[0]["latest"], "51.0.1")

    def test_a_name_with_no_gnome_module_is_a_visible_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            entry = dict(LOOKASIDE_NAUTILUS, name="not-a-gnome-module")
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [entry]}, indent=2) + "\n"
            )
            proposals = plan(root, only="not-a-gnome-module", opener=fake_opener({}))
        self.assertEqual(len(proposals), 1)
        self.assertIn("error", proposals[0])

    def test_relock_moves_the_primary_and_all_three_files(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps({"packages": [LOOKASIDE_NAUTILUS]}, indent=2) + "\n"
            )
            package = root / "packages" / "nautilus"
            package.mkdir(parents=True)
            (package / "nautilus.spec").write_text("Version:        51~beta\n")
            (package / "sources").write_text(
                f"SHA512 (nautilus-51.beta.tar.xz) = {'d' * 128}\n"
            )
            payload = b"a plausible nautilus tarball"
            expected = hashlib.sha512(payload).hexdigest()
            opener = fake_opener(
                {
                    "https://download.gnome.org/sources/nautilus/51/nautilus-51.0.1.tar.xz": payload
                }
            )
            apply(
                root,
                {"name": "nautilus", "latest": "51.0.1", "module": "nautilus", "kind": "relock"},
                opener=opener,
            )
            written = json.loads((root / "config" / "upstream-sources.json").read_text())[
                "packages"
            ][0]
            self.assertEqual(written["version"], "51.0.1")
            self.assertEqual(
                written["url"],
                "https://download.gnome.org/sources/nautilus/51/nautilus-51.0.1.tar.xz",
            )
            self.assertEqual(written["filename"], "nautilus-51.0.1.tar.xz")
            self.assertEqual(written["sha512"], expected)
            self.assertIn("Version:        51.0.1", (package / "nautilus.spec").read_text())
            self.assertEqual(
                (package / "sources").read_text(),
                f"SHA512 (nautilus-51.0.1.tar.xz) = {expected}\n",
            )


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
                {"https://download.gnome.org/sources/pango/1.59/pango-1.59.0.tar.xz": b"bytes"}
            )
            updated = apply(root, {"name": "pango", "latest": "1.59.0"}, opener=opener)
            self.assertNotEqual(updated["sha512"], "d" * 128)

    def test_a_forge_update_fetches_from_its_own_url_not_gnome(self) -> None:
        # forge_proposal() puts its feed label under "module". apply() read
        # that as a GNOME module and fetched
        # download.gnome.org/sources/github.com/..., a 404 that ended every
        # scheduled run with a forge update in it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "packages" / "adw-gtk3-theme").mkdir(parents=True)
            (root / "config" / "upstream-sources.json").write_text(
                json.dumps(
                    {
                        "packages": [
                            {
                                "name": "adw-gtk3-theme",
                                "version": "6.4",
                                "url": "https://github.com/lassekongo83/adw-gtk3/releases/download/v6.4/adw-gtk3v6.4.tar.xz",
                                "filename": "adw-gtk3v6.4.tar.xz",
                                "sha512": "e" * 128,
                            }
                        ]
                    },
                    indent=2,
                )
                + "\n"
            )
            opener = fake_opener(
                {
                    "https://github.com/lassekongo83/adw-gtk3/releases/download/v6.5/adw-gtk3v6.5.tar.xz": b"6.5"
                }
            )
            updated = apply(
                root,
                {
                    "kind": "update",
                    "name": "adw-gtk3-theme",
                    "module": "github.com/lassekongo83/adw-gtk3",
                    "current": "6.4",
                    "latest": "6.5",
                },
                opener=opener,
            )
            self.assertEqual(updated["version"], "6.5")
            self.assertEqual(updated["filename"], "adw-gtk3v6.5.tar.xz")


    def test_a_spec_that_cannot_be_bumped_leaves_the_lock_alone(self) -> None:
        # main() skips a package whose apply() raises; nothing may be half
        # written when it does.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            package = root / "packages" / "pango"
            package.mkdir(parents=True)
            lock = {"packages": [{
                "name": "pango", "version": "1.58.2",
                "url": "https://download.gnome.org/sources/pango/1/pango-1.58.2.tar.xz",
                "filename": "pango-1.58.2.tar.xz", "sha512": "d" * 128}]}
            config = root / "config" / "upstream-sources.json"
            config.write_text(json.dumps(lock, indent=2) + "\n")
            before = config.read_text()
            (package / "pango.spec").write_text("Name: pango\n")
            opener = fake_opener(
                {"https://download.gnome.org/sources/pango/1.58/pango-1.58.3.tar.xz": b"x"})
            with self.assertRaises(ValueError):
                apply(root, {"name": "pango", "latest": "1.58.3"}, opener=opener)
            self.assertEqual(config.read_text(), before)

class MainApplyTests(unittest.TestCase):
    """main() keeps going when one bump's bytes cannot be fetched."""

    def run_main(self, proposals, apply_side_effect):
        import contextlib
        from unittest import mock

        from tools import upstream_bump

        out, err = io.StringIO(), io.StringIO()
        argv = ["upstream_bump.py", "--apply"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(upstream_bump, "plan", return_value=proposals), \
                mock.patch.object(upstream_bump, "apply", side_effect=apply_side_effect) as applied, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            out.reconfigure = lambda **_: None
            code = upstream_bump.main()
        return code, applied, err.getvalue()

    def test_one_failed_download_skips_only_that_package(self) -> None:
        proposals = [
            {"kind": "update", "name": "broken", "current": "1.0", "latest": "1.1"},
            {"kind": "update", "name": "fine", "current": "2.0", "latest": "2.1"},
        ]

        def side_effect(root, bump):
            if bump["name"] == "broken":
                raise urllib.error.HTTPError("https://x/broken", 404, "Not Found", {}, None)
            return {}

        code, applied, err = self.run_main(proposals, side_effect)
        self.assertEqual(code, 0)
        self.assertEqual(applied.call_count, 2)
        self.assertIn("skipped broken", err)

    def test_fails_when_nothing_could_be_applied(self) -> None:
        proposals = [{"kind": "update", "name": "broken", "current": "1.0", "latest": "1.1"}]

        def side_effect(root, bump):
            raise OSError("unreachable")

        code, _, _ = self.run_main(proposals, side_effect)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()


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
            # evtest is locked over http, and a scheme is not worth a missed feed.
            ("http://gitlab.freedesktop.org/libevdev/evtest/-/archive/evtest-1.36/x.tar.bz2",
             "libevdev/evtest"),
        ):
            with self.subTest(url=url):
                feed = self.feed(url)
                self.assertEqual(feed["forge"], "gitlab")
                self.assertEqual(feed["path"], path)

    def test_sources_without_a_release_feed_are_not_claimed(self):
        # A lookaside path carries its digest in the URL and has nothing to
        # poll; a bare directory listing has no API. Both must be skipped
        # rather than guessed at.
        for url in (
            "https://src.fedoraproject.org/repo/pkgs/rpms/speex/speex-1.2.0.tar.gz/sha512/7fe/speex-1.2.0.tar.gz",
            "https://xorg.freedesktop.org/archive/individual/app/igt-gpu-tools-2.5.tar.xz",
            "https://download.gnome.org/sources/gtk4/4.23/gtk4-4.23.3.tar.xz",
        ):
            with self.subTest(url=url):
                self.assertIsNone(self.feed(url))

    def test_every_automatable_lock_in_the_real_inventory_is_claimed_once(self):
        from tools.package_inventory import source_locks

        locks = source_locks(ROOT)
        found = candidates(locks)
        names = [name for name, _, _ in found]
        self.assertEqual(len(names), len(set(names)), "a lock was claimed twice")
        # GNOME must keep being handled by the GNOME path, not swept into a
        # forge one: gitlab.gnome.org and download.gnome.org are different
        # feeds and only the latter has a cache.json.
        for name, entry, feed in found:
            with self.subTest(package=name):
                if entry["url"].startswith("https://download.gnome.org/sources/"):
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
        # A maintainer's prerelease flag is a stronger signal than the version
        # string, and some prereleases carry no alpha/beta suffix at all.
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
        feed = {"forge": "gitlab", "endpoint": "tags",
                "host": "gitlab.freedesktop.org", "path": "camera/libcamera"}
        url = ("https://gitlab.freedesktop.org/api/v4/projects/"
               "camera%2Flibcamera/repository/tags?per_page=100")
        opener = fake_opener({url: json.dumps([{"name": "v0.6.0"}]).encode()})
        self.assertEqual(forge_versions(feed, opener=opener), ["0.6.0"])

    def test_a_non_list_response_is_an_error_not_an_empty_feed(self):
        # GitHub answers rate limiting and 404 with an object. Treating that as
        # "no releases" would silently report every package as up to date.
        feed = {"forge": "github", "endpoint": "tags", "owner": "o", "repo": "r"}
        opener = fake_opener(
            {
                "https://api.github.com/repos/o/r/tags?per_page=100":
                    b'{"message": "API rate limit exceeded"}'
            }
        )
        with self.assertRaises(ValueError):
            forge_versions(feed, opener=opener)


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
                "https://api.github.com/repos/rockowitz/ddcutil/tags?per_page=100":
                    json.dumps([{"name": t} for t in tags]).encode()
            }
        )
        return forge_proposal("ddcutil", self.ENTRY, self.FEED, opener=opener)

    def test_a_newer_release_in_the_same_major_is_an_update(self):
        p = self.propose(["v2.3.0", "v2.2.1"])
        self.assertEqual((p["kind"], p["latest"]), ("update", "2.3.0"))

    def test_crossing_a_major_is_review_only(self):
        # A major can move a soname and break every consumer in the graph.
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
                "ddcutil-2.2.1.tar.gz/sha512/" + "old" * 10 + "/ddcutil-2.2.1.tar.gz"
            ],
        }
        updated = forge_planned_entry(entry, "2.3.0", "new" * 10)
        self.assertEqual(updated["version"], "2.3.0")
        self.assertEqual(updated["sha512"], "new" * 10)
        # The v-prefixed tag moves in the same substitution as the bare version.
        self.assertIn("/archive/v2.3.0/", updated["url"])
        self.assertEqual(updated["filename"], "ddcutil-2.3.0.tar.gz")
        # The lookaside fallback embeds both the filename and the digest, and
        # is exactly what a field-by-field rebuild leaves pointing at the old
        # tarball.
        fallback = updated["fallback_urls"][0]
        self.assertNotIn("2.2.1", fallback)
        self.assertNotIn("old" * 10, fallback)
        self.assertIn("new" * 10, fallback)

    def test_a_version_absent_from_the_url_refuses_to_substitute(self):
        # Substituting nothing would write a new version beside an old tarball.
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
        self.assertEqual(substituted(["a-1.0", "b-1.0"], [("1.0", "2.0")]),
                         ["a-2.0", "b-2.0"])


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
