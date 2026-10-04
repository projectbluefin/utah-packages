#!/usr/bin/env python3
"""Validate package-factory configuration."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.buildroot_pin import parse as parse_buildroot_pin
from tools.check_suppressed_tests import main as check_suppressed_tests
from tools.bootstrap_upstream_sources import FEDORA_HOSTS
from tools.bump_gate import REVIEW_ONLY, load_review_only
from tools.package_inventory import inventory


def check_buildroot_drift(data: dict, pin_file: Path) -> None:
    """Fail when a locked buildroot is not the root prepare pulls.

    prepare pulls exactly what config/buildroot-image pins
    (tools/buildroot_pin.py). The lock names that root again, by digest, for
    the provenance manifest, so the two copies are compared here rather than
    trusted to stay equal. ``buildroot_pin.py set`` moves both, which keeps the
    weekly refresh pull request green; this is what catches a hand edit to
    either one.

    The comparison is the whole reference, tag and digest, and every locked
    root must be the pinned one: the factory runs one build root, so a second
    entry would attest a root nothing pulls. A missing pin is drift too -- the
    lock would then describe a root with nothing behind it.
    """
    if not pin_file.is_file():
        raise SystemExit(
            f"buildroot drift: the lock names a build root but there is no pin at {pin_file}"
        )
    try:
        pin = parse_buildroot_pin(pin_file.read_text())
    except ValueError as error:
        raise SystemExit(f"invalid build-root pin {pin_file}: {error}")
    for name, buildroot in data["buildroots"].items():
        if buildroot["image"] != pin:
            raise SystemExit(
                f"buildroot drift: {name} is locked to {buildroot['image']} but "
                f"{pin_file.name} pins {pin}; move both with tools/buildroot_pin.py set"
            )


def validate_buildroots(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"missing buildroot lock: {path}")
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"invalid buildroot lock: {path}")
    if data.get("schema") != 1 or not isinstance(data.get("buildroots"), dict):
        raise SystemExit(f"invalid buildroot lock: {path}")
    if not data["buildroots"]:
        raise SystemExit(f"invalid buildroot lock: no buildroots defined in {path}")
    for name, buildroot in data["buildroots"].items():
        image = buildroot.get("image") if isinstance(buildroot, dict) else None
        if not isinstance(image, str) or "@sha256:" not in image:
            raise SystemExit(f"buildroot {name} image must be digest-pinned")
        packages = buildroot.get("packages", [])
        if not isinstance(packages, list):
            raise SystemExit(f"buildroot {name} packages must be a list")
        for package in packages:
            if not isinstance(package, dict) or not package.get("nevra"):
                raise SystemExit(f"buildroot {name} package locks must carry NEVRA entries")

    check_buildroot_drift(data, path.with_name("buildroot-image"))


def check_provenance(path: Path, data: dict) -> None:
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
        if not data.get("remote"):
            raise SystemExit(f"upstream import must name its upstream remote: {path}")
    else:
        # Fedora dist-git imports pin the exact rawhide snapshot.
        for key in ("commit", "tree"):
            if not data.get(key):
                raise SystemExit(f"rawhide import must carry {key}: {path}")
            if not FULL_SHA.fullmatch(data[key]):
                raise SystemExit(f"rawhide import must carry a full {key} SHA: {path}")


def fedora_primary_sources(path: Path) -> list[str]:
    """Names in the source lock whose primary `url` is Fedora infrastructure.

    `tools/source_pipeline.py` fetches the primary `url` directly, so an entry
    pointing at Fedora takes its payload from the lookaside rather than from
    the project's own release -- which is the one thing AGENTS.md and
    docs/targeting-hummingbird.md say the factory does not do. The SHA-512 lock
    still holds, so this is provenance, not integrity: Fedora belongs in
    `fallback_urls`, which source_pipeline already consults after an upstream
    transport failure, not in the primary position.
    """
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"invalid source lock: {path}")
    offenders = []
    for entry in data.get("packages", []):
        if not isinstance(entry, dict):
            continue
        host = urllib.parse.urlparse(entry.get("url") or "").hostname or ""
        if host in FEDORA_HOSTS or host.endswith(".fedoraproject.org"):
            offenders.append(entry.get("name") or entry.get("filename") or "<unnamed>")
    return sorted(offenders)


def read_fedora_primary_baseline(path: Path) -> list[str]:
    if not path.is_file():
        return []
    names = []
    for line in path.read_text().splitlines():
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            names.append(stripped)
    return sorted(names)


def check_fedora_primary_sources(root: Path) -> None:
    """A ratchet: the Fedora-primary set may shrink, never grow.

    Re-pointing every entry at its upstream release is a long bulk edit
    (utah-packages#42); until it finishes, the gap has to stop widening, so the
    packages still on a Fedora primary URL are listed in the baseline and
    anything outside it fails. The baseline is also checked for staleness --
    a package re-pinned upstream but left in the file would hold a slot open
    for the gap to reopen under the same name.
    """
    offenders = fedora_primary_sources(root / "config" / "upstream-sources.json")
    baseline_path = root / "config" / "fedora-primary-sources.txt"
    baseline = read_fedora_primary_baseline(baseline_path)
    added = sorted(set(offenders) - set(baseline))
    removed = sorted(set(baseline) - set(offenders))
    if added:
        raise SystemExit(
            "source lock takes its payload from Fedora, not upstream: "
            f"{', '.join(added)}\n"
            "Point the entry's `url` at the project's own release and keep the "
            "Fedora URL in `fallback_urls`, which source_pipeline.py already "
            "uses after an upstream transport failure. Where no upstream "
            "artifact exists verbatim, add a generator in "
            "tools/generated_sources.py instead."
        )
    if removed:
        raise SystemExit(
            f"{baseline_path.name} lists packages that no longer use a Fedora "
            f"primary URL: {', '.join(removed)}\n"
            "Delete those lines. The list only shrinks; a stale entry holds the "
            "slot open for the same package to regress unnoticed."
        )


def check_bump_review_only(root: Path) -> None:
    """Every name in the review-only list is a lock the bump could move.

    The list keeps upstream_bump.py and the bump gate from self-merging a
    package's new upstream bytes. A misspelled or retired name protects
    nothing and says otherwise, so it fails here, where a human is reading.
    """
    lock = root / "config" / "upstream-sources.json"
    if not lock.is_file():
        return
    try:
        data = json.loads(lock.read_text())
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"invalid source lock: {lock}")
    locked = {entry.get("name") for entry in data.get("packages", []) if isinstance(entry, dict)}
    unknown = sorted(load_review_only(root) - locked)
    if unknown:
        raise SystemExit(
            f"{REVIEW_ONLY} names packages the source lock does not carry: "
            f"{', '.join(unknown)}\n"
            "Each line must be the `name` of a config/upstream-sources.json entry; "
            "a name that matches nothing guards nothing."
        )


def main(root: Path = Path(".")) -> int:
    packages_dir = root / "packages"
    if not packages_dir.is_dir():
        return 0
    for directory in sorted(packages_dir.iterdir()):
        if not directory.is_dir():
            continue
        path = directory / ".hummingbird-upstream.json"
        if not path.is_file():
            raise SystemExit(f"missing upstream provenance: {path}")
        data = json.loads(path.read_text())
        check_provenance(path, data)
    # Report every problem in one run rather than stopping at the first, so a
    # contributor is not sent round the loop twice.
    status = check_suppressed_tests(root)
    # Before the recipe tally, so a package that is merely missing a Packit
    # entry cannot hide a buildroot that drifted from its lock.
    validate_buildroots(root / "config" / "buildroot-lock.json")
    # Before the tally too: a lock that builds from the lookaside is a
    # provenance failure whether or not every recipe is otherwise accounted for.
    check_fedora_primary_sources(root)
    check_bump_review_only(root)
    records = inventory(root)
    missing_locks = sorted(record.name for record in records if not record.source_locked)
    missing_packit = sorted(record.name for record in records if not record.packit_configured)
    missing_provenance = sorted(record.name for record in records if record.provenance is None)
    if missing_locks or missing_packit or missing_provenance:
        if missing_locks:
            print(f"packages missing source locks: {', '.join(missing_locks)}")
        if missing_packit:
            print(f"packages missing Packit config: {', '.join(missing_packit)}")
        if missing_provenance:
            print(f"packages missing recipe provenance: {', '.join(missing_provenance)}")
        return 1
    # The suppressed-test gate reports its own detail on stderr; say nothing
    # more here. Printing "validated N source RPMs" and then exiting 1 leaves
    # a CI log whose last stdout line reads as success.
    if status:
        return status
    # The split is the point of the count: a direct-upstream recipe carries a
    # different provenance form from a dist-git import, and both are mandatory.
    forms: dict[str, int] = {}
    for record in records:
        forms[record.provenance_branch] = forms.get(record.provenance_branch, 0) + 1
    summary = ", ".join(f"{count} {form}" for form, count in sorted(forms.items()))
    print(f"validated {len(records)} source RPMs ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
