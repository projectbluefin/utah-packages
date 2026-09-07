#!/usr/bin/env python3
"""The source package names the factory currently promises to build.

The lane seeds /work/prior from the `:building` accumulator, which is shared
across runs and refs, and then derives the Fedora exclusion list from the names
it finds there: whatever the factory builds, Fedora must not answer for. That
is correct while an entry exists and wrong the moment one is removed. The
accumulator still carries the RPMs, so Fedora's copy stays excluded and nothing
provides the capability any more -- dropping `libbluray` from the manifest left
Fedora's libbluray excluded by a build from the run before, which stranded
Fedora's own libavformat-free and took ten unrelated stage 0 packages with it.

So the accumulator is filtered against this list before it becomes a repository.
A name here is a *source* package name, matched against %{SOURCERPM}, because a
source build ships subpackages that require each other by exact NEVR: dropping
one and keeping its siblings leaves them unsatisfiable. Same reasoning as the
ICU-77 purge beside it in the lane.

Four spellings can each be the source name, and all four are allowed rather
than guessed between:

  the entry name          an entry usually is its own source package
  the recipe directory    a shard builds another entry's recipe
  the dist_git name       the import may have been named differently upstream
  every Name: in the spec webkitgtk sets it per GTK port, so one recipe
                          legitimately produces webkitgtk and webkitgtk4.1

Five recipes set Name: from a macro this cannot expand (libayatana-ido,
mozjs140, python-dasbus, python-dbus-next) or from a font template that does
not spell it at all (google-noto-sans-cjk-vf-fonts). Each resolves to its own
recipe directory name, which is already in the list, so they need no special
case -- but a *new* recipe whose source name matches none of the four would
have its RPMs purged, so this errs toward keeping and the test pins the shape.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import recipe

NAME_LINE = re.compile(r"(?m)^Name:\s*(\S+)")


def promised(root: Path = Path(".")) -> list[str]:
    config = json.loads((root / "config" / "upstream-sources.json").read_text())
    packages = config.get("packages", [])
    if not packages:
        raise ValueError("source manifest lists no packages")

    names: set[str] = set()
    for item in packages:
        names.add(item["name"])
        names.add(recipe.recipe_name(item))
        names.add(recipe.lookaside_name(item))

        directory = root / "packages" / recipe.recipe_name(item)
        for spec in sorted(directory.glob("*.spec")):
            for name in NAME_LINE.findall(spec.read_text()):
                # A macro this cannot expand is not a name. The recipe
                # directory is already recorded above and covers every such
                # spec in the tree today.
                if "%" not in name:
                    names.add(name)

    return sorted(names)


def main() -> int:
    for name in promised():
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
