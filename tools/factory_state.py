#!/usr/bin/env python3
"""What the published repository was built from, package by package.

An incremental factory has to answer "has this package changed since the
build that is published?" for every recipe, on every run. A git diff cannot:
merges queue, a pending run is replaced by a newer one, and a diff from the
previous push forgets whatever the replaced run never built. So the answer is
recorded where the packages are -- as a label on the published image:

    org.projectbluefin.factory.state = {"inputs": {name: digest},
                                        "failed": {name: digest},
                                        "withheld": {name: digest}}

`inputs` is the input digest each published build was made from; `failed`
names packages whose latest attempt at that digest failed, and which
therefore still carry an older build. `withheld` names packages that built
at that digest but were held back from publication because they would have
left the repository unresolvable (tools/publish_holdback.py) -- a library
whose soname moved before its consumers were rebuilt. They also carry an
older build, but nothing about them failed, so every run retries them. A package is changed when its current
digest differs from `inputs`, which also makes a run the union of every
change since the last publication, however many runs were skipped.

The digest covers everything that decides what a recipe builds and that the
recipe directory does not record: its inventory entry (source URL, checksum,
stage, dist_bump) and the build-root inputs every package shares. A change to
the build root therefore changes every digest, which is a full rebuild --
mostly cache misses, since the cache key carries the build root too.

A label adds no layer: the image keeps the repodata-first two-layer layout
Utah reads (#254).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = "org.projectbluefin.factory.state"

# Shared inputs every package is built from and no recipe records.
SHARED_INPUTS = ("config/buildroot-image", "config/hummingbird.repo")


def shared_digest(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    for relative in SHARED_INPUTS:
        path = root / relative
        digest.update(relative.encode() + b"\0")
        digest.update(path.read_bytes() if path.exists() else b"<absent>")
        digest.update(b"\0")
    return digest.hexdigest()


def input_digest(root: Path, entry: dict, shared: str) -> str:
    """16 hex characters over recipe files, inventory entry and shared inputs."""
    from tools.package_cache_key import recipe_digest

    digest = hashlib.sha256()
    digest.update(recipe_digest(root / "packages" / entry["name"]).encode())
    digest.update(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode())
    digest.update(shared.encode())
    return digest.hexdigest()[:16]


def current(root: Path, locks: dict[str, dict]) -> dict[str, str]:
    shared = shared_digest(root)
    return {name: input_digest(root, entry, shared) for name, entry in sorted(locks.items())}


def parse_labels(labels: dict | None) -> dict | None:
    """The recorded state out of an image's labels, or None when absent."""
    raw = (labels or {}).get(LABEL)
    if not raw:
        return None
    state = json.loads(raw)
    return {
        "inputs": dict(state.get("inputs", {})),
        "failed": dict(state.get("failed", {})),
        "withheld": dict(state.get("withheld", {})),
    }


def changed(
    state: dict, digests: dict[str, str], *, retry_failed: bool
) -> tuple[set[str], set[str]]:
    """(changed, held) against a recorded state.

    changed: packages whose digest differs from the published build's, plus
    -- when `retry_failed` -- every package whose last attempt failed. A
    failure can leave the digest matching (a flaky test, or a consumer
    dragged along by its provider), so the digest alone would never retry it.
    held: packages left out because their last attempt at this exact digest
    failed. Rebuilding an unchanged, known-failing package on every merge
    buys nothing; the scheduled and dispatched runs (retry_failed) try again.

    A withheld package is retried by every run, push included: it built, and
    what kept it out was its consumers, which a later run may well have
    rebuilt. Its digest can match `inputs` (a full rebuild withheld it), so
    the digest alone would never bring it back.
    """
    moved = {name for name, digest in digests.items()
             if state["inputs"].get(name) != digest}
    failing = {name for name in state["failed"] if name in digests}
    withheld = {name for name in state.get("withheld", {}) if name in digests}
    if retry_failed:
        return moved | failing | withheld, set()
    held = {name for name in moved
            if state["failed"].get(name) == digests[name] and name not in withheld}
    return (moved - held) | withheld, held


def merge(
    seed: dict | None,
    digests: dict[str, str],
    *,
    trusted: list[str],
    replaced: list[str],
    failed: list[str],
    pruned: list[str],
    withheld: list[str] = (),
) -> dict:
    """The state to record on the image a publish is about to push.

    trusted: packages prepare judged already published at their current
    digest (everything it did not select), which is how the first labelled
    image learns the state of packages it did not rebuild. replaced: built
    and published by this run. failed: selected but not published; they keep
    their previous entry in `inputs` and are recorded in `failed`. withheld:
    built but held back from publication; they too keep their previous entry
    in `inputs`, and are recorded in `withheld` until a publication replaces
    them.
    """
    inputs = dict((seed or {}).get("inputs", {}))
    previous_failures = dict((seed or {}).get("failed", {}))
    previous_withheld = dict((seed or {}).get("withheld", {}))
    for name in trusted:
        if name in digests:
            inputs.setdefault(name, digests[name])
    for name in replaced:
        inputs[name] = digests[name]
        previous_failures.pop(name, None)
        previous_withheld.pop(name, None)
    for name in failed:
        if name in digests:
            previous_failures[name] = digests[name]
            previous_withheld.pop(name, None)
    for name in withheld:
        if name in digests:
            previous_withheld[name] = digests[name]
            previous_failures.pop(name, None)
    for name in pruned:
        inputs.pop(name, None)
        previous_failures.pop(name, None)
        previous_withheld.pop(name, None)
    known = set(digests)
    return {
        "inputs": {k: v for k, v in sorted(inputs.items()) if k in known},
        "failed": {k: v for k, v in sorted(previous_failures.items()) if k in known},
        "withheld": {k: v for k, v in sorted(previous_withheld.items()) if k in known},
    }


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT))
    from tools.package_inventory import source_locks

    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    cmd_merge = commands.add_parser("merge", help="print the label value for a publish")
    cmd_merge.add_argument("--seed-labels", type=Path, required=True,
                           help="JSON labels of the seed image (null or {} if none)")
    cmd_merge.add_argument("--plan", required=True, help="JSON: the prepare-time plan")
    cmd_merge.add_argument("--report", type=Path, required=True,
                           help="publish_gate.py assemble report")
    cmd_merge.add_argument("--pruned", default="[]")
    args = parser.parse_args(argv)

    digests = current(ROOT, source_locks(ROOT))
    seed = parse_labels(json.loads(args.seed_labels.read_text() or "null"))
    plan = json.loads(args.plan)
    report = json.loads(args.report.read_text())
    state = merge(
        seed,
        digests,
        trusted=plan.get("trusted", []),
        replaced=report.get("replaced", []) + report.get("bootstrapped", []),
        failed=report.get("failed", []),
        pruned=json.loads(args.pruned),
        withheld=list(report.get("withheld", [])),
    )
    print(json.dumps(state, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
