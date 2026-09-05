"""The imported source must be Source0, not whichever line dist-git lists first.

The sources file is in dist-git order and carries every archive a recipe
fetches, bundled ones included. iputils lists ifenslave.tar.gz ahead of its own
tarball, so taking the first entry recorded ifenslave as the upstream source of
iputils -- a manifest entry that would have fetched, hash-checked and shipped
the wrong archive under the right name. These pin the selection and then assert
the property across every entry the manifest actually carries.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import batch_import_closure as closure  # noqa: E402

SOURCE_LINE = re.compile(r"(?m)^Source0?:\s*(\S+)")


class Source0SelectionTests(unittest.TestCase):
    def test_iputils_selects_its_own_tarball(self):
        """The live case. ifenslave is Source1 and comes first in sources."""
        sources = closure.read_sources("iputils", ROOT / "packages")
        self.assertIn("ifenslave.tar.gz", sources)
        self.assertEqual(next(iter(sources)), "ifenslave.tar.gz")
        self.assertEqual(
            closure.read_source0_basename("iputils", ROOT / "packages", "20250605"),
            "iputils-20250605.tar.gz",
        )

    def test_an_undefined_conditional_macro_expands_to_nothing(self):
        """A Source0 may carry a macro that only a pre-release defines.

        firefox spelled it firefox-%{version}%{?pre_version}.source.tar.xz.
        Left unexpanded, that basename matches nothing in the sources file and
        the importer falls back to whatever line comes first. The tree no
        longer carries firefox, so the shape is pinned with a fixture.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "demo").mkdir()
            (root / "demo" / "demo.spec").write_text(
                "Name: demo\n"
                "Version: 155.0\n"
                "Source0: https://example.invalid/%{version}%{?pre_version}/"
                "%{name}-%{version}%{?pre_version}.source.tar.xz\n"
            )
            self.assertEqual(
                closure.read_source0_basename("demo", root, "155.0"),
                "demo-155.0.source.tar.xz",
            )

    def test_a_recipe_with_one_source_is_unaffected(self):
        self.assertEqual(
            closure.read_source0_basename("libICE", ROOT / "packages", "1.1.2"),
            "libICE-1.1.2.tar.xz",
        )


class ManifestMatchesSource0Tests(unittest.TestCase):
    """Whatever a recipe calls Source0 is what the manifest must promise."""

    def setUp(self):
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        self.entries = config["packages"]

    def test_every_entry_naming_a_recorded_source0_names_that_one(self):
        checked = 0
        for item in self.entries:
            directory = ROOT / "packages" / item["name"]
            if not directory.exists():
                continue
            sources = closure.read_sources(item["name"], ROOT / "packages")
            if len(sources) < 2:
                continue
            basename = closure.read_source0_basename(
                item["name"], ROOT / "packages", item["version"]
            )
            if basename not in sources:
                # A Source0 spelled with macros this cannot expand, or fetched
                # from somewhere other than the lookaside. Nothing to assert.
                continue
            checked += 1
            self.assertEqual(item["filename"], basename, item["name"])
            self.assertEqual(item["sha512"], sources[basename], item["name"])
        self.assertGreater(checked, 0, "expected some multi-source recipes to check")


if __name__ == "__main__":
    unittest.main()
