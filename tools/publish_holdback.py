#!/usr/bin/env python3
"""Hold back the builds that would break a publication, and publish the rest.

A publication replaces each source package this run built (publish_gate.py
`assemble`) and is gated on one Hummingbird-only consumer transaction over the
whole candidate. When one replacement breaks that transaction, nothing moves:
run 44224171778 built libnfs 8.0.0 (libnfs.so.18) in wave 0, while the
published gvfs-nfs and qemu-block-nfs still needed libnfs.so.17. gvfs and
qemu were rebuilt against it in waves 10 and 12, but every publication,
including the final one, failed on

    nothing provides libnfs.so.17()(64bit) needed by gvfs-nfs-1.62.0-1.hum1.bfin

and 491 other source packages that built and broke nothing were published by
none of them. The plan state moves only on a publish, so the next run had to
build all of them again.

This decides, from repository metadata alone, which of the builds a
publication is about to accept would break its consumer transaction, and
holds those back:

* Only what the transaction installs is judged: the packages it names (the
  runtime contract, or every binary for the canary's `consumer: built`)
  and everything their Requires reach in the candidate plus Hummingbird. A
  -devel subpackage that gains an unmet Requires, or a consumer outside that
  set that failed to build, breaks nothing the transaction installs and holds
  nothing back -- holding it would publish less than the transaction allows.
* A **regression** is a Requires, inside that set, that the published
  repository (the seed) plus Hummingbird satisfied, or did not need, and the
  candidate does not. Requires the seed already left unmet are not this
  publication's doing -- stale_from_primary in rebuild_plan.py explains how
  many of those there are -- so they are never a reason to hold anything.
* A seed binary that loses a capability is the fault of the build that
  dropped it: libnfs 8.0.0 no longer provides libnfs.so.17, so libnfs is held
  and the seed's libnfs 7.0.2 stays, which is what gvfs-nfs was linked
  against. Held means exactly what a precedence loser means to `assemble`:
  the source keeps its previous published build, whole.
* A new build with a Requires nothing provides is held itself.
* A hold spreads, and here the whole publication is judged, not only what
  the transaction installs. Every other build in it that was built against a
  held one is held too, so nothing ships against a library that is not
  shipped. Two witnesses say "built against", and either is enough:
  - the build graph (tools/build_graph.py): it BuildRequires the held build
    directly. That is what catches a consumer compiled against headers, a
    static library or an unversioned soname, which leaves no trace in its
    Requires. Only the direct edge counts: following the graph through
    other builds held 215 of run 44478890278's builds because one consumer
    of abseil-cpp failed to build (abseil-cpp has 6 direct dependents and
    126 through the graph). A dependent further out that really links what
    only a held build provides is caught by the next witness;
  - the metadata: one of its binaries needs a capability only the held
    build's new binaries provide -- gvfs-nfs rebuilt against libnfs.so.18 --
    which also catches a runtime-only consumer the graph has no edge for.
  Each round re-derives the candidate, so this runs to a fixpoint.
* After each round the candidate is re-derived without the held builds and
  checked again, until nothing new breaks.

The model reads names, not versions: it does not evaluate versioned or rich
dependencies, Conflicts or Obsoletes, and it judges a file Requires only
where primary.xml lists the files (bin/ and /etc/). That is deliberate. It
chooses what to hold; it does not decide whether the result installs. The
same dnf consumer transaction still gates every push, over exactly the set
that will be pushed, and a reduced set that still fails it publishes nothing,
as before.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rebuild_plan import (  # noqa: E402
    COMMON_NS,
    EXCLUDED_EXTERNAL,
    RPM_NS,
    provides_by_source,
    source_name,
)

# createrepo_c lists a package's files in primary.xml only when they match
# this (its default `--files` filter): anything under a bin/ directory, /etc,
# and sendmail. A file Requires elsewhere cannot be judged from primary.xml.
PRIMARY_FILE = re.compile(r"^(/etc/|.*bin/|/usr/lib/sendmail$)")

# Built only to feed a later wave; publish deletes them (publish_gate.py).
BOOTSTRAP_RPM = re.compile(r"-0\.bootstrap\.")


@dataclass(frozen=True)
class Binary:
    """One binary RPM, as much of it as the decision reads."""

    name: str
    source: str
    nevra: str
    provides: frozenset[str]
    requires: frozenset[str]


def judged(capability: str) -> bool:
    """Whether a Requires is one this model can judge from primary.xml."""
    if not capability or capability.startswith(("rpmlib(", "(", "config(")):
        return False
    if capability.startswith("/"):
        return bool(PRIMARY_FILE.match(capability))
    return True


def binaries_from_primary(
    primary: bytes,
    *,
    publishable_only: bool = False,
    excluded: tuple[tuple[str, str], ...] = (),
) -> list[Binary]:
    """Every binary RPM in a primary.xml, with its provides and judged requires.

    `publishable_only` drops the bootstrap builds publish deletes anyway;
    `excluded` drops builds the consumer transaction refuses, as
    (name, version prefix) -- rebuild_plan.EXCLUDED_EXTERNAL for Hummingbird.
    """
    result: list[Binary] = []
    root = ElementTree.fromstring(primary)
    for package in root.iter(f"{{{COMMON_NS}}}package"):
        if package.findtext(f"{{{COMMON_NS}}}arch") == "src":
            continue
        location = package.find(f"{{{COMMON_NS}}}location")
        href = location.get("href", "") if location is not None else ""
        if publishable_only and BOOTSTRAP_RPM.search(Path(href).name):
            continue
        fmt = package.find(f"{{{COMMON_NS}}}format")
        if fmt is None:
            continue
        source = source_name(fmt.findtext(f"{{{RPM_NS}}}sourcerpm") or "")
        if source is None:
            continue
        name = package.findtext(f"{{{COMMON_NS}}}name") or ""
        version = package.find(f"{{{COMMON_NS}}}version")
        if version is not None and any(
            name == excluded_name and version.get("ver", "").startswith(prefix)
            for excluded_name, prefix in excluded
        ):
            continue
        evr = ""
        if version is not None:
            epoch = version.get("epoch", "0")
            evr = f"{'' if epoch in ('', '0') else epoch + ':'}{version.get('ver')}-{version.get('rel')}"
        arch = package.findtext(f"{{{COMMON_NS}}}arch") or ""
        provides = {name}
        provides.update(e.get("name", "") for e in fmt.iterfind(f"{{{RPM_NS}}}provides/{{{RPM_NS}}}entry"))
        provides.update(f.text or "" for f in fmt.iterfind(f"{{{COMMON_NS}}}file"))
        provides.discard("")
        requires = {
            e.get("name", "") for e in fmt.iterfind(f"{{{RPM_NS}}}requires/{{{RPM_NS}}}entry")
        }
        result.append(Binary(
            name=name,
            source=source,
            nevra=f"{name}-{evr}.{arch}",
            provides=frozenset(provides),
            requires=frozenset(cap for cap in requires if judged(cap)),
        ))
    return result


@dataclass
class Holdback:
    """What one publication holds back, and why."""

    withheld: dict[str, list[str]] = field(default_factory=dict)
    """Source name -> why it is held. A held source keeps its published build."""
    rounds: int = 0

    def names(self) -> list[str]:
        return sorted(self.withheld)


def _provided(binaries: list[Binary]) -> set[str]:
    provided: set[str] = set()
    for binary in binaries:
        provided |= binary.provides
    return provided


def installed(
    install: set[str] | None, binaries: list[Binary], external: list[Binary]
) -> set[Binary]:
    """The factory binaries a transaction installing `install` can reach.

    Every binary that provides a named package, then every provider of every
    Requires of those, transitively, across the factory and Hummingbird. All
    providers count, not only the one dnf would pick: over-approximating can
    only make a hold more likely, never ship a break. `install` None means
    every factory binary, which is the canary's `consumer: built`.
    """
    if install is None:
        return set(binaries)
    pool = binaries + external
    providers: dict[str, list[Binary]] = {}
    for binary in pool:
        for capability in binary.provides:
            providers.setdefault(capability, []).append(binary)
    reached: set[Binary] = set()
    frontier = [b for name in sorted(install) for b in providers.get(name, [])]
    while frontier:
        binary = frontier.pop()
        if binary in reached:
            continue
        reached.add(binary)
        for capability in binary.requires:
            frontier.extend(b for b in providers.get(capability, []) if b not in reached)
    factory = set(binaries)
    return {binary for binary in reached if binary in factory}


def holdback(
    *,
    seed: list[Binary],
    built: list[Binary],
    external: list[Binary],
    accepted: set[str],
    install: set[str] | None = None,
    dependents: dict[str, set[str]] | None = None,
) -> Holdback:
    """The accepted builds to hold back so that the transaction does not regress.

    `seed` is the published repository the publication starts from, `built`
    every publishable binary this publication downloaded, `external` the
    binaries of the consumer's other repository (Hummingbird), and
    `accepted` the source names `assemble` would otherwise replace (built,
    minus precedence losers). `install` is what the transaction installs by
    name; None means every factory binary. `dependents` is
    build_graph.dependents(): provider -> the packages that BuildRequire it.
    """
    # Built-against edges inside this publication only: a build that is not
    # in it was not rebuilt against anything this run is replacing.
    inside = {
        provider: {dependent for dependent in found if dependent in accepted}
        for provider, found in (dependents or {}).items()
        if provider in accepted
    }
    external_provided = _provided(external)
    seed_provided = external_provided | _provided(seed)
    baseline = {
        (binary.name, capability)
        for binary in seed
        for capability in binary.requires
        if capability not in seed_provided
    }
    seed_providers: dict[str, set[str]] = {}
    for binary in seed:
        for capability in binary.provides:
            seed_providers.setdefault(capability, set()).add(binary.source)

    result = Holdback()
    while True:
        result.rounds += 1
        publishing = accepted - set(result.withheld)
        candidate = [b for b in seed if b.source not in publishing]
        candidate += [b for b in built if b.source in publishing]
        provided = external_provided | _provided(candidate)
        found: dict[str, list[str]] = {}
        held_new: dict[str, set[str]] = {}
        for b in built:
            if b.source in result.withheld:
                for capability in b.provides:
                    held_new.setdefault(capability, set()).add(b.source)

        def blame(capability: str, needed_by: str, binary: Binary | None) -> None:
            dropped_by = sorted(seed_providers.get(capability, set()) & publishing)
            if dropped_by:
                for source in dropped_by:
                    found.setdefault(source, []).append(
                        f"{needed_by} needs {capability}, which the new "
                        f"{source} no longer provides"
                    )
            elif binary is not None and binary.source in publishing:
                found.setdefault(binary.source, []).append(
                    f"{needed_by} needs {capability}, which nothing provides"
                )

        # A package the transaction names that the candidate no longer has
        # at all: a build dropped the subpackage.
        for name in sorted(install or ()):
            if name not in provided and name in seed_provided:
                blame(name, "the consumer transaction", None)
        for binary in sorted(installed(install, candidate, external), key=lambda b: b.nevra):
            for capability in sorted(binary.requires):
                if (capability in provided or capability in held_new
                        or (binary.name, capability) in baseline):
                    continue
                blame(capability, binary.nevra, binary)
        # Built against a held build: a binary anywhere in this publication
        # that needs what only a held build's new binaries provide.
        for binary in sorted((b for b in built if b.source in publishing), key=lambda b: b.nevra):
            for capability in sorted(binary.requires):
                if capability in provided or capability not in held_new:
                    continue
                for held in sorted(held_new[capability]):
                    found.setdefault(binary.source, []).append(
                        f"built against {held}, which is held back: "
                        f"{binary.nevra} needs {capability}"
                    )
        if not found:
            return result
        for source, reasons in found.items():
            result.withheld.setdefault(source, []).extend(reasons)
        for source in sorted(found):
            for dependent in sorted(inside.get(source, set())):
                if dependent not in found:
                    result.withheld.setdefault(dependent, []).append(
                        f"built against {source}, which is held back: it BuildRequires it"
                    )


def summary(result: Holdback, publishing: int) -> str:
    """Markdown for the job summary."""
    lines = ["### Held back from this publication", ""]
    if not result.withheld:
        lines.append(f"Nothing: all {publishing} accepted build(s) resolve against the candidate.")
        return "\n".join(lines) + "\n"
    lines += [
        f"{len(result.withheld)} build(s) would leave the candidate unresolvable, so "
        "they keep their previous published build and the next run retries them. "
        f"The other {publishing - len(result.withheld)} publish.",
        "",
        "| package | why |",
        "| --- | --- |",
    ]
    for name in result.names():
        reasons = result.withheld[name]
        shown = "; ".join(reasons[:3]) + (f"; and {len(reasons) - 3} more" if len(reasons) > 3 else "")
        lines.append(f"| `{name}` | {shown} |")
    return "\n".join(lines) + "\n"


def read_primary(repository: Path) -> bytes | None:
    """primary.xml of a repository directory, or None if it has no metadata."""
    if not (repository / "repodata" / "repomd.xml").is_file():
        return None
    from tools.rebuild_matrix import fetch_primary

    return fetch_primary(repository.resolve().as_uri().rstrip("/") + "/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=Path, required=True,
                        help="the seeded repository (its repodata is read)")
    parser.add_argument("--built", type=Path, required=True,
                        help="a repository made over this publication's built RPMs")
    parser.add_argument("--losers", default="[]", help="JSON: precedence losers")
    parser.add_argument("--graph", type=Path,
                        help="the build-graph rows prepare extracted (its build-graph artifact)")
    parser.add_argument("--external", type=Path,
                        help="Hummingbird's primary.xml; fetched from config/hummingbird.repo if absent")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--install", type=Path,
                       help="the package names the consumer transaction installs, one per line")
    scope.add_argument("--install-all", action="store_true",
                       help="the transaction installs every factory binary (consumer: built)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    install = None
    if args.install:
        install = {line.strip() for line in args.install.read_text().splitlines() if line.strip()}

    built_primary = read_primary(args.built)
    built = binaries_from_primary(built_primary, publishable_only=True) if built_primary else []
    seed_primary = read_primary(args.seed)
    seed = binaries_from_primary(seed_primary) if seed_primary else []
    accepted = {binary.source for binary in built} - set(json.loads(args.losers or "[]"))

    if args.external:
        external_primary = args.external.read_bytes()
    else:
        from tools.rebuild_matrix import fetch_primary, hummingbird_baseurl

        try:
            external_primary = fetch_primary(hummingbird_baseurl(ROOT / "config" / "hummingbird.repo"))
        except OSError as error:  # URLError is an OSError: availability, not correctness
            # Without Hummingbird's provides every build would look broken.
            # Hold nothing, and let the transaction decide alone, as it did
            # before this existed. Only this fails open; a bug below does not.
            print(f"::warning title=hold-back not decided::could not read Hummingbird's "
                  f"metadata ({error}), so nothing is held back; the consumer "
                  "transaction alone decides this publication", file=sys.stderr)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({"withheld": {}}) + "\n")
            return 0
    external = binaries_from_primary(external_primary, excluded=EXCLUDED_EXTERNAL)

    dependents: dict[str, set[str]] = {}
    if args.graph and args.graph.is_dir():
        from tools import build_graph

        _, edges = build_graph.load(
            args.graph, provides_by_source(seed_primary) if seed_primary else None)
        dependents = build_graph.dependents(edges)
    else:
        print("::warning title=no build graph::holding back without the build graph: "
              "a build is held as built against a held one only when its Requires say so",
              file=sys.stderr)

    result = holdback(seed=seed, built=built, external=external,
                      accepted=accepted, install=install, dependents=dependents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(
        {"withheld": {name: result.withheld[name] for name in result.names()}}, indent=2) + "\n")
    print(summary(result, len(accepted)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
