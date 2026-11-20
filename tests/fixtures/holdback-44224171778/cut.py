#!/usr/bin/env python3
"""Cut this fixture from run 44224171778's real repository metadata.

Not run by the tests; kept so the fixture can be cut again. Inputs, all
primary.xml (decompressed):

    seed       the published image the run seeded from,
               ghcr.io/projectbluefin/utah-packages@sha256:744c4632..., layer 0
    wave0      createrepo_c over the run's rpm-s0-* artifacts
    through10  createrepo_c over its rpm-s0-* .. rpm-s10-* artifacts
    all        createrepo_c over every rpm-s* artifact (waves 0..12)
    external   Hummingbird's primary.xml, from config/hummingbird.repo
    rows       the run's build-graph artifact (work/graph/rows), whose rows
               for the kept sources are packed into graph-rows.json.gz

    python3 -I cut.py SEED WAVE0 THROUGH10 ALL EXTERNAL OUTDIR ROWS

It keeps every binary of the named sources plus a deterministic sample of
wave 0, then, transitively, every provider of anything a kept binary
requires -- whole source packages on the factory side, so a source never
appears to drop a subpackage it did not drop -- and writes each input back
out, gzipped, with only the kept packages.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

NAMED = {"libnfs", "gvfs", "qemu", "gdm", "sssd", "autofs", "gnome-initial-setup"}
SAMPLE = 40
INSTALL = ["gvfs-nfs", "gdm"]

PACKAGE = re.compile(rb'<package type="rpm">.*?</package>', re.S)
SOURCERPM = re.compile(rb"<rpm:sourcerpm>([^<]*)</rpm:sourcerpm>")
PROVIDE = re.compile(rb'<rpm:provides>(.*?)</rpm:provides>', re.S)
REQUIRE = re.compile(rb'<rpm:requires>(.*?)</rpm:requires>', re.S)
ENTRY = re.compile(rb'<rpm:entry name="([^"]*)"')
FILE = re.compile(rb"<file[^>]*>([^<]*)</file>")
NAME = re.compile(rb"<name>([^<]*)</name>")
PROSE = re.compile(rb"<(summary|description|url|packager)>.*?</\1>", re.S)


def source(element: bytes) -> str:
    match = SOURCERPM.search(element)
    nevr = match.group(1).decode() if match else ""
    return nevr.rsplit("-", 2)[0]


def parse(path: Path) -> list[tuple[bytes, str, set[str], set[str]]]:
    data = path.read_bytes()
    out = []
    for element in PACKAGE.findall(data):
        if b"<arch>src</arch>" in element:
            continue
        provides = {NAME.search(element).group(1).decode()}
        if (block := PROVIDE.search(element)):
            provides |= {e.decode() for e in ENTRY.findall(block.group(1))}
        provides |= {f.decode() for f in FILE.findall(element)}
        requires = set()
        if (block := REQUIRE.search(element)):
            requires = {e.decode() for e in ENTRY.findall(block.group(1))}
        out.append((element, source(element), provides, requires))
    return out


def write(path: Path, elements: list[bytes]) -> None:
    body = b"\n".join(elements)
    xml = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
           b'<metadata xmlns="http://linux.duke.edu/metadata/common" '
           b'xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="%d">\n' % len(elements)
           + body + b"\n</metadata>\n")
    with gzip.GzipFile(path, "wb", mtime=0) as handle:
        handle.write(xml)


def main(seed, wave0, through10, everything, external, outdir, rows) -> int:
    factory = {name: parse(Path(path)) for name, path in
               (("seed", seed), ("wave0", wave0), ("through10", through10), ("all", everything))}
    hummingbird = parse(Path(external))
    sample = sorted({s for _, s, _, _ in factory["wave0"]} - NAMED)[:SAMPLE]
    keep_sources = set(NAMED) | set(sample)
    keep_external: set[int] = set()
    providers: dict[str, list[tuple[str, object]]] = {}
    for pool in factory.values():
        for _, src, provides, _ in pool:
            for capability in provides:
                providers.setdefault(capability, []).append(("factory", src))
    for index, (_, _, provides, _) in enumerate(hummingbird):
        for capability in provides:
            providers.setdefault(capability, []).append(("external", index))
    wanted = list(INSTALL)
    seen_caps: set[str] = set()
    changed = True
    while changed:
        changed = False
        for capability in wanted:
            if capability in seen_caps:
                continue
            seen_caps.add(capability)
            for kind, ref in providers.get(capability, []):
                if kind == "factory" and ref not in keep_sources:
                    keep_sources.add(ref)
                    changed = True
                elif kind == "external":
                    # One Hummingbird provider is enough to satisfy a
                    # Requires; the repository carries several versions of
                    # most packages, and keeping them all only adds bytes.
                    if not any(k == "external" and r in keep_external
                               for k, r in providers[capability]):
                        keep_external.add(ref)
                        changed = True
                    break
        wanted = []
        for pool in factory.values():
            for _, src, _, requires in pool:
                if src in keep_sources:
                    wanted.extend(requires - seen_caps)
        for index in keep_external:
            wanted.extend(hummingbird[index][3] - seen_caps)
        changed = changed or bool(wanted)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    # Of a package's files, only those something requires; and none of the
    # prose, which the decision never reads.
    def trim(element: bytes) -> bytes:
        element = FILE.sub(lambda m: m.group(0) if m.group(1).decode() in seen_caps else b"", element)
        return PROSE.sub(rb"<\1/>", element)

    for name, pool in factory.items():
        write(out / f"{name}-primary.xml.gz",
              [trim(element) for element, src, _, _ in pool if src in keep_sources])

    write(out / "hummingbird-primary.xml.gz",
          [trim(hummingbird[index][0]) for index in sorted(keep_external)])
    (out / "install.txt").write_text("\n".join(INSTALL) + "\n")
    packed = {
        recipe.name: {f.name: f.read_text(errors="replace") for f in sorted(recipe.iterdir())}
        for recipe in sorted(Path(rows).iterdir()) if recipe.name in keep_sources
    }
    with gzip.GzipFile(out / "graph-rows.json.gz", "wb", mtime=0) as handle:
        handle.write(json.dumps(packed, sort_keys=True).encode())
    print(f"kept {len(keep_sources)} factory sources, {len(keep_external)} Hummingbird binaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
