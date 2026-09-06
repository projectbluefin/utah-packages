set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Everything CI gates on, minus the builds.
check: factory-check validate

# Package-factory configuration: provenance, source locks, Packit coverage.
validate:
    python3 tools/validate.py

# Project Bluefin factory onboarding contract.
factory-check:
    python3 tools/factory_contract.py

test:
    python3 -m pytest tests -q
