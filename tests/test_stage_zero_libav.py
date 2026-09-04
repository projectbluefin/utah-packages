"""ffmpeg is a stage 0 package, so nothing else in stage 0 may link libav.

A stage resolves the factory's own packages from the accumulator, which is the
previous run's output; only later stages see what this run has just built. So
the moment the manifest promises ffmpeg, the Fedora libav is excluded by name
everywhere, while the factory replacement is a run behind. Any *other* stage 0
package that links libav therefore builds against whatever the last run left,
and when the soname moves -- Fedora 8.x libavutil.so.60 against the factory
ffmpeg 9.x -- that package becomes uninstallable and takes down every buildroot
that reaches it. libheif did exactly that, through gdk-pixbuf2, glycin,
graphviz and doxygen, to ten packages with no connection to video.

Two ways out, both used here: move the package to a later stage (waypipe), or
decline the libav feature (libheif's ffmpegdec plugin). This test fails when a
third package takes neither.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import recipe  # noqa: E402

LIBAV_BUILDREQUIRES = re.compile(
    r"(?m)^BuildRequires:\s*.*\b(?:pkgconfig\((?:libav\w+|libswscale|libswresample)\)"
    r"|libav\w+-(?:free-)?devel|ffmpeg(?:-free)?-devel)"
)
CONDITIONAL = re.compile(r"(?m)^%(if|ifarch|ifnarch|else|elif|endif)\b")


def guarded_libav_lines(text: str) -> tuple[list[str], list[str]]:
    """Split libav BuildRequires into (inside some %if, unconditional)."""
    depth = 0
    guarded: list[str] = []
    bare: list[str] = []
    for line in text.splitlines():
        directive = CONDITIONAL.match(line)
        if directive:
            keyword = directive.group(1)
            if keyword in ("if", "ifarch", "ifnarch"):
                depth += 1
            elif keyword == "endif":
                depth = max(0, depth - 1)
            continue
        if LIBAV_BUILDREQUIRES.match(line):
            (guarded if depth else bare).append(line.strip())
    return guarded, bare


class StageZeroLibavTests(unittest.TestCase):
    def setUp(self):
        config = json.loads((ROOT / "config" / "upstream-sources.json").read_text())
        self.entries = config["packages"]
        self.stage = {item["name"]: item.get("stage", 0) for item in self.entries}

    def test_ffmpeg_is_stage_zero(self):
        """The premise. If ffmpeg ever moves, this whole rule can be revisited."""
        self.assertEqual(self.stage["ffmpeg"], 0)

    def test_no_other_stage_zero_recipe_links_libav_unconditionally(self):
        offenders = {}
        for item in self.entries:
            if item["name"] == "ffmpeg" or item.get("stage", 0) != 0:
                continue
            directory = ROOT / "packages" / recipe.recipe_name(item)
            for spec in sorted(directory.glob("*.spec")):
                _, bare = guarded_libav_lines(spec.read_text())
                if bare:
                    offenders[item["name"]] = bare
        self.assertEqual(
            offenders, {},
            "stage 0 packages linking libav unconditionally; move them to a later "
            "stage or gate the feature off:\n"
            + "\n".join(f"  {name}: {lines}" for name, lines in offenders.items()),
        )

    def test_libheif_declines_the_ffmpeg_decoder(self):
        spec = (ROOT / "packages" / "libheif" / "libheif.spec").read_text()
        self.assertIn("%bcond ffmpeg 0", spec)
        guarded, bare = guarded_libav_lines(spec)
        self.assertEqual(bare, [])
        self.assertTrue(guarded, "expected the libavcodec BuildRequires to survive, gated")

    def test_waypipe_builds_after_ffmpeg(self):
        """waypipe keeps its video feature by moving, since nothing depends on it."""
        self.assertGreater(self.stage["waypipe"], self.stage["ffmpeg"])

    def test_the_scanner_recognises_a_bare_buildrequires(self):
        guarded, bare = guarded_libav_lines(
            "Name: x\nBuildRequires:  pkgconfig(libavcodec)\n"
        )
        self.assertEqual(bare, ["BuildRequires:  pkgconfig(libavcodec)"])
        self.assertEqual(guarded, [])

    def test_the_scanner_recognises_a_guarded_buildrequires(self):
        guarded, bare = guarded_libav_lines(
            "%if %{with ffmpeg}\nBuildRequires:  pkgconfig(libavcodec)\n%endif\n"
        )
        self.assertEqual(bare, [])
        self.assertEqual(guarded, ["BuildRequires:  pkgconfig(libavcodec)"])


if __name__ == "__main__":
    unittest.main()
