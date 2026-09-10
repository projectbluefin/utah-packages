#!/usr/bin/env python3
"""Decide which packages a factory run has to build.

A package is rebuilt when

* its own build identity differs from the one recorded for it, or its
  recorded RPM outputs are no longer all present with the checksums they were
  built with;
* its recipe directory changed in the commits under test;
* a factory package it was built against -- recorded by the build as
  ``build_deps`` -- now carries a different identity, has been dropped from
  the manifest, or is itself being rebuilt for any of these reasons.  This
  propagates: a soname bump at the bottom of the tree rebuilds everything
  that linked it, however many steps removed.  Removal matters as much as
  change: dropping ``libbluray`` from the manifest once stranded Fedora's
  libavformat-free and took ten unrelated stage-0 packages with it;
* it carries no dependency record at all -- built before the factory kept
  one, or by something that did not write it.  An empty record means the
  build looked and found no factory package upstream; a missing one means
  nobody looked, and a package whose upstream cannot be checked is rebuilt
  rather than assumed current;
* the run is a full rebuild, or names it in a selected recovery set.

Nothing else triggers a rebuild.  Build scripts and workflow edits do not,
because they are not inputs to the package; an operator who changes how the
factory builds and wants that reflected everywhere dispatches ``full``.

This is Packit's per-package trigger with the dependent rebuild that Packit
and Copr leave to a manual mass rebuild folded in.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping


def plan(
    packages: Iterable[Mapping[str, object]],
    *,
    expected_keys: Mapping[str, str],
    published_keys: Mapping[str, str],
    published_deps: Mapping[str, Mapping[str, str | None]],
    published_versions: Mapping[str, str],
    outputs_match: Callable[[str], bool],
    recipe_of: Callable[[Mapping[str, object]], str],
    changed_recipes: Iterable[str] = (),
    full: bool = False,
    selected: Iterable[str] = (),
) -> tuple[list[str], dict[str, str]]:
    """Return the ordered names to build and a reason per name."""
    items = list(packages)
    names = [str(item["name"]) for item in items]
    changed = set(changed_recipes)
    chosen = set(selected)
    reasons: dict[str, str] = {}

    if chosen:
        for item in items:
            name = str(item["name"])
            if name in chosen:
                reasons[name] = "selected"
        return [name for name in names if name in reasons], reasons

    def norm(version: object) -> str:
        return str(version).replace("~", ".")

    for item in items:
        name = str(item["name"])
        if full:
            reasons[name] = "full rebuild"
        elif recipe_of(item) in changed:
            reasons[name] = "recipe changed"
        elif name in published_keys:
            if published_keys[name] != expected_keys.get(name):
                reasons[name] = "identity changed"
            elif not outputs_match(name):
                reasons[name] = "recorded outputs missing"
            elif name not in published_deps:
                reasons[name] = "no dependency record"
        elif name not in published_versions:
            reasons[name] = "never built"
        elif norm(published_versions[name]) != norm(item.get("version", "")):
            reasons[name] = f"version {published_versions[name]} -> {item.get('version', '')}"

    # Dependents: iterate to a fixed point so a rebuild propagates through
    # every level of the tree, whatever order the manifest lists them in.
    grew = True
    while grew:
        grew = False
        for item in items:
            name = str(item["name"])
            if name in reasons:
                continue
            for dep, key in published_deps.get(name, {}).items():
                if dep in reasons:
                    reasons[name] = f"built against {dep}, which is rebuilding"
                elif dep not in expected_keys:
                    reasons[name] = f"built against {dep}, no longer in the manifest"
                elif key is not None and expected_keys[dep] != key:
                    reasons[name] = f"built against {dep}, whose identity changed"
                else:
                    continue
                grew = True
                break

    return [name for name in names if name in reasons], reasons
