#!/usr/bin/env python3
"""Deterministic audit of GNOME RPM recipes against GNOME/gnome-build-meta.

This factory inherits Fedora RPM recipes, but GNOME release integration is
defined upstream in `GNOME/gnome-build-meta` (BuildStream). Without a repeatable
comparison, drift is invisible: source version/commit can leave the intended
GNOME release line, GNOME carries secondary sources / wraps / patches the RPM
recipe handles differently, Meson feature choices diverge, dependency edges
differ, and the package set can drift from GNOME core/sdk membership.

This tool makes that delta explicit and classified. It is an AUDIT, not a
mechanism to replace Fedora packaging: Fedora integration, Hummingbird
constraints, RPM subpackages and downstream policy can all justify a
difference. The goal is a maintained, evidence-backed delta, not a one-time
spreadsheet.

Inputs
------
- ``config/gnome-build-meta.json``   pinned GNOME release (tag + commit) and the
  explicit source-name mapping (RPM name -> gbm element path).
- ``config/upstream-sources.json``   the factory source locks (identity /
  version / filename / sha512), consistent with the factory contract.
- ``packages/<name>/<name>.spec``    the Fedora recipe (version, Source0,
  patches, feature options, dependency edges).
- ``--gbm-dir``                      a checkout of gnome-build-meta at the pinned
  commit. If it is a git repository the tool verifies the working tree resolves
  to the pinned commit (unless ``--no-verify``) so a mutable checkout cannot be
  silently compared against.

Outputs
-------
- machine-readable JSON (``--json-out``) and a human reviewable Markdown
  summary (``--markdown-out``). Every difference is classified, and the raw
  evidence (source identity, release line, patches, feature options,
  dependency categories, component membership) is preserved for review.

Only the Python standard library plus PyYAML is required, so it runs on a
GitHub-hosted runner and in the digest-pinned factory images without installing
extra runtime tooling.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
import subprocess

import yaml

# --- Classification vocabulary -------------------------------------------------
ALIGNED = "aligned"
INTENTIONAL_FEDORA = "intentional_fedora"
INTENTIONAL_HUMMINGBIRD = "intentional_hummingbird"
ACTIONABLE = "actionable_drift"
NEEDS_REVIEW = "needs_review"
UNMAPPED = "unmapped"

# BuildStream merge/overlay operators that we record but do not fully resolve.
_BST_EXTENSIONS = ("(>)", "(<)", "(=)", "(^)", "(/)", "(~)")

_VERSION_LINE_RE = re.compile(r"(\d+)\.(\d+)")


def numeric_components(version: str) -> list[str]:
    """Leading numeric components of a version string (``51.beta`` -> ``["51"]``)."""
    if not version:
        return []
    return re.findall(r"\d+", version)


def release_line(version: str) -> str | None:
    """The release line of a GNOME-style version.

    GNOME switched to consecutive single-number cycles at 40 (``51.0``,
    ``51.beta`` -> ``51``); libraries keep ``major.minor`` lines (``4.23``,
    ``1.10``, ``2.62``, ``3.12``...). A version whose major is >= 40 is treated
    as a GNOME-cycle number; anything smaller as a library line.
    """
    digits = numeric_components(version)
    if not digits:
        return None
    if int(digits[0]) >= 40:
        return digits[0]
    if len(digits) >= 2:
        return f"{digits[0]}.{digits[1]}"
    return digits[0]


def same_release_line(version_a: str, version_b: str) -> bool:
    """True when two versions share a release line (see ``release_line``)."""
    a = release_line(version_a)
    b = release_line(version_b)
    return bool(a) and a == b


@dataclass
class Element:
    """A resolved gbm BuildStream element, normalized for comparison."""

    path: str
    kind: str | None
    sources: list[dict]
    variables: dict
    build_depends: list[str]
    runtime_depends: list[str]
    depends: list[str]
    includes: list[str]
    extensions: list[str]
    primary_source: dict | None


class Loader:
    """Resolve BuildStream ``(@)`` includes into a normalized element.

    BuildStream ``(@)`` handles includes deliberately; a regex-only scan that
    ignores included variables or dependency composition is explicitly not a
    sufficient audit. This loader:

    - splices ``- (@): path`` list items (splicing list-form includes into the
      list; dict-form includes such as ``include/gcc-for-recc.yml`` are recorded
      but not treated as dependency entries, because they carry compiler
      configuration rather than element references);
    - opens mapping-level ``(@): path|list`` includes and deep-merges them;
    - records every resolved include and every unresolved BuildStream merge
      operator (``(>)``, ``(<)``, ...) so the report states exactly what was and
      was not expanded.
    """

    def __init__(self, root: Path):
        self.root = root                       # repository root of the checkout
        self.seen: set[str] = set()            # include files resolved (repo-relative)

    def _resolve_path(self, raw: str) -> Path:
        # BuildStream include paths are repo-relative: both `include/x.yml` and
        # `elements/core/foo.inc` resolve against the repository root, never
        # against the including element's directory.
        target = Path(raw)
        if target.is_absolute():
            return self.root / str(target).lstrip("/")
        return self.root / target

    def load(self, relpath: str) -> dict:
        """Load and fully resolve one element file (repo-relative path)."""
        path = self.root / relpath
        node = self._file(path)
        return node

    def _file(self, path: Path) -> dict:
        node = yaml.safe_load(path.read_text())
        if not isinstance(node, dict):
            return node if node is not None else {}
        return self._node(node, path)

    def _merge(self, base: dict, over: dict) -> dict:
        """Deep merge; ``(>)`` keys in ``over`` win (BuildStream override)."""
        out = dict(base)
        for key, value in over.items():
            if key.startswith("(>)"):
                real_key = key[3:].lstrip()
                if not real_key:
                    # Bare ``(>)`` is a list-append operator with no key; treat
                    # its value as an extension of the list it modifies elsewhere.
                    # Without a key it cannot be merged here, so record that it
                    # was seen and continue — the per-element ``extensions`` set
                    # already captures it.
                    continue
                if isinstance(value, list) and isinstance(out.get(real_key), list):
                    out[real_key] = out[real_key] + value
                elif isinstance(value, dict) and isinstance(out.get(real_key), dict):
                    out[real_key] = self._merge(out[real_key], value)
                else:
                    out[real_key] = value
                continue
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = self._merge(out[key], value)
            else:
                out[key] = value
        return out

    def _open_include(self, raw: str) -> dict:
        p = self._resolve_path(raw)
        self._note_include(p)
        return self._file(p)

    def _note_include(self, path: Path) -> None:
        try:
            self.seen.add(str(path.relative_to(self.root)))
        except ValueError:
            self.seen.add(str(path))

    def _node(self, node: dict, path: Path) -> dict:
        node = dict(node)

        # Mapping-level `(@):` open include: value is a path or list of paths.
        inc = node.pop("(@)", None)
        if inc is not None:
            items = inc if isinstance(inc, list) else [inc]
            merged: dict = {}
            for raw in items:
                part = self._open_include(raw)
                merged = self._merge(merged, part)
            node = self._merge(merged, node)

        for key, value in list(node.items()):
            if key in _BST_EXTENSIONS:
                continue
            if isinstance(value, dict):
                node[key] = self._node(value, path)
            elif isinstance(value, list):
                node[key] = self._list(value, path)
        return node

    def _list(self, items: list, path: Path) -> list:
        out: list = []
        for item in items:
            if isinstance(item, dict) and "(@)" in item:
                raw = item["(@)"]
                p = self._resolve_path(raw)
                self._note_include(p)
                loaded = self._file(p)
                if isinstance(loaded, list):
                    out.extend(loaded)
                # dict-form include (e.g. gcc-for-recc.yml) resolved elsewhere;
                # not a dependency entry.
                continue
            if isinstance(item, dict):
                out.append(self._node(item, path))
            else:
                out.append(item)
        return out


def _expand_alias(url: str, aliases: dict) -> str:
    """Expand a ``gnome_downloads:module/...`` source url using aliases.yml."""
    if ":" not in url:
        return url
    alias, _, rest = url.partition(":")
    base = aliases.get(alias)
    if base is None:
        return url
    return base.rstrip("/") + "/" + rest.lstrip("/")


def _aliases(loader: Loader) -> dict:
    p = loader.root / "include" / "aliases.yml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text()) or {}
    return data.get("aliases", {}) if isinstance(data, dict) else {}


def resolve_element(loader: Loader, aliases: dict, relpath: str) -> Element:
    # Includes are reported per element, so the resolved-include set starts
    # empty for every element even when one Loader resolves many of them.
    loader.seen = set()
    node = loader.load(relpath)
    bs = node.get("bst") or {}
    depends = node.get("depends", []) or []
    build_depends = node.get("build-depends", []) or []
    runtime_depends = node.get("runtime-depends", []) or []

    def refs(items: list) -> list[str]:
        return [i for i in items if isinstance(i, str) and i.endswith(".bst")]

    sources = node.get("sources", []) or []
    if not isinstance(sources, list):
        sources = []
    variables = node.get("variables", {}) or {}
    if not isinstance(variables, dict):
        variables = {}

    # collect extension operators that reached this element node
    extensions = sorted(_collect_extensions(node))

    primary = None
    for source in sources:
        if source.get("kind") != "patch" and source.get("url"):
            primary = {
                "kind": source.get("kind"),
                "url": _expand_alias(str(source.get("url")), aliases),
                "ref": source.get("ref"),
                "directory": source.get("directory") or source.get("subdir"),
                "track": source.get("track"),
            }
            break

    return Element(
        path=relpath,
        kind=node.get("kind"),
        sources=sources,
        variables=variables,
        build_depends=refs(build_depends),
        runtime_depends=refs(runtime_depends),
        depends=refs(depends),
        includes=sorted(loader.seen),
        extensions=extensions,
        primary_source=primary,
    )


def _collect_extensions(node: dict) -> set[str]:
    found: set[str] = set()
    for key, value in node.items():
        if key in _BST_EXTENSIONS:
            found.add(key)
        if isinstance(value, dict):
            found |= _collect_extensions(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found |= _collect_extensions(item)
    return found


def element_patch_sources(element: Element, aliases: dict) -> list[str]:
    """Patch sources (``kind: patch``) carried by the element.

    BuildStream's patch plugin names the file in ``path:``, relative to the
    project directory (``patches/mozjs/python-3.14.patch`` in
    ``elements/sdk/mozjs.bst`` at the pinned commit). ``local`` and ``url`` are
    accepted as a fallback for a source that spells the reference differently.
    """
    patches = []
    for source in element.sources:
        if source.get("kind") == "patch":
            ref = (
                source.get("path")
                or source.get("local")
                or source.get("url")
                or ""
            )
            patches.append(_expand_alias(str(ref), aliases))
    return patches


_MESON_INVOCATION = re.compile(
    r"^\s*(?:%(?:meson|cmake)(?![_A-Za-z0-9])"
    r"|(?:meson\s+(?:setup|configure)|cmake)\b)"
)
_RPM_CONDITIONAL = re.compile(r"^%(?:if|ifarch|ifnarch|ifos|else|elif|endif)\b")
# -D immediately preceded by a word character or hyphen is not an option flag:
# that is how `Unicode-DFS-2016` produced the option `FS-2016`.
_MESON_OPTION = re.compile(r"(?<![\w-])-D([A-Za-z0-9][\w.+:-]*)(?:=(\S*))?")
_MACRO_REF = re.compile(r"%\{?(\w+)\}?")
_MACRO_DEFINE = re.compile(
    r"^\s*%(?:define|global)\s+(\w+)\s+(.*)$", flags=re.MULTILINE
)


def _unbalanced_brace(token: str) -> str:
    """Drop the closing brace an RPM macro wrapper leaves on an option.

    ``%meson %{?rhel:-Davif=disabled}`` puts the macro's own ``}`` inside the
    option value, which would be recorded as ``disabled}``.
    """
    while token.endswith("}") and token.count("}") > token.count("{"):
        token = token[:-1]
    return token


def _expanded_flag_macros(block: str, text: str) -> list[str]:
    """Bodies of the spec macros a configure invocation expands.

    evolution-data-server builds its CMake flags in ``%define ldap_flags
    -DWITH_OPENLDAP=ON`` and passes ``%ldap_flags`` to ``%cmake``, so every
    macro the invocation block references is looked up and its body scanned
    too. A macro defined in both branches of an ``%if`` contributes both,
    consistent with how the conditional lines inside a block are handled.
    """
    bodies: dict[str, list[str]] = {}
    for name, body in _MACRO_DEFINE.findall(text):
        if "-D" in body:
            bodies.setdefault(name, []).append(body)
    out: list[str] = []
    for name in dict.fromkeys(_MACRO_REF.findall(block)):
        out.extend(bodies.get(name, []))
    return out


def meson_options(text: str) -> dict[str, str]:
    """Extract ``-Dname=value`` options from a spec's configure invocations.

    ``%meson`` and ``%cmake`` are both read: a handful of GNOME components
    (evolution-data-server, for one) are CMake-built and their ``-D`` flags are
    the same feature evidence this axis exists to record.

    Fedora GNOME specs spread options across ``%meson \\`` continuation
    lines, so each invocation is followed to the end of its continuation block
    -- and only that block is read, because a ``-D`` elsewhere in the file is
    not a feature flag: ``gtk4``'s ``CFLAGS='... -DG_DISABLE_CAST_CHECKS'`` are
    C preprocessor defines and ``librsvg2``'s licence string
    ``Unicode-DFS-2016`` is not an option at all.

    RPM conditionals (``%if``/``%endif``) inside a continuation block are kept:
    the options they guard are real options, and the audit records what the
    recipe can pass, not what one build configuration resolved to.
    """
    out: dict[str, str] = {}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not _MESON_INVOCATION.match(lines[index]):
            index += 1
            continue
        block: list[str] = []
        cursor = index
        while cursor < len(lines):
            line = lines[cursor]
            block.append(line)
            if _RPM_CONDITIONAL.match(line.strip()):
                cursor += 1
                continue
            if line.rstrip().endswith("\\"):
                cursor += 1
                continue
            break
        block.extend(_expanded_flag_macros("\n".join(block), text))
        for match in _MESON_OPTION.finditer("\n".join(block)):
            name = _unbalanced_brace(match.group(1).strip("-").strip())
            value = (match.group(2) or "").strip().strip("'\"").rstrip("\\")
            value = _unbalanced_brace(value)
            if name and name not in out:
                out[name] = value
        index = cursor + 1
    return out


_SPEC_REQUIRES = re.compile(
    r"^(BuildRequires|Requires(?:\([^)]*\))?)\s*:\s*(.+)$",
    flags=re.MULTILINE | re.IGNORECASE,
)


def spec_dependencies(text: str) -> dict[str, list[str]]:
    """Build-time and runtime dependency edges declared by a Fedora spec.

    This is the spec half of the dependency axis; the gbm half is
    ``build-depends``/``runtime-depends``/``depends`` on the element.

    Version constraints are dropped and names are returned sorted and unique:
    these are edges for a human to compare against gbm element names, not a
    resolvable dependency set. Names that are still an unexpanded RPM macro are
    kept verbatim -- the audit reports what the recipe declares, and no macro
    is expanded anywhere else in this tool either.
    """
    build: set[str] = set()
    runtime: set[str] = set()
    for match in _SPEC_REQUIRES.finditer(text):
        field = match.group(1).lower()
        bucket = build if field.startswith("buildrequires") else runtime
        for clause in match.group(2).split(","):
            name = clause.strip().split()[0] if clause.strip() else ""
            name = name.strip()
            if not name or name in (">=", "<=", "=", ">", "<"):
                continue
            bucket.add(name)
    return {"build_requires": sorted(build), "requires": sorted(runtime)}


def spec_patches(text: str) -> list[str]:
    """Patch references in a Fedora spec (``Patch:`` / ``PatchN:`` lines)."""
    patches = []
    for m in re.finditer(r"^Patch\d*\s*:\s*(\S+)", text, flags=re.MULTILINE):
        patches.append(m.group(1))
    return patches


def spec_sources(text: str) -> list[str]:
    """Source tarball references (``Source``/``Source0:``... lines)."""
    sources = []
    for m in re.finditer(r"^Source\w*\s*:\s*(\S+)", text, flags=re.MULTILINE):
        sources.append(m.group(1).strip())
    return sources


def _gbm_module(primary: dict) -> str | None:
    """The GNOME module name a primary source belongs to.

    download.gnome.org URLs are ``/sources/<module>/<line>/<file>``; git URLs
    carry the repo name in the final path segment.
    """
    url = primary.get("url") or ""
    m = re.search(r"/sources/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.search(r"/([^/]+?)\.git/?$", url)
    if m:
        return m.group(1)
    return None


def _rpm_base_name(name: str) -> str:
    """RPM name with a trailing subpackage/version digit(s) stripped.

    Fedora names ``gnome-desktop3``, ``gdk-pixbuf2``, ``gtk3``, ``librsvg2``
    for GNOME modules named ``gnome-desktop``, ``gdk-pixbuf``, ``gtk``,
    ``librsvg``.
    """
    return re.sub(r"\d+$", "", name).lower()


_GIT_REF_VERSION_RE = re.compile(
    r"^v?(\d[\w.~]*?)(?:-\d+-g[0-9a-f]{4,})?$"
)


def _gbm_version(primary: dict) -> str | None:
    """The version a gbm primary source encodes.

    ``tar`` sources carry it in the url (``mutter-51.0.tar.xz``). ``git_repo``
    sources have no version in the url, but their ``ref`` is a ``git describe``
    string (``1.18.4-0-g0ee7c10a0`` for cairo, ``4.23.0`` for a plain tag), so
    the leading tag component is read from ``ref`` -- otherwise the release-line
    comparison would be skipped for every git-tracked element.
    """
    m = re.search(r"-(\d[\w.~-]*)\.tar(?:\.(?:gz|bz2|xz|zst))?$", primary.get("url", "") or "")
    if m:
        return m.group(1)
    for key in ("ref", "track"):
        raw = primary.get(key)
        if not isinstance(raw, str):
            continue
        raw = raw.strip()
        if re.fullmatch(r"[0-9a-f]{7,}", raw):
            # A bare commit sha (or a tar checksum), not a version.
            continue
        m = _GIT_REF_VERSION_RE.match(raw)
        if m and numeric_components(m.group(1)):
            return m.group(1)
    return None


def classify(gbm: Element | None, factory: dict | None,
             factory_version: str | None) -> tuple[str, str]:
    """Classify the difference for one mapped source.

    Returns ``(classification, reason)``. The classifier is deliberately
    conservative: it marks *aligned* only when there is no material drift
    evidence, and otherwise returns ``needs_review`` with concrete notes so a
    human can re-classify as intentional Fedora/Hummingbird policy.
    """
    if gbm is None:
        return UNMAPPED, "no gnome-build-meta element in the pinned tree"
    if factory is None:
        return UNMAPPED, "factory source not present in config/upstream-sources.json"
    if not gbm.sources:
        if gbm.kind in ("filter", "stack", "compose"):
            return ALIGNED, (
                f"gbm element is a {gbm.kind} aggregating shared sources; "
                "membership aligned (no independent source identity to compare)"
            )
        return NEEDS_REVIEW, "element present but has no analysable sources"

    primary = gbm.primary_source
    if primary is None:
        return NEEDS_REVIEW, "gnome-build-meta element has no analysable primary source"

    gbm_version = _gbm_version(primary)
    gbm_module = _gbm_module(primary)
    src_name = factory.get("name", "")

    drift: list[str] = []
    info: list[str] = []

    # Source identity: same GNOME module on both sides.
    if gbm_module and src_name:
        if _rpm_base_name(src_name) != gbm_module.lower():
            drift.append(
                f"factory module '{src_name}' (base '{_rpm_base_name(src_name)}') "
                f"vs gbm module '{gbm_module}'"
            )

    # Release line comparison (factory is usually the rawhide/dev line).
    if gbm_version and factory_version:
        if same_release_line(gbm_version, factory_version):
            if gbm_version != factory_version:
                info.append(
                    f"release line {release_line(gbm_version)} matches; factory "
                    f"{factory_version} vs gbm {gbm_version} (factory tracks the "
                    f"dev/rawhide bump within the same line)"
                )
        else:
            drift.append(
                f"release line {release_line(factory_version)} (factory) vs "
                f"{release_line(gbm_version)} (gbm)"
            )
    elif factory_version and not gbm_version:
        # Silence here would read as "release line aligned" for a comparison
        # that never happened (a git_repo pinned to a bare commit, for one).
        info.append(
            f"release line NOT compared: gbm source (kind '{primary.get('kind')}', "
            f"ref '{primary.get('ref')}') encodes no version; factory is "
            f"{factory_version}"
        )

    gbm_patch_list = element_patch_sources(gbm, {})
    spec_patch_list = factory.get("patches", [])
    if spec_patch_list and not gbm_patch_list:
        drift.append(f"factory carries {len(spec_patch_list)} local patch(es); gbm none")
    if gbm_patch_list and not spec_patch_list:
        drift.append("gbm carries upstream patches; factory spec has none")
    if gbm_patch_list and spec_patch_list:
        # Both sides patch. gbm names a project-relative path and the spec
        # names a Patch: filename, so only the basenames are comparable -- and
        # two different patch sets are the drift a reviewer needs to see.
        gbm_names = {name.rsplit("/", 1)[-1] for name in gbm_patch_list}
        spec_names = {name.rsplit("/", 1)[-1] for name in spec_patch_list}
        if gbm_names != spec_names:
            drift.append(
                "both sides carry patches and they differ: gbm "
                f"{sorted(gbm_names)} vs factory {sorted(spec_names)}"
            )

    if drift:
        return NEEDS_REVIEW, "; ".join(drift)
    return ALIGNED, "; ".join(info) if info else "source identity and release line aligned"


def build_report(pin: dict, loader: Loader, aliases: dict,
                 factory_sources: dict, packages_dir: Path) -> dict:
    mapping = pin["mapping"]
    alias = pin.get("factory_alias", {}) or {}
    entries = []
    for rpm, elem_path in mapping.items():
        # Subpackages (gvfs-client, gvfs-daemon) and rename aliases (tinysparql)
        # resolve to a real factory source registry name.
        factory_name = alias.get(rpm, rpm)
        pkg = factory_sources.get(factory_name)
        notes: list[str] = []
        if factory_name != rpm and pkg is None:
            notes.append(f"factory alias '{rpm}' -> '{factory_name}' has no registry entry")

        elem_path_full = pin["element_path"]["root"] + "/" + elem_path
        gbm = None
        if (loader.root / elem_path_full).exists():
            try:
                gbm = resolve_element(loader, aliases, elem_path_full)
            except Exception as exc:  # noqa: BLE001 - report, never abort the audit
                notes.append(f"gbm element failed to parse: {exc}")
        else:
            notes.append(f"mapped element '{elem_path}' not found in gnome-build-meta")

        factory_version = None
        factory_spec = {}
        if pkg:
            factory_version = pkg.get("version")
            spec_name = pkg.get("spec", f"{factory_name}.spec")
            spec_path = packages_dir / factory_name / spec_name
            if spec_path.exists():
                spec_text = spec_path.read_text()
                spec_deps = spec_dependencies(spec_text)
                factory_spec = {
                    "sources": spec_sources(spec_text),
                    "patches": spec_patches(spec_text),
                    "meson_options": meson_options(spec_text),
                    "build_requires": spec_deps["build_requires"],
                    "requires": spec_deps["requires"],
                    "version": factory_version,
                }
            else:
                factory_spec = {
                    "version": factory_version,
                    "meson_options": {},
                    "build_requires": [],
                    "requires": [],
                }
                notes.append(f"no spec file found at {spec_path}")

        classify_factory = dict(pkg) if pkg else None
        if classify_factory is not None:
            classify_factory["patches"] = factory_spec.get("patches", [])
        classification, reason = classify(gbm, classify_factory, factory_version)

        entry = {
            "rpm_name": rpm,
            "gbm_element": elem_path,
            "gbm_present": gbm is not None,
            "classification": classification,
            "reason": reason,
            "factory": {
                "name": pkg.get("name") if pkg else None,
                "version": factory_version,
                "filename": pkg.get("filename") if pkg else None,
                "patches": factory_spec.get("patches", []),
                "features": factory_spec.get("meson_options", {}),
                "source_urls": factory_spec.get("sources", []),
                "build_requires": factory_spec.get("build_requires", []),
                "requires": factory_spec.get("requires", []),
            },
            "gnome_build_meta": {
                "kind": gbm.kind if gbm else None,
                "primary_source": gbm.primary_source if gbm else None,
                "secondary_sources": _secondary_sources(gbm, aliases),
                "patches": element_patch_sources(gbm, aliases) if gbm else [],
                "features": gbm.variables if gbm else {},
                "build_depends": gbm.build_depends if gbm else [],
                "runtime_depends": gbm.runtime_depends if gbm else [],
                "depends": gbm.depends if gbm else [],
                "includes": gbm.includes if gbm else [],
                "extensions": gbm.extensions if gbm else [],
            },
        }
        entries.append(entry)

    return {
        "schema": 1,
        "generated_for": {
            "release_tag": pin["source"]["release_tag"],
            "release_commit": pin["source"]["release_commit"],
            "factory_base": _factory_rev(),
        },
        "unmapped_factory_sources": _unmapped_observed(pin),
        "unaccounted_gnome_sources": _unaccounted_gnome_sources(
            pin, factory_sources, loader, aliases
        ),
        "packages": entries,
    }


def _secondary_sources(gbm: Element | None, aliases: dict) -> list[dict]:
    """Element sources other than the primary (secondary sources, wraps).

    Patch sources are excluded -- they carry no ``url`` to compare against the
    primary and are reported by ``element_patch_sources`` under ``patches``.
    """
    if gbm is None:
        return []
    primary = gbm.primary_source
    if primary is None:
        return []
    primary_expanded = primary.get("url")
    out = []
    for source in gbm.sources:
        if source.get("kind") == "patch":
            continue
        if _expand_alias(str(source.get("url", "")), aliases) == primary_expanded:
            continue
        out.append(source)
    return out


def _unmapped_observed(pin: dict) -> list[dict]:
    """GNOME-owned factory sources the mapping deliberately does not track."""
    return [dict(u) for u in pin.get("unmapped", [])]


_GNOME_HOSTS = ("download.gnome.org", "ftp.gnome.org", "gitlab.gnome.org")


def _host(url: str) -> str:
    m = re.match(r"[a-zA-Z][\w+.-]*://([^/]+)", url or "")
    return m.group(1).lower() if m else ""


def _is_gnome_url(url: str) -> bool:
    host = _host(url)
    return any(host == h or host.endswith("." + h) for h in _GNOME_HOSTS)


def _gnome_aliases(aliases: dict) -> list[str]:
    """Alias names from ``include/aliases.yml`` that expand to a GNOME host."""
    return sorted(name for name, base in aliases.items()
                  if isinstance(base, str) and _is_gnome_url(base))


def _gbm_gnome_modules(loader: Loader, pin: dict, aliases: dict) -> dict[str, str]:
    """Element stems in the pinned tree whose sources come from a GNOME host.

    A factory source can be GNOME-owned while its recorded url points at the
    Fedora lookaside mirror (``gcr``, ``libsecret``, ``json-glib``...), so url
    inspection alone cannot decide ownership. The pinned gbm tree is the
    authority: an element whose own source url is on ``*.gnome.org`` (directly
    or through a ``gnome_downloads:``/``gnome:`` alias) names a GNOME-owned
    module. ``.inc`` fragments are scanned too, because several elements
    (``sdk/gobject-introspection.bst``) keep their ``sources:`` there.
    Returns ``{module stem: element path}``.
    """
    root = loader.root / pin["element_path"]["root"]
    if not root.is_dir():
        return {}
    alias_prefixes = tuple(f"{name}:" for name in _gnome_aliases(aliases))
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in (".bst", ".inc") or not path.is_file():
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        urls = re.findall(r"^\s*url:\s*(\S+)", text, flags=re.MULTILINE)
        if not any(_is_gnome_url(u) or u.startswith(alias_prefixes) for u in urls):
            continue
        stem = path.stem.lower()
        rel = str(path.relative_to(loader.root))
        # Prefer the element file over the .inc fragment it includes.
        if stem not in out or (rel.endswith(".bst") and out[stem].endswith(".inc")):
            out[stem] = rel
    return out


def _unaccounted_gnome_sources(pin: dict, factory_sources: dict,
                               loader: Loader, aliases: dict) -> list[dict]:
    """GNOME-owned factory sources that are neither mapped nor listed unmapped.

    Issue #201 requires every GNOME-owned factory source to be either mapped to
    a gbm element or explicitly recorded as unmapped with a reason. Echoing the
    pin's ``unmapped`` list cannot show a source that was simply forgotten, so
    ownership is derived from evidence -- a gnome.org url in the factory lock,
    or a matching element in the pinned gbm tree that pulls from gnome.org --
    and anything unaccounted for is reported here for a human to resolve.
    """
    mapping = pin.get("mapping", {}) or {}
    alias = pin.get("factory_alias", {}) or {}
    accounted = set(mapping)
    accounted |= {alias.get(rpm, rpm) for rpm in mapping}
    accounted |= {u.get("name") for u in pin.get("unmapped", []) or []}

    gbm_modules = _gbm_gnome_modules(loader, pin, aliases)
    out: list[dict] = []
    for name, pkg in sorted(factory_sources.items()):
        if name in accounted:
            continue
        url = pkg.get("url") or ""
        if _is_gnome_url(url):
            evidence = f"factory source url is on {_host(url)}"
        else:
            module = name.lower() if name.lower() in gbm_modules else _rpm_base_name(name)
            element = gbm_modules.get(module)
            if not element:
                continue
            evidence = (
                f"gnome-build-meta builds module '{module}' from gnome.org "
                f"({element})"
            )
        out.append({
            "name": name,
            "version": pkg.get("version"),
            "url": url,
            "evidence": evidence,
        })
    return out


def _factory_rev(root: Path | None = None) -> str:
    """HEAD of the factory checkout this tool ships in.

    Resolved with ``git -C`` against the repository that contains this file,
    the same way ``parse_args`` resolves every default path, so the report's
    provenance does not depend on the caller's working directory.
    """
    root = root or Path(__file__).resolve().parent.parent
    try:
        rev = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return rev or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _load_factory_sources(path: Path) -> dict:
    data = json.loads(path.read_text())
    packages = data.get("packages", [])
    return {p["name"]: p for p in packages}


def load_pin(path: Path) -> dict:
    pin = json.loads(path.read_text())
    if pin.get("schema") != 1:
        raise ValueError(f"unsupported gnome-build-meta pin schema {pin.get('schema')}")
    if not pin.get("mapping"):
        raise ValueError("gnome-build-meta pin has an empty mapping")
    return pin


def _verify_checkout(loader: Loader, commit: str) -> str:
    """Return the verified HEAD of the gbm checkout, or exit non-zero."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(loader.root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        raise SystemExit(
            f"gnome-build-meta checkout at {loader.root} is not a git repository. "
            f"Pass --no-verify to audit an exported snapshot, or clone the pinned commit "
            f"{commit}."
        )
    head = proc.stdout.strip()
    if head != commit and not head.startswith(commit[:12]):
        raise SystemExit(
            f"gnome-build-meta checkout is at {head}, not the pinned commit "
            f"{commit}. Pass --no-verify to audit an exported snapshot instead."
        )
    return head


def render_markdown(report: dict) -> str:
    pin = report["generated_for"]
    lines = [
        f"# GNOME recipes vs gnome-build-meta audit",
        "",
        f"- GNOME release: `{pin['release_tag']}` @ `{pin['release_commit']}`",
        f"- factory revision audited: `{pin['factory_base']}`",
        "",
        "Every difference is classified, not treated as an automatic defect. "
        "`needs_review` entries carry evidence for a human to re-classify as "
        "intentional Fedora/RPM integration, intentional Hummingbird/downstream "
        "policy, or actionable drift.",
        "",
    ]
    totals: dict[str, int] = {}
    for entry in report["packages"]:
        totals[entry["classification"]] = totals.get(entry["classification"], 0) + 1
    lines.append("## Summary")
    lines.append("")
    for classification in sorted(totals):
        lines.append(f"- **{classification}**: {totals[classification]}")
    lines.append("")

    unmapped = report.get("unmapped_factory_sources", [])
    lines.append("## GNOME-owned factory sources not mapped")
    lines.append("")
    if unmapped:
        for item in unmapped:
            lines.append(f"- `{item.get('name')}`: {item.get('reason', '')}")
    else:
        lines.append("- none")
    lines.append("")

    unaccounted = report.get("unaccounted_gnome_sources", [])
    lines.append("## Unaccounted GNOME-owned factory sources")
    lines.append("")
    if unaccounted:
        lines.append("These are neither mapped nor listed as unmapped with a reason; "
                     "each needs a mapping or an explicit `unmapped` entry in "
                     "`config/gnome-build-meta.json`.")
        lines.append("")
        for item in unaccounted:
            lines.append(
                f"- `{item.get('name')}` {item.get('version')} — {item.get('evidence')}"
            )
    else:
        lines.append("- none: every GNOME-owned factory source is mapped or "
                     "explicitly unmapped with a reason.")
    lines.append("")

    for entry in report["packages"]:
        lines.append(f"## {entry['rpm_name']} → `{entry['gbm_element']}`")
        lines.append("")
        lines.append(f"- Classification: **{entry['classification']}**")
        if entry["reason"]:
            lines.append(f"- Reason: {entry['reason']}")
        lines.append("")
        if entry["factory"].get("version"):
            lines.append(f"- Factory version: `{entry['factory']['version']}`")
        gbm_src = entry["gnome_build_meta"].get("primary_source")
        if gbm_src and gbm_src.get("url"):
            lines.append(f"- GBM primary source: `{gbm_src['url']}`")
        if entry["factory"].get("patches"):
            lines.append(f"- Factory patches: {', '.join(entry['factory']['patches'])}")
        if entry["gnome_build_meta"].get("patches"):
            lines.append("- GBM patches: " + ", ".join(entry["gnome_build_meta"]["patches"]))
        ffeat = entry["factory"].get("features") or {}
        gfeat = entry["gnome_build_meta"].get("features") or {}
        if ffeat or gfeat:
            lines.append("- Feature options: see JSON report for the full diff.")
        dep_count = (
            len(entry["gnome_build_meta"].get("depends", []))
            + len(entry["gnome_build_meta"].get("build_depends", []))
            + len(entry["gnome_build_meta"].get("runtime_depends", []))
        )
        lines.append(f"- GBM dependency edges: {dep_count}")
        lines.append("")
    lines.append("")
    lines.append("_This is a non-gating evidence report. It is safe to regenerate "
                 "for a newer GNOME release without rewriting the tool._")
    return "\n".join(lines)


def parse_args(argv):
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Audit GNOME RPM recipes against gnome-build-meta."
    )
    parser.add_argument("--gbm-dir", type=Path, required=True,
                        help="path to a gnome-build-meta checkout at the pinned commit")
    parser.add_argument("--pin", type=Path, default=repo / "config" / "gnome-build-meta.json")
    parser.add_argument("--sources", type=Path, default=repo / "config" / "upstream-sources.json")
    parser.add_argument("--packages-dir", type=Path, default=repo / "packages")
    parser.add_argument("--json-out", type=Path, default=repo / "reports" / "audit-gnome-build-meta.json")
    parser.add_argument("--markdown-out", type=Path, default=repo / "reports" / "audit-gnome-build-meta.md")
    parser.add_argument("--no-verify", action="store_true",
                        help="do not require --gbm-dir to be a git checkout at the pinned commit")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    pin = load_pin(args.pin)
    if not args.gbm_dir.exists():
        print(f"error: gnome-build-meta checkout not found: {args.gbm_dir}", file=sys.stderr)
        return 2

    loader = Loader(args.gbm_dir)
    if not args.no_verify:
        _verify_checkout(loader, pin["source"]["release_commit"])
    aliases = _aliases(loader)

    factory_sources = _load_factory_sources(args.sources)
    if not args.packages_dir.exists():
        print(f"warning: packages dir not found: {args.packages_dir}", file=sys.stderr)

    # Fail-closed: a missing elements root or zero resolved elements means the
    # checkout is unusable — do not write a plausible-looking all-unmapped report.
    elements_root = loader.root / pin["element_path"]["root"]
    if not elements_root.is_dir():
        print(f"error: gnome-build-meta elements root not found: {elements_root}", file=sys.stderr)
        return 2

    report = build_report(pin, loader, aliases, factory_sources, args.packages_dir)

    if not any(e["gbm_present"] for e in report["packages"]):
        print("error: no mapped gnome-build-meta elements resolved — checkout is unusable", file=sys.stderr)
        return 2

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    args.markdown_out.write_text(render_markdown(report) + "\n")

    print(f"audit written: {args.json_out}")
    print(f"audit written: {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
