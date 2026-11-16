#!/usr/bin/env python3
"""Map every element of Dakota's BuildStream graph to the RPM that provides it.

Dakota (`projectbluefin/dakota`) is the parity target for Utah. It is GNOME OS
built with BuildStream on gnome-build-meta and freedesktop-sdk, so it has no
RPM database: parity has to be measured element by element. This tool keeps
that measurement explicit, evidence-backed and reproducible:

- ``config/dakota-elements.tsv`` is the element snapshot: one row per element
  in the SPDX SBOM Dakota's publish workflow uploads, with the element's
  primary source version and how many files (and user-visible files) it owns
  in the published image. Ownership comes from the ``user.component`` xattr
  chunkah writes on every file of the image, so "ships in the image" is
  measured, not guessed. ``--import-sbom`` rewrites it.
- ``config/dakota.json`` pins the Dakota revision, the SBOM's publish run and
  the image digest, carries the reviewer decisions (``overrides``,
  ``aliases``) and the generated element -> RPM source-package mapping with a
  disposition per element. ``--refresh`` regenerates the mapping online
  (Fedora Rawhide repodata, Fedora dist-git, Hummingbird repodata); the audit
  itself is offline.
- ``reports/audit-dakota.json`` / ``.md`` hold the disposition counts, the
  import queue (Fedora-importable and new-spec elements without a factory
  recipe, user-visible ones first) and the version drift of the elements the
  factory already builds. They are derived and never committed: every recipe
  import moves them, so a tracked copy would go stale or make concurrent
  import PRs conflict (#309). CI publishes the live report as an artifact.
- ``--check`` builds the report in memory, writes nothing, and fails when the
  committed inputs break the audit's contract (see ``contract_problems``).

Dispositions
------------
``factory``           a recipe for the RPM exists in ``packages/``
``hummingbird``       Hummingbird's repository already builds the source package
``fedora-importable`` Fedora Rawhide has the source package: import its recipe
``dakota-config``     a Dakota config-only element: a ``dakota-config`` subpackage
``gnomeos-config``    a gnome-build-meta config-only element: a ``gnome-os-config``
                      subpackage
``new-spec``          no Fedora recipe: write the spec from the ``.bst``
``not-applicable``    BuildStream, bootstrap, SDK-only or GNOME OS image
                      machinery, or an element that owns no file in the image
``structural``        decided by a Utah Dakota-parity issue (#1222-#1236)

Only the Python standard library is needed (plus PyYAML through the shared
``audit_gnome_build_meta`` helpers), so it runs on a GitHub-hosted runner.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import io
import json
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit_gnome_build_meta import (  # noqa: E402
    ALIGNED,
    NEEDS_REVIEW,
    _factory_rev,
    numeric_components,
    release_line,
)
from tools.package_inventory import load_source_locks  # noqa: E402

# --- Disposition vocabulary ----------------------------------------------------
FACTORY = "factory"
HUMMINGBIRD = "hummingbird"
FEDORA_IMPORTABLE = "fedora-importable"
DAKOTA_CONFIG = "dakota-config"
GNOMEOS_CONFIG = "gnomeos-config"
NEW_SPEC = "new-spec"
NOT_APPLICABLE = "not-applicable"
STRUCTURAL = "structural"
DISPOSITIONS = (
    FACTORY, HUMMINGBIRD, FEDORA_IMPORTABLE, DAKOTA_CONFIG, GNOMEOS_CONFIG,
    NEW_SPEC, NOT_APPLICABLE, STRUCTURAL,
)
# Dispositions a reviewer records in ``overrides``. The availability
# dispositions (factory, hummingbird, fedora-importable) are measured, never
# asserted; ``new-spec`` is allowed so a reviewer can refuse a Fedora recipe
# that does not match the element (a different upstream behind the same name).
OVERRIDE_DISPOSITIONS = (
    DAKOTA_CONFIG, GNOMEOS_CONFIG, NEW_SPEC, NOT_APPLICABLE, STRUCTURAL,
)
STRUCTURAL_ISSUES = range(1222, 1237)

# Drift classification: the release-line comparison reuses the gnome-build-meta
# audit's vocabulary; ``not_compared`` says out loud that one side has no
# version (a bare commit, a checksum), instead of reading as aligned.
NOT_COMPARED = "not_compared"

# Import-queue ordering: what a user sees first.
VISIBILITY_GROUPS = ("apps", "daemons", "commands", "libraries-and-data")

BUILD_ONLY_REASON = "build-only: owns no file in the published image"

SNAPSHOT_COLUMNS = (
    "element", "name", "in_image", "sources", "version", "url", "patches",
    "files", "apps", "units", "commands",
)

DAKOTA_PROJECT = "dakota"
GBM_PROJECT = "gnome-build-meta"
FDSDK_PROJECT = "freedesktop-sdk"
FDSDK_EXTRA_PROJECT = "freedesktop-sdk-extra"
_JUNCTIONS = {
    "": DAKOTA_PROJECT,
    "gnome-build-meta.bst": GBM_PROJECT,
    "freedesktop-sdk.bst": FDSDK_PROJECT,
    "gnome-build-meta.bst:freedesktop-sdk-extra.bst": FDSDK_EXTRA_PROJECT,
}

# Sources that carry no upstream component: files from the project itself.
_LOCAL_KINDS = {"local"}
_PATCH_KINDS = {"patch", "patch_queue"}
# Vendored crates and modules ride along with a primary source.
_VENDORED_KINDS = {"cargo2", "go_module", "git_module"}

_SHA_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{40,64}$")
_DESCRIBE_RE = re.compile(r"^(?P<tag>.+?)-\d+-g[0-9a-f]{7,40}$")
_ARCHIVE_SUFFIX = re.compile(
    r"\.(?:tar\.(?:gz|xz|bz2|zst|lz)|tgz|tbz2|zip|gem|crate|git)$"
)
_VERSION_TAIL = re.compile(r"[-_.]v?\d[\w.+~-]*$")


@dataclass(frozen=True)
class ElementRecord:
    """One row of the element snapshot."""

    element: str
    name: str
    in_image: bool
    sources: tuple[str, ...]
    version: str
    url: str
    patches: int
    files: int = 0
    apps: int = 0
    units: int = 0
    commands: int = 0

    @property
    def project(self) -> str:
        return project_of(self.element)

    @property
    def path(self) -> str:
        return self.element.rsplit(":", 1)[-1]

    @property
    def basename(self) -> str:
        return PurePosixPath(self.path).name.removesuffix(".bst")

    @property
    def config_only(self) -> bool:
        """No upstream source: the element installs the project's own files."""
        upstream = [kind for kind in self.sources
                    if kind not in _LOCAL_KINDS | _PATCH_KINDS]
        return not upstream

    @property
    def visibility(self) -> str:
        if self.apps:
            return "apps"
        if self.units:
            return "daemons"
        if self.commands:
            return "commands"
        return "libraries-and-data"


def project_of(element: str) -> str:
    """The BuildStream project an SBOM locator belongs to."""
    junction = element.rsplit(":", 1)[0] if ":" in element else ""
    try:
        return _JUNCTIONS[junction]
    except KeyError:
        raise ValueError(f"unknown junction in element locator: {element}") from None


# --- Snapshot (SBOM + image ownership) ----------------------------------------

def _bare(element: str) -> str:
    """Element path without junction prefixes: how chunkah names an owner."""
    return element.rsplit(":", 1)[-1]


def sbom_elements(sbom: dict) -> list[dict]:
    """Elements of a buildstream-sbom SPDX document with their sources in order.

    Each element is a package with a ``bst-element`` reference and no
    ``sourceInfo``; its sources are the packages it is ``GENERATED_FROM``,
    numbered ``<element-id>-<n>`` in the element's source order.
    """
    packages = {pkg["SPDXID"]: pkg for pkg in sbom["packages"]}
    sources: dict[str, list[str]] = {}
    for rel in sbom.get("relationships", []):
        if rel["relationshipType"] == "GENERATED_FROM":
            sources.setdefault(rel["spdxElementId"], []).append(rel["relatedSpdxElement"])

    def order(spdx_id: str) -> int:
        tail = spdx_id.rsplit("-", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    elements = []
    for pkg in sbom["packages"]:
        if "sourceInfo" in pkg:
            continue
        refs = [ref["referenceLocator"] for ref in pkg.get("externalRefs", [])
                if ref.get("referenceType") == "bst-element"]
        if len(refs) != 1:
            raise ValueError(f"SBOM element {pkg['SPDXID']} has no single bst-element ref")
        elements.append({
            "element": refs[0],
            "name": pkg["name"],
            "sources": [packages[s] for s in sorted(sources.get(pkg["SPDXID"], []), key=order)],
        })
    return elements


def primary_source(sources: list[dict]) -> dict | None:
    """The element's first upstream source (not a patch, not a local file)."""
    for source in sources:
        kind = source.get("sourceInfo")
        if kind in _LOCAL_KINDS or kind in _PATCH_KINDS or kind in _VENDORED_KINDS:
            continue
        return source
    return None


def image_ownership(members) -> dict[str, dict[str, int]]:
    """Per-owner file statistics from image layer tar members.

    ``members`` yields ``(path, owner)``; the owner is the chunkah
    ``user.component`` xattr (an element path without junction prefix).
    """
    stats: dict[str, dict[str, int]] = {}
    for path, owner in members:
        if not owner:
            continue
        entry = stats.setdefault(owner, {"files": 0, "apps": 0, "units": 0, "commands": 0})
        entry["files"] += 1
        path = path.lstrip("./")
        if path.startswith("usr/share/applications/") and path.endswith(".desktop"):
            entry["apps"] += 1
        elif re.match(r"usr/lib/systemd/(?:system|user)/[^/]+\.(?:service|socket|timer|path)$", path):
            entry["units"] += 1
        elif re.match(r"usr/s?bin/[^/]+$", path):
            entry["commands"] += 1
    return stats


def _layer_members(blob: Path):
    """``(path, owner)`` for each regular file or symlink in one OCI layer."""
    with blob.open("rb") as raw:
        magic = raw.read(4)
    if magic == b"\x28\xb5\x2f\xfd":
        proc = subprocess.Popen(["zstd", "-dc", str(blob)], stdout=subprocess.PIPE)
        stream = proc.stdout
    elif magic[:2] == b"\x1f\x8b":
        proc = None
        stream = gzip.open(blob, "rb")
    else:
        proc = None
        stream = blob.open("rb")
    try:
        with tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                if member.isdir():
                    continue
                yield member.name, member.pax_headers.get("SCHILY.xattr.user.component")
    finally:
        stream.close()
        if proc is not None:
            proc.wait()


def scan_image_layout(layout: Path, digest: str) -> dict[str, dict[str, int]]:
    """File ownership of the image ``digest`` inside an OCI layout directory."""
    algo, _, hexdigest = digest.partition(":")
    manifest_path = layout / "blobs" / algo / hexdigest
    if not manifest_path.is_file():
        raise SystemExit(f"error: {digest} is not in OCI layout {layout}")
    manifest = json.loads(manifest_path.read_text())

    def scan(layer: dict) -> list[tuple[str, str | None]]:
        a, _, h = layer["digest"].partition(":")
        return list(_layer_members(layout / "blobs" / a / h))

    members: list[tuple[str, str | None]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for chunk in pool.map(scan, manifest["layers"]):
            members.extend(chunk)
    return image_ownership(members)


def build_snapshot(sbom: dict, ownership: dict[str, dict[str, int]]) -> list[ElementRecord]:
    records = []
    owners = set(ownership)
    known = {_bare(e["element"]) for e in sbom_elements(sbom)}
    unknown = sorted(owners - known - {"chunkah/unclaimed", "dakota.integration"})
    if unknown:
        print(f"warning: image owners missing from the SBOM: {unknown[:10]}", file=sys.stderr)
    for element in sbom_elements(sbom):
        primary = primary_source(element["sources"])
        stats = ownership.get(_bare(element["element"]), {})
        records.append(ElementRecord(
            element=element["element"],
            name=element["name"],
            in_image=bool(stats.get("files")),
            sources=tuple(sorted({s.get("sourceInfo", "") for s in element["sources"]})),
            version=(primary or {}).get("versionInfo", "") or "",
            url=(primary or {}).get("downloadLocation", "") or "",
            patches=sum(1 for s in element["sources"] if s.get("sourceInfo") in _PATCH_KINDS),
            files=stats.get("files", 0),
            apps=stats.get("apps", 0),
            units=stats.get("units", 0),
            commands=stats.get("commands", 0),
        ))
    return sorted(records, key=lambda r: r.element)


def write_snapshot(path: Path, records: list[ElementRecord]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(SNAPSHOT_COLUMNS)
        for r in records:
            writer.writerow([
                r.element, r.name, "yes" if r.in_image else "no", "+".join(r.sources),
                r.version, r.url, r.patches, r.files, r.apps, r.units, r.commands,
            ])


def read_snapshot(path: Path) -> list[ElementRecord]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = tuple(next(reader))
        if header != SNAPSHOT_COLUMNS:
            raise ValueError(f"{path}: unexpected columns {header}")
        records = []
        for row in reader:
            values = dict(zip(SNAPSHOT_COLUMNS, row))
            records.append(ElementRecord(
                element=values["element"],
                name=values["name"],
                in_image=values["in_image"] == "yes",
                sources=tuple(s for s in values["sources"].split("+") if s),
                version=values["version"],
                url=values["url"],
                patches=int(values["patches"]),
                files=int(values["files"]),
                apps=int(values["apps"]),
                units=int(values["units"]),
                commands=int(values["commands"]),
            ))
    elements = [r.element for r in records]
    if len(set(elements)) != len(elements):
        raise ValueError(f"{path}: duplicate element rows")
    return records


# --- Versions and drift ---------------------------------------------------------

def sbom_version(value: str) -> str | None:
    """The upstream version an SBOM ``versionInfo`` encodes, if any.

    Tags (``1.2.14``, ``v4.23.0``) and ``git describe`` refs
    (``51.1-36-g8a89846...``) carry one; a bare commit, a checksum or a local
    file digest (``<sha256>/<size>``) does not.
    """
    value = (value or "").strip()
    if not value or "/" in value or _SHA_RE.match(value):
        return None
    match = _DESCRIBE_RE.match(value)
    if match:
        value = match.group("tag")
    value = re.sub(r"^[A-Za-z_-]*?[-_]?v?(?=\d)", "", value)
    if not value or not value[0].isdigit():
        return None
    return value.replace("_", ".")


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in numeric_components(version))


def version_drift(dakota_version: str | None, factory_version: str | None) -> tuple[str, str]:
    """Compare the factory recipe with the Dakota element by release line."""
    if not factory_version:
        return NOT_COMPARED, "factory recipe has no locked version"
    if not dakota_version:
        return NOT_COMPARED, (
            f"Dakota's source encodes no version (a commit or checksum); "
            f"factory is {factory_version}"
        )
    factory_line = release_line(factory_version)
    dakota_line = release_line(dakota_version)
    if factory_line and factory_line == dakota_line:
        if factory_version == dakota_version:
            return ALIGNED, f"same version {factory_version}"
        return ALIGNED, (
            f"release line {dakota_line} matches; factory {factory_version} "
            f"vs Dakota {dakota_version}"
        )
    direction = "ahead of" if _version_key(factory_version) > _version_key(dakota_version) else "behind"
    return NEEDS_REVIEW, (
        f"release line {factory_line} (factory {factory_version}) is {direction} "
        f"Dakota's {dakota_line} ({dakota_version})"
    )


# --- Fedora name resolution ------------------------------------------------------

_SPLIT_SUFFIXES = (
    "-daemon-only", "-daemon", "-libs", "-lib", "-gobject", "-tools", "-full",
    "-systemd", "-base", "-minimal", "-app", "-client", "-config", "-stage1",
    "-headers", "-docs", "-only",
)


def _url_stem(url: str) -> str | None:
    """Project name from a source url: the tarball or repository name."""
    if not url or url == "NOASSERTION":
        return None
    tail = url.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
    tail = _ARCHIVE_SUFFIX.sub("", tail)
    stem = _VERSION_TAIL.sub("", tail)
    if not stem or stem[0].isdigit() or stem in ("download", "archive", "releases"):
        return None
    return stem


def _variants(seed: str) -> list[str]:
    """Fedora spellings of one element or project name, the name itself first."""
    out = [seed]
    if "-" in seed:
        out.append(seed.replace("-", "_"))           # lm_sensors, wpa_supplicant
    if seed.startswith("python3-"):
        out.append("python-" + seed[len("python3-"):])
    if seed.startswith("gstreamer"):
        out.append("gstreamer1" + seed[len("gstreamer"):])
    if seed.startswith("xorg-lib-"):
        out.append("lib" + seed[len("xorg-lib-"):])  # libxft -> libXft, case-folded
    if seed.startswith(("xorg-app-", "xorg-data-")):
        out.append(seed.split("-", 2)[2])
    if seed.startswith("xorg-font-"):
        out.append("xorg-x11-font-" + seed[len("xorg-font-"):])
    for suffix in _SPLIT_SUFFIXES:
        if seed.endswith(suffix) and len(seed) > len(suffix):
            out.append(seed[: -len(suffix)])          # avahi-libs -> avahi
            break
    return out


def candidate_names(record: ElementRecord, aliases: dict[str, list[str]]) -> list[str]:
    """Fedora package names to try for an element, most specific first.

    Reviewer ``aliases`` first, then the element's own name and its Fedora
    spellings, then the upstream project name from the source url. The url
    comes last because it names the repository, not the split: every
    ``gstreamer-plugins-*`` element is built from ``gstreamer.git``.
    """
    out: list[str] = []

    def add(*names: str | None) -> None:
        for name in names:
            if name and name not in out:
                out.append(name)

    add(*aliases.get(record.element, []))
    base = record.basename
    if "/shell-extensions/" in f"/{record.path}":
        add("gnome-shell-extension-" + base)
    add(*_variants(base))
    add(*_variants(record.name))
    stem = _url_stem(record.url)
    if stem:
        if base.startswith("perl-"):
            add("perl-" + stem)                        # perl-ssl -> perl-IO-Socket-SSL
        if base.startswith("python3-"):
            add("python-" + stem.lower(), "python-" + stem)
        add(*_variants(stem))
    return out


@dataclass
class FedoraIndex:
    """Rawhide's active source packages and binary -> source map."""

    sources: set[str]
    binaries: dict[str, str]

    def __post_init__(self) -> None:
        self._sources_ci: dict[str, str] = {}
        for name in sorted(self.sources):
            self._sources_ci.setdefault(name.lower(), name)
        self._binaries_ci: dict[str, str] = {}
        for name in sorted(self.binaries):
            self._binaries_ci.setdefault(name.lower(), name)

    def resolve(self, candidates: list[str]) -> tuple[str | None, str | None]:
        """First candidate Rawhide builds: ``(source package, evidence)``."""
        for name in candidates:
            if name in self.sources:
                return name, "rawhide source"
            folded = self._sources_ci.get(name.lower())
            if folded:
                return folded, f"rawhide source {folded} (case-folded from {name})"
            if name in self.binaries:
                return self.binaries[name], f"rawhide binary {name}"
            folded = self._binaries_ci.get(name.lower())
            if folded:
                return self.binaries[folded], f"rawhide binary {folded}"
        return None, None


# --- Classification -----------------------------------------------------------

_CONFIG_PROJECTS = {DAKOTA_CONFIG: DAKOTA_PROJECT, GNOMEOS_CONFIG: GBM_PROJECT}


def config_package(pin: dict, record: ElementRecord) -> str | None:
    """The config disposition of a config-only Dakota or gbm element.

    A Dakota element without upstream sources installs Dakota's own files
    (often written inline in the ``.bst``). A gbm element only counts when it
    has ``local`` sources: a gbm element with no sources at all is usually a
    ``filter`` splitting an upstream component (``core-deps/systemd.bst``).
    """
    if not record.config_only:
        return None
    if record.project == DAKOTA_PROJECT:
        return DAKOTA_CONFIG
    if record.project == GBM_PROJECT and record.sources:
        return GNOMEOS_CONFIG
    return None


def _config_decision(pin: dict, record: ElementRecord, disposition: str, reason: str) -> dict:
    package = pin["config_packages"][_CONFIG_PROJECTS[disposition]]
    return {
        "disposition": disposition,
        "rpm": package,
        "subpackage": f"{package}-{record.basename}",
        "reason": reason,
    }


def classify_element(record: ElementRecord, pin: dict, resolution: dict,
                     factory: set[str]) -> dict:
    """Disposition of one element.

    ``resolution`` is the measured availability: ``rpm`` (the Fedora source
    package, or None), ``hummingbird`` (Hummingbird builds it) and
    ``evidence``. Precedence: a reviewer override, then build-only (no file
    in the image), then config-only, then factory > hummingbird >
    fedora-importable > new-spec.
    """
    override = (pin.get("overrides") or {}).get(record.element)
    rpm = resolution.get("rpm")
    if override is not None:
        disposition = override["disposition"]
        if disposition in _CONFIG_PROJECTS:
            return {**_config_decision(pin, record, disposition, override["reason"]),
                    "override": True}
        rpm = override.get("rpm", rpm)
        decision = {
            "disposition": disposition,
            "rpm": rpm,
            "reason": override["reason"],
            "override": True,
        }
        if override.get("issue"):
            decision["issue"] = override["issue"]
        if disposition == NEW_SPEC and rpm in factory:
            decision["disposition"] = FACTORY
        return decision
    if not record.in_image:
        return {"disposition": NOT_APPLICABLE, "rpm": rpm, "reason": BUILD_ONLY_REASON}
    config = config_package(pin, record)
    if config is not None:
        return _config_decision(
            pin, record, config,
            f"config-only {record.project} element: installs the project's own files")
    if rpm and rpm in factory:
        return {"disposition": FACTORY, "rpm": rpm, "reason": resolution.get("evidence") or ""}
    if not rpm:
        recipe = next((n for n in candidate_names(record, pin.get("aliases", {}))
                       if n in factory), None)
        if recipe:
            return {"disposition": FACTORY, "rpm": recipe,
                    "reason": "factory-authored recipe (no Fedora source package)"}
    if resolution.get("hummingbird"):
        return {"disposition": HUMMINGBIRD, "rpm": rpm, "reason": resolution.get("evidence") or ""}
    if rpm:
        return {"disposition": FEDORA_IMPORTABLE, "rpm": rpm,
                "reason": resolution.get("evidence") or ""}
    reason = "no Fedora source package matches " + ", ".join(
        candidate_names(record, pin.get("aliases", {}))[:4])
    if resolution.get("evidence"):
        reason += f" ({resolution['evidence']})"
    return {"disposition": NEW_SPEC, "rpm": None, "reason": reason}


def gnome_build_meta_aliases(gbm_pin: dict) -> dict[str, list[str]]:
    """RPM names the gnome-build-meta audit already maps, keyed by Dakota locator.

    ``config/gnome-build-meta.json`` maps GNOME source packages to gbm
    elements (``gtk4 -> sdk/gtk.bst``); Dakota reaches the same elements
    through its ``gnome-build-meta.bst`` junction. Reusing that mapping keeps
    one answer for each GNOME rename.
    """
    factory_alias = gbm_pin.get("factory_alias") or {}
    out: dict[str, list[str]] = {}
    for rpm, path in sorted((gbm_pin.get("mapping") or {}).items()):
        name = factory_alias.get(rpm, rpm)
        names = out.setdefault(f"gnome-build-meta.bst:{path}", [])
        if name not in names:
            names.append(name)
    return out


def with_gbm_aliases(pin: dict, gbm_pin: dict) -> dict:
    """The pin with gnome-build-meta's names appended after its own aliases."""
    merged = {element: list(names) for element, names in (pin.get("aliases") or {}).items()}
    for element, names in gnome_build_meta_aliases(gbm_pin).items():
        merged.setdefault(element, [])
        merged[element] += [n for n in names if n not in merged[element]]
    resolved = dict(pin)
    resolved["aliases"] = merged
    return resolved


# --- Pin ----------------------------------------------------------------------

def load_pin(path: Path) -> dict:
    pin = json.loads(path.read_text())
    validate_pin(pin)
    return pin


def validate_pin(pin: dict) -> None:
    if pin.get("schema") != 1:
        raise ValueError("config/dakota.json: unsupported schema")
    if not re.fullmatch(r"[0-9a-f]{40}", pin["source"]["revision"]):
        raise ValueError("source.revision must be a full commit")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", pin["source"]["image_digest"]):
        raise ValueError("source.image_digest must be a sha256 digest")
    for element, override in (pin.get("overrides") or {}).items():
        disposition = override.get("disposition")
        if disposition not in OVERRIDE_DISPOSITIONS:
            raise ValueError(f"override {element}: disposition {disposition!r} is measured, not asserted")
        if not (override.get("reason") or "").strip():
            raise ValueError(f"override {element}: needs a reason")
        if disposition == STRUCTURAL:
            issue = override.get("issue", "")
            number = int(issue.lstrip("#")) if re.fullmatch(r"#\d+", issue or "") else None
            if number not in STRUCTURAL_ISSUES:
                raise ValueError(f"override {element}: structural needs an issue in #1222-#1236")
    for element, entry in (pin.get("elements") or {}).items():
        if entry.get("disposition") not in DISPOSITIONS:
            raise ValueError(f"element {element}: unknown disposition {entry.get('disposition')!r}")
    prefixes = tuple(f"{pkg}-" for pkg in pin["config_packages"].values())
    for element, subpackages in (pin.get("config_subpackages") or {}).items():
        for sub in subpackages:
            if not sub.startswith(prefixes):
                raise ValueError(f"config_subpackages {element}: {sub} is not a config package")


# --- Report -------------------------------------------------------------------

def stored_resolution(pin: dict, element: str) -> dict:
    entry = (pin.get("elements") or {}).get(element) or {}
    return {
        "rpm": entry.get("fedora"),
        "hummingbird": entry.get("hummingbird", False),
        "evidence": entry.get("evidence"),
    }


_SPEC_PACKAGE = re.compile(r"^%package\s+(?:(-n)\s+)?(\S+)", flags=re.MULTILINE)


def spec_subpackages(spec: Path) -> set[str]:
    """Full names of the subpackages a spec declares (``%package [-n] name``)."""
    name = spec.stem
    return {sub if flag else f"{name}-{sub}"
            for flag, sub in _SPEC_PACKAGE.findall(spec.read_text())}


def config_gaps(pin: dict, entries: list[dict], packages_dir: Path | None) -> dict[str, dict]:
    """Per config source package: the subpackages the mapping expects and the recipe lacks.

    Expected are the ``subpackage`` of every config-disposition element plus
    ``config_subpackages``: the config part of a component element (a preset
    Dakota writes next to the component it enables).
    """
    expected: dict[str, set[str]] = {pkg: set() for pkg in pin["config_packages"].values()}
    for entry in entries:
        if entry["disposition"] in _CONFIG_PROJECTS:
            expected[entry["rpm"]].add(entry["subpackage"])
        for sub in entry.get("config_subpackages") or []:
            owner = next(pkg for pkg in expected if sub.startswith(pkg + "-"))
            expected[owner].add(sub)
    gaps = {}
    for package, wanted in sorted(expected.items()):
        spec = packages_dir / package / f"{package}.spec" if packages_dir else None
        if spec is None or not spec.is_file():
            gaps[package] = {"recipe": False, "missing": sorted(wanted)}
            continue
        gaps[package] = {"recipe": True, "missing": sorted(wanted - spec_subpackages(spec))}
    return gaps


def build_report(pin: dict, records: list[ElementRecord], factory_locks: dict,
                 packages_dir: Path | None = None) -> dict:
    factory = set(factory_locks)
    stored = pin.get("elements") or {}
    entries = []
    stale = []
    unmapped = []
    for record in records:
        if record.element not in stored:
            unmapped.append(record.element)
        decision = classify_element(record, pin, stored_resolution(pin, record.element), factory)
        recorded = (stored.get(record.element) or {}).get("disposition")
        if recorded and recorded != decision["disposition"]:
            stale.append({"element": record.element, "recorded": recorded,
                          "now": decision["disposition"], "rpm": decision.get("rpm")})
        entries.append({
            "element": record.element,
            "name": record.name,
            "in_image": record.in_image,
            "visibility": record.visibility if record.in_image else None,
            "dakota_version": sbom_version(record.version),
            **decision,
        })
        extras = (pin.get("config_subpackages") or {}).get(record.element)
        if extras:
            entries[-1]["config_subpackages"] = list(extras)

    # A split element (a ``filter`` such as bluez-libs, or a stack such as
    # bluez over _private/bluez-base) has no source of its own; the element
    # that builds the same RPM carries the version.
    rpm_versions: dict[str, tuple[str, str]] = {}
    for entry in entries:
        if entry.get("rpm") and entry["dakota_version"]:
            rpm_versions.setdefault(entry["rpm"], (entry["dakota_version"], entry["element"]))
    for entry in entries:
        if entry["disposition"] != FACTORY or entry.get("rpm") not in factory_locks:
            continue
        dakota_version, via = entry["dakota_version"], None
        if not dakota_version and entry["rpm"] in rpm_versions:
            dakota_version, via = rpm_versions[entry["rpm"]]
        factory_version = factory_locks[entry["rpm"]].get("version")
        classification, reason = version_drift(dakota_version, factory_version)
        entry["drift"] = {
            "factory_version": factory_version,
            "dakota_version": dakota_version,
            "classification": classification,
            "reason": reason if via is None else f"{reason} (Dakota version from {via})",
        }

    counts = {d: 0 for d in DISPOSITIONS}
    for entry in entries:
        counts[entry["disposition"]] += 1

    return {
        "schema": 1,
        "generated_for": {
            "dakota_revision": pin["source"]["revision"],
            "sbom": pin["source"]["sbom"],
            "image": f"{pin['source']['image']}@{pin['source']['image_digest']}",
            "factory_base": _factory_rev(),
        },
        "counts": counts,
        "counts_in_image": {
            d: sum(1 for e in entries if e["in_image"] and e["disposition"] == d)
            for d in DISPOSITIONS
        },
        "import_queue": {
            FEDORA_IMPORTABLE: import_queue(entries, FEDORA_IMPORTABLE),
            NEW_SPEC: import_queue(entries, NEW_SPEC),
        },
        "drift": sorted(
            ({"element": e["element"], "rpm": e["rpm"], **e["drift"]}
             for e in entries if "drift" in e),
            key=lambda d: ({NEEDS_REVIEW: 0, NOT_COMPARED: 1, ALIGNED: 2}[d["classification"]],
                           d["rpm"], d["element"]),
        ),
        "stale_mappings": stale,
        "unmapped_elements": unmapped,
        "config_gaps": config_gaps(pin, entries, packages_dir),
        # Build-only elements need no RPM; listing their names keeps the
        # report reviewable (and under the repository's large-file limit).
        # Drift lives in "drift" only.
        "build_only": [e["element"] for e in entries if e.get("reason") == BUILD_ONLY_REASON],
        "elements": [{k: v for k, v in e.items() if k != "drift"}
                     for e in entries if e.get("reason") != BUILD_ONLY_REASON],
    }


def import_queue(entries: list[dict], disposition: str) -> list[dict]:
    """Elements awaiting a recipe, one row per RPM, user-visible ones first."""
    rows: dict[str, dict] = {}
    for entry in entries:
        if entry["disposition"] != disposition:
            continue
        key = entry["rpm"] or entry["name"]
        row = rows.setdefault(key, {
            "rpm": entry["rpm"],
            "name": key,
            "elements": [],
            "dakota_versions": [],
            "visibility": "libraries-and-data",
        })
        row["elements"].append(entry["element"])
        if entry["dakota_version"] and entry["dakota_version"] not in row["dakota_versions"]:
            row["dakota_versions"].append(entry["dakota_version"])
        if VISIBILITY_GROUPS.index(entry["visibility"]) < VISIBILITY_GROUPS.index(row["visibility"]):
            row["visibility"] = entry["visibility"]
    return sorted(rows.values(),
                  key=lambda r: (VISIBILITY_GROUPS.index(r["visibility"]), r["name"].lower()))


def render_markdown(report: dict) -> str:
    pin = report["generated_for"]
    lines = [
        "# Dakota element audit",
        "",
        f"- Dakota revision: `{pin['dakota_revision']}`",
        f"- SBOM: {pin['sbom']}",
        f"- Image: `{pin['image']}`",
        f"- Factory revision audited: `{pin['factory_base']}`",
        "",
        "Every element of Dakota's BuildStream graph, mapped to the RPM source "
        "package that provides it on Utah. An element that owns no file in the "
        "published image is build-only and needs no RPM. Reviewer decisions "
        "live in `overrides` in `config/dakota.json`; see "
        "`docs/skills/dakota-parity.md`.",
        "",
        "## Dispositions",
        "",
        "| disposition | elements | in the image |",
        "| --- | ---: | ---: |",
    ]
    for disposition in DISPOSITIONS:
        lines.append(f"| {disposition} | {report['counts'][disposition]} | "
                     f"{report['counts_in_image'][disposition]} |")
    lines.append(f"| **total** | {sum(report['counts'].values())} | "
                 f"{sum(report['counts_in_image'].values())} |")
    lines.append("")

    for disposition, title in ((FEDORA_IMPORTABLE, "Import queue: Fedora-importable, no factory recipe"),
                               (NEW_SPEC, "Import queue: new spec from the .bst")):
        queue = report["import_queue"][disposition]
        lines += [f"## {title}", "", f"{len(queue)} source packages, user-visible first.", ""]
        lines += ["| group | package | Dakota version | elements |", "| --- | --- | --- | --- |"]
        for row in queue:
            elements = ", ".join(f"`{e}`" for e in row["elements"])
            versions = ", ".join(row["dakota_versions"]) or "—"
            lines.append(f"| {row['visibility']} | {row['name']} | {versions} | {elements} |")
        lines.append("")

    drift = report["drift"]
    lines += ["## Version drift of factory recipes", ""]
    totals: dict[str, int] = {}
    for item in drift:
        totals[item["classification"]] = totals.get(item["classification"], 0) + 1
    for classification in sorted(totals):
        lines.append(f"- **{classification}**: {totals[classification]}")
    lines += ["", "| package | factory | Dakota | classification | element |",
              "| --- | --- | --- | --- | --- |"]
    for item in drift:
        if item["classification"] == ALIGNED:
            continue
        lines.append(f"| {item['rpm']} | {item['factory_version'] or '—'} | "
                     f"{item['dakota_version'] or '—'} | {item['classification']} | "
                     f"`{item['element']}` |")
    lines.append("")

    structural = [e for e in report["elements"] if e["disposition"] == STRUCTURAL]
    lines += ["## Structural (Utah parity issues)", "", "| issue | element | reason |",
              "| --- | --- | --- |"]
    for entry in sorted(structural, key=lambda e: (e.get("issue", ""), e["element"])):
        lines.append(f"| {entry.get('issue', '')} | `{entry['element']}` | {entry['reason']} |")
    lines.append("")

    config = [e for e in report["elements"]
              if e["disposition"] in (DAKOTA_CONFIG, GNOMEOS_CONFIG) or e.get("config_subpackages")]
    lines += ["## Config packages", "", "| subpackage | element |", "| --- | --- |"]
    for entry in sorted(config, key=lambda e: (e["rpm"] or "", e["element"])):
        subs = [entry["subpackage"]] if entry.get("subpackage") else []
        subs += entry.get("config_subpackages") or []
        lines.append(f"| {', '.join(subs)} | `{entry['element']}` |")
    lines.append("")
    for package, gap in report["config_gaps"].items():
        if not gap["recipe"]:
            lines.append(f"- `{package}`: no recipe in `packages/` yet; "
                         f"{len(gap['missing'])} subpackages expected.")
        elif gap["missing"]:
            lines.append(f"- `{package}`: recipe lacks " + ", ".join(f"`{s}`" for s in gap["missing"]))
        else:
            lines.append(f"- `{package}`: every expected subpackage is in the recipe.")
    lines.append("")

    policy = [e for e in report["elements"]
              if e["disposition"] == NOT_APPLICABLE and e["reason"] != BUILD_ONLY_REASON]
    lines += ["## Not applicable (in the image)", "", "| element | reason |", "| --- | --- |"]
    for entry in policy:
        lines.append(f"| `{entry['element']}` | {entry['reason']} |")
    lines.append("")

    lines += ["## Stale mappings", ""]
    if report["stale_mappings"] or report["unmapped_elements"]:
        lines.append("`config/dakota.json` records a different disposition than the "
                     "tool computes now (a recipe landed, an override changed). "
                     "Run `python3 tools/audit_dakota.py --refresh`.")
        lines.append("")
        for item in report["stale_mappings"]:
            lines.append(f"- `{item['element']}`: recorded {item['recorded']}, now {item['now']}")
        for element in report["unmapped_elements"]:
            lines.append(f"- `{element}`: not in the mapping")
    else:
        lines.append("- none")
    lines += ["", "_This is a non-gating evidence report; `tools/audit_dakota.py` "
              "regenerates it offline from the committed snapshot and mapping._"]
    return "\n".join(lines)


# --- Online refresh -----------------------------------------------------------

RAWHIDE_REPO = "https://dl.fedoraproject.org/pub/fedora/linux/development/rawhide/Everything/x86_64/os/"
HUMMINGBIRD_REPO = "https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/"
DIST_GIT = "https://src.fedoraproject.org/rpms/{name}"
_REPO_NS = "{http://linux.duke.edu/metadata/repo}"
_COMMON_NS = "{http://linux.duke.edu/metadata/common}"
_RPM_NS = "{http://linux.duke.edu/metadata/rpm}"


def _fetch(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-audit-dakota"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _decompress(data: bytes, href: str) -> bytes:
    if href.endswith(".gz"):
        return gzip.decompress(data)
    if href.endswith(".zst"):
        try:
            from compression import zstd  # Python 3.14+
            return zstd.decompress(data)
        except ImportError:
            return subprocess.run(["zstd", "-dc"], input=data, capture_output=True,
                                  check=True).stdout
    if href.endswith(".xml"):
        return data
    raise ValueError(f"unsupported primary.xml compression: {href}")


def repo_packages(base_url: str) -> dict[str, str]:
    """Binary name -> source package name from a repository's primary.xml."""
    repomd = ElementTree.fromstring(_fetch(base_url + "repodata/repomd.xml"))
    location = repomd.find(f"{_REPO_NS}data[@type='primary']/{_REPO_NS}location")
    if location is None:
        raise ValueError(f"{base_url}: repomd.xml names no primary metadata")
    href = location.get("href")
    return parse_primary(_decompress(_fetch(base_url + href), href))


def primary_packages(saved: Path | None, base_url: str) -> dict[str, str]:
    """A saved primary.xml(.gz|.zst) when given, otherwise the live repository."""
    if saved is not None:
        return parse_primary(_decompress(saved.read_bytes(), saved.name))
    return repo_packages(base_url)


def parse_primary(primary: bytes) -> dict[str, str]:
    """Binary name -> source package name; streamed, Rawhide's is ~200 MB."""
    binaries: dict[str, str] = {}
    for _, node in ElementTree.iterparse(io.BytesIO(primary)):
        if node.tag != f"{_COMMON_NS}package":
            continue
        name = node.findtext(f"{_COMMON_NS}name")
        sourcerpm = node.findtext(f"{_COMMON_NS}format/{_RPM_NS}sourcerpm") or ""
        source = sourcerpm.rsplit("-", 2)[0] if sourcerpm.count("-") >= 2 else None
        if name and source:
            binaries.setdefault(name, source)
        node.clear()
    return binaries


def dist_git_exists(name: str) -> bool | None:
    """HEAD on the dist-git repository; None when it cannot be told."""
    request = urllib.request.Request(DIST_GIT.format(name=name), method="HEAD",
                                     headers={"User-Agent": "utah-packages-audit-dakota"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status == 200
    except urllib.error.HTTPError as error:
        return False if error.code == 404 else None
    except (urllib.error.URLError, TimeoutError):
        return None


def refresh_mapping(pin: dict, records: list[ElementRecord], fedora: FedoraIndex,
                    hummingbird_sources: set[str], factory: set[str],
                    head=dist_git_exists) -> dict:
    """Re-resolve every element against Fedora and Hummingbird: the new ``elements``."""
    aliases = pin.get("aliases", {})
    resolutions: dict[str, dict] = {}
    for record in records:
        candidates = candidate_names(record, aliases)
        rpm, evidence = fedora.resolve(candidates)
        resolutions[record.element] = {"rpm": rpm, "evidence": evidence, "candidates": candidates}

    names = {r["rpm"] for r in resolutions.values() if r["rpm"]}
    # A dist-git repository that is not in Rawhide is a retired package: worth
    # saying, because "Fedora has it" would otherwise be guessed from memory.
    retired_probe = {r["candidates"][0] for r in resolutions.values()
                     if not r["rpm"] and r["candidates"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        heads = dict(zip(sorted(names | retired_probe),
                         pool.map(head, sorted(names | retired_probe))))

    elements = {}
    for record in records:
        res = resolutions[record.element]
        rpm = res["rpm"]
        evidence = res["evidence"]
        if rpm and heads.get(rpm) is False:
            evidence = f"{evidence}; dist-git HEAD 404"
        elif rpm and heads.get(rpm):
            evidence = f"{evidence}; dist-git rpms/{rpm} exists"
        elif rpm:
            evidence = f"{evidence}; dist-git unreachable"
        elif res["candidates"] and heads.get(res["candidates"][0]):
            evidence = f"dist-git rpms/{res['candidates'][0]} exists but is retired from Rawhide"
        resolution = {
            "rpm": rpm,
            "evidence": evidence,
            "hummingbird": bool(rpm and rpm in hummingbird_sources),
        }
        decision = classify_element(record, pin, resolution, factory)
        entry = {
            "disposition": decision["disposition"],
            "rpm": decision.get("rpm"),
            "fedora": rpm,
            "hummingbird": resolution["hummingbird"],
            "evidence": evidence,
        }
        if decision.get("subpackage"):
            entry["subpackage"] = decision["subpackage"]
        elements[record.element] = entry
    return dict(sorted(elements.items()))


# --- CLI ----------------------------------------------------------------------

def contract_problems(pin: dict, records: list[ElementRecord]) -> list[str]:
    """What makes the committed snapshot and pin unusable for the audit.

    The mapping names exactly the snapshot's elements, and every reviewer
    decision names a snapshot element, so a typo or a re-pin without
    ``--refresh`` cannot silently drop an element. A stale disposition is not
    a problem: importing a recipe makes one, and the report lists it.
    """
    snapshot = {record.element for record in records}
    problems = []
    elements = set(pin.get("elements") or {})
    problems += [f"{e}: in the snapshot, not in the mapping (run --refresh)"
                 for e in sorted(snapshot - elements)]
    problems += [f"{e}: in the mapping, not in the snapshot (run --refresh)"
                 for e in sorted(elements - snapshot)]
    for section in ("overrides", "aliases", "config_subpackages"):
        problems += [f"{section} {e}: not an element of the snapshot"
                     for e in sorted(set(pin.get(section) or {}) - snapshot)]
    return problems


def parse_args(argv):
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Map Dakota's BuildStream elements to RPMs.")
    parser.add_argument("--pin", type=Path, default=repo / "config" / "dakota.json")
    parser.add_argument("--snapshot", type=Path, default=repo / "config" / "dakota-elements.tsv")
    parser.add_argument("--sources", type=Path, default=repo / "config" / "upstream-sources.json")
    parser.add_argument("--packages-dir", type=Path, default=repo / "packages")
    parser.add_argument("--json-out", type=Path, default=repo / "reports" / "audit-dakota.json")
    parser.add_argument("--markdown-out", type=Path, default=repo / "reports" / "audit-dakota.md")
    parser.add_argument("--check", action="store_true",
                        help="build the report in memory, write nothing, and exit 1 when "
                             "the snapshot and config/dakota.json break the audit contract")
    parser.add_argument("--refresh", action="store_true",
                        help="re-resolve Fedora and Hummingbird availability online and "
                             "rewrite the mapping in --pin")
    parser.add_argument("--import-sbom", type=Path,
                        help="rewrite --snapshot from Dakota's SPDX SBOM (needs --image-layout)")
    parser.add_argument("--image-layout", type=Path,
                        help="OCI layout holding the pinned image (skopeo copy docker://... oci:DIR)")
    parser.add_argument("--gbm-pin", type=Path, default=repo / "config" / "gnome-build-meta.json",
                        help="the gnome-build-meta audit's mapping, reused for GNOME renames")
    parser.add_argument("--rawhide-primary", type=Path,
                        help="with --refresh: a saved Rawhide primary.xml instead of downloading")
    parser.add_argument("--hummingbird-primary", type=Path,
                        help="with --refresh: a saved Hummingbird primary.xml instead of downloading")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.check and (args.refresh or args.import_sbom):
        print("error: --check writes nothing; it cannot --refresh or --import-sbom",
              file=sys.stderr)
        return 2
    pin = load_pin(args.pin)

    if args.import_sbom:
        if not args.image_layout:
            print("error: --import-sbom needs --image-layout", file=sys.stderr)
            return 2
        sbom = json.loads(args.import_sbom.read_text())
        namespace = sbom.get("documentNamespace", "")
        if not namespace.endswith("/" + pin["source"]["revision"]):
            print(f"error: SBOM {namespace} is not Dakota {pin['source']['revision']}",
                  file=sys.stderr)
            return 2
        ownership = scan_image_layout(args.image_layout, pin["source"]["image_digest"])
        write_snapshot(args.snapshot, build_snapshot(sbom, ownership))
        print(f"snapshot written: {args.snapshot}")

    records = read_snapshot(args.snapshot)
    factory_locks = load_source_locks(args.sources)
    resolved = with_gbm_aliases(pin, json.loads(args.gbm_pin.read_text()))

    if args.refresh:
        fedora_binaries = primary_packages(args.rawhide_primary, RAWHIDE_REPO)
        fedora = FedoraIndex(set(fedora_binaries.values()), fedora_binaries)
        hummingbird = set(primary_packages(args.hummingbird_primary, HUMMINGBIRD_REPO).values())
        pin["elements"] = refresh_mapping(resolved, records, fedora, hummingbird, set(factory_locks))
        args.pin.write_text(json.dumps(pin, indent=2) + "\n")
        resolved["elements"] = pin["elements"]
        print(f"mapping written: {args.pin}")

    report = build_report(resolved, records, factory_locks, args.packages_dir)
    if args.check:
        render_markdown(report)
        problems = contract_problems(pin, records)
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        print(json.dumps(report["counts"]))
        print(f"{len(report['stale_mappings'])} stale mapping(s); "
              f"{len(report['import_queue'][FEDORA_IMPORTABLE])} Fedora-importable and "
              f"{len(report['import_queue'][NEW_SPEC])} new-spec RPMs in the import queue")
        return 1 if problems else 0
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown_out.write_text(render_markdown(report) + "\n")
    print(json.dumps(report["counts"]))
    print(f"audit written: {args.json_out}")
    print(f"audit written: {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
