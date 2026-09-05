#!/usr/bin/env python3
"""Create direct-source candidates from imported RPM recipes.

This deliberately does not consult Fedora's lookaside cache. A candidate is
accepted only when the resolved Source0 is an upstream HTTP(S) URL and its
bytes can be downloaded directly. Everything else is reported for an explicit
maintainer decision rather than silently falling back to Rawhide.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


FEDORA_HOSTS = ("fedoraproject.org", "src.fedoraproject.org", "kojipkgs.fedoraproject.org")

LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms/{pkg}/{name}/sha512/{hash}/{name}"


def manifest_pins(package_dir: Path) -> dict[str, str]:
    """Return the SHA-512 pins recorded in a package's Fedora `sources` file."""
    pins = {}
    manifest = package_dir / "sources"
    if manifest.is_file():
        for line in manifest.read_text().splitlines():
            match = re.fullmatch(r"SHA512 \((\S+)\) = ([0-9a-f]{128})", line.strip())
            if match:
                pins[match.group(1)] = match.group(2)
    return pins


def recipe_macros(text: str) -> dict[str, str]:
    """Collect the tag/%global values a generated Source0 filename expands from.

    rpmspec is the macro authority for direct downloads, but the generated
    Source0 recipes must stay resolvable without an RPM toolchain, and their
    filenames only ever draw on literal tags and %global definitions.
    """
    macros = dict(re.findall(r"^%global\s+(\w+)\s+(\S+)", text, flags=re.MULTILINE))
    for tag in ("Name", "Version"):
        match = re.search(rf"^{tag}:\s*(\S+)", text, flags=re.MULTILINE)
        if match:
            macros[tag.lower()] = match.group(1)
    return macros


def expand_macros(value: str, macros: dict[str, str]) -> str:
    for _ in range(5):
        expanded = re.sub(r"%\{(\w+)\}", lambda m: macros.get(m.group(1), m.group(0)), value)
        if expanded == value:
            break
        value = expanded
    if "%{" in value:
        raise ValueError(f"unresolved macros in {value}")
    return value


def _generated_lock(package_dir: Path, generated: dict[str, str]) -> dict:
    """Pin a generated Source0 to its exact manifest-recorded bytes.

    The spec consumes an archive that no upstream publishes verbatim (a VCS
    snapshot, a stripped repack, a vendored bundle), so the lock fetches the
    content-addressed lookaside artifact -- immutable by construction -- and
    the caller re-hashes the download against the manifest pin. The
    first-party transformation that produced the bytes stays explicit in the
    entry rather than hidden behind a fallback.
    """
    specs = list(package_dir.glob("*.spec"))
    if len(specs) != 1:
        raise ValueError(f"expected one spec, found {len(specs)}")
    text = specs[0].read_text()
    macros = recipe_macros(text)
    source0 = re.search(r"^Source0:\s*(\S+)", text, flags=re.MULTILINE)
    if not source0:
        raise ValueError(f"no Source0 in {specs[0]}")
    filename = expand_macros(source0.group(1), macros)
    version = expand_macros(macros["version"], macros)
    pins = manifest_pins(package_dir)
    if filename not in pins:
        raise ValueError(f"{filename} is not pinned in {package_dir}/sources")
    digest = pins[filename]
    return {
        "name": package_dir.name,
        "version": version,
        "url": LOOKASIDE.format(pkg=package_dir.name, name=filename, hash=digest),
        "filename": filename,
        "sha512": digest,
        "generated": {key: expand_macros(value, macros) for key, value in generated.items()},
    }


def _gcc_generated(package_dir: Path) -> dict:
    text = (package_dir / "gcc.spec").read_text()
    macros = recipe_macros(text)
    revision = macros["gitrev"]
    version = macros["gcc_version"]
    prefix = f"gcc-{version}-{macros['DATE']}"
    return _generated_lock(package_dir, {
        "input": f"https://gcc.gnu.org/git/gcc.git revision {revision} (vendors/redhat/heads/gcc-{macros['gcc_major']}-branch)",
        "method": f"git archive --prefix={prefix}/ {revision} | xz -9e",
        "script": "packages/gcc/update-gcc.sh",
    })


def _intel_media_driver_free_generated(package_dir: Path) -> dict:
    return _generated_lock(package_dir, {
        "input": "https://github.com/intel/media-driver/archive/intel-media-%{version}.tar.gz",
        "method": "remove non-free EU kernel files from the extracted tag archive and repack as intel-media-%{version}-free.tar.gz",
        "script": "packages/intel-media-driver-free/strip.py",
    })


def _tailscale_generated(package_dir: Path) -> dict:
    return _generated_lock(package_dir, {
        "input": "https://github.com/tailscale/tailscale tag v%{version}",
        "method": "go mod tidy && go mod vendor, drop unused cmd trees/k8s-operator/tstest, XZ_OPT='-e -9 -T0' tar -cJf",
        "script": "packages/tailscale/create-vendor-tarball.sh",
    })


GENERATED_SOURCES = {
    "gcc": _gcc_generated,
    "intel-media-driver-free": _intel_media_driver_free_generated,
    "tailscale": _tailscale_generated,
}


def generated_candidate(package_dir: Path) -> dict:
    """Build the source lock for a recipe whose Source0 is generated, not published."""
    resolver = GENERATED_SOURCES.get(package_dir.name)
    if resolver is None:
        raise ValueError(f"no generated source resolver for {package_dir.name}")
    return resolver(package_dir)


def merge_candidates(existing: dict, candidates: list[dict]) -> dict:
    """Append candidates for unlocked packages, never disturbing a lock.

    Existing entries keep their parsed form exactly, so a merge round-trips
    byte-for-byte once JSON-normalized. A candidate naming an already-locked
    package is a conflict, not an update.
    """
    merged = dict(existing)
    packages = list(existing.get("packages", []))
    locked = {entry["name"] for entry in packages}
    seen = set()
    for candidate in candidates:
        name = candidate["name"]
        if name in locked:
            raise ValueError(f"source lock already exists: {name}")
        if name in seen:
            raise ValueError(f"duplicate candidate: {name}")
        seen.add(name)
        packages.append(candidate)
    merged["packages"] = packages
    return merged


def plan_targets(packages: Path, already_supplied: dict, only: str | None = None) -> list[Path]:
    """Select recipe directories to process.

    An explicit ``only`` selection is processed even when Hummingbird already
    supplies the package; the default scan keeps skipping supplied packages.
    """
    available = sorted(path for path in packages.iterdir() if path.is_dir())
    if only is not None:
        selected = [path for path in available if path.name == only]
        if not selected:
            raise ValueError(f"no package recipe named {only}")
        return selected
    return [path for path in available if path.name not in already_supplied]


def rpm_value(spec: Path, query: str) -> str:
    # A spec can emit dozens of binary package records.  Source identity and
    # Version must come from the one SRPM record, not concatenated binary
    # subpackages (for example, libblockdev's plugins).
    return subprocess.check_output(["rpmspec", "-q", "--srpm", "--qf", query, str(spec)], text=True).splitlines()[0]


def sources(spec: Path) -> list[tuple[int, str]]:
    parsed = subprocess.check_output(["rpmspec", "--parse", str(spec)], text=True, stderr=subprocess.STDOUT)
    return [(int(index or 0), url) for index, url in re.findall(r"^Source(\d*):\s*(\S+)\s*$", parsed, flags=re.MULTILINE)]


def sha512(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-bootstrap/1"})
    value = hashlib.sha512()
    with urllib.request.urlopen(request, timeout=120) as response:
        # GitHub release redirects end at an opaque object-store name, and some
        # upstreams have a meaningless path basename -- a crates.io download URL
        # ends in literally "download". RPM takes the local file name from the
        # "#/name" fragment when the URL carries one, and from the declared URL
        # basename otherwise; mirror that so the staged file matches Source0.
        parsed = urllib.parse.urlparse(url)
        filename = parsed.fragment.lstrip("/") or Path(parsed.path).name
        for block in iter(lambda: response.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest(), filename


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--packages", type=Path, default=Path("packages"))
    parser.add_argument("--output", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/direct-source-bootstrap.json"))
    parser.add_argument("--provided-packages", type=Path, help="newline-delimited package names already supplied by Hummingbird")
    parser.add_argument("--provided-sources", type=Path, help="JSON inventory of source packages already supplied by Hummingbird")
    parser.add_argument("--merge", action="store_true",
                        help="merge candidates into the existing output file instead of replacing it")
    parser.add_argument("--package",
                        help="process only this recipe, even if Hummingbird already supplies it")
    args = parser.parse_args()
    root = args.root.resolve()
    packages = (root / args.packages).resolve()
    provided_names = set(args.provided_packages.read_text().split()) if args.provided_packages else set()
    resolution_path = root / "reports/bluefin-rawhide-resolution.json"
    resolution = json.loads(resolution_path.read_text()) if resolution_path.exists() else {}
    requested_by_source: dict[str, set[str]] = {}
    for binary, source in resolution.get("resolved_binary_to_source", {}).items():
        requested_by_source.setdefault(source, set()).add(binary)
    already_supplied = {
        source: sorted(binaries)
        for source, binaries in requested_by_source.items()
        if binaries and binaries <= provided_names
    }
    if args.provided_sources:
        supplied_sources = json.loads(args.provided_sources.read_text()).get("sources", [])
        for source in supplied_sources:
            already_supplied.setdefault(source, sorted(requested_by_source.get(source, [])))
    candidates, rejected = [], []
    for package in plan_targets(packages, already_supplied, only=args.package):
        specs = list(package.glob("*.spec"))
        if len(specs) != 1:
            rejected.append({"package": package.name, "reason": f"expected one spec, found {len(specs)}"})
            continue
        spec = specs[0]
        try:
            if package.name in GENERATED_SOURCES:
                candidate = generated_candidate(package)
                # The lock records the manifest pin; prove the served bytes
                # are those exact bytes before accepting the entry.
                digest, filename = sha512(candidate["url"])
                if digest != candidate["sha512"] or filename != candidate["filename"]:
                    raise ValueError(
                        f"lookaside artifact mismatch for {candidate['filename']}: "
                        f"expected {candidate['sha512']}, got {digest}"
                    )
                candidates.append(candidate)
                continue
            name, version = rpm_value(spec, "%{NAME}"), rpm_value(spec, "%{VERSION}")
            declared_sources = sources(spec)
            url = next((value for index, value in declared_sources if index == 0), None)
            if not url or not url.startswith(("http://", "https://")):
                raise ValueError("Source0 is not a direct HTTP(S) URL")
            if len(declared_sources) > 1 and not args.package:
                raise ValueError("additional Source entries require an explicit verified source-closure mapping")
            if urllib.parse.urlparse(url).hostname in FEDORA_HOSTS:
                raise ValueError("Source0 points at Fedora infrastructure, not the upstream")
            digest, filename = sha512(url)
            if args.package:
                # An explicit selection asserts that upstream still serves the
                # exact bytes the recipe's Fedora manifest pins for Source0.
                pinned = manifest_pins(package).get(filename)
                if pinned and pinned != digest:
                    raise ValueError(
                        f"upstream bytes for {filename} do not match the pinned manifest: "
                        f"expected {pinned}, got {digest}"
                    )
            candidates.append({"name": name, "version": version, "url": url, "filename": filename, "sha512": digest})
        except Exception as error:
            rejected.append({"package": package.name, "spec": str(spec.relative_to(root)), "reason": str(error)})
    output, report = root / args.output, root / args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    if args.merge:
        existing = json.loads(output.read_text()) if output.exists() else {"schema": 1, "packages": []}
        payload = merge_candidates(existing, candidates)
    else:
        payload = {"schema": 1, "packages": candidates}
    output.write_text(json.dumps(payload, indent=2) + "\n")
    report.write_text(json.dumps({"accepted": len(candidates), "already_supplied_by_hummingbird": already_supplied,
                                  "rejected": rejected}, indent=2) + "\n")
    print(f"accepted direct sources: {len(candidates)}; already supplied: {len(already_supplied)}; needs explicit mapping: {len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
