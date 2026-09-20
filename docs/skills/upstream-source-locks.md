---
name: upstream-source-locks
description: >-
  Rules and conventions for upstream source locking, primary URL enforcement,
  Fedora availability fallbacks, and handling non-verbatim upstream artifacts.
metadata:
  type: procedure
---

# Upstream Source Locks and Provenance Policy

Sources must come from **upstream releases**, verified and SHA-512 locked.
Fedora dist-git supplies the **recipe only**, pinned by commit in
`.hummingbird-upstream.json`.

## The Rule

1. Direct-source entries in `config/upstream-sources.json` must fetch their
   primary payload from upstream releases (e.g., GitHub releases, GNOME
   releases, project release mirrors), not from Fedora's lookaside cache.
2. `tools/validate.py` enforces that primary URLs must not sit on Fedora hosts
   (`src.fedoraproject.org`, `fedoraproject.org`).
3. Fedora's lookaside is permitted only as an availability fallback in
   `fallback_urls`. The pipeline tries upstream first and falls back to Fedora
   only on transport errors.

## Exceptions

When an upstream release artifact cannot be downloaded verbatim:

- **Built from vendored Go source (`gosource`)**: `containerd`, `runc`, `mozc`,
  `alsa-firmware`, `alsa-tools`.
- **Recipe file only (no tarball)**: `kde-filesystem`, `kf5`.
- **Fedora-patched sdists**: `python-psutil`, `python-argcomplete`,
  `python-dbus-next`, `python-pydantic-core` (where Fedora re-rolls the sdist).
- **Work remaining**: Packages with Fedora lookaside URLs tracked under
  issue #134 for automated or manual feed discovery.
