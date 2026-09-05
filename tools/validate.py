#!/usr/bin/env python3
"""Validate package-factory configuration."""
from pathlib import Path
import json
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recipe  # noqa: E402

packages = [
    raw.strip()
    for raw in Path("config/bootstrap-packages.txt").read_text().splitlines()
    if raw.strip() and not raw.lstrip().startswith("#")
]
for path in Path("packages").glob("*/.hummingbird-upstream.json"):
    import json
    data = json.loads(path.read_text())
    required = {"package", "branch", "remote", "commit", "tree", "imported_at"}
    if set(data) != required:
        raise SystemExit(f"invalid upstream provenance: {path}")
    if data["branch"] not in ("rawhide", "upstream"):
        raise SystemExit(f"only rawhide or upstream imports are supported: {path}")
    if data["branch"] == "upstream":
        # Direct-upstream recipes (e.g. liblc3plus, libfreeaptx,
        # pipewire-libs-extra) are imported from the project's own release
        # repository rather than Fedora dist-git. They carry a remote and
        # imported_at but no dist-git commit/tree; the verified source lock
        # lives in config/upstream-sources.json instead.
        for key in ("commit", "tree"):
            if data[key]:
                raise SystemExit(f"upstream import must not carry {key}: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        for key in ("commit", "tree"):
            if not data[key]:
                raise SystemExit(f"rawhide import must carry {key}: {path}")
if not packages:
    raise SystemExit("bootstrap package set is empty")
if len(packages) != len(set(packages)):
    raise SystemExit("bootstrap package set contains duplicates")
if any(" " in package or "/" in package for package in packages):
    raise SystemExit("package names must be source RPM names, one per line")

manifest = json.loads(Path("config/upstream-sources.json").read_text())
manifest_names = {item["name"] for item in manifest.get("packages", [])}
if len(manifest_names) != len(manifest.get("packages", [])):
    raise SystemExit("source manifest contains duplicate package names")
for item in manifest.get("packages", []):
    stage = item.get("stage", 0)
    if not isinstance(stage, int) or not 0 <= stage <= 4:
        raise SystemExit(f"unsupported factory stage for {item.get('name')}: {stage!r}")
    # A shard builds another entry's recipe with extra rpm defines; the
    # directory must exist and the defines must be what rpmbuild -D takes.
    recipe_dir = Path("packages") / recipe.recipe_name(item)
    if not recipe_dir.is_dir():
        raise SystemExit(f"{item.get('name')} builds from {recipe_dir}, which does not exist")
    try:
        recipe.rpm_defines(item)
        recipe.compiler_cache(item)
    except ValueError as error:
        raise SystemExit(str(error))
    if "recipe" in item and item["recipe"] == item["name"]:
        raise SystemExit(f"{item['name']}: recipe is redundant when it equals the name")

lane_config = tomllib.loads(Path("config/build-lanes.toml").read_text())
lane_names = []
for lane, value in lane_config.items():
    names = value.get("packages", [])
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise SystemExit(f"[{lane}].packages must be an array of strings")
    lane_names.extend(names)
if len(lane_names) != len(set(lane_names)):
    raise SystemExit("build lane config contains duplicate packages")
if not set(lane_names) <= manifest_names:
    missing = ", ".join(sorted(set(lane_names) - manifest_names))
    raise SystemExit(f"build lane packages absent from source manifest: {missing}")
print(f"validated {len(packages)} source RPMs and {len(lane_names)} lane overrides")
