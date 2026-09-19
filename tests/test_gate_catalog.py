#!/usr/bin/env python3
"""The Justfile check recipe aligns with the CI workflow gate catalog.

``just check`` is documented as "Everything CI gates on, minus the builds", but
historically the gate catalog was restated independently in the Justfile, in
``.github/workflows/validate.yml``, and in the ``prepare`` job of
``.github/workflows/rebuild-rpms.yml``, and the three lists disagreed about
which tools are gates.

This test enforces bidirectional consistency between the Justfile and the CI
workflows, ensuring that neither side carries gates omitted by the other.

A *gate* is recognised structurally: a workflow ``run:`` block in
``validate.yml`` or the ``prepare`` validation step of ``rebuild-rpms.yml`` is a
gate step when every logical command in it begins with ``python3`` and contains
no ``$``. That signature separates the fixed-argument validators (which produce
no pipeline output and run purely for exit status) from parameterized pipeline
tools. Workflows may also explicitly tag steps with a ``# gate`` comment.

The same commands must be reachable from ``just check``. Adding a gate to CI
without adding it to ``just check`` fails here, and so does the reverse: a gate
that only ever runs locally is not a gate CI enforces.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
JUSTFILE = ROOT / "Justfile"

# Verbosity only; it does not change what a gate checks, so two invocations
# that differ solely by it are the same gate.
VERBOSITY = {"-v", "-vv", "-q", "-qq", "--verbose", "--quiet"}


def normalise(command: str) -> str | None:
    """Canonical identity of a gate command, or ``None`` if it is not one.

    Both ``python3 -m unittest discover -s tests`` and ``python3 -m pytest
    tests`` run the same suite over ``tests/``; they collapse to one identity so
    the Justfile is not forced to run the suite twice to satisfy this gate.
    """
    words = [word for word in command.split() if word not in VERBOSITY]
    if len(words) < 2 or words[0] != "python3":
        return None
    if words[1] == "-m" and len(words) > 2 and words[2] in ("pytest", "unittest"):
        return "unit-tests"
    if words[1].startswith("tools/") and words[1].endswith(".py"):
        return " ".join(words[1:])
    return None


def logical_commands(script: str) -> list[str]:
    """Split a shell script into commands, joining backslash continuations."""
    joined = re.sub(r"\\\n\s*", " ", script)
    commands = []
    for line in joined.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            commands.append(re.sub(r"\s+", " ", line))
    return commands


def run_blocks(text: str) -> list[str]:
    """Every ``run:`` block body in a workflow, by indentation.

    Parsed from the raw text rather than through a YAML loader so a block's own
    indentation is preserved exactly as written.
    """
    blocks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)-?\s*run:\s*(\|[-+]?|>[-+]?)?\s*(\S.*)?$", lines[index])
        if not match:
            index += 1
            continue
        indent, block, inline = match.group(1), match.group(2), match.group(3)
        index += 1
        if not block:
            if inline:
                blocks.append(inline)
            continue
        body: list[str] = []
        while index < len(lines):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip()) <= len(indent):
                break
            body.append(line)
            index += 1
        blocks.append("\n".join(body))
    return blocks


def workflow_gates() -> dict[str, set[str]]:
    """Gate identities CI runs, mapped to the workflows that run them.

    CI gates live in .github/workflows/validate.yml (the dedicated gate
    workflow) and in the 'Validate factory policy and tests' step of
    .github/workflows/rebuild-rpms.yml (the pre-build gate).
    Any step in other workflows explicitly tagged with '# gate' is also
    recognised.
    """
    gates: dict[str, set[str]] = {}

    # 1. validate.yml is the dedicated gate workflow
    validate_file = WORKFLOWS / "validate.yml"
    if validate_file.exists():
        for block in run_blocks(validate_file.read_text()):
            commands = logical_commands(block)
            if not commands or any("$" in c for c in commands):
                continue
            identities = [normalise(c) for c in commands]
            if not all(identities):
                continue
            for identity in identities:
                gates.setdefault(identity, set()).add(validate_file.name)

    # 2. rebuild-rpms.yml runs gates in the prepare job's validation step
    rebuild_file = WORKFLOWS / "rebuild-rpms.yml"
    if rebuild_file.exists():
        rebuild_text = rebuild_file.read_text()
        match = re.search(
            r"-\s+name:\s+Validate factory policy and tests.*?\n\s+run:\s*(\|[-+]?|>[-+]?)?\s*\n(.*?)(?=\n\s+-\s+(?:name|uses|id):|\Z)",
            rebuild_text,
            re.DOTALL,
        )
        if match:
            commands = logical_commands(match.group(2))
            if commands and not any("$" in c for c in commands):
                identities = [normalise(c) for c in commands]
                if all(identities):
                    for identity in identities:
                        gates.setdefault(identity, set()).add(rebuild_file.name)

    # 3. Steps in other workflows explicitly tagged with `# gate`
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        if wf.name in ("validate.yml", "rebuild-rpms.yml"):
            continue
        for block in run_blocks(wf.read_text()):
            if "# gate" in block:
                commands = logical_commands(block)
                if commands and not any("$" in c for c in commands):
                    identities = [normalise(c) for c in commands]
                    if all(identities):
                        for identity in identities:
                            gates.setdefault(identity, set()).add(wf.name)

    return gates


def just_recipes() -> dict[str, tuple[list[str], list[str]]]:
    """Every Justfile recipe, as ``name -> (dependencies, commands)``."""
    recipes: dict[str, tuple[list[str], list[str]]] = {}
    name: str | None = None
    for line in JUSTFILE.read_text().splitlines():
        header = re.match(r"^([A-Za-z][\w-]*)\s*([^:=]*):(?!=)\s*(.*)$", line)
        if header and not line.startswith((" ", "\t")):
            name = header.group(1)
            recipes[name] = (header.group(3).split(), [])
            continue
        if name and line.startswith((" ", "\t")) and line.strip():
            recipes[name][1].append(line.strip().lstrip("@-"))
        elif not line.startswith((" ", "\t")):
            name = None
    return recipes


def reachable_commands(recipe: str) -> list[str]:
    """Commands run by ``just <recipe>``, following recipe dependencies."""
    recipes = just_recipes()
    seen: set[str] = set()
    commands: list[str] = []
    pending = [recipe]
    while pending:
        current = pending.pop()
        if current in seen or current not in recipes:
            continue
        seen.add(current)
        dependencies, body = recipes[current]
        pending.extend(dependencies)
        commands.extend(logical_commands("\n".join(body)))
    return commands


class GateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.ci = workflow_gates()
        self.local = {
            identity
            for identity in (normalise(command) for command in reachable_commands("check"))
            if identity
        }

    def test_the_workflows_still_contain_recognisable_gates(self):
        """Guard against the recogniser silently matching nothing."""
        self.assertGreaterEqual(
            len(self.ci), 4,
            msg="gate recogniser found almost nothing; the rule no longer matches "
                "the workflows and every other assertion here is vacuous",
        )

    def test_just_check_runs_every_gate_ci_runs(self):
        for identity, workflows in sorted(self.ci.items()):
            with self.subTest(gate=identity):
                self.assertIn(
                    identity, self.local,
                    msg=f"{', '.join(sorted(workflows))} runs '{identity}' but "
                        "'just check' does not; the documented local gate and CI "
                        "disagree about what the factory enforces",
                )

    def test_just_check_runs_no_gate_ci_does_not(self):
        for identity in sorted(self.local):
            with self.subTest(gate=identity):
                self.assertIn(
                    identity, self.ci,
                    msg=f"'just check' runs '{identity}' but no workflow does; a "
                        "gate nothing in CI enforces cannot block a merge",
                )

    def test_the_runtime_contract_gate_runs_in_checking_mode(self):
        """Without ``--check`` the tool dumps the resolved package list instead
        of reporting a verdict, so the same command is a query, not a gate."""
        gates = [
            identity for identity in self.local
            if identity.startswith("tools/runtime_contract.py")
        ]
        self.assertEqual(len(gates), 1, msg=f"expected one runtime-contract gate, got {gates}")
        self.assertIn("--check", gates[0])


if __name__ == "__main__":
    unittest.main()
