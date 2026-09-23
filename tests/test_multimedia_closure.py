#!/usr/bin/env python3
"""Coverage for tools/multimedia_closure.py and the report it keeps current.

Two kinds of test. The synthetic ones drive `resolve` against a factory tree
built in a temporary directory, one rule per case, so a failure names the rule
rather than a fixture that drifted. The repository ones run the real
`config/multimedia-closure.toml` against the real tree, because the inventory
is only worth anything if it is true of `packages/` as it stands -- and because
`reports/multimedia-closure.json` is committed, so something has to fail when
it stops matching what the tool would write today.
"""

from __future__ import annotations

import gzip
import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tools.multimedia_closure import (
    ClosureError,
    published_nevra,
    requirements,
    resolve,
)

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "multimedia-closure.json"

MANIFEST = """\
[multimedia_overrides]
packages = ["mesa-libGL"]
"""

PRIMARY = """\
<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common"
          xmlns:rpm="http://linux.duke.edu/metadata/rpm">
  <package type="rpm">
    <name>libjxl</name>
    <arch>x86_64</arch>
    <version epoch="1" ver="0.11.2" rel="3.hum1.bfin"/>
  </package>
  <package type="rpm">
    <name>mesa-libGL</name>
    <arch>x86_64</arch>
    <version epoch="0" ver="26.2.1" rel="10.hum1.bfin"/>
  </package>
  <package type="rpm">
    <name>mesa-libGL</name>
    <arch>x86_64</arch>
    <version epoch="0" ver="26.2.1" rel="2.hum1.bfin"/>
  </package>
</metadata>
"""


def factory(root: Path, closure: str, *, recipes=("mesa",), locked=None, packit=None) -> None:
    """Write the smallest tree `resolve` accepts, then let a case break it."""
    locked = recipes if locked is None else locked
    packit = recipes if packit is None else packit
    (root / "config").mkdir(parents=True)
    (root / "config" / "bluefin-packages.toml").write_text(MANIFEST)
    (root / "config" / "multimedia-closure.toml").write_text(closure)
    for name in recipes:
        directory = root / "packages" / name
        directory.mkdir(parents=True)
        (directory / f"{name}.spec").write_text(f"Name: {name}\n")
    (root / "config" / "upstream-sources.json").write_text(json.dumps({
        "schema": 1,
        "packages": [{"name": name, "version": "26.2.1"} for name in locked],
    }))
    (root / ".packit.yaml").write_text(
        "packages:\n" + "".join(f"  {name}:\n    specfile_path: {name}.spec\n" for name in packit)
    )


CLOSURE = """\
[transaction]
source = "https://example.invalid/03-packages.sh"
overrides_manifest = "config/bluefin-packages.toml"
overrides_section = "multimedia_overrides"
codecs = []

[policy]
codec_parity = "negativo17-multimedia-rpmfusion-nonfree"

[upstream_spec_sources]
mesa-libGL = "https://github.com/negativo17/mesa"

[built]
mesa-libGL = "mesa"
"""


class RequirementTests(unittest.TestCase):
    def test_group_members_expand_and_keep_their_first_origin(self) -> None:
        manifest = {"multimedia_overrides": {"packages": ["shared"]}}
        closure = {
            "transaction": {
                "overrides_section": "multimedia_overrides",
                "codecs": ["codec"],
                "groups": ["@multimedia"],
            },
            "groups": {"@multimedia": {"members": ["member", "shared", "codec"]}},
        }
        self.assertEqual(
            requirements(manifest, closure),
            [
                ("shared", "multimedia-override"),
                ("codec", "codec-transaction"),
                ("@multimedia", "comps-group"),
                ("member", "comps-group:@multimedia"),
            ],
        )

    def test_a_group_with_no_definition_is_an_error(self) -> None:
        manifest = {"multimedia_overrides": {"packages": []}}
        closure = {
            "transaction": {"overrides_section": "multimedia_overrides", "groups": ["@multimedia"]},
        }
        with self.assertRaisesRegex(ClosureError, "@multimedia"):
            requirements(manifest, closure)


class ResolveTests(unittest.TestCase):
    def resolve(self, closure: str, **kwargs) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            factory(root, closure, **kwargs)
            return resolve(root)

    def test_a_requirement_resolves_to_its_recipe(self) -> None:
        report = self.resolve(CLOSURE)
        entry = report["requirements"][0]
        self.assertEqual(entry["requirement"], "mesa-libGL")
        self.assertEqual(entry["factory_source"], "mesa")
        self.assertEqual(entry["recipe"], "packages/mesa")
        self.assertEqual(entry["version"], "26.2.1")
        self.assertEqual(entry["upstream_spec_source"], "https://github.com/negativo17/mesa")
        self.assertEqual(report["counts"]["built"], 1)
        self.assertNotIn("published", report["counts"])

    def test_an_unclaimed_requirement_fails(self) -> None:
        with self.assertRaisesRegex(ClosureError, "mesa-libGL"):
            self.resolve(CLOSURE.replace('mesa-libGL = "mesa"\n', ""))

    def test_a_claim_the_transaction_does_not_ask_for_fails(self) -> None:
        with self.assertRaisesRegex(ClosureError, "does not ask for"):
            self.resolve(CLOSURE + 'mesa-libOSMesa = "mesa"\n')

    def test_two_tables_claiming_one_requirement_fail(self) -> None:
        closure = CLOSURE + (
            '\n[exception.mesa-libGL]\nreason = "duplicate"\n'
        )
        with self.assertRaisesRegex(ClosureError, "claimed by two tables"):
            self.resolve(closure)

    def test_a_claim_on_a_recipe_that_does_not_exist_fails(self) -> None:
        with self.assertRaisesRegex(ClosureError, "not a recipe"):
            self.resolve(CLOSURE.replace('"mesa"', '"mesa-libGL"'))

    def test_a_claim_on_a_recipe_that_cannot_build_fails(self) -> None:
        with self.assertRaisesRegex(ClosureError, "not eligible to build"):
            self.resolve(CLOSURE, locked=())

    def test_an_exception_without_a_reason_fails(self) -> None:
        closure = CLOSURE.replace(
            'mesa-libGL = "mesa"\n', ""
        ) + '\n[exception.mesa-libGL]\nreason = ""\n'
        with self.assertRaisesRegex(ClosureError, "missing reason"):
            self.resolve(closure)

    def test_an_override_without_an_upstream_spec_source_fails(self) -> None:
        closure = CLOSURE.replace('mesa-libGL = "https://github.com/negativo17/mesa"\n', "")
        with self.assertRaisesRegex(ClosureError, "no named upstream spec source"):
            self.resolve(closure)


class PublishedNevraTests(unittest.TestCase):
    def test_epoch_is_carried_and_the_highest_release_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml.gz").write_bytes(gzip.compress(PRIMARY.encode()))
            found = published_nevra(repodata)
        # jpegxl carries an epoch; a NEVRA that dropped it would name a package
        # no transaction can install by the string the report prints.
        self.assertEqual(found["libjxl"], "libjxl-1:0.11.2-3.hum1.bfin.x86_64")
        # Release 10 beats release 2. Sorted as text it does not, which is the
        # one ordering mistake the seeded repository actually produces.
        self.assertEqual(found["mesa-libGL"], "mesa-libGL-0:26.2.1-10.hum1.bfin.x86_64")

    def test_a_repodata_directory_with_no_primary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ClosureError, "no primary.xml under"):
                published_nevra(Path(directory))

    @unittest.skipIf(
        importlib.util.find_spec("zstandard") is None,
        "zstandard is installed in the publish job, not in every checkout",
    )
    def test_a_zstd_compressed_primary_is_read(self) -> None:
        # createrepo_c >= 1.0 defaults primary compression to zstd. The
        # workflow installs createrepo-c unpinned via apt-get, so a runner
        # image bump renames this file without anything here changing. Globbing
        # *primary.xml.gz turned that into "no primary.xml" -- which, before
        # the publish step became continue-on-error, failed the publish job.
        zstandard = importlib.import_module("zstandard")
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml.zst").write_bytes(
                zstandard.ZstdCompressor().compress(PRIMARY.encode())
            )
            found = published_nevra(repodata)
        self.assertEqual(found["libjxl"], "libjxl-1:0.11.2-3.hum1.bfin.x86_64")

    def test_a_zstd_primary_without_the_module_names_the_cause(self) -> None:
        # The zstd branch is dormant on ubuntu-24.04 (createrepo_c 0.17.3
        # writes gzip), so the test above skips wherever the module is absent
        # and no gate would notice a missing install. This one runs
        # everywhere: with the module hidden, the failure must arrive as a
        # ClosureError main() can report, not a ModuleNotFoundError traceback
        # that `continue-on-error: true` would swallow in the publish step.
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml.zst").write_bytes(b"not really zstd")
            with unittest.mock.patch.dict(sys.modules, {"zstandard": None}):
                with self.assertRaisesRegex(ClosureError, "zstandard module"):
                    published_nevra(repodata)

    def test_the_publish_job_installs_zstandard(self) -> None:
        # The job that runs `--repodata` must be able to read a zstd primary,
        # and no unit test can prove that from the tool alone: the zstd branch
        # is dormant on today's runner image, so a missing install shows up
        # only on the runner-image bump that makes it live. Assert the wiring
        # instead. `prepare` carries the same install for the same reason.
        from tools.publish_gate import load_workflow

        workflow = load_workflow()
        for job in ("prepare", "publish"):
            runs = " ".join(
                str(step.get("run", ""))
                for step in workflow["jobs"][job]["steps"]
            )
            # assertTrue, not assertIn: assertIn would print the job's entire
            # run block as the haystack and bury the message.
            self.assertTrue(
                "zstandard" in runs,
                f"the {job} job no longer installs zstandard; a zstd-compressed "
                "primary.xml would fail there with the module missing",
            )

    def test_an_uncompressed_primary_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml").write_text(PRIMARY)
            found = published_nevra(repodata)
        self.assertEqual(found["libjxl"], "libjxl-1:0.11.2-3.hum1.bfin.x86_64")

    def test_repomd_names_the_primary_when_several_are_present(self) -> None:
        # repomd.xml is the index; the glob is only the fallback. A repository
        # carrying a superseded primary alongside the current one must be read
        # through the index, not through whatever sorts first.
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            stale = PRIMARY.replace("0.11.2", "0.0.1")
            (repodata / "aaa-primary.xml.gz").write_bytes(gzip.compress(stale.encode()))
            (repodata / "zzz-primary.xml.gz").write_bytes(
                gzip.compress(PRIMARY.encode())
            )
            (repodata / "repomd.xml").write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<repomd xmlns="http://linux.duke.edu/metadata/repo">\n'
                '  <data type="primary">\n'
                '    <location href="repodata/zzz-primary.xml.gz"/>\n'
                "  </data>\n"
                "</repomd>\n"
            )
            found = published_nevra(repodata)
        self.assertEqual(found["libjxl"], "libjxl-1:0.11.2-3.hum1.bfin.x86_64")

    def test_an_unreadable_compression_is_named_rather_than_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repodata = Path(directory)
            (repodata / "abc-primary.xml.bz2").write_bytes(b"not really bz2")
            with self.assertRaisesRegex(ClosureError, "unsupported primary.xml"):
                published_nevra(repodata)


class RepositoryClosureTests(unittest.TestCase):
    def test_the_inventory_is_true_of_this_tree(self) -> None:
        report = resolve(ROOT)
        unresolved = [
            entry for entry in report["requirements"]
            if entry["status"] != "exception" and entry["recipe"] is None
        ]
        self.assertEqual(unresolved, [])
        self.assertGreater(report["counts"]["built"], 0)

    def test_the_committed_report_is_current(self) -> None:
        self.assertEqual(
            json.loads(REPORT.read_text()),
            resolve(ROOT),
            "reports/multimedia-closure.json is stale; regenerate it with "
            "python3 tools/multimedia_closure.py --output reports/multimedia-closure.json",
        )

    def test_every_multimedia_override_binary_is_accounted_for(self) -> None:
        """AC1 of projectbluefin/utah-packages#24, as an assertion.

        The override half is the part Bluefin version-locks, so a manifest sync
        that adds a name to it must not be able to land without an entry here.
        """
        report = resolve(ROOT)
        overrides = [
            entry for entry in report["requirements"]
            if entry["origin"] == "multimedia-override"
        ]
        self.assertTrue(overrides)
        self.assertEqual([entry for entry in overrides if entry["recipe"] is None], [])

    def test_every_multimedia_override_binary_has_a_named_upstream_spec_source(self) -> None:
        """AC1 of projectbluefin/utah-packages#230, as an assertion.

        Every Bluefin multimedia-override binary must map to a factory recipe
        with a named upstream spec source from negativo17 or RPM Fusion.
        """
        report = resolve(ROOT)
        overrides = [
            entry for entry in report["requirements"]
            if entry["origin"] == "multimedia-override"
        ]
        self.assertEqual(len(overrides), 12)
        for entry in overrides:
            self.assertIsNotNone(entry["recipe"], f"{entry['requirement']} has no recipe")
            upstream = entry.get("upstream_spec_source")
            self.assertTrue(
                upstream,
                f"{entry['requirement']} has no upstream spec source",
            )
            self.assertTrue(
                "negativo17" in upstream or "rpmfusion" in upstream,
                f"{entry['requirement']} upstream source {upstream} is not from negativo17 or rpmfusion",
            )


if __name__ == "__main__":
    unittest.main()
