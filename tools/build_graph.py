#!/usr/bin/env python3
"""The factory's build-dependency graph, solved from real BuildRequires.

Waves used to be a hand-assigned `stage` integer in config/upstream-sources.json:
a manual cache of a computed value, two of which were discovered by a build
failing (docs/architecture.md, "Stage assignment"). Hummingbird has no stage
numbers; it solves them. This does the same:

1. `prepare` runs rpmspec in the build root over every recipe
   (`rpmspec -q --buildrequires`, `--provides`, and the subpackage names) and
   leaves one directory per package: `br`, `provides`, `names`, `rc`, `err`.
2. `graph()` maps each BuildRequires capability to the factory source
   packages that provide it -- from the spec's own subpackage names and
   explicit Provides, and from the published repository's primary.xml, which
   carries the generated ones (sonames, pkgconfig(), python3dist()).
3. `waves()` orders a build set by longest path over those edges. Only edges
   inside the set matter: anything else comes from the published factory.

The hand-assigned `stage` survives only as an override inside a dependency
cycle (malcontent-bootstrap before flatpak before malcontent): an edge
between two members of one strongly connected component is kept only when
config stages its provider strictly earlier. A cycle config does not order
is not fatal -- its members build side by side, as same-stage packages
always did -- but it is reported by name, because each one is a decision
nobody has made yet.

`dependents()` is the same edge set reversed, which is what an incremental
run drags along: a change to a library rebuilds everything that
BuildRequires it, transitively.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# Words inside a rich dependency that are operators, not capabilities.
RICH_OPERATORS = {"and", "or", "if", "else", "with", "without", "unless"}
CAPABILITY = re.compile(r"[^\s()<>=!,]+(?:\([^()]*\))?")
VERSION_START = re.compile(r"^[0-9%]")



def capabilities(line: str) -> list[str]:
    """The capability names a BuildRequires line asks for.

    `pkgconfig(gtk4) >= 4.10` -> [pkgconfig(gtk4)];
    `(python3dist(foo) or python3dist(bar))` -> both names. Versions and
    operators are dropped: the graph orders builds, it does not solve them.
    """
    line = line.strip()
    if not line:
        return []
    if line.startswith("("):
        tokens = CAPABILITY.findall(line[1:-1] if line.endswith(")") else line[1:])
        return [
            token for token in tokens
            if token not in RICH_OPERATORS and not VERSION_START.match(token)
        ]
    match = CAPABILITY.match(line)
    return [match.group(0)] if match else []


@dataclass
class Recipe:
    name: str
    buildrequires: list[str] = field(default_factory=list)
    provides: set[str] = field(default_factory=set)
    parsed: bool = True
    error: str = ""


def read_rows(rows: Path) -> dict[str, Recipe]:
    """One Recipe per package directory the extraction step left behind."""
    recipes: dict[str, Recipe] = {}
    for directory in sorted(path for path in rows.iterdir() if path.is_dir()):

        def lines(name: str) -> list[str]:
            path = directory / name
            return path.read_text(errors="replace").splitlines() if path.exists() else []

        codes = [code.strip() for code in lines("rc")]
        provides = set(lines("names"))
        for line in lines("provides"):
            provides.update(capabilities(line)[:1])
        recipes[directory.name] = Recipe(
            name=directory.name,
            buildrequires=[cap for line in lines("br") for cap in capabilities(line)],
            provides={p for p in provides if p},
            parsed=bool(codes) and all(code == "0" for code in codes),
            error=" ".join(line for line in lines("err") if not line.startswith("warning"))[:300],
        )
    return recipes


def graph(
    recipes: dict[str, Recipe], published: dict[str, set[str]] | None = None
) -> dict[str, set[str]]:
    """package -> the factory packages it BuildRequires.

    `published` is source name -> every capability its published binaries
    provide (primary.xml provides and files), which covers what rpmspec
    cannot see: sonames, pkgconfig() and other generated provides.
    """
    providers: dict[str, set[str]] = {}
    for recipe in recipes.values():
        for capability in recipe.provides:
            providers.setdefault(capability, set()).add(recipe.name)
    for source, provided in (published or {}).items():
        if source not in recipes:
            continue
        for capability in provided:
            providers.setdefault(capability, set()).add(source)
    edges: dict[str, set[str]] = {}
    for recipe in recipes.values():
        needs = set()
        for capability in recipe.buildrequires:
            needs |= providers.get(capability, set())
        needs.discard(recipe.name)
        edges[recipe.name] = needs
    return edges


def dependents(edges: dict[str, set[str]]) -> dict[str, set[str]]:
    """The reverse of `graph`: provider -> packages that BuildRequire it."""
    reverse: dict[str, set[str]] = {}
    for package, needs in edges.items():
        for provider in needs:
            reverse.setdefault(provider, set()).add(package)
    return reverse


def components(nodes: Iterable[str], edges: dict[str, set[str]]) -> list[set[str]]:
    """Strongly connected components (Tarjan), for the given nodes only."""
    nodes = set(nodes)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    result: list[set[str]] = []
    counter = 0

    def visit(root: str) -> None:
        nonlocal counter
        work = [(root, iter(sorted(edges.get(root, set()) & nodes)))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(edges.get(child, set()) & nodes))))
                    advanced = True
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = set()
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.add(member)
                    if member == node:
                        break
                result.append(component)

    for node in sorted(nodes):
        if node not in index:
            visit(node)
    return result


def break_cycles(
    nodes: set[str],
    edges: dict[str, set[str]],
    stages: dict[str, int],
    unordered: list[set[str]] | None = None,
) -> dict[str, set[str]]:
    """Edges restricted to `nodes`, with each cycle broken by config stage.

    Inside one strongly connected component an edge survives only when config
    stages its provider strictly earlier than its consumer; stages are a
    total order, so what survives is acyclic. Members config leaves unordered
    relative to each other are appended to `unordered`.
    """
    restricted = {node: edges.get(node, set()) & nodes for node in nodes}
    for component in components(nodes, restricted):
        if len(component) == 1:
            continue
        levels: dict[int, set[str]] = {}
        for node in component:
            levels.setdefault(stages.get(node, 0), set()).add(node)
            restricted[node] = {
                provider for provider in restricted[node]
                if provider not in component
                or stages.get(provider, 0) < stages.get(node, 0)
            }
        if unordered is not None:
            unordered.extend(
                members for members in levels.values() if len(members) > 1
            )
    return restricted


def waves(
    build: Iterable[str],
    edges: dict[str, set[str]],
    stages: dict[str, int],
    unordered: list[set[str]] | None = None,
) -> dict[str, int]:
    """package -> wave, by longest path over the edges inside `build`."""
    nodes = set(build)
    restricted = break_cycles(nodes, edges, stages, unordered)
    wave: dict[str, int] = {}

    def depth(node: str, trail: tuple[str, ...] = ()) -> int:
        if node in wave:
            return wave[node]
        if node in trail:  # break_cycles makes this unreachable
            raise AssertionError(" -> ".join(trail + (node,)))
        providers = restricted[node]
        wave[node] = 0 if not providers else 1 + max(
            depth(provider, trail + (node,)) for provider in providers
        )
        return wave[node]

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10_000))
    for node in sorted(nodes):
        depth(node)
    return wave


def load(rows: Path, published: dict[str, set[str]] | None = None) -> tuple[dict[str, Recipe], dict[str, set[str]]]:
    recipes = read_rows(rows)
    return recipes, graph(recipes, published)


def main(argv: list[str] | None = None) -> int:
    """Print the solved waves for the whole inventory, for inspection."""
    import argparse

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from tools.package_inventory import source_locks

    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("--primary", type=Path, help="published primary.xml (decompressed)")
    args = parser.parse_args(argv)
    published = None
    if args.primary:
        from tools.rebuild_plan import provides_by_source

        published = provides_by_source(args.primary.read_bytes())
    recipes, edges = load(args.rows, published)
    locks = source_locks(Path(__file__).resolve().parent.parent)
    stages = {name: entry.get("stage") or 0 for name, entry in locks.items()}
    solved = waves(recipes, edges, stages)
    unparsed = sorted(name for name, recipe in recipes.items() if not recipe.parsed)
    print(json.dumps({
        "depth": max(solved.values(), default=0),
        "waves": {str(w): sorted(n for n, v in solved.items() if v == w)
                  for w in range(max(solved.values(), default=0) + 1)},
        "unparsed": unparsed,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
