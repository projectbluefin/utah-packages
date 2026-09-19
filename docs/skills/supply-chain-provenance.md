---
name: supply-chain-provenance
description: >-
  Rules and conventions for buildroot locking, live package NEVRA snapshots,
  recipe provenance verification, and factory manifest generation.
metadata:
  type: procedure
---

# Supply Chain Provenance and Buildroot Locking

Factory rebuilds require reviewably reproducible inputs and immutable recipe
provenance rather than relying on mutable container tags and repository state.

## Buildroot Lock Contract

- Buildroots are pinned by image digest in `config/buildroot-lock.json`.
- Each buildroot entry specifies a digest-pinned image reference containing
  `@sha256:`.
- `tools/buildroot_lock.py` provides:
  - `image <name>` to resolve the pinned image reference.
  - `snapshot <name> --output <path> [--strict]` to snapshot package NEVRAs
    from `rpm -qa` inside the buildroot. When the lock specifies an expected
    package list, `--strict` verifies the buildroot package set.

## Recipe Provenance

Every recipe in `packages/<name>/` must carry `.hummingbird-upstream.json`:

- **rawhide imports**: Must pin full 40-character hexadecimal git commit and
  tree SHAs from Fedora dist-git.
- **upstream imports**: Must specify a non-empty `remote` URL and must not
  carry dist-git commit or tree hashes (the source archive is verified and
  pinned in `config/upstream-sources.json`).
- `tools/validate.py` enforces these rules and rejects unpinned or missing
  provenance across all recipes.

## Source Verification Reporting

`tools/source_pipeline.py` records verification status in package reports:

- Cryptographic signatures (`signature_url`) set `verification: "signature"`
  and `checksum_only: false`.
- Upstream SHA-256 manifests (`sha256_url`) set `verification: "sha256-manifest"`
  and `checksum_only: true`.
- Locked SHA-512 archives set `verification: "sha512"` and `checksum_only: true`.

## Factory Manifest

`tools/factory_manifest.py` aggregates binary RPM files, source verification
reports, buildroot snapshots, and the published OCI digest into `manifest.json`.
This file is published alongside the repository and stored as a build artifact.
