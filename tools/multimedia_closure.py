#!/usr/bin/env python3
"""Resolve Bluefin's multimedia transaction against what this factory builds.

Bluefin's codec surface arrives in two moves that live in different places: the
`[multimedia_overrides]` distro-sync, which `config/bluefin-packages.toml`
mirrors from Bluefin's own manifest, and a codec tail written inline on the
`dnf5 install` line of `build_files/base/03-packages.sh`, which no manifest
carries at all. The second half was therefore invisible to every tool here --
`tools/rawhide_sources.py` imports what the manifest names, and the manifest
never named ffmpeg, lame, libjxl or ffmpegthumbnailer.

`config/multimedia-closure.toml` inventories both halves and states, for every
requirement, which factory recipe answers it, along with named upstream spec
sources from negativo17 and RPM Fusion. This module is the check that the
inventory is true of the tree: a requirement with no entry, an entry naming a
recipe that does not exist or is not eligible to build, an override without a
named upstream spec source, and an entry for something the transaction does not
ask for are all contract violations.

It also writes the report that answers the question the inventory exists for --
"which factory source, and which published binary, satisfies each Bluefin
multimedia requirement". Given `--repodata`, the published NEVRA comes out of
the repository's own `primary.xml`; without it the report carries the static
half alone and stays byte-for-byte reproducible, which is what lets
`tests/test_multimedia_closure.py` assert that the committed copy is current.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.package_inventory import inventory, source_locks

# repodata primary.xml puts every rpm: element in this namespace; the rest of
# the document is in the common one. Same two constants tools/rebuild_plan.py
# reads the published repository with.
COMMON_NS = "http://linux.duke.edu/metadata/common"
RPM_NS = "http://linux.duke.edu/metadata/rpm"

SCHEMA = 1


class ClosureError(Exception):
    """A statement in the inventory that the repository does not support."""


def load_closure(path: Path) -> dict:
    return tomllib.loads(path.read_text())


def requirements(manifest: dict, closure: dict) -> list[tuple[str, str]]:
    """Every name Bluefin's multimedia transaction asks for, with its origin.

    Order is the order the transaction writes it -- overrides, then the codec
    tail, then each comps group and the members it expands to -- because the
    report is read next to `03-packages.sh`, and a resorted list is harder to
    check against the line it came from.

    The override half is read out of the Bluefin manifest rather than out of
    the closure file. Restating it would give the factory two copies of a list
    upstream owns, and the next manifest sync would silently disagree with one
    of them.

    A name the transaction asks for twice -- `gstreamer1-plugins-good` is both
    on the install line and in `@multimedia` -- is one requirement, recorded
    under the first origin that asked for it. A comps group keeps its own
    entry as well as its members': the members are what has to be built, and
    the group name is what has to resolve, and against a repository with no
    comps metadata those are different questions.
    """
    transaction = closure.get("transaction", {})
    section = transaction.get("overrides_section")
    if not section:
        raise ClosureError("[transaction].overrides_section is required")
    if section not in manifest:
        raise ClosureError(f"Bluefin manifest has no [{section}] section")

    ordered: list[tuple[str, str]] = []
    for binary in manifest[section].get("packages", []):
        ordered.append((binary, "multimedia-override"))
    for binary in transaction.get("codecs", []):
        ordered.append((binary, "codec-transaction"))
    for group in transaction.get("groups", []):
        ordered.append((group, "comps-group"))
        definition = closure.get("groups", {}).get(group)
        if definition is None:
            raise ClosureError(f"[groups.\"{group}\"] is missing")
        for member in definition.get("members", []):
            ordered.append((member, f"comps-group:{group}"))

    names: list[tuple[str, str]] = []
    seen = set()
    for name, origin in ordered:
        if name in seen:
            continue
        seen.add(name)
        names.append((name, origin))
    if not names:
        raise ClosureError("the multimedia transaction resolved to no requirements")
    return names


def _claims(closure: dict) -> dict[str, dict]:
    """Flatten [built], [equivalent] and [exception] into one keyed map.

    A requirement claimed twice is caught here rather than by whichever of the
    three tables happened to be read last.
    """
    claims: dict[str, dict] = {}

    def record(name: str, claim: dict) -> None:
        if name in claims:
            raise ClosureError(f"requirement claimed by two tables: {name}")
        claims[name] = claim

    for name, source in closure.get("built", {}).items():
        if not isinstance(source, str) or not source:
            raise ClosureError(f"[built].{name} must name a factory source recipe")
        record(name, {"status": "built", "factory_source": source, "factory_binary": name})
    for name, entry in closure.get("equivalent", {}).items():
        for field in ("source", "binary", "reason"):
            if not entry.get(field):
                raise ClosureError(f"[equivalent.{name}] is missing {field}")
        record(name, {
            "status": "equivalent",
            "factory_source": entry["source"],
            "factory_binary": entry["binary"],
            "note": " ".join(entry["reason"].split()),
        })
    for name, entry in closure.get("exception", {}).items():
        if not entry.get("reason"):
            raise ClosureError(f"[exception.{name}] is missing reason")
        record(name, {
            "status": "exception",
            "factory_source": None,
            "factory_binary": None,
            "note": " ".join(entry["reason"].split()),
        })
    return claims


def evr_key(epoch: str, version: str, release: str) -> tuple:
    """A sort key that orders two builds of one package the way rpm does.

    Not a full `rpmvercmp` -- it does not model tilde or caret -- but it does
    model the part that matters here: compare digit and letter runs
    separately, and treat a numeric run as newer than an alphabetic one. A
    plain string comparison gets this wrong in the one case the factory
    actually produces, a release counter passing nine: "10.hum1.bfin" sorts
    below "2.hum1.bfin" as text, so the report would name the build the
    transaction will not install.
    """
    def runs(value: str) -> list[tuple[int, int, str]]:
        return [
            (1, int(part), "") if part.isdigit() else (0, 0, part)
            for part in re.findall(r"\d+|[A-Za-z]+", value)
        ]

    return (int(epoch or 0), runs(version), runs(release))


def primary_xml(repodata: Path) -> bytes:
    """The repository's decompressed primary.xml, whatever it is compressed with.

    `repomd.xml` is the index and names the file; the compression is
    createrepo_c's choice, not ours. Globbing `*primary.xml.gz` hard-coded the
    gzip default of createrepo_c < 1.0 -- an unpinned `apt-get install
    createrepo-c` on a runner-image bump moves that to zstd, renames the file,
    and the glob finds nothing. `tools/rebuild_matrix.py` already reads the
    published repository this way; this is the same read against a local tree.
    """
    index = repodata / "repomd.xml"
    candidates: list[Path] = []
    if index.is_file():
        href = re.search(r'<location href="([^"]*primary[^"]*)"', index.read_text())
        if href:
            named = repodata / Path(href.group(1)).name
            if named.is_file():
                candidates = [named]
    if not candidates:
        candidates = sorted(repodata.glob("*primary.xml*"))
    if not candidates:
        raise ClosureError(f"no primary.xml under {repodata}")

    path = candidates[0]
    raw = path.read_bytes()
    if path.suffix == ".gz":
        return gzip.decompress(raw)
    if path.suffix == ".zst":
        try:
            import zstandard
        except ImportError as error:  # pragma: no cover - environment-dependent
            # Raised as a ClosureError so main() names the cause instead of
            # letting a ModuleNotFoundError traceback out. The publish step
            # runs under `continue-on-error: true`, where an uncaught
            # exception is indistinguishable from "nothing to report".
            raise ClosureError(
                f"{path.name} is zstd-compressed but the zstandard module is "
                "not installed; add `pip install zstandard` to this job"
            ) from error

        return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)).read()
    if path.suffix == ".xml":
        return raw
    raise ClosureError(f"unsupported primary.xml compression: {path.name}")


def published_nevra(repodata: Path) -> dict[str, str]:
    """Binary package name -> NEVRA, read from a repository's primary.xml.

    The RPM file names in the repository would be cheaper to scan, but they
    carry no Epoch, and jpegxl -- which answers `libjxl` here -- has one. A
    report that silently dropped it would name a package that cannot be
    installed by the string it prints.
    """
    primary = primary_xml(repodata)
    best: dict[str, tuple] = {}
    found: dict[str, str] = {}
    for package in ElementTree.fromstring(primary).iter(f"{{{COMMON_NS}}}package"):
        name = package.findtext(f"{{{COMMON_NS}}}name") or ""
        version = package.find(f"{{{COMMON_NS}}}version")
        architecture = package.findtext(f"{{{COMMON_NS}}}arch") or ""
        if not name or version is None:
            continue
        epoch = version.get("epoch", "0")
        release = version.get("rel", "")
        key = evr_key(epoch, version.get("ver", ""), release)
        # One name can appear at several versions: the publish job seeds the
        # repository from the image it is replacing, so a superseded build is
        # still there until createrepo indexes over it. The newest is the one
        # a transaction gets, so it is the one the report names.
        if name not in best or key > best[name]:
            best[name] = key
            found[name] = (
                f"{name}-{epoch}:{version.get('ver', '')}-{release}.{architecture}"
            )
    return found


def resolve(root: Path, repodata: Path | None = None) -> dict:
    manifest = tomllib.loads((root / "config" / "bluefin-packages.toml").read_text())
    closure = load_closure(root / "config" / "multimedia-closure.toml")
    recipes = {record.name: record for record in inventory(root)}
    locks = source_locks(root)
    claims = _claims(closure)
    upstream_sources = closure.get("upstream_spec_sources", {})
    nevra = published_nevra(repodata) if repodata else {}

    wanted = requirements(manifest, closure)
    unclaimed = [name for name, _ in wanted if name not in claims]
    if unclaimed:
        raise ClosureError(
            "multimedia requirements with no entry in config/multimedia-closure.toml: "
            + ", ".join(unclaimed)
        )
    stale = sorted(set(claims) - {name for name, _ in wanted})
    if stale:
        raise ClosureError(
            "config/multimedia-closure.toml claims requirements the transaction "
            "does not ask for: " + ", ".join(stale)
        )
    stale_sources = sorted(set(upstream_sources) - {name for name, _ in wanted})
    if stale_sources:
        raise ClosureError(
            "config/multimedia-closure.toml [upstream_spec_sources] maps names the "
            "transaction does not ask for: " + ", ".join(stale_sources)
        )

    resolved = []
    for name, origin in wanted:
        claim = claims[name]
        upstream_spec_source = upstream_sources.get(name) or (
            upstream_sources.get(claim["factory_source"]) if claim.get("factory_source") else None
        )
        entry = {
            "requirement": name,
            "origin": origin,
            "status": claim["status"],
            "factory_source": claim["factory_source"],
            "factory_binary": claim["factory_binary"],
            "upstream_spec_source": upstream_spec_source,
            "recipe": None,
            "stage": None,
            "version": None,
            "nevra": None,
            "recipe_provenance": None,
        }
        if "note" in claim:
            entry["note"] = claim["note"]
        source = claim["factory_source"]
        if source is not None:
            record = recipes.get(source)
            if record is None:
                raise ClosureError(
                    f"{name} is answered by {source}, which is not a recipe in packages/"
                )
            if not record.source_locked or not record.packit_configured:
                raise ClosureError(
                    f"{name} is answered by {source}, which is not eligible to build "
                    "(no source lock or no Packit entry)"
                )
            entry["recipe"] = f"packages/{source}"
            entry["stage"] = record.stage
            entry["version"] = locks[source].get("version")
            upstream_json = root / "packages" / source / ".hummingbird-upstream.json"
            if upstream_json.is_file():
                try:
                    entry["recipe_provenance"] = json.loads(
                        upstream_json.read_text()
                    ).get("remote")
                except Exception:
                    entry["recipe_provenance"] = None
        if claim["factory_binary"]:
            entry["nevra"] = nevra.get(claim["factory_binary"])

        if origin == "multimedia-override":
            if not claim.get("factory_source"):
                raise ClosureError(
                    f"multimedia override binary '{name}' has no factory source recipe"
                )
            if not upstream_spec_source:
                raise ClosureError(
                    f"multimedia override binary '{name}' has no named upstream spec source"
                )
            if not any(domain in upstream_spec_source for domain in ("negativo17", "rpmfusion")):
                raise ClosureError(
                    f"multimedia override binary '{name}' upstream spec source '{upstream_spec_source}' "
                    "must be from negativo17 or rpmfusion"
                )

        resolved.append(entry)

    counts = {
        "requirements": len(resolved),
        "built": sum(1 for entry in resolved if entry["status"] == "built"),
        "equivalent": sum(1 for entry in resolved if entry["status"] == "equivalent"),
        "exception": sum(1 for entry in resolved if entry["status"] == "exception"),
        "sources": len({entry["factory_source"] for entry in resolved if entry["factory_source"]}),
    }
    report = {
        "schema": SCHEMA,
        "transaction": {
            "source": closure["transaction"].get("source", ""),
            "overrides": f"{closure['transaction'].get('overrides_manifest', '')}"
                         f" [{closure['transaction'].get('overrides_section', '')}]",
            "codecs": "config/multimedia-closure.toml [transaction].codecs",
        },
        "policy": closure.get("policy", {}),
        "counts": counts,
        "requirements": resolved,
    }
    if repodata is not None:
        # Only meaningful against a real repository, so it is absent rather
        # than zero in the static report.
        report["counts"]["published"] = sum(1 for entry in resolved if entry["nevra"])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--repodata", type=Path,
                        help="a published repository's repodata directory, for NEVRAs")
    parser.add_argument("--output", type=Path, help="write the report here")
    parser.add_argument("--check", action="store_true",
                        help="validate the inventory without writing a report")
    args = parser.parse_args(argv)

    try:
        report = resolve(args.root.resolve(), args.repodata)
    except (ClosureError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    counts = report["counts"]
    summary = ", ".join(f"{value} {key}" for key, value in counts.items())
    if args.check:
        print(f"multimedia closure inventoried: {summary}")
    else:
        print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
