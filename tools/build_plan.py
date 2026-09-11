#!/usr/bin/env python3
"""Build plan computation for incremental factory rebuilds.

Computes which packages to build given changed files, recipe changes,
global changes, and upstream published repository state. Reverse dependencies
are transitively resolved so that any package affected by an upstream library
or buildroot change is included in the build plan.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


# Global paths that trigger a full rebuild or policy-defined rebuild
GLOBAL_REBUILD_PATTERNS = (
    r"^\.github/workflows/.*",
    r"^config/.*",
    r"^tools/.*",
    r"^tests/.*",
)

GLOBAL_IGNORE_PATTERNS = (
    r"^\.agents/.*",
    r"^\.claude/.*",
    r"^docs/.*",
    r"^\.gitignore$",
    r"^\.pre-commit-config\.yaml$",
    r"^AGENTS\.md$",
    r"^Justfile$",
    r"^README\.md$",
    r"^renovate\.json$",
    r"^reports/.*",
)


@dataclass
class BuildPlan:
    packages: List[str]
    stages: Dict[int, List[str]]
    reasons: Dict[str, List[str]]
    direct_changes: Set[str] = field(default_factory=set)
    reverse_deps: Set[str] = field(default_factory=set)
    is_full_rebuild: bool = False
    global_triggers: List[str] = field(default_factory=list)

    def summary_markdown(self) -> str:
        """Format the build plan as a reviewable GitHub Actions step summary / report."""
        lines = ["# Factory Build Plan", ""]
        if self.is_full_rebuild:
            lines.append("**Build Mode:** Full Rebuild")
            if self.global_triggers:
                lines.append(f"- **Triggered by global changes:** {', '.join(sorted(self.global_triggers))}")
        else:
            lines.append("**Build Mode:** Incremental")
            lines.append(f"- **Direct recipe changes ({len(self.direct_changes)}):** {', '.join(sorted(self.direct_changes)) or 'none'}")
            lines.append(f"- **Reverse dependency closures ({len(self.reverse_deps)}):** {', '.join(sorted(self.reverse_deps)) or 'none'}")

        total_selected = len(self.packages)
        lines.append(f"- **Total packages selected:** {total_selected}")
        lines.append("")

        if not self.packages:
            lines.append("No packages require building in this run.")
            return "\n".join(lines)

        lines.append("## Build Waves")
        lines.append("")
        for stage_num in sorted(self.stages.keys()):
            stage_pkgs = self.stages[stage_num]
            lines.append(f"### Stage {stage_num} ({len(stage_pkgs)} packages)")
            if stage_pkgs:
                for pkg in sorted(stage_pkgs):
                    pkg_reasons = ", ".join(self.reasons.get(pkg, ["unknown"]))
                    lines.append(f"- **{pkg}**: {pkg_reasons}")
            else:
                lines.append("- *(empty)*")
            lines.append("")

        lines.append("## Package Impact Matrix")
        lines.append("")
        lines.append("| Package | Stage | Selection Reason |")
        lines.append("| --- | --- | --- |")
        for pkg in sorted(self.packages):
            st = next((s for s, pkgs in self.stages.items() if pkg in pkgs), 0)
            reason_str = "; ".join(self.reasons.get(pkg, []))
            lines.append(f"| `{pkg}` | {st} | {reason_str} |")
        lines.append("")

        return "\n".join(lines)


def parse_spec_symbols(root_dir: Path, factory_pkgs: Set[str]) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    """Parse spec files to build a mapping from provided symbols to factory packages,

    and extract the forward build dependencies (BuildRequires) for each factory package.
    """
    symbol_to_pkg: Dict[str, str] = {}
    pkg_specs: Dict[str, str] = {}

    for p in factory_pkgs:
        symbol_to_pkg[p] = p
        for sfx in ("-devel", "-libs", "-common", "-static", "-tools", "-utils", "-doc", "-docs"):
            symbol_to_pkg[f"{p}{sfx}"] = p
        symbol_to_pkg[f"pkgconfig({p})"] = p
        if p.startswith("lib"):
            symbol_to_pkg[f"pkgconfig({p[3:]})"] = p
        else:
            symbol_to_pkg[f"pkgconfig(lib{p})"] = p

    for sf in (root_dir / "packages").glob("*/*.spec"):
        pkg = sf.parent.name
        if pkg not in factory_pkgs:
            continue
        content = sf.read_text(errors="ignore")
        pkg_specs[pkg] = content

        clean_lines = []
        for line in content.splitlines():
            if re.match(r"^%changelog\b", line):
                break
            clean_lines.append(re.sub(r"#.*$", "", line))
        clean_content = "\n".join(clean_lines)

        macros = {"name": pkg}
        for m in re.finditer(r"%(?:global|define)\s+([a-zA-Z0-9_]+)\s+([^\n]+)", clean_content):
            macros[m.group(1)] = m.group(2).strip()

        for line in clean_lines:
            m = re.match(r"^%package\s+(.*)", line)
            if m:
                sub = m.group(1).strip()
                for k, v in macros.items():
                    sub = sub.replace(f"%{{{k}}}", v).replace(f"%{k}", v)
                if sub.startswith("-n"):
                    subname = re.sub(r"^-n\s*", "", sub).strip()
                else:
                    subname = f"{pkg}-{sub}"
                symbol_to_pkg[subname] = pkg
                for sfx in ("-devel", "-libs", "-common", "-static", "-tools", "-utils", "-doc", "-docs"):
                    symbol_to_pkg[f"{subname}{sfx}"] = pkg
                symbol_to_pkg[f"pkgconfig({subname})"] = pkg

            m = re.match(r"^Provides:\s+(.*)", line, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                for k, v in macros.items():
                    val = val.replace(f"%{{{k}}}", v).replace(f"%{k}", v)
                for token in re.findall(r"[^\s,]+(?:\([^)]*\))?", val):
                    if token in (">=", "<=", "=", ">", "<") or (token and token[0].isdigit()) or "%" in token:
                        continue
                    symbol_to_pkg[token] = pkg
                    symbol_to_pkg[f"pkgconfig({token})"] = pkg

            for pcm in re.finditer(r"([a-zA-Z0-9_\-+*%{}]+)\.pc", line):
                pcname = pcm.group(1)
                for k, v in macros.items():
                    pcname = pcname.replace(f"%{{{k}}}", v).replace(f"%{k}", v)
                if "%" not in pcname:
                    if "*" in pcname:
                        # e.g. *-%{apiver} -> *-1 -> libadwaita-1
                        expanded_pc = pcname.replace("*", pkg)
                        symbol_to_pkg[f"pkgconfig({expanded_pc})"] = pkg
                    else:
                        symbol_to_pkg[f"pkgconfig({pcname})"] = pkg

    forward_deps: Dict[str, Set[str]] = {p: set() for p in factory_pkgs}
    for pkg, content in pkg_specs.items():
        clean_lines = []
        for line in content.splitlines():
            if re.match(r"^%changelog\b", line):
                break
            clean_lines.append(re.sub(r"#.*$", "", line))
        clean_content = "\n".join(clean_lines)
        macros = {"name": pkg}
        for m in re.finditer(r"%(?:global|define)\s+([a-zA-Z0-9_]+)\s+([^\n]+)", clean_content):
            macros[m.group(1)] = m.group(2).strip()

        for line in clean_lines:
            m = re.match(r"^BuildRequires:\s*(.*)", line, re.IGNORECASE)
            if not m:
                continue
            val = m.group(1).strip()
            for k, v in macros.items():
                val = val.replace(f"%{{{k}}}", v).replace(f"%{k}", v)

            for token in re.findall(r"[^\s,()]+(?:\([^)]*\))?", val):
                token = token.strip()
                if not token or token in (">=", "<=", "=", ">", "<") or token[0].isdigit() or "%" in token:
                    continue
                if token in symbol_to_pkg:
                    target = symbol_to_pkg[token]
                    if target != pkg:
                        forward_deps[pkg].add(target)
                elif token.startswith("pkgconfig("):
                    inner = token[10:-1]
                    candidates = [inner]
                    no_ver = re.sub(r"[-_.]?[0-9]+(?:\.[0-9]+)*$", "", inner)
                    if no_ver != inner:
                        candidates.append(no_ver)
                    for cand in candidates:
                        cand_key = f"pkgconfig({cand})"
                        if cand_key in symbol_to_pkg:
                            target = symbol_to_pkg[cand_key]
                            if target != pkg:
                                forward_deps[pkg].add(target)
                                break
                        elif cand in symbol_to_pkg:
                            target = symbol_to_pkg[cand]
                            if target != pkg:
                                forward_deps[pkg].add(target)
                                break
                        elif f"lib{cand}" in symbol_to_pkg:
                            target = symbol_to_pkg[f"lib{cand}"]
                            if target != pkg:
                                forward_deps[pkg].add(target)
                                break
                        elif cand.startswith("lib") and cand[3:] in symbol_to_pkg:
                            target = symbol_to_pkg[cand[3:]]
                            if target != pkg:
                                forward_deps[pkg].add(target)
                                break

    return symbol_to_pkg, forward_deps


def compute_reverse_dependency_closure(
    initial_packages: Iterable[str],
    forward_deps: Dict[str, Set[str]],
    factory_pkgs: Set[str],
) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Given initial packages and forward dependencies (pkg -> deps),

    compute the reverse dependency mapping and transitive closure of affected packages.
    """
    reverse_deps: Dict[str, Set[str]] = {p: set() for p in factory_pkgs}
    for p, deps in forward_deps.items():
        for d in deps:
            if d in reverse_deps:
                reverse_deps[d].add(p)

    closure = set(initial_packages)
    stack = list(initial_packages)
    while stack:
        curr = stack.pop()
        for downstream in reverse_deps.get(curr, set()):
            if downstream not in closure:
                closure.add(downstream)
                stack.append(downstream)

    return closure, reverse_deps


def normalize_version(version: str) -> str:
    """Normalize RPM version strings (e.g. replacing '~' with '.')."""
    return version.replace("~", ".")


def compute_build_plan(
    root_dir: Path,
    changed_files: Optional[Iterable[str]] = None,
    published_packages: Optional[Dict[str, str]] = None,
    full_rebuild: bool = False,
    override_packages: Optional[Iterable[str]] = None,
) -> BuildPlan:
    """Compute the build plan for the factory repository.

    Parameters:
    - root_dir: Repository root directory.
    - changed_files: List of file paths changed between base and HEAD.
    - published_packages: Mapping of package name -> published version string.
    - full_rebuild: If True, rebuilds all packages.
    - override_packages: Explicit set of package names to build.
    """
    config_path = root_dir / "config" / "upstream-sources.json"
    config = json.loads(config_path.read_text())
    packages_meta = {p["name"]: p for p in config["packages"]}
    factory_pkgs = set(packages_meta.keys())
    stages_meta = {p["name"]: p.get("stage", 0) for p in config["packages"]}

    _, forward_deps = parse_spec_symbols(root_dir, factory_pkgs)

    reasons: Dict[str, List[str]] = {}
    direct_changes: Set[str] = set()
    reverse_selected: Set[str] = set()
    global_triggers: List[str] = []

    if full_rebuild:
        selected = set(factory_pkgs)
        for p in selected:
            reasons[p] = ["full rebuild requested"]
        is_full = True
    elif override_packages is not None:
        selected = set(override_packages) & factory_pkgs
        for p in selected:
            reasons[p] = ["explicit override"]
        is_full = False
    else:
        # Check changed_files for global or recipe changes
        is_global = False
        if changed_files is not None:
            for path in changed_files:
                path = path.strip()
                if not path:
                    continue
                # Ignore non-build changes like docs, agents, etc.
                if any(re.match(pat, path) for pat in GLOBAL_IGNORE_PATTERNS):
                    continue

                # Check if it matches a package recipe directly
                m = re.match(r"^packages/([^/]+)/", path)
                if m:
                    pkg_name = m.group(1)
                    if pkg_name in factory_pkgs:
                        direct_changes.add(pkg_name)
                        reasons.setdefault(pkg_name, []).append(f"recipe edit ({path})")
                elif any(re.match(pat, path) for pat in GLOBAL_REBUILD_PATTERNS):
                    is_global = True
                    global_triggers.append(path)

        if is_global:
            selected = set(factory_pkgs)
            for p in selected:
                reasons.setdefault(p, []).append(f"global trigger ({', '.join(sorted(global_triggers)[:3])})")
            is_full = True
        else:
            # Check version differences or new packages against published repo
            if published_packages is not None:
                for pkg_name, meta in packages_meta.items():
                    version = meta.get("version", "")
                    if pkg_name not in published_packages:
                        direct_changes.add(pkg_name)
                        reasons.setdefault(pkg_name, []).append("new or unpublished package")
                    elif normalize_version(published_packages[pkg_name]) != normalize_version(version):
                        direct_changes.add(pkg_name)
                        pub_v = published_packages[pkg_name]
                        reasons.setdefault(pkg_name, []).append(f"version change (published: {pub_v} != target: {version})")
            elif not direct_changes:
                # If neither published repo nor git diff was supplied, rebuild all
                pass

            # Expand reverse dependencies of direct_changes
            closure, reverse_deps = compute_reverse_dependency_closure(direct_changes, forward_deps, factory_pkgs)
            reverse_selected = closure - direct_changes
            for downstream in reverse_selected:
                # Find which direct changes triggered this downstream
                triggers = [src for src in direct_changes if downstream in compute_reverse_dependency_closure([src], forward_deps, factory_pkgs)[0]]
                reasons.setdefault(downstream, []).append(f"reverse dependency of {', '.join(sorted(triggers))}")

            selected = direct_changes | reverse_selected
            is_full = False

    # Partition into stages 0..4
    stages: Dict[int, List[str]] = {n: [] for n in range(5)}
    overflow = []
    for pkg in selected:
        st = stages_meta.get(pkg, 0)
        if st in stages:
            stages[st].append(pkg)
        else:
            overflow.append((pkg, st))

    if overflow:
        overflow_names = [f"{p} (stage {st})" for p, st in sorted(overflow)]
        raise ValueError(f"no job exists for stage 5 or later; reduce the stage of: {', '.join(overflow_names)}")

    for st in stages:
        stages[st].sort()

    return BuildPlan(
        packages=sorted(selected),
        stages=stages,
        reasons=reasons,
        direct_changes=direct_changes,
        reverse_deps=reverse_selected,
        is_full_rebuild=is_full,
        global_triggers=global_triggers,
    )


def main():
    """CLI interface for build plan generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Compute factory build plan")
    parser.add_argument("--base-sha", help="Base commit SHA for git diff comparison")
    parser.add_argument("--head-sha", default="HEAD", help="Head commit SHA (default: HEAD)")
    parser.add_argument("--full", action="store_true", help="Rebuild every package")
    parser.add_argument("--output-json", help="Path to write build plan JSON")
    parser.add_argument("--summary-file", action="append", default=[], help="Path to append or write Markdown step summary")
    parser.add_argument("--github-output", help="Write step outputs to GITHUB_OUTPUT file")

    args = parser.parse_args()
    root = Path.cwd()

    changed_files = None
    if args.base_sha and re.fullmatch(r"[0-9a-f]{40}", args.base_sha) and set(args.base_sha) != {"0"}:
        import subprocess
        try:
            diff_out = subprocess.check_output(
                ["git", "diff", "--name-only", f"{args.base_sha}..{args.head_sha}"],
                text=True,
            )
            changed_files = diff_out.splitlines()
        except subprocess.CalledProcessError as e:
            print(f"Warning: git diff failed: {e}", file=sys.stderr)

    # Fetch published repo if not full rebuild
    published = None
    if not args.full:
        import gzip, io, urllib.request
        try:
            base_url = "https://projectbluefin.github.io/utah-packages/"
            repomd = urllib.request.urlopen(base_url + "repodata/repomd.xml", timeout=60).read().decode()
            href = re.search(r'<location href="([^"]*primary[^"]*)"', repomd).group(1)
            raw = urllib.request.urlopen(base_url + href, timeout=120).read()
            if href.endswith(".zst"):
                import zstandard
                stream = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw))
            else:
                stream = gzip.GzipFile(fileobj=io.BytesIO(raw))
            text = stream.read()
            published = {}
            for m in re.finditer(rb'<package[^>]*>.*?<name>([^<]+)</name>.*?<version[^>]*ver="([^"]+)"', text, re.S):
                published[m.group(1).decode()] = m.group(2).decode()
        except Exception as err:
            print(f"Warning: could not read published repo: {err}", file=sys.stderr)

    plan = compute_build_plan(
        root_dir=root,
        changed_files=changed_files,
        published_packages=published,
        full_rebuild=args.full,
    )

    if args.output_json:
        out_data = {
            "packages": plan.packages,
            "stages": plan.stages,
            "reasons": plan.reasons,
            "direct_changes": sorted(plan.direct_changes),
            "reverse_deps": sorted(plan.reverse_deps),
            "is_full_rebuild": plan.is_full_rebuild,
        }
        Path(args.output_json).write_text(json.dumps(out_data, indent=2))

    summary_md = plan.summary_markdown()
    for summary_path in args.summary_file:
        if summary_path:
            with open(summary_path, "a") as f:
                f.write(summary_md + "\n")

    gh_output_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output_path:
        with open(gh_output_path, "a") as f:
            f.write(f"build_list={json.dumps(plan.packages)}\n")
            for n in range(5):
                f.write(f"stage{n}={json.dumps(plan.stages.get(n, []))}\n")

    print(f"Build plan computed: {len(plan.packages)} packages selected")
    for n in range(5):
        print(f"  Stage {n}: {len(plan.stages.get(n, []))} packages")


if __name__ == "__main__":
    main()
