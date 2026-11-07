#!/usr/bin/env python3
"""Check every dependency floor the factory's GNOME modules declare (D9).

Owner decision D9: every minimum version a GNOME module the factory builds
declares for a dependency must be satisfied by the factory's locked version of
that dependency. A recipe's BuildRequires is not where that floor lives:
nautilus 51.1 failed meson configure with `gtk4 ... found 4.23.4 but need:
'>= 4.24.0'` while its spec still asked for `pkgconfig(gtk4) >= 4.22.0`
(#565). The floor is in the module's own build files, so this reads them from
the locked upstream tarball itself.

1. GNOME modules are the locks whose primary is download.gnome.org, plus the
   packages config/gnome-build-meta.json maps (through factory_alias). Each
   locked tarball is downloaded into a temporary directory, verified against
   the lock's SHA-512, read for its build files and deleted again.
2. Floors: meson `dependency('x', version: ...)`, with the version evaluated
   through the string variables, `+`, `.format()` and f-strings meson code
   uses (`glib_req = '>= 2.86'`, `'>= @0@'.format(glib_min)`), following
   `subdir()` like meson does; `PKG_CHECK_MODULES`/`PKG_CHECK_EXISTS` in
   configure.ac; `pkg_check_modules` in CMakeLists.txt. Only minimums
   (`>=`, `>`, `==`) are floors.
3. A pkg-config name maps to the factory recipe whose published binaries
   provide `pkgconfig(name)` (the factory image's primary.xml, as
   tools/build_graph.py reads it) or whose spec ships `name.pc`
   (tools/extract_buildrequires.sh --pc-provides). That recipe's lock is the
   factory's version. A name no recipe provides is checked against
   Hummingbird's primary.xml instead, which outranks Fedora in the build root
   (tools/mock_config.py). Fedora, the build root's last resort, is not read:
   a name neither provides is reported as unmapped, not failed.
4. Report: one row per (module, dependency, floor). Exit 1 when a floor is
   unmet (by a factory lock or by Hummingbird), or a module could not be read.
5. `--apply` moves each unmet factory dependency with
   `tools/upstream_bump.py --package <dep> --cycle <series> --apply`, to the
   newest stable release of the lowest series that satisfies the floor: the
   series the floor itself names, which GNOME's numbering cannot otherwise
   tell apart from a development series above it (see cycle_final in
   tools/upstream_bump.py). Each move is dry-run first and refused, with the
   reason, unless the release upstream_bump.py proposes meets the floor. A
   moved GNOME module is read again, since its own floors moved with it.

A floor the factory cannot meet is reported with the specific reason: the
dependency is not built by the factory (Hummingbird's version is too old), no
stable release satisfies it, or upstream_bump.py would not move it there.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import functools
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.package_index import fetch_image, primary_from_layer  # noqa: E402
from tools.mock_config import FEDORA_RELEASEVER  # noqa: E402
from tools.package_inventory import GNOME_FEED, source_locks  # noqa: E402
from tools.rebuild_matrix import fetch_primary, hummingbird_baseurl  # noqa: E402
from tools.rebuild_plan import COMMON_NS, RPM_NS, provides_by_source  # noqa: E402

GNOME_SOURCES = "https://download.gnome.org/sources/"
GBM_PIN = "config/gnome-build-meta.json"
FACTORY_IMAGE = "projectbluefin/utah-packages:latest"
UPSTREAM_BUMP = ROOT / "tools" / "upstream_bump.py"
PC_PROVIDES = ROOT / "tools" / "extract_buildrequires.sh"
HEADERS = {"User-Agent": "utah-packages-floors/1"}
# A moved module can raise floors of its own; stop following that chain here.
MAX_ROUNDS = 5


# --- versions ---------------------------------------------------------------


def _segments(version: str, index: int) -> tuple[str, int]:
    """The next alphanumeric run of `version` from `index`, rpmvercmp style."""
    start = index
    if version[index].isdigit():
        while index < len(version) and version[index].isdigit():
            index += 1
    else:
        while index < len(version) and version[index].isascii() and version[index].isalpha():
            index += 1
    return version[start:index], index


def vercmp(left: str, right: str) -> int:
    """rpmvercmp: -1, 0 or 1. pkg-config compares versions the same way.

    A tilde sorts before anything, so a lock at 51~beta is below a 51 floor.
    """
    if left == right:
        return 0
    i = j = 0

    def separator(text: str, at: int) -> bool:
        if at >= len(text):
            return False
        char = text[at]
        return not (char.isascii() and char.isalnum()) and char not in "~^"

    while i < len(left) or j < len(right):
        while separator(left, i):
            i += 1
        while separator(right, j):
            j += 1
        if (i < len(left) and left[i] == "~") or (j < len(right) and right[j] == "~"):
            if i >= len(left) or left[i] != "~":
                return 1
            if j >= len(right) or right[j] != "~":
                return -1
            i, j = i + 1, j + 1
            continue
        if (i < len(left) and left[i] == "^") or (j < len(right) and right[j] == "^"):
            if i >= len(left):
                return -1
            if j >= len(right):
                return 1
            if left[i] != "^":
                return 1
            if right[j] != "^":
                return -1
            i, j = i + 1, j + 1
            continue
        if i >= len(left) or j >= len(right):
            break
        numeric = left[i].isdigit()
        mine, i = _segments(left, i)
        theirs, j = (
            _segments(right, j) if right[j].isdigit() == numeric else ("", j)
        )
        if not theirs:
            return 1 if numeric else -1
        if numeric:
            mine, theirs = mine.lstrip("0"), theirs.lstrip("0")
            if len(mine) != len(theirs):
                return 1 if len(mine) > len(theirs) else -1
        if mine != theirs:
            return 1 if mine > theirs else -1
    if i >= len(left) and j >= len(right):
        return 0
    return 1 if i < len(left) else -1


# A prerelease marker and its separator. Build files and tarballs spell a
# prerelease 2.2.alpha.7, the lock spells it 2.2~beta: compared as written,
# the tilde sorts the beta below the alpha.
PRERELEASE_SEPARATOR = re.compile(r"[.~-](alpha|beta|rc|dev)(?=[.~-]|\d|$)", re.IGNORECASE)


def rpm_spelling(version: str) -> str:
    """A version with its prerelease marker behind a tilde, as RPM orders it."""
    return PRERELEASE_SEPARATOR.sub(lambda m: "~" + m.group(1), version, count=1)


def satisfies(have: str, op: str, version: str) -> bool:
    """Whether `have` meets the floor `op version`."""
    order = vercmp(rpm_spelling(have), rpm_spelling(version))
    return order > 0 if op == ">" else order >= 0


# Sort key for max()/min() over versions.
VERSION_KEY = functools.cmp_to_key(vercmp)


def file_sha512(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# The GNOME feed's prereleases: a marker (51.beta, 1.10.beta.1, 1.25.95-dev)
# or, in the library scheme, a micro of 90 or more (gjs 1.89.90 before 1.90.0).
# The same rule as is_gnome_prerelease in tools/upstream_bump.py; the dry run
# in plan_move() catches any drift between the two.
PRERELEASE = re.compile(r"(?:^|[.~-])(alpha|beta|rc|dev)(?=[.~-]|\d|$)", re.IGNORECASE)


def is_prerelease(version: str) -> bool:
    if PRERELEASE.search(version):
        return True
    parts = version.split(".")
    return (
        len(parts) == 3
        and all(part.isdigit() for part in parts)
        and int(parts[0]) < 40
        and int(parts[2]) >= 90
    )


# --- floors -----------------------------------------------------------------


@dataclass(frozen=True)
class Floor:
    """One minimum version a build file declares; op None when unevaluable."""

    dependency: str
    op: str | None
    version: str | None
    expression: str
    path: str

    @property
    def required(self) -> str:
        return f"{self.op} {self.version}" if self.op else f"? ({self.expression})"


CONSTRAINT = re.compile(r"^\s*(>=|<=|==|!=|=|>|<)\s*(\S+)\s*$")
FLOOR_OPS = {">=": ">=", ">": ">", "==": ">=", "=": ">="}


def constraint_floors(name: str, constraints: list, expression: str, path: str) -> list[Floor]:
    """The floors in a list of `op version` strings; ceilings are dropped."""
    floors = []
    for constraint in constraints:
        match = CONSTRAINT.match(constraint) if isinstance(constraint, str) else None
        if match is None:
            if isinstance(constraint, str) and not constraint.strip():
                continue
            floors.append(Floor(name, None, None, expression, path))
            continue
        op, version = match.groups()
        if op in FLOOR_OPS:
            floors.append(Floor(name, FLOOR_OPS[op], version, expression, path))
    return floors


class Unsupported(Exception):
    """A meson expression outside the subset evaluate() understands."""


MESON_TOKEN = re.compile(
    r"""
      (?P<skip>[ \t\r\f]+|\\\n|\#[^\n]*)
    | (?P<nl>\n)
    | (?P<string>f?'''.*?'''|f?'(?:\\.|[^'\\\n])*')
    | (?P<ident>[A-Za-z_]\w*)
    | (?P<number>\d+)
    | (?P<op>==|!=|<=|>=|\+=|[-+*/%<>=()\[\]{},:.?])
    | (?P<other>.)
    """,
    re.DOTALL | re.VERBOSE,
)
Token = tuple[str, str]


def meson_statements(text: str) -> list[list[Token]]:
    """Tokens per logical line: a newline inside brackets continues it."""
    statements: list[list[Token]] = [[]]
    depth = 0
    for match in MESON_TOKEN.finditer(text):
        kind, value = match.lastgroup, match.group()
        if kind == "skip":
            continue
        if kind == "nl":
            if depth == 0 and statements[-1]:
                statements.append([])
            continue
        if kind == "op" and value in ("(", "[", "{"):
            depth += 1
        elif kind == "op" and value in (")", "]", "}"):
            depth = max(0, depth - 1)
        statements[-1].append((kind, value))
    return [statement for statement in statements if statement]


ESCAPE = re.compile(r"\\(.)")


class Expression:
    """Evaluates the string subset of meson a version argument is built from."""

    def __init__(self, tokens: list[Token], env: dict):
        self.tokens, self.env, self.pos = tokens, env, 0

    def peek(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("end", "")

    def take(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def expect(self, value: str) -> None:
        if self.take() != ("op", value):
            raise Unsupported(f"expected {value!r}")

    def evaluate(self):
        value = self.sum()
        if self.pos != len(self.tokens):
            raise Unsupported(f"unexpected {self.peek()[1]!r}")
        return value

    def sum(self):
        value = self.postfix()
        while self.peek() == ("op", "+"):
            self.take()
            right = self.postfix()
            if type(value) is not type(right) or not isinstance(value, (str, list)):
                raise Unsupported("+ of mixed types")
            value = value + right
        return value

    def postfix(self):
        value = self.primary()
        while True:
            if self.peek() == ("op", "."):
                self.take()
                method = self.take()
                self.expect("(")
                arguments = self.items(")")
                if method != ("ident", "format") or not isinstance(value, str):
                    raise Unsupported(f"method {method[1]}")
                try:
                    value = re.sub(r"@(\d+)@", lambda m: str(arguments[int(m.group(1))]), value)
                except IndexError as error:
                    raise Unsupported("format index") from error
            elif self.peek() == ("op", "["):
                self.take()
                index = self.sum()
                self.expect("]")
                if not isinstance(value, list) or not isinstance(index, int):
                    raise Unsupported("subscript")
                try:
                    value = value[index]
                except IndexError as error:
                    raise Unsupported("subscript") from error
            else:
                return value

    def items(self, close: str) -> list:
        values = []
        while self.peek() != ("op", close):
            values.append(self.sum())
            if self.peek() == ("op", ","):
                self.take()
            elif self.peek() != ("op", close):
                raise Unsupported(f"expected {close!r}")
        self.take()
        return values

    def primary(self):
        kind, value = self.take()
        if kind == "string":
            formatted = value.startswith("f")
            body = value[1:] if formatted else value
            text = body[3:-3] if body.startswith("'''") else ESCAPE.sub(
                lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body[1:-1]
            )
            if formatted:
                text = re.sub(r"@(\w+)@", lambda m: str(self.variable(m.group(1))), text)
            return text
        if kind == "number":
            return int(value)
        if kind == "ident":
            if value in ("true", "false"):
                return value == "true"
            return self.variable(value)
        if (kind, value) == ("op", "["):
            return self.items("]")
        if (kind, value) == ("op", "("):
            inner = self.sum()
            self.expect(")")
            return inner
        raise Unsupported(f"unexpected {value!r}")

    def variable(self, name: str):
        if name not in self.env:
            raise Unsupported(f"unknown variable {name}")
        return self.env[name]


def _closing(tokens: list[Token], start: int) -> int:
    """The index of the bracket closing the one at `start`."""
    depth = 0
    for index in range(start, len(tokens)):
        kind, value = tokens[index]
        if kind == "op" and value in ("(", "[", "{"):
            depth += 1
        elif kind == "op" and value in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                return index
    return len(tokens)


def _arguments(tokens: list[Token]) -> list[list[Token]]:
    """A call's argument tokens, split at top-level commas."""
    arguments: list[list[Token]] = [[]]
    depth = 0
    for kind, value in tokens:
        if kind == "op" and value in ("(", "[", "{"):
            depth += 1
        elif kind == "op" and value in (")", "]", "}"):
            depth -= 1
        if (kind, value) == ("op", ",") and depth == 0:
            arguments.append([])
            continue
        arguments[-1].append((kind, value))
    return [argument for argument in arguments if argument]


def _calls(statement: list[Token], function: str):
    """(arguments) of every bare `function(...)` call in a statement."""
    for index, token in enumerate(statement[:-1]):
        if token != ("ident", function) or statement[index + 1] != ("op", "("):
            continue
        if index and statement[index - 1] == ("op", "."):
            continue
        end = _closing(statement, index + 1)
        yield _arguments(statement[index + 2:end])


def _positional(arguments: list[list[Token]], env: dict) -> list:
    values = []
    for argument in arguments:
        if len(argument) >= 2 and argument[0][0] == "ident" and argument[1] == ("op", ":"):
            continue
        try:
            values.append(Expression(argument, env).evaluate())
        except Unsupported:
            values.append(None)
    return values


def _keyword(arguments: list[list[Token]], name: str) -> list[Token] | None:
    for argument in arguments:
        if len(argument) >= 2 and argument[0] == ("ident", name) and argument[1] == ("op", ":"):
            return argument[2:]
    return None


def meson_floors(files: dict[str, str]) -> list[Floor]:
    """Floors of a meson project, walked from meson.build through subdir()."""
    floors: list[Floor] = []
    env: dict = {}
    visited: set[str] = set()

    def walk(path: str) -> None:
        if path in visited or path not in files:
            return
        visited.add(path)
        for statement in meson_statements(files[path]):
            for arguments in _calls(statement, "dependency"):
                names = [value for value in _positional(arguments, env) if isinstance(value, str)]
                version = _keyword(arguments, "version")
                if not names or version is None:
                    continue
                expression = " ".join(value for _, value in version)
                try:
                    value = Expression(version, env).evaluate()
                except Unsupported:
                    floors.append(Floor(names[0], None, None, expression, path))
                    continue
                constraints = value if isinstance(value, list) else [value]
                floors.extend(constraint_floors(names[0], constraints, expression, path))
            if len(statement) > 2 and statement[0][0] == "ident" and statement[1][0] == "op":
                name, op = statement[0][1], statement[1][1]
                if op in ("=", "+="):
                    try:
                        value = Expression(statement[2:], env).evaluate()
                        if op == "+=":
                            value = env[name] + value
                        env[name] = value
                    except (Unsupported, KeyError, TypeError):
                        env.pop(name, None)
            for arguments in _calls(statement, "subdir"):
                values = _positional(arguments, env)
                if values and isinstance(values[0], str):
                    parent = PurePosixPath(path).parent
                    walk(str(parent / values[0] / "meson.build"))

    walk("meson.build")
    return floors


def requirement_floors(text: str, expression: str, path: str) -> list[Floor]:
    """Floors in a pkg-config module list: `gtk+-3.0 >= 3.22 glib-2.0>=2.40`."""
    words = re.sub(r"(>=|<=|!=|==|=|>|<)", r" \1 ", text).split()
    floors = []
    index = 0
    while index < len(words):
        name = words[index]
        index += 1
        if index + 1 < len(words) and CONSTRAINT.match(f"{words[index]} {words[index + 1]}"):
            op, version = words[index], words[index + 1]
            index += 2
            if "$" in version or "@" in version:
                floors.append(Floor(name, None, None, expression, path))
            elif op in FLOOR_OPS:
                floors.append(Floor(name, FLOOR_OPS[op], version, expression, path))
    return floors


def m4_arguments(text: str, start: int) -> list[str]:
    """The arguments of an m4 call whose '(' is at `start`, quotes stripped."""
    arguments, current, depth, quote = [], [], 0, 0
    for char in text[start + 1:]:
        if char == "[":
            quote += 1
            if quote == 1:
                continue
        elif char == "]":
            quote -= 1
            if quote == 0:
                continue
        elif not quote and char == "(":
            depth += 1
        elif not quote and char == ")":
            if depth == 0:
                break
            depth -= 1
        elif not quote and depth == 0 and char == ",":
            arguments.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    arguments.append("".join(current).strip())
    return arguments


SHELL_ASSIGNMENT = re.compile(r"""^\s*([A-Za-z_]\w*)=(["']?)([^"'\s;]*)\2\s*$""", re.MULTILINE)
M4_DEFINE = re.compile(r"m4_define\(\s*\[?(\w+)\]?\s*,\s*\[?([^\])]*)\]?\s*\)")
PKG_CHECK = re.compile(r"PKG_CHECK_(MODULES|EXISTS)\s*\(")


def autotools_floors(path: str, text: str) -> list[Floor]:
    """Floors in configure.ac, with shell and m4_define variables expanded."""
    shell = {name: value for name, _, value in SHELL_ASSIGNMENT.findall(text)}
    macros = dict(M4_DEFINE.findall(text))
    floors = []
    for match in PKG_CHECK.finditer(text):
        arguments = m4_arguments(text, match.end() - 1)
        index = 1 if match.group(1) == "MODULES" else 0
        if len(arguments) <= index:
            continue
        modules = arguments[index]
        expanded = re.sub(
            r"\$\{?(\w+)\}?", lambda m: shell.get(m.group(1), m.group(0)), modules
        )
        expanded = re.sub(r"\b\w+\b", lambda m: macros.get(m.group(0), m.group(0)), expanded)
        floors.extend(requirement_floors(expanded, " ".join(modules.split()), path))
    return floors


CMAKE_SET = re.compile(r"\bset\s*\(\s*(\w+)\s+\"?([^\s\")]+)\"?\s*\)", re.IGNORECASE)
CMAKE_PKG = re.compile(r"\bpkg_(?:check_modules|search_module)\s*\(([^)]*)\)", re.IGNORECASE)
CMAKE_KEYWORDS = {
    "REQUIRED", "QUIET", "IMPORTED_TARGET", "GLOBAL", "NO_CMAKE_PATH",
    "NO_CMAKE_ENVIRONMENT_PATH",
}


def cmake_floors(files: dict[str, str]) -> list[Floor]:
    """Floors in pkg_check_modules() across a CMake project."""
    ordered = sorted(files, key=lambda path: (path.count("/"), path))
    variables: dict[str, str] = {}
    for path in ordered:
        variables.update(CMAKE_SET.findall(files[path]))
    floors = []
    for path in ordered:
        for match in CMAKE_PKG.finditer(files[path]):
            words = match.group(1).replace('"', " ").split()[1:]
            modules = " ".join(word for word in words if word not in CMAKE_KEYWORDS)
            expanded = re.sub(r"\$\{(\w+)\}", lambda m: variables.get(m.group(1), m.group(0)), modules)
            floors.extend(requirement_floors(expanded, modules, path))
    return floors


def build_files(member: str) -> bool:
    name = PurePosixPath(member).name
    return name in ("meson.build", "configure.ac", "configure.in", "CMakeLists.txt")


def tarball_floors(tarball: Path) -> list[Floor]:
    """Every floor the build files in one source tarball declare."""
    files: dict[str, str] = {}
    with tarfile.open(tarball, mode="r|*") as archive:
        for member in archive:
            if not member.isfile() or "/" not in member.name:
                continue
            relative = member.name.split("/", 1)[1]
            if not build_files(relative):
                continue
            handle = archive.extractfile(member)
            if handle is not None:
                files[relative] = handle.read().decode("utf-8", errors="replace")
    if "meson.build" in files:
        return meson_floors({p: t for p, t in files.items() if p.endswith("meson.build")})
    for configure in ("configure.ac", "configure.in"):
        if configure in files:
            return autotools_floors(configure, files[configure])
    cmake = {p: t for p, t in files.items() if p.endswith("CMakeLists.txt")}
    return cmake_floors(cmake) if cmake else []


# --- sources ----------------------------------------------------------------


class FetchError(Exception):
    pass


def download(entry: dict, dest: Path, opener=urllib.request.urlopen) -> Path:
    """The locked tarball at `dest`, streamed and verified against its SHA-512.

    A transport failure moves on to the next fallback URL; a digest mismatch
    stops, because another mirror is not a second source of truth.
    """
    if dest.is_file() and file_sha512(dest) == entry["sha512"]:
        return dest
    part = dest.with_name(dest.name + ".part")
    errors = []
    for url in [entry["url"], *entry.get("fallback_urls", [])]:
        digest = hashlib.sha512()
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with opener(request, timeout=300) as response, part.open("wb") as handle:
                for block in iter(lambda: response.read(1 << 20), b""):
                    digest.update(block)
                    handle.write(block)
        except (urllib.error.URLError, OSError) as error:
            errors.append(f"{url}: {error}")
            continue
        if digest.hexdigest() != entry["sha512"]:
            part.unlink(missing_ok=True)
            raise FetchError(f"{url}: SHA-512 does not match the lock")
        part.rename(dest)
        return dest
    part.unlink(missing_ok=True)
    raise FetchError("; ".join(errors) or "no URL")


def gnome_modules(root: Path, locks: dict[str, dict]) -> list[str]:
    """Locks on a download.gnome.org primary, plus gnome-build-meta's mapping."""
    mapped: set[str] = set()
    pin = root / GBM_PIN
    if pin.is_file():
        config = json.loads(pin.read_text())
        alias = config.get("factory_alias") or {}
        mapped = {alias.get(name, name) for name in config.get("mapping") or {}}
    return sorted(
        name for name, entry in locks.items()
        if entry.get("url", "").startswith(GNOME_SOURCES) or name in mapped
    )


def module_floors(
    names: list[str],
    locks: dict[str, dict],
    scratch: Path,
    keep: bool,
    jobs: int = 8,
    opener=urllib.request.urlopen,
) -> tuple[dict[str, list[Floor]], dict[str, str]]:
    """name -> floors, and name -> why it could not be read."""

    def read(name: str) -> list[Floor]:
        entry = locks[name]
        if not entry.get("url") or not entry.get("sha512") or not entry.get("filename"):
            raise FetchError("the lock names no upstream tarball")
        tarball = download(entry, scratch / entry["filename"], opener=opener)
        try:
            return tarball_floors(tarball)
        except (tarfile.TarError, OSError, EOFError) as error:
            raise FetchError(f"{entry['filename']}: {error}") from error
        finally:
            if not keep:
                tarball.unlink(missing_ok=True)

    floors, errors = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(read, name): name for name in names}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                floors[name] = future.result()
            except FetchError as error:
                errors[name] = str(error)
    return floors, errors


# --- providers --------------------------------------------------------------


MACRO_DEFINITION = re.compile(r"(?m)^%(?:global|define)\s+(\w+)\s+(\S.*?)\s*$")
TAG = re.compile(r"(?mi)^(Name|Version):\s*(\S+)\s*$")
PROVIDES_PKGCONFIG = re.compile(r"(?m)^Provides:.*?$")


def spec_pkgconfig(text: str) -> set[str]:
    """pkg-config names a spec ships: explicit Provides plus %files .pc paths."""
    names = set()
    for line in PROVIDES_PKGCONFIG.findall(text):
        names.update(re.findall(r"pkgconfig\(([^)\s]+)\)", line))
    if ".pc" not in text:
        return {name for name in names if "%" not in name}
    macros = {key.lower(): value for key, value in TAG.findall(text)}
    macros.update(MACRO_DEFINITION.findall(text))
    expanded = text
    for _ in range(4):
        expanded = re.sub(
            r"%\{\??(\w+)\}|%(\w+)",
            lambda m: macros.get(m.group(1) or m.group(2), m.group(0)),
            expanded,
        )
    result = subprocess.run(
        ["bash", str(PC_PROVIDES), "--pc-provides"],
        input=expanded, capture_output=True, text=True, check=False,
    )
    names.update(re.findall(r"^pkgconfig\((.+)\)$", result.stdout, re.MULTILINE))
    return {name for name in names if "%" not in name}


def factory_providers(root: Path, published: dict[str, set[str]]) -> dict[str, set[str]]:
    """pkg-config name -> the factory recipes that ship it."""
    providers: dict[str, set[str]] = {}
    for source, capabilities in published.items():
        for capability in capabilities:
            if capability.startswith("pkgconfig(") and capability.endswith(")"):
                providers.setdefault(capability[10:-1], set()).add(source)
    for spec in sorted((root / "packages").glob("*/*.spec")):
        for name in spec_pkgconfig(spec.read_text(errors="replace")):
            providers.setdefault(name, set()).add(spec.parent.name)
    return providers


def pkgconfig_versions(primary: bytes) -> dict[str, str]:
    """pkg-config name -> the highest version a repository's Provides carry."""
    versions: dict[str, str] = {}
    provides = f"{{{RPM_NS}}}provides"
    entry = f"{{{RPM_NS}}}entry"
    package = f"{{{COMMON_NS}}}package"
    inside = False
    for event, element in ElementTree.iterparse(io.BytesIO(primary), events=("start", "end")):
        if element.tag == provides:
            inside = event == "start"
        elif event == "end" and inside and element.tag == entry:
            name, version = element.get("name", ""), element.get("ver")
            if name.startswith("pkgconfig(") and name.endswith(")") and version:
                key = name[10:-1]
                if key not in versions or vercmp(version, versions[key]) > 0:
                    versions[key] = version
        elif event == "end" and element.tag == package:
            element.clear()
    return versions


# --- evaluation -------------------------------------------------------------


@dataclass
class Row:
    module: str
    floor: Floor
    status: str  # ok, unmet, external, unmapped, unlocked, unparsed
    provider: str = ""
    have: str = ""
    reason: str = ""

    @property
    def failing(self) -> bool:
        return self.status in ("unmet", "external")


def evaluate(
    module: str,
    floor: Floor,
    locks: dict[str, dict],
    providers: dict[str, set[str]],
    external: dict[str, str] | None,
) -> Row | None:
    """One floor against the factory's locks; None when the module provides it."""
    found = providers.get(floor.dependency, set())
    if module in found:
        return None
    if floor.op is None:
        return Row(module, floor, "unparsed",
                   reason=f"{floor.path}: version `{floor.expression}` is not a literal "
                   "this tool can evaluate")
    locked = sorted(name for name in found if name in locks)
    if locked:
        name = max(locked, key=lambda n: VERSION_KEY(locks[n]["version"]))
        have = locks[name]["version"]
        if satisfies(have, floor.op, floor.version):
            return Row(module, floor, "ok", name, have)
        return Row(module, floor, "unmet", name, have)
    if found:
        return Row(module, floor, "unlocked",
                   reason=f"factory recipe {', '.join(sorted(found))} ships "
                   f"pkgconfig({floor.dependency}) but has no source lock")
    if external is None:
        return Row(module, floor, "unmapped",
                   reason=f"no factory recipe provides pkgconfig({floor.dependency}), "
                   "and Hummingbird's repository could not be read")
    if floor.dependency in external:
        have = external[floor.dependency]
        if satisfies(have, floor.op, floor.version):
            return Row(module, floor, "ok", "Hummingbird", have)
        return Row(module, floor, "external", "Hummingbird", have,
                   reason=f"pkgconfig({floor.dependency}) is not built by the factory; "
                   f"Hummingbird ships {have}, so --apply cannot move it")
    # The build root's last repository is Fedora (tools/mock_config.py), which
    # this check does not read: the name is either Fedora's to supply or one
    # the recipe never asks for (a foreign platform, an unused fallback).
    return Row(module, floor, "unmapped",
               reason=f"neither a factory recipe nor Hummingbird provides "
               f"pkgconfig({floor.dependency}); if the recipe needs it, the build "
               f"root takes Fedora {FEDORA_RELEASEVER}'s, which this check does not read")


def check(
    floors: dict[str, list[Floor]],
    locks: dict[str, dict],
    providers: dict[str, set[str]],
    external: dict[str, str] | None,
) -> list[Row]:
    rows = []
    for module in sorted(floors):
        seen = set()
        for floor in floors[module]:
            key = (floor.dependency, floor.op, floor.version,
                   floor.expression if floor.op is None else "")
            if key in seen:
                continue
            seen.add(key)
            row = evaluate(module, floor, locks, providers, external)
            if row is not None:
                rows.append(row)
    return rows


# --- moves ------------------------------------------------------------------


@dataclass
class Move:
    package: str
    current: str
    op: str
    version: str
    modules: list[str] = field(default_factory=list)
    cycle: str = ""
    target: str = ""
    reason: str = ""

    @property
    def required(self) -> str:
        return f"{self.op} {self.version}"


def needed(rows: list[Row]) -> list[Move]:
    """The strongest unmet floor per factory dependency."""
    moves: dict[str, Move] = {}
    for row in rows:
        if row.status != "unmet":
            continue
        floor = row.floor
        move = moves.get(row.provider)
        if move is None:
            move = moves[row.provider] = Move(row.provider, row.have, floor.op, floor.version)
        else:
            order = vercmp(floor.version, move.version)
            if order > 0 or (order == 0 and floor.op == ">"):
                move.op, move.version = floor.op, floor.version
        if row.module not in move.modules:
            move.modules.append(row.module)
    return [moves[name] for name in sorted(moves)]


def gnome_module(entry: dict) -> str | None:
    """The download.gnome.org module a lock's primary or explicit feed names."""
    for url in (entry.get("url", ""), entry.get("feed", "")):
        match = GNOME_FEED.match(url or "")
        if match:
            return match.group("module")
    return None


def gnome_releases(module: str, opener=urllib.request.urlopen) -> dict[str, str]:
    """version -> the series directory download.gnome.org files it under."""
    request = urllib.request.Request(f"{GNOME_SOURCES}{module}/cache.json", headers=HEADERS)
    with opener(request, timeout=60) as response:
        document = json.loads(response.read())
    releases = {}
    for version, files in (document[1].get(module) or {}).items():
        path = next((p for p in files.values() if isinstance(p, str) and "/" in p), "")
        if path:
            releases[version] = path.split("/", 1)[0]
    return releases


def choose_release(releases: dict[str, str], op: str, version: str) -> tuple[str, str] | None:
    """(series, release): the newest final of the lowest series meeting the floor."""
    stable = {v: s for v, s in releases.items() if not is_prerelease(v)}
    meeting = [v for v in stable if satisfies(v, op, version)]
    if not meeting:
        return None
    series = min((stable[v] for v in meeting), key=VERSION_KEY)
    newest = max((v for v, s in stable.items() if s == series), key=VERSION_KEY)
    return series, newest


Runner = Callable[..., subprocess.CompletedProcess]


def bump_command(root: Path, move: Move, apply: bool) -> list[str]:
    command = [sys.executable, str(UPSTREAM_BUMP), "--root", str(root),
               "--package", move.package, "--cycle", move.cycle]
    return command + ["--apply"] if apply else command


def bump_output(move: Move, result: subprocess.CompletedProcess) -> tuple[str | None, str]:
    """(the release upstream_bump.py proposes, its words about the package)."""
    proposal = re.search(
        rf"^{re.escape(move.package)}: \S+ -> (\S+)", result.stdout or "", re.MULTILINE
    )
    said = [
        line.strip() for line in (result.stderr or "").splitlines()
        if re.search(rf"\b{re.escape(move.package)}:", line)
    ]
    return (proposal.group(1) if proposal else None), "; ".join(said)


def plan_move(
    root: Path, move: Move, locks: dict[str, dict],
    opener=urllib.request.urlopen, run: Runner = subprocess.run,
) -> Move:
    """Fill in a move's cycle and target, or the reason it cannot be made."""
    entry = locks[move.package]
    module = gnome_module(entry)
    if module:
        try:
            releases = gnome_releases(module, opener=opener)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as error:
            move.reason = f"cannot read {module}'s release index: {error}"
            return move
        chosen = choose_release(releases, move.op, move.version)
        if chosen is None:
            stable = [v for v in releases if not is_prerelease(v)]
            newest = max(stable, key=VERSION_KEY) if stable else "none"
            move.reason = (f"no stable {module} release satisfies {move.required} "
                           f"(newest stable: {newest})")
            return move
        move.cycle, move.target = chosen
    else:
        # A forge or Anitya feed takes no cycle; upstream_bump.py moves it to
        # the newest release of its major and the dry run says which.
        move.cycle = ".".join(move.version.split(".")[:2])
    result = run(bump_command(root, move, apply=False), capture_output=True, text=True,
                 check=False)
    proposed, said = bump_output(move, result)
    if proposed is None:
        move.reason = (f"upstream_bump.py --package {move.package} --cycle {move.cycle} "
                       f"proposes no move ({said or 'nothing newer it may take'})")
    elif not satisfies(proposed, move.op, move.version):
        move.reason = (f"upstream_bump.py would move {move.package} only to {proposed}, "
                       f"which does not satisfy {move.required}")
    else:
        move.target = proposed
    return move


def apply_move(root: Path, move: Move, run: Runner = subprocess.run) -> str:
    """Run the bump; the error, or '' once the lock meets the floor."""
    result = run(bump_command(root, move, apply=True), capture_output=True, text=True,
                 check=False)
    sys.stdout.write(result.stdout or "")
    sys.stderr.write(result.stderr or "")
    if result.returncode != 0:
        return f"upstream_bump.py exited {result.returncode}"
    have = source_locks(root)[move.package]["version"]
    if not satisfies(have, move.op, move.version):
        return f"{move.package} is at {have} after the bump, still below {move.required}"
    return ""


# --- report -----------------------------------------------------------------


SATISFIED = {
    "ok": "yes", "unmet": "**no**", "external": "**no**",
    "unmapped": "unknown", "unlocked": "unknown", "unparsed": "unknown",
}


def table(rows: list[Row], versions: dict[str, str]) -> list[str]:
    lines = [
        "| Module | Dependency | Required floor | Factory lock | Satisfied |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        have = f"{row.provider} {row.have}" if row.provider else "—"
        lines.append(
            f"| {row.module} {versions.get(row.module, '')} | {row.floor.dependency} "
            f"| {row.floor.required} | {have} | {SATISFIED[row.status]} |"
        )
    return lines


def findings(rows: list[Row], moves: list[Move], errors: dict[str, str]) -> list[str]:
    lines = []
    for move in moves:
        unmet = (f"- unmet: {move.package} {move.current} < {move.required} "
                 f"(needed by {', '.join(move.modules)}): ")
        if move.reason:
            lines.append(unmet + move.reason)
        else:
            lines.append(unmet + f"--apply moves it to {move.target} with `upstream_bump.py "
                         f"--package {move.package} --cycle {move.cycle} --apply`")
    for row in rows:
        if row.status != "ok" and row.status != "unmet":
            lines.append(f"- {row.status}: {row.module} needs {row.floor.dependency} "
                         f"{row.floor.required}: {row.reason}")
    for name, error in sorted(errors.items()):
        lines.append(f"- unread: {name}: {error}")
    return lines


def factory_published(args) -> dict[str, set[str]]:
    if args.primary:
        return provides_by_source(args.primary.read_bytes())
    repository, _, tag = args.image.rpartition(":")
    _, _, blob = fetch_image(repository, tag)
    return provides_by_source(primary_from_layer(blob))


def hummingbird(args) -> dict[str, str] | None:
    try:
        if args.hummingbird_primary:
            return pkgconfig_versions(args.hummingbird_primary.read_bytes())
        repo = args.root / "config" / "hummingbird.repo"
        return pkgconfig_versions(fetch_primary(hummingbird_baseurl(repo)))
    except (OSError, ValueError, ElementTree.ParseError) as error:
        print(f"warning: Hummingbird's repository could not be read: {error}", file=sys.stderr)
        return None


def main(
    argv: list[str] | None = None,
    opener=urllib.request.urlopen,
    run: Runner = subprocess.run,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true",
                        help="move each unmet factory dependency with tools/upstream_bump.py")
    parser.add_argument("--module", action="append", default=[],
                        help="check only this GNOME module (repeatable)")
    parser.add_argument("--image", default=FACTORY_IMAGE,
                        help="factory image whose repodata maps pkg-config names (ghcr.io)")
    parser.add_argument("--primary", type=Path,
                        help="a decompressed factory primary.xml instead of --image")
    parser.add_argument("--hummingbird-primary", type=Path,
                        help="a decompressed Hummingbird primary.xml instead of config/hummingbird.repo")
    parser.add_argument("--cache-dir", type=Path,
                        help="keep downloaded tarballs here (default: a temporary directory)")
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--summary", type=Path,
                        help="append the findings as Markdown (for $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    locks = source_locks(args.root)
    names = gnome_modules(args.root, locks)
    if args.module:
        unknown = sorted(set(args.module) - set(names))
        if unknown:
            parser.error(f"not a GNOME module lock: {', '.join(unknown)}")
        names = sorted(args.module)
    providers = factory_providers(args.root, factory_published(args))
    external = hummingbird(args)

    floors: dict[str, list[Floor]] = {}
    read_at: dict[str, str] = {}
    applied: list[Move] = []
    failed: dict[str, str] = {}
    rounds = 0
    with tempfile.TemporaryDirectory(prefix="gnome-dep-floors-") as temporary:
        scratch = args.cache_dir or Path(temporary)
        scratch.mkdir(parents=True, exist_ok=True)
        while True:
            rounds += 1
            # Only modules whose lock moved since they were read: a bumped
            # module brings floors of its own.
            stale = [n for n in names if read_at.get(n) != locks[n].get("sha512")]
            found, errors = module_floors(stale, locks, scratch, keep=args.cache_dir is not None,
                                          jobs=args.jobs, opener=opener)
            floors.update(found)
            read_at.update({n: locks[n].get("sha512") for n in found})
            rows = check(floors, locks, providers, external)
            moves = []
            for move in needed(rows):
                if move.package in failed:
                    move.reason = failed[move.package]
                else:
                    plan_move(args.root, move, locks, opener=opener, run=run)
                moves.append(move)
            doable = [move for move in moves if not move.reason]
            if not args.apply or not doable or rounds >= MAX_ROUNDS:
                break
            for move in doable:
                error = apply_move(args.root, move, run=run)
                if error:
                    failed[move.package] = error
                else:
                    applied.append(move)
            locks = source_locks(args.root)

    versions = {name: locks[name]["version"] for name in floors}
    rows.sort(key=lambda r: (r.status == "ok", r.module, r.floor.dependency))
    print("\n".join(table(rows, versions)))
    report = findings(rows, moves, errors)
    if applied:
        print("\nApplied:")
        for move in applied:
            print(f"- {move.package} -> {move.target} ({move.required}, for {', '.join(move.modules)})")
    print()
    print("\n".join(report) or "every declared floor is met")
    failing = [r for r in rows if r.failing]
    for row in failing:
        print(f"::error title=GNOME dependency floor::{row.module} needs "
              f"{row.floor.dependency} {row.floor.required}; the factory has "
              f"{row.provider} {row.have}", file=sys.stderr)
    for name, error in sorted(errors.items()):
        print(f"::error title=GNOME dependency floor::{name}: {error}", file=sys.stderr)
    counts = {status: sum(r.status == status for r in rows) for status in SATISFIED}
    totals = ", ".join(f"{count} {status}" for status, count in counts.items() if count)
    print(f"\n{len(floors)} modules, {len(rows)} floors: {totals or 'none'}")
    if args.summary:
        with args.summary.open("a") as handle:
            handle.write("## GNOME dependency floors (D9)\n\n")
            handle.write(f"{len(floors)} modules, {len(rows)} floors: {totals or 'none'}\n\n")
            handle.write("\n".join(report) + "\n\n" if report else "Every declared floor is met.\n\n")
            unresolved = [r for r in rows if r.status != "ok"]
            if unresolved:
                handle.write("\n".join(table(unresolved, versions)) + "\n")
    return 1 if failing or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
