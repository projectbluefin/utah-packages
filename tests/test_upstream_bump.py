#!/usr/bin/env python3

import io
import json
from pathlib import Path
import tempfile
import unittest

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

    def test_considers_only_packages_locked_to_gnome(self) -> None:
        # glib-networking is locked to Fedora's lookaside, so it is out of scope
        # even though it is a GNOME module and is sitting on a prerelease.
        self.assertEqual(plan(ROOT, only="glib-networking", opener=fake_opener({})), [])


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


if __name__ == "__main__":
    unittest.main()
