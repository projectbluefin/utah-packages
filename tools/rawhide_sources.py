#!/usr/bin/env python3
"""Single source for Fedora source-RPM naming and the Bluefin import grammar.

Two independent tools ask the same two questions of Fedora and of
``config/bluefin-packages.toml``:

* ``tools/scan_rawhide_state.py`` -- what does Rawhide currently ship for the
  Bluefin binaries, and which source packages changed?
* ``tools/import_bluefin_rawhide.py`` -- which source packages back the Bluefin
  binaries, so their dist-git can be imported?

Before this module both restated the source-RPM regex verbatim and both
restated the set of manifest tables that make up "the packages we ingest".
A Fedora naming edge case therefore had to be fixed twice, and adding a table
to the manifest updated whichever copy the author happened to open.  The
grammar lives here once; see the accompanying issue for the separate,
policy-level divergence between *this* grammar and the two other section
grammars used by ``tools/runtime_contract.py`` and
``tools/recalculate_hummingbird_gaps.py``.
"""

from __future__ import annotations

import re

# Fedora source RPM versions begin with a digit; package names may contain '-'.
SRPM_NAME = re.compile(r"^(.+)-[0-9][^-]*-.*\.src\.rpm$")

# Manifest tables the factory ingests from Fedora Rawhide.  This is deliberately
# narrower than the full Bluefin contract: the release-version tables
# (fedora_v42/v43/v44) and [excluded] are not ingestion inputs.
IMPORT_SECTIONS = ("fedora", "multimedia_overrides")


def source_name(sourcerpm: str) -> str:
    """Derive the source package name from a ``*.src.rpm`` file name."""
    match = SRPM_NAME.match(sourcerpm)
    if not match:
        raise ValueError(f"cannot parse source RPM: {sourcerpm}")
    return match.group(1)


def import_binaries(manifest: dict, sections: tuple[str, ...] = IMPORT_SECTIONS) -> list[str]:
    """Return the sorted, de-duplicated binaries the factory ingests.

    A missing table is an error rather than an empty list: a manifest that lost
    a table would otherwise resolve to a silently smaller import set.
    """
    binaries: list[str] = []
    for section in sections:
        if section not in manifest:
            raise ValueError(f"Bluefin manifest has no [{section}] section")
        binaries.extend(manifest[section].get("packages", []))
    return sorted(set(binaries))
