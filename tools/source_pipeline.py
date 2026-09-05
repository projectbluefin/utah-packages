#!/usr/bin/env python3
"""Fetch and verify direct-upstream sources, failing closed on any mismatch.

The configuration intentionally uses JSON so the standard Python runtime on
GitHub-hosted runners is sufficient.  A package entry has ``name``, ``url``,
and a required ``sha512``.  An optional ``sha256_url`` points at an upstream
checksum manifest; the downloaded archive must appear in that manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


# An upstream that answers but sends nothing is the failure mode worth naming.
# git.zx2c4.com returned zero bytes for wireguard-tools, and because the
# pipeline hashed whatever arrived, the build reported
#
#   SHA-512 mismatch: expected ab56199..., got cf83e1357eefb8bd...
#
# cf83e135... is the SHA-512 of the empty string. That reads as a tampered or
# re-rolled tarball, which is alarming and wrong: nothing was served at all.
# An empty body is transient, so it is retried, and if it persists it is
# reported as what it is rather than as a digest mismatch.
FETCH_ATTEMPTS = 3


class EmptyDownload(RuntimeError):
    """The server answered but sent no bytes."""


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "utah-packages-source-pipeline/1"})
    last: Exception | None = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
            if destination.stat().st_size == 0:
                raise EmptyDownload(f"{url} returned an empty body")
            return
        except (EmptyDownload, urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = error
            if attempt < FETCH_ATTEMPTS:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url} after {FETCH_ATTEMPTS} attempts: {last}") from last


def fetch_with_fallbacks(urls: list[str], destination: Path) -> str:
    """Fetch the upstream source first, falling back only on transport failure.

    A fallback is an availability mirror, never a replacement for integrity:
    the caller still validates the configured SHA-512 (and, where present, the
    upstream signature/checksum manifest).  A fetched file whose digest is
    wrong must fail closed rather than quietly trying another source.
    """
    errors: list[str] = []
    for url in urls:
        try:
            fetch(url, destination)
            return url
        except RuntimeError as error:
            errors.append(f"{url}: {error}")
    raise RuntimeError("all source URLs failed: " + "; ".join(errors))


def verify_signature(package: dict, target: Path, directory: Path) -> None:
    key, signature_url = package.get("gpg_key"), package.get("signature_url")
    if bool(key) != bool(signature_url):
        raise ValueError("gpg_key and signature_url must be configured together")
    if not key:
        return
    signature = directory / f"{target.name}.asc"
    fetch(signature_url, signature)
    key_path = Path(key)
    if not key_path.is_file():
        raise ValueError(f"configured GPG key does not exist: {key_path}")
    with __import__("tempfile").TemporaryDirectory(prefix="source-pipeline-gpg-") as home:
        environment = {"GNUPGHOME": home}
        subprocess.run(["gpg", "--batch", "--import", str(key_path)], check=True, env=environment, capture_output=True)
        subprocess.run(["gpg", "--batch", "--verify", str(signature), str(target)], check=True, env=environment, capture_output=True)


LOOKASIDE = "https://src.fedoraproject.org/repo/pkgs/rpms/{pkg}/{name}/sha512/{hash}/{name}"


def generate_source(package: dict, target_dir: Path) -> Path:
    """Rebuild a generated Source0 from its pinned first-party input.

    Some recipes consume an archive no upstream publishes verbatim (a VCS
    snapshot, a stripped repack, a vendored bundle). Their lock entries carry
    a ``generate`` block naming the factory script instead of a ``url``; the
    script fetches pinned upstream input and deterministically produces the
    archive, which is then hash-verified below exactly like a downloaded one.
    Fedora's lookaside never supplies the primary payload.
    """
    name = package["name"]
    script = Path(package["generate"]["script"])
    if not script.is_file():
        raise ValueError(f"generation script does not exist: {script}")
    if not package.get("filename"):
        raise ValueError(f"generated source entry for {name} requires a filename")
    package_dir = Path("packages") / package.get("dist_git_name", name)
    if not package_dir.is_dir():
        raise ValueError(f"package recipe directory does not exist: {package_dir}")
    scratch = target_dir / ".generate"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    subprocess.run(
        [sys.executable, str(script), name, str(package_dir), str(scratch)],
        check=True,
    )
    produced = scratch / package["filename"]
    if not produced.is_file():
        raise ValueError(f"generation did not produce {package['filename']}")
    return produced


def source_manifest(package: dict) -> list[tuple[str, str]]:
    """Return the Fedora lookaside filenames and SHA-512 digests."""
    manifest = Path("packages") / package.get("dist_git_name", package["name"]) / "sources"
    if not manifest.is_file():
        return []
    entries = []
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"SHA512 \((\S+)\) = ([0-9a-f]{128})", line.strip())
        if match:
            entries.append(match.groups())
    return entries


def bundled_sources(package: dict, target_dir: Path, already: str) -> list[str]:
    """Fetch the sources a spec carries that upstream does not publish.

    Several specs bundle tarballs that only exist in Fedora's lookaside cache --
    malcontent's Source2 is a gvdb snapshot with no upstream URL at all -- and
    the dist-git checkout records them in a `sources` file rather than in the
    spec. Nothing fetched them, so `%prep` would have died on

        tar -xf /.../gvdb.tar.xz: No such file or directory

    the moment the buildroot resolved. Each entry names its own SHA-512 and the
    lookaside is addressed by that hash, so the URL is only satisfiable by the
    exact bytes recorded here.
    """
    fetched = []
    for filename, expected in source_manifest(package):
        if filename == already:  # Source0 comes from upstream, with its own checks.
            continue
        url = LOOKASIDE.format(pkg=package.get("dist_git_name", package["name"]),
                               name=filename, hash=expected)
        candidate = target_dir / f"{filename}.candidate"
        fetch(url, candidate)
        actual = digest(candidate, "sha512")
        if actual != expected:
            candidate.unlink(missing_ok=True)
            raise ValueError(f"SHA-512 mismatch for {filename}: expected {expected}, got {actual}")
        candidate.replace(target_dir / filename)
        fetched.append(filename)
    return fetched


def verify_staged_sources(package: dict, package_root: Path) -> list[str]:
    """Fail if Packit changed any source after the verification gate."""
    package_dir = package_root / package.get("dist_git_name", package["name"])
    expected_sources = {
        package.get("filename", ""): package["sha512"].lower(),
        **dict(source_manifest(package)),
    }
    verified = []
    for filename, expected in expected_sources.items():
        if not filename:
            continue
        source = package_dir / filename
        if not source.is_file():
            raise ValueError(f"staged source does not exist: {source}")
        actual = digest(source, "sha512")
        if actual != expected:
            raise ValueError(
                f"SHA-512 mismatch for {source}: expected {expected}, got {actual}"
            )
        verified.append(str(source))
    return verified


def stage_for_packit(package: dict, sources: list[Path], package_root: Path) -> list[str]:
    """Copy verified sources beside the package spec for `packit srpm`."""
    package_name = package.get("dist_git_name", package["name"])
    package_dir = package_root / package_name
    if not package_dir.is_dir():
        raise ValueError(f"package recipe directory does not exist: {package_dir}")
    staged = []
    for source in sources:
        destination = package_dir / source.name
        shutil.copy2(source, destination)
        staged.append(str(destination))
    return staged



def selected(config: dict, name: str | None) -> list[dict]:
    packages = config.get("packages", [])
    if name is None:
        return packages
    matches = [package for package in packages if package.get("name") == name]
    if not matches:
        raise SystemExit(f"package is not configured for direct upstream tracking: {name}")
    return matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", nargs="?")
    parser.add_argument("--config", type=Path, default=Path("config/upstream-sources.json"))
    parser.add_argument("--output", type=Path, default=Path("sources"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/source-pipeline"))
    parser.add_argument(
        "--stage-into",
        type=Path,
        help="copy accepted source files beside each package spec for Packit",
    )
    parser.add_argument(
        "--verify-staged",
        type=Path,
        help="verify that Packit did not change sources staged beside the spec",
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.verify_staged:
        for package in selected(config, args.package):
            verified = verify_staged_sources(package, args.verify_staged)
            print(json.dumps({"package": package["name"], "verified": verified}, sort_keys=True))
        return 0
    succeeded = True
    for package in selected(config, args.package):
        missing = {"name", "sha512"} - package.keys()
        if missing:
            raise SystemExit(f"invalid direct-source entry: missing {', '.join(sorted(missing))}")
        generate = package.get("generate")
        if generate is not None:
            if "url" in package or "url_template" in package or package.get("fallback_urls"):
                raise SystemExit(
                    f"invalid generated-source entry for {package['name']}: "
                    "must not carry url/url_template/fallback_urls"
                )
            if not package.get("filename"):
                raise SystemExit("invalid generated-source entry: require filename")
            url = None
        elif "url" in package:
            url = package["url"]
        elif "url_template" in package and "version" in package:
            url = package["url_template"].format(version=package["version"])
        else:
            raise SystemExit("invalid direct-source entry: require url or url_template plus version")
        name, expected = package["name"], package["sha512"].lower()
        target_dir = args.output / name
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = package.get("filename") or Path(urllib.parse.urlparse(url).path).name or f"{name}.source"
        candidate = target_dir / f"{filename}.candidate"
        fallback_urls = package.get("fallback_urls", [])
        if generate is None and (
            not isinstance(fallback_urls, list) or not all(isinstance(item, str) and item for item in fallback_urls)
        ):
            raise SystemExit("invalid direct-source entry: fallback_urls must be a list of non-empty URLs")
        report: dict[str, object] = {"package": name, "checked_at": datetime.now(UTC).isoformat()}
        if url is not None:
            report["url"] = url
        try:
            if generate is not None:
                produced = generate_source(package, target_dir)
                produced.replace(candidate)
                resolved_url = f"generated:{generate['script']}"
            else:
                resolved_url = fetch_with_fallbacks([url, *fallback_urls], candidate)
            actual = digest(candidate, "sha512")
            if actual != expected:
                raise ValueError(f"SHA-512 mismatch: expected {expected}, got {actual}")
            verify_signature(package, candidate, target_dir)
            if checksum_url := package.get("sha256_url"):
                checksum_file = target_dir / "upstream.sha256"
                fetch(checksum_url, checksum_file)
                expected_sha256 = digest(candidate, "sha256")
                if expected_sha256 not in checksum_file.read_text(errors="replace"):
                    raise ValueError("download is absent from the upstream SHA-256 manifest")
            final = target_dir / filename
            candidate.replace(final)
            bundled = bundled_sources(package, target_dir, filename)
            report.update({"result": "accepted", "sha512": actual, "file": str(final), "resolved_url": resolved_url})
            if bundled:
                report["bundled"] = bundled
            if args.stage_into:
                source_files = [final, *(target_dir / item for item in bundled)]
                report["staged"] = stage_for_packit(package, source_files, args.stage_into)
        except Exception as error:  # Do not replace an accepted source.
            candidate.unlink(missing_ok=True)
            succeeded = False
            report.update({"result": "rejected", "error": str(error)})
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / f"{name}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, sort_keys=True))
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
