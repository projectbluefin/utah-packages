#!/usr/bin/env python3
"""Batch-import the desktop dependency closure from Fedora dist-git.

The factory already builds the top of the desktop stack (gnome-shell, mutter,
gtk4, ...). Those builds reference a runtime dependency closure that Fedora
satisfied in the buildroot but the Hummingbird-only runtime does not ship:
cairo, glib, libdrm, wayland, mesa, gstreamer, ibus, webkitgtk and friends.

This imports each missing source from Fedora dist-git rawhide (recording the
exact snapshot in .hummingbird-upstream.json), then appends a config entry to
config/upstream-sources.json whose source is the Fedora lookaside archive,
addressed by the SHA-512 recorded in the dist-git `sources` file so the
pipeline fails closed on any re-roll.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms/{pkg}/{name}/sha512/{hash}/{name}"


def import_one(name: str, destination: Path) -> None:
    """Mirror tools/import_rawhide.py for a single package."""
    if (destination / name).exists():
        print(f"SKIP {name}: already imported", flush=True)
        return
    remote = f"https://src.fedoraproject.org/rpms/{name}.git"
    with tempfile.TemporaryDirectory(prefix=f"closure-import-{name}-") as temporary:
        clone = Path(temporary) / "dist-git"
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--branch", "rawhide", remote, str(clone)],
            check=True, capture_output=True,
        )
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=clone, text=True).strip()
        tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=clone, text=True).strip()
        target = destination / name
        target.mkdir(parents=True)
        archive = subprocess.Popen(["git", "archive", "rawhide"], cwd=clone, stdout=subprocess.PIPE)
        try:
            subprocess.run(["tar", "-x", "-C", str(target)], stdin=archive.stdout, check=True)
        finally:
            if archive.stdout:
                archive.stdout.close()
            archive.wait()
    provenance = {
        "package": name,
        "branch": "rawhide",
        "remote": remote,
        "commit": commit,
        "tree": tree,
        "imported_at": datetime.now(UTC).isoformat(),
    }
    (target / ".hummingbird-upstream.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"IMPORTED {name} {commit[:8]}", flush=True)


def read_sources(name: str, destination: Path) -> dict[str, str]:
    """Parse the dist-git sources file: filename -> sha512."""
    manifest = destination / name / "sources"
    if not manifest.exists():
        return {}
    entries: dict[str, str] = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"SHA512 \((\S+)\) = ([0-9a-f]{128})", line.strip())
        if match:
            entries[match.group(1)] = match.group(2)
    return entries


def read_source0_basename(name: str, destination: Path, version: str) -> str | None:
    """The basename of Source0, with the macros a source line usually carries.

    The sources file is in dist-git order, and Source0 is not always first:
    iputils lists a bundled ifenslave.tar.gz ahead of its own tarball, so
    taking the first entry recorded the wrong archive as the upstream source.
    """
    spec = next((destination / name).glob("*.spec"))
    for line in spec.read_text().splitlines():
        if not re.match(r"Source0?:", line):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.replace("%{name}", name).replace("%{version}", version)
        # A conditional macro that nothing defines expands to nothing, and a
        # Source0 line is where they cluster: firefox spells its tarball
        # firefox-%{version}%{?pre_version}.source.tar.xz, which is a plain
        # release name on every build that is not a pre-release.
        value = re.sub(r"%\{\?[^}]*\}", "", value)
        return value.rsplit("/", 1)[-1]
    return None


def read_spec_version(name: str, destination: Path) -> str:
    """The recorded version, with the spec's own %global macros expanded.

    A Version line is not always a literal: hunspell-en spells its as
    0.%{upstreamid} against a %global two lines above, and recording that
    verbatim puts an unexpanded macro in the lock file, where the drift
    check compares it against a real upstream version and never matches.
    """
    spec = next((destination / name).glob("*.spec"))
    text = spec.read_text()
    globals_ = dict(re.findall(r"(?m)^%global\s+(\S+)\s+(\S+)\s*$", text))
    for line in text.splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip().lstrip("%{?")
            for key, value in globals_.items():
                version = version.replace("%%{%s}" % key, value)
            return version
    raise SystemExit(f"{name}: cannot determine Version from spec")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("list", type=Path, help="file with one dist-git source name per line")
    parser.add_argument("--destination", type=Path, default=Path("packages"))
    parser.add_argument("--config", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument("--parallel", type=int, default=4)
    args = parser.parse_args()

    names = [line.strip() for line in args.list.read_text().splitlines() if line.strip()]
    print(f"importing {len(names)} sources", flush=True)

    # Phase 1: import recipes in parallel.
    procs = []
    for name in names:
        procs.append(subprocess.Popen(
            [sys.executable, __file__, "--worker", name, "--destination", str(args.destination)],
        ))
        if len(procs) >= args.parallel:
            for p in procs:
                p.wait()
            procs = []
    for p in procs:
        p.wait()

    # Phase 2: generate config entries from what was actually imported.
    config = json.loads(args.config.read_text())
    existing = {p["name"] for p in config["packages"]}
    added = 0
    for name in names:
        if name in existing:
            print(f"SKIP {name}: already in config", flush=True)
            continue
        if not (args.destination / name).exists():
            print(f"WARN {name}: import did not produce a recipe", flush=True)
            continue
        sources = read_sources(name, args.destination)
        if not sources:
            print(f"WARN {name}: no SHA-512 sources recorded; skipping config entry", flush=True)
            continue
        # Source0 is the primary upstream archive; record it hash-addressed.
        version = read_spec_version(name, args.destination)
        source0 = read_source0_basename(name, args.destination, version)
        filename = source0 if source0 in sources else next(iter(sources))
        sha512 = sources[filename]
        url = LOOKASIDE.format(pkg=name, name=filename, hash=sha512)
        config["packages"].append({
            "name": name,
            "version": version,
            "url": url,
            "filename": filename,
            "sha512": sha512,
        })
        existing.add(name)
        added += 1
        print(f"CONFIG {name} {version}", flush=True)

    config["packages"].sort(key=lambda p: p["name"])
    args.config.write_text(json.dumps(config, indent=2) + "\n")
    print(f"added {added} config entries", flush=True)
    return 0


if __name__ == "__main__":
    if "--worker" in sys.argv:
        idx = sys.argv.index("--worker")
        name = sys.argv[idx + 1]
        dest = Path(sys.argv[sys.argv.index("--destination") + 1])
        import_one(name, dest)
    else:
        raise SystemExit(main())
