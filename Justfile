set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# tests/test_gate_catalog.py fails when a workflow gate is missing here, or
# when a gate here is enforced by no workflow.
#
# Everything CI gates on, minus the builds.
check: factory-check validate multimedia workflow-quoting runtime-contract test

# Package-factory configuration: provenance, source locks, Packit coverage,
# and no recipe silencing its own %check with tests_nonfatal.
validate:
    python3 tools/validate.py

# Bluefin's multimedia override and codec transaction against what we build.
multimedia:
    python3 tools/multimedia_closure.py --check

# Project Bluefin factory onboarding contract.
factory-check:
    python3 tools/factory_contract.py

# Shell-quoting safety of the build scripts embedded in the workflows.
workflow-quoting:
    python3 tools/check_workflow_quoting.py

# The image manifest resolved against the pinned runtime contract.
runtime-contract:
    python3 tools/runtime_contract.py config/bluefin-packages.toml config/runtime-contract.toml --check

test:
    python3 -m pytest tests -q
