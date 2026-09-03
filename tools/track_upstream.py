#!/usr/bin/env python3
"""Follow Fedora rawhide for every source the factory builds.

Hummingbird is upstream-first, so the factory should track what Fedora
currently ships rather than freeze whatever version happened to be imported.
config/upstream-sources.json records the snapshot being built; this keeps that
record moving with rawhide instead of standing still.

Two things it corrects, which are easy to confuse:

  Version drift. Our entry names a version older than rawhide's. Following
  upstream means taking rawhide's, but only once Koji reports a COMPLETE build
  of that exact NVR -- dist-git advancing is not the same as Fedora having
  built it, and a package promoted on a dist-git commit alone can name a
  version no binary exists for.

  Location drift. Our entry fetches from the upstream project rather than
  Fedora's lookaside. Upstream hosts rewrite and expire: git.zx2c4.com serves
  snapshot tarballs generated per request, GitHub archive tarballs are not
  byte-stable, and both 404 once a tag moves. The lookaside is content
  addressed by the very sha512 Fedora recorded, so it is immutable and always
  the artifact Fedora actually built. Same bytes, a source that stays put.

The sha512 stays either way. It is not a version pin -- it is what makes the
pipeline fail closed when a tarball is re-rolled underneath us, which is
exactly the risk that following upstream increases.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import recipe
from tools.dist_git import koji_complete, nvr_from_spec

LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms/{pkg}/{name}/sha512/{hash}/{name}"
REMOTE = "https://src.fedoraproject.org/rpms/{pkg}.git"


def lookaside_url(pkg: str, filename: str, sha512: str) -> str:
    return LOOKASIDE.format(pkg=pkg, name=filename, hash=sha512)


def parse_sources(text: str) -> list[tuple[str, str]]:
    """Return (filename, sha512) for each SHA512 line in a dist-git sources file."""
    found = []
    for line in text.splitlines():
        match = re.match(r"^SHA512 \((.+?)\) = ([0-9a-f]{128})$", line.strip())
        if match:
            found.append((match.group(1), match.group(2)))
    return found


def rawhide_state(pkg: str) -> dict | None:
    """Clone rawhide dist-git and read the version, sources and NVR it declares."""
    with tempfile.TemporaryDirectory(prefix=f"track-{pkg}-") as temporary:
        checkout = Path(temporary) / pkg
        clone = subprocess.run(
            ["git", "clone", "--depth=1", "--branch", "rawhide", REMOTE.format(pkg=pkg), str(checkout)],
            capture_output=True, text=True,
        )
        if clone.returncode != 0:
            return None
        specs = list(checkout.glob("*.spec"))
        sources = checkout / "sources"
        if len(specs) != 1 or not sources.is_file():
            return None
        version = ""
        for line in specs[0].read_text(errors="replace").splitlines():
            match = re.match(r"^Version:\s*(\S+)", line)
            if match:
                version = match.group(1)
                break
        return {
            "package": pkg,
            "version": version,
            "nvr": nvr_from_spec(specs[0]),
            "sources": parse_sources(sources.read_text(errors="replace")),
        }


def classify(entry: dict, state: dict) -> dict | None:
    """Describe how an entry differs from rawhide, or None when it matches."""
    pkg = recipe.lookaside_name(entry)
    wanted = entry.get("filename")
    match = None
    for filename, sha512 in state["sources"]:
        if wanted and filename == wanted:
            match = (filename, sha512)
            break
    if match is None and len(state["sources"]) == 1:
        match = state["sources"][0]
    if match is None:
        return None
    filename, sha512 = match
    url = lookaside_url(pkg, filename, sha512)

    reasons = []
    if state["version"] and state["version"] != entry.get("version"):
        reasons.append(f"version {entry.get('version')} -> {state['version']}")
    if entry.get("url") != url:
        reasons.append("source is not the Fedora lookaside")
    if not reasons:
        return None
    return {
        "package": entry["name"],
        "dist_git": pkg,
        "nvr": state["nvr"],
        "reasons": reasons,
        "proposed": {"version": state["version"], "filename": filename,
                     "sha512": sha512, "url": url},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument("--only", help="comma-separated package names, for a targeted check")
    parser.add_argument("--parallel", type=int, default=8)
    parser.add_argument(
        "--apply", action="store_true",
        help="rewrite the manifest with the Koji-gated proposals",
    )
    args = parser.parse_args()

    config = json.loads(args.config.read_text())
    packages = config["packages"]
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        packages = [entry for entry in packages if entry["name"] in wanted]

    names = {entry["name"]: recipe.lookaside_name(entry) for entry in packages}
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        states = dict(zip(names, pool.map(rawhide_state, names.values())))

    proposals = []
    for entry in packages:
        state = states.get(entry["name"])
        if state is None:
            print(f"SKIP {entry['name']}: no rawhide dist-git", file=sys.stderr)
            continue
        found = classify(entry, state)
        if found:
            proposals.append(found)

    # Koji is the build authority: dist-git advancing is not proof Fedora built
    # it. Only a version change needs the gate -- moving a source to the
    # lookaside changes where the same bytes come from, not which build.
    gated = []
    for found in proposals:
        moves_version = any(reason.startswith("version ") for reason in found["reasons"])
        if moves_version and not koji_complete(found["nvr"]):
            print(f"HOLD {found['package']}: {found['nvr']} has no completed Koji build",
                  file=sys.stderr)
            continue
        gated.append(found)

    print(json.dumps({"proposals": gated}, indent=2, sort_keys=True))

    if args.apply and gated:
        by_name = {found["package"]: found["proposed"] for found in gated}
        for entry in config["packages"]:
            proposed = by_name.get(entry["name"])
            if not proposed:
                continue
            entry["version"] = proposed["version"] or entry["version"]
            entry["filename"] = proposed["filename"]
            entry["sha512"] = proposed["sha512"]
            entry["url"] = proposed["url"]
            entry.pop("fallback_urls", None)
        args.config.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
        print(f"applied {len(gated)} update(s) to {args.config}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
