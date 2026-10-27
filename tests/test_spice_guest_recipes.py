"""Keep the Linux guest agent and its build-time protocol headers together."""

import json
from pathlib import Path

from tools.build_graph import Recipe, capabilities, graph, waves

ROOT = Path(__file__).resolve().parents[1]


def test_guest_agent_builds_after_protocol_headers():
    agent = (ROOT / "packages/spice-vdagent/spice-vdagent.spec").read_text()
    protocol = (ROOT / "packages/spice-protocol/spice-protocol.spec").read_text()
    requirements = [
        capability
        for line in agent.splitlines()
        if line.startswith("BuildRequires:")
        for capability in capabilities(line.removeprefix("BuildRequires:"))
    ]
    assert "spice-protocol" in requirements
    assert "Name:           spice-protocol" in protocol
    assert "%bcond_with mingw" in protocol
    assert "%bcond_without mingw" not in protocol
    recipes = {
        "spice-protocol": Recipe("spice-protocol", provides={"spice-protocol"}),
        "spice-vdagent": Recipe("spice-vdagent", buildrequires=requirements),
    }
    edges = graph(recipes)
    assert edges["spice-vdagent"] == {"spice-protocol"}
    assert waves(edges, edges, {}) == {"spice-protocol": 0, "spice-vdagent": 1}


def test_guest_agent_and_protocol_sources_are_locked():
    locks = json.loads((ROOT / "config/upstream-sources.json").read_text())["packages"]
    for name in ("spice-protocol", "spice-vdagent"):
        lock = next(entry for entry in locks if entry["name"] == name)
        source = (ROOT / "packages" / name / "sources").read_text().strip()
        assert source == f'SHA512 ({lock["filename"]}) = {lock["sha512"]}'
        assert lock["url"].startswith("https://")
        assert "src.fedoraproject.org" not in lock["url"]
