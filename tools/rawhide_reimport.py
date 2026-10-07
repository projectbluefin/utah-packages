#!/usr/bin/env python3
"""Re-import carried recipes whose Fedora Rawhide build moved, when that is safe.

For every recipe imported from Fedora dist-git (``branch: rawhide`` in its
``.hummingbird-upstream.json``) this asks Koji which dist-git commit the latest
build tagged into Rawhide was built from. A recipe pinned to an older commit
on the same line of history is a candidate, and :func:`classify` decides
whether it may be taken without a human:

* the factory carries the recipe exactly as Fedora had it at the pinned
  commit -- no Utah-local patch, spec edit or repinned ``sources`` that a
  wholesale re-import would silently drop. Fedora CI and monitoring metadata
  the build never reads (``INERT_FILES``) may be absent, and stays absent;
* its source lock records no Utah-local build decision (``dist_bump``,
  ``rebuild_reason``, ``generate``, ``dist_git_name``, ...) that was reasoned
  about against the old recipe;
* Fedora's ``sources`` file, ``Name:``, ``Epoch:`` and ``Version:`` are
  unchanged, so the SHA-512 source lock in ``config/upstream-sources.json``
  still describes the payload byte for byte and needs no rewrite;
* the new spec adds no ``BuildRequires`` (or ``%generate_buildrequires``),
  so the build graph and the hermetic build root cannot grow a dependency the
  factory has never resolved;
* the move is a fast-forward: Koji's commit descends from the pinned one.

Everything else is reported, never applied. Version moves belong to
``tools/upstream_bump.py``; divergent recipes belong to a human.

Only commits Koji finished building and tagged into Rawhide are considered, never
the dist-git branch head, so a snapshot is still accepted only after Fedora's
own build gate (see ``tools/scan_rawhide_state.py``). A re-import replaces a
recipe already in every inventory, so the recipe set -- and with it the Packit
blocks and the recipe counts in tests and docs -- cannot change; ``--apply``
re-renders ``.packit.yaml`` anyway and refuses to finish if the set moved.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import xmlrpc.client
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import import_rawhide
from tools.render_packit_config import render

KOJI_HUB = "https://koji.fedoraproject.org/kojihub"
KOJI_TAG = "rawhide"
FEDORA_REMOTE = "https://src.fedoraproject.org/rpms/{package}.git"
KOJI_SOURCE = re.compile(
    r"^git\+https://src\.fedoraproject\.org/(?:rpms/)?(?P<package>[^#/]+?)(?:\.git)?#(?P<commit>[0-9a-f]{40})$"
)

# Lock fields that only say where the payload comes from and in which order to
# build it. Anything else is a decision taken against the current recipe
# (a disttag counter, a forced rebuild, a generated archive, an ICU staging
# switch) and has to be re-made by a human when the recipe changes.
PLAIN_LOCK_KEYS = frozenset({
    "name", "version", "url", "filename", "sha512", "sha256_url",
    "fallback_urls", "feed", "stage",
})
# Written by the import itself, never part of Fedora's tree.
FACTORY_FILES = frozenset({".hummingbird-upstream.json"})
# Fedora infrastructure metadata that rpmbuild never reads: CI plans and
# tests, gating, Packit, release monitoring. Recipes imported before
# import_rawhide.py used git archive lack them, so their absence is not a
# Utah-local change -- unless the spec names the file, in which case it is a
# source after all and dropping it is divergence (``.fmf/version`` is
# matched by full path: every spec says "version"). A re-import keeps the
# factory's shape and leaves out whatever of these the recipe already lacked.
INERT_FILES = frozenset({
    ".gitignore", ".mailmap", ".packit.yaml", "README.packit", "README.md",
    "monitoring.toml", "gating.yaml", "rpminspect.yaml", "ci.fmf", "plans.fmf",
})
INERT_DIRECTORIES = (".fmf/", "plans/", "tests/")

BUILD_REQUIRES = re.compile(r"^BuildRequires:\s*(.+?)\s*$", re.MULTILINE)
FIELD = r"^{}:\s*(.+?)\s*$"


Tree = dict[str, bytes]


def read_tree(directory: Path) -> Tree:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


OPERATORS = frozenset({"<", "<=", "=", "==", ">=", ">"})


def dependency_items(value: str) -> list[str]:
    """Split one dependency field the way RPM does.

    Items are separated by commas or whitespace; ``name op version`` is one
    item, and so is a parenthesised rich dependency.
    """
    tokens = value.replace(",", " ").split()
    items: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("("):
            depth = token.count("(") - token.count(")")
            group = [token]
            while depth > 0 and index + 1 < len(tokens):
                index += 1
                group.append(tokens[index])
                depth += tokens[index].count("(") - tokens[index].count(")")
            items.append(" ".join(group))
        elif index + 2 < len(tokens) and tokens[index + 1] in OPERATORS:
            items.append(" ".join(tokens[index:index + 3]))
            index += 2
        else:
            items.append(token)
        index += 1
    return items


def build_requires(spec: str) -> set[str]:
    """Every ``BuildRequires:`` item, unexpanded.

    Literal text is compared rather than rpmspec output on purpose: a
    conditional ``BuildRequires`` that appears is a new edge whether or not
    this host's macros would enable it.
    """
    items: set[str] = set()
    for value in BUILD_REQUIRES.findall(spec):
        items.update(dependency_items(value.split("#", 1)[0]))
    return items


def field_lines(spec: str, name: str) -> list[str]:
    return [" ".join(value.split()) for value in re.findall(FIELD.format(name), spec, re.MULTILINE)]


def single_spec(tree: Tree) -> tuple[str, str] | None:
    specs = [path for path in tree if "/" not in path and path.endswith(".spec")]
    if len(specs) != 1:
        return None
    return specs[0], tree[specs[0]].decode(errors="replace")


def inert(path: str, spec: str) -> bool:
    """Whether ``path`` is dist-git metadata the build cannot see."""
    if path not in INERT_FILES and not path.startswith(INERT_DIRECTORIES):
        return False
    return path not in spec


def omitted_inert(local: Tree, pinned: Tree) -> set[str]:
    """Inert Fedora files the factory's copy of the recipe does not carry."""
    spec = single_spec(pinned)
    text = spec[1] if spec else ""
    return {path for path in pinned.keys() - local.keys() if inert(path, text)}


def build_inputs(tree: Tree) -> Tree:
    """The part of a dist-git tree the build can see."""
    spec = single_spec(tree)
    text = spec[1] if spec else ""
    return {path: data for path, data in tree.items() if not inert(path, text)}


def build_relevant(pinned: Tree, target: Tree) -> bool:
    """Whether Fedora's move touched anything but metadata.

    An empty rebuild commit or a gating.yaml edit is not worth a re-import:
    the provenance bump alone changes the recipe digest, which rebuilds the
    package and everything that BuildRequires it for no change in bytes.
    """
    return build_inputs(pinned) != build_inputs(target)


def divergence(local: Tree, pinned: Tree) -> list[str]:
    """How the factory's recipe differs from Fedora's tree at the pinned commit."""
    ours = {path: data for path, data in local.items() if path not in FACTORY_FILES}
    skipped = omitted_inert(ours, pinned)
    theirs = {path: data for path, data in pinned.items() if path not in skipped}
    changed = sorted(path for path in ours.keys() & theirs.keys() if ours[path] != theirs[path])
    only_ours = sorted(ours.keys() - theirs.keys())
    only_theirs = sorted(theirs.keys() - ours.keys())
    reasons = []
    if changed:
        reasons.append(f"factory edited {', '.join(changed)}")
    if only_ours:
        reasons.append(f"factory added {', '.join(only_ours)}")
    if only_theirs:
        reasons.append(f"factory dropped {', '.join(only_theirs)}")
    return reasons


def classify(name: str, provenance: dict, lock: dict | None, local: Tree,
             pinned: Tree, target: Tree, *, fast_forward: bool) -> list[str]:
    """Why re-importing ``target`` over ``local`` is unsafe; empty means safe.

    Pure: every input is already fetched, so the policy is testable offline.
    """
    reasons: list[str] = []
    if provenance.get("branch") != "rawhide" or provenance.get("package") != name \
            or provenance.get("remote") != FEDORA_REMOTE.format(package=name):
        reasons.append("recipe is not a plain Fedora Rawhide import")
    if not fast_forward:
        reasons.append("Koji's commit does not descend from the pinned commit")
    if lock is None:
        reasons.append("no source lock")
    else:
        decisions = sorted(set(lock) - PLAIN_LOCK_KEYS)
        if decisions:
            reasons.append(f"source lock carries Utah-local decisions: {', '.join(decisions)}")
    reasons.extend(f"recipe diverges from Fedora: {reason}" for reason in divergence(local, pinned))

    old, new = single_spec(pinned), single_spec(target)
    if old is None or new is None:
        reasons.append("expected exactly one spec file on both commits")
        return reasons
    if old[0] != new[0]:
        reasons.append(f"spec renamed {old[0]} -> {new[0]}")
    if pinned.get("sources") != target.get("sources"):
        reasons.append("Fedora changed `sources`: the source lock would have to move")
    for field in ("Name", "Epoch", "Version"):
        before, after = field_lines(old[1], field), field_lines(new[1], field)
        if before != after:
            reasons.append(f"{field}: changed {before} -> {after}")
    added = sorted(build_requires(new[1]) - build_requires(old[1]))
    if added:
        reasons.append(f"adds BuildRequires: {', '.join(added)}")
    if "%generate_buildrequires" in new[1] and "%generate_buildrequires" not in old[1]:
        reasons.append("adds %generate_buildrequires")
    return reasons


def multicall(proxy, method: str, calls: list[tuple], size: int = 100) -> list:
    """Run ``method`` once per argument tuple; a per-call Koji fault yields None.

    Koji faults on a package name it has never heard of, and one unknown name
    must not cost the whole batch.
    """
    results: list = []
    for start in range(0, len(calls), size):
        batch = xmlrpc.client.MultiCall(proxy)
        for arguments in calls[start:start + size]:
            getattr(batch, method)(*arguments)
        answers = batch()
        for index in range(len(calls[start:start + size])):
            try:
                results.append(answers[index])
            except xmlrpc.client.Fault:
                results.append(None)
    return results


def koji_rawhide_commits(names: list[str], hub: str = KOJI_HUB) -> dict[str, dict]:
    """Latest Rawhide-tagged build per package: ``{name: {nvr, commit}}``.

    Packages Koji has no Rawhide build for are omitted. Batched through
    multicall, so 400 recipes cost a handful of requests.
    """
    proxy = xmlrpc.client.ServerProxy(hub, allow_none=True)
    latest = dict(zip(names, multicall(proxy, "getLatestBuilds", [(KOJI_TAG, None, name) for name in names])))
    builds = {name: found[0] for name, found in latest.items() if found}
    found = sorted(builds)
    details = multicall(proxy, "getBuild", [(builds[name]["build_id"],) for name in found])
    for name, build in zip(found, details):
        builds[name] = {"nvr": builds[name]["nvr"], "source": (build or {}).get("source") or ""}
    result = {}
    for name, build in builds.items():
        match = KOJI_SOURCE.match(build["source"])
        result[name] = {"nvr": build["nvr"], "commit": match.group("commit") if match else None}
    return result


def prune_empty_directories(directory: Path) -> None:
    for path in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def is_ancestor(repository: Path, older: str, newer: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], cwd=repository, check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def tree_at(repository: Path, ref: str, scratch: Path) -> Tree:
    destination = scratch / ref
    import_rawhide.extract(repository, ref, destination)
    return read_tree(destination)


def load_locks(path: Path) -> dict[str, dict]:
    return {entry["name"]: entry for entry in json.loads(path.read_text()).get("packages", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--package", action="append", help="limit to this recipe (repeatable)")
    parser.add_argument("--report", type=Path, default=Path("reports/rawhide-reimport.json"))
    parser.add_argument("--apply", action="store_true", help="re-import every safe candidate")
    args = parser.parse_args()

    root = args.root.resolve()
    packages = root / "packages"
    locks = load_locks(root / "config" / "upstream-sources.json")
    recipes = {}
    for directory in sorted(path for path in packages.iterdir() if path.is_dir()):
        record = json.loads((directory / ".hummingbird-upstream.json").read_text())
        if record.get("branch") == "rawhide":
            recipes[directory.name] = record
    if args.package:
        unknown = sorted(set(args.package) - recipes.keys())
        if unknown:
            raise SystemExit(f"not a Rawhide-imported recipe: {', '.join(unknown)}")
        recipes = {name: recipes[name] for name in args.package}

    koji = koji_rawhide_commits(sorted(recipes))
    report: dict[str, list] = {"current": [], "behind_pin": [], "metadata_only": [], "safe": [], "unsafe": [], "errors": []}
    packit_before = (root / ".packit.yaml").read_text()
    with tempfile.TemporaryDirectory(prefix="rawhide-reimport-") as temporary:
        for name, record in recipes.items():
            build = koji.get(name)
            if build is None or build["commit"] is None:
                report["errors"].append({"name": name, "reason": "no Koji Rawhide build with a dist-git source"})
                continue
            if build["commit"] == record["commit"]:
                report["current"].append(name)
                continue
            work = Path(temporary) / name
            repository = work / "dist-git"
            try:
                import_rawhide.clone(record["remote"], record["branch"], repository)
                if is_ancestor(repository, build["commit"], record["commit"]):
                    # Imported from a dist-git head Koji has not built yet.
                    report["behind_pin"].append(name)
                    continue
                if not is_ancestor(repository, build["commit"], "HEAD"):
                    raise ValueError(f"Koji commit {build['commit']} is not on {record['branch']}")
                pinned = tree_at(repository, record["commit"], work)
                target = tree_at(repository, build["commit"], work)
            except (subprocess.CalledProcessError, ValueError, OSError) as error:
                report["errors"].append({"name": name, "reason": str(error)})
                continue
            if not build_relevant(pinned, target):
                report["metadata_only"].append(name)
                continue
            reasons = classify(
                name, record, locks.get(name), read_tree(packages / name), pinned, target,
                fast_forward=is_ancestor(repository, record["commit"], build["commit"]),
            )
            entry = {"name": name, "from": record["commit"], "to": build["commit"], "nvr": build["nvr"]}
            if reasons:
                report["unsafe"].append({**entry, "reasons": reasons})
                continue
            report["safe"].append(entry)
            if args.apply:
                local = read_tree(packages / name)
                import_rawhide.import_snapshot(
                    repository, name, record["branch"], record["remote"], build["commit"],
                    packages / name, replace=True,
                )
                for path in omitted_inert(local, target):
                    (packages / name / path).unlink()
                prune_empty_directories(packages / name)

    if args.apply and report["safe"]:
        rendered = render(root)
        (root / ".packit.yaml").write_text(rendered)
        if rendered != packit_before:
            raise SystemExit("re-import changed the Packit configuration; the recipe set must not move")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{len(recipes)} Rawhide recipes: {len(report['current'])} current, "
        f"{len(report['behind_pin'])} pinned ahead of Koji, "
        f"{len(report['metadata_only'])} metadata-only moves, {len(report['safe'])} safe, "
        f"{len(report['unsafe'])} unsafe, {len(report['errors'])} errors"
    )
    for entry in report["safe"]:
        print(f"  safe   {entry['name']}: {entry['nvr']}")
    for entry in report["unsafe"]:
        print(f"  unsafe {entry['name']}: {entry['nvr']}: {'; '.join(entry['reasons'])}")
    for entry in report["errors"]:
        print(f"  error  {entry['name']}: {entry['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
