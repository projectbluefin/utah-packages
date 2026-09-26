#!/usr/bin/env python3
"""Resolve what Utah actually installs against a candidate factory repository.

The publish gate's Hummingbird-only consumer transaction resolves the runtime
contract in config/ -- about 78 packages. Utah installs far more:
packages/bluefin.toml [fedora] and [fedora_v<major>] plus packages/utah.toml
[gnome], [parity], [hardware], [services] and [build], minus [unavailable]
(projectbluefin/utah scripts/install-packages.py). A factory repository could
satisfy the first and still break the second, and Utah found out one image
build at a time: libgphoto2 needing libexif and lockdev, libppd needing
ghostscript.

This computes Utah's set with Utah's own code, fetched from its main branch,
so it cannot drift from what Utah installs, and resolves it in the Hummingbird
base image against the candidate repository plus Hummingbird. It names every
package that does not resolve. It is advisory: incremental publication must
not let one gap freeze every other package, so it warns, reports in the job
summary, and the report job keeps one issue per unresolvable package.

    utah_install_set.py fetch --dir utah [--ref main]
        (host) fetch Utah's installer, manifests and repository files, and
        write utah/packages.txt, the package set
    utah_install_set.py resolve --dir /utah --report report.json
        (inside the base image, the candidate repository mounted where
        Utah's utah-packages.repo expects it, /etc/utah-packages) install
        Utah's repository files, enable the ones Utah installs from, resolve
        the whole set, then each package on its own when the whole set
        fails, and write the verdict
"""

from __future__ import annotations

import argparse
import sys as _sys
_sys.dont_write_bytecode = True
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

UTAH = "https://raw.githubusercontent.com/projectbluefin/utah/{ref}/{path}"
FILES = {
    "installer": "scripts/install-packages.py",
    "manifest": "packages/bluefin.toml",
    "overlay": "packages/utah.toml",
    # Utah's own repository files, so the resolution uses its excludes and
    # priorities -- utah-packages.repo excludes grub2*, for one.
    "utah_packages_repo": "packages/utah-packages.repo",
    "hummingbird_repo": "packages/hummingbird.repo",
    "gpg_key": "packages/RPM-GPG-KEY-redhat-release-2",
}
FEDORA_MAJOR = "44"

# The same patterns Utah's --resolve and the gate's transaction treat as a
# failure; an --assumeno run otherwise exits non-zero on a valid transaction.
ERRORS = re.compile(
    r"No match for argument|nothing provides|conflicting requests|cannot install both"
    r"|Error:|Failed to",
    re.IGNORECASE,
)
SUMMARY = re.compile(r"(?m)^Transaction Summary:?\s*$|^Nothing to do\.?\s*$")


def fetch(ref: str, directory: Path) -> dict[str, Path]:
    paths = {}
    for key, path in FILES.items():
        target = directory / Path(path).name
        with urllib.request.urlopen(UTAH.format(ref=ref, path=path), timeout=60) as response:
            target.write_bytes(response.read())
        paths[key] = target
    return paths


def installer_module(installer: Path):
    spec = importlib.util.spec_from_file_location("utah_install_packages", installer)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_set(installer: Path, manifest: Path, overlay: Path,
                major: str = FEDORA_MAJOR) -> list[str]:
    """Utah's contract plus its [build] section, computed by Utah's own code."""
    module = installer_module(installer)
    packages = module.contract(manifest, overlay, major)
    packages += module.section(overlay, "build")
    return list(dict.fromkeys(packages))


def dnf() -> str:
    found = shutil.which("dnf5") or shutil.which("dnf")
    if not found:
        raise RuntimeError("no dnf in this image")
    return found


def attempt(packages: list[str], repos: tuple[str, ...]) -> tuple[bool, str]:
    """Resolve without installing, the way Utah's --resolve does."""
    result = subprocess.run(
        [dnf(), "--assumeno", "--disablerepo=*",
         *(f"--enablerepo={repo}" for repo in repos),
         "-x", "PackageKit*", "install", *packages],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={**os.environ, "LC_ALL": "C"}, check=False,
    )
    ok = (result.returncode in (0, 1)
          and not ERRORS.search(result.stdout)
          and bool(SUMMARY.search(result.stdout)))
    return ok, result.stdout


# dnf's own problem lines, most specific first: "conflicting requests" is
# the heading dnf puts over the line that actually says what is missing.
PROBLEMS = (
    re.compile(r"nothing provides|No match for argument"),
    re.compile(r"requires .*, but none|cannot install both|conflicts with"),
    re.compile(r"conflicting requests"),
)


def first_problem(output: str) -> str:
    """The line that says why, for the report: dnf's own problem line."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for pattern in PROBLEMS:
        for line in lines:
            if pattern.search(line):
                return line.lstrip("- ")[:300]
    for index, line in enumerate(lines):
        if ERRORS.search(line) and index + 1 < len(lines):
            return lines[index + 1].lstrip("- ")[:300]
    return lines[-1][:300] if lines else "no output"


def resolve(packages: list[str], repos: tuple[str, ...]) -> dict:
    ok, output = attempt(packages, repos)
    report = {"requested": len(packages), "resolved": ok, "unresolved": {}}
    if ok:
        return report
    # One transaction reports the first problems it meets; asking per
    # package names every one, which is what an issue per package needs.
    for package in packages:
        single_ok, single = attempt([package], repos)
        if not single_ok:
            report["unresolved"][package] = first_problem(single)
    if not report["unresolved"]:
        # Every package resolves alone but not together: a conflict between
        # them. Name it rather than reporting success.
        report["unresolved"]["(the set together)"] = first_problem(output)
    return report


def summary(report: dict) -> str:
    lines = ["### Utah install set", ""]
    if report.get("error"):
        lines.append(f"**Not checked:** {report['error']}")
    elif report["resolved"]:
        lines.append(f"All {report['requested']} packages Utah installs resolve against this "
                     "repository plus Hummingbird.")
    else:
        unresolved = report["unresolved"]
        lines += [f"**{len(unresolved)} of {report['requested']} packages Utah installs do not "
                  "resolve** against this repository plus Hummingbird. Publication is not "
                  "blocked by this; each gets a tracking issue on main.", "",
                  "| package | why |", "| --- | --- |"]
        for package, why in sorted(unresolved.items()):
            lines.append(f"| `{package}` | `{why.replace('|', '/')}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    fetching = commands.add_parser("fetch")
    fetching.add_argument("--ref", default="main")
    fetching.add_argument("--dir", type=Path, required=True)
    resolving = commands.add_parser("resolve")
    resolving.add_argument("--dir", type=Path, required=True)
    resolving.add_argument("--report", type=Path, required=True)
    rendering = commands.add_parser("summary")
    rendering.add_argument("report", type=Path)
    args = parser.parse_args(argv)

    if args.command == "fetch":
        args.dir.mkdir(parents=True, exist_ok=True)
        files = fetch(args.ref, args.dir)
        packages = install_set(files["installer"], files["manifest"], files["overlay"])
        (args.dir / "packages.txt").write_text("".join(f"{name}\n" for name in packages))
        print(f"Utah installs {len(packages)} packages (projectbluefin/utah@{args.ref})")
        return 0
    if args.command == "resolve":
        packages = [line.strip() for line in (args.dir / "packages.txt").read_text().splitlines()
                    if line.strip()]
        repos_dir = Path("/etc/yum.repos.d")
        for repo in args.dir.glob("*.repo"):
            shutil.copy(repo, repos_dir / repo.name)
        key = args.dir / "RPM-GPG-KEY-redhat-release-2"
        if key.exists():
            Path("/etc/pki/rpm-gpg").mkdir(parents=True, exist_ok=True)
            shutil.copy(key, "/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release-2")
        repos = tuple(installer_module(args.dir / "install-packages.py").install_repos(repos_dir))
        print(f"resolving {len(packages)} packages from {', '.join(repos)}")
        report = resolve(packages, repos)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(summary(report))
        return 0
    if args.command == "summary":
        print(summary(json.loads(args.report.read_text())))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
