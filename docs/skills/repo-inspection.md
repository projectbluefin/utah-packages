---
name: repo-inspection
description: Inspect what the pinned factory OCI image and Hummingbird actually publish — repodata queries, digest pins, and the publication-vs-build distinction. Live metadata, not hard-coded names.
---

# Inspecting the package repositories

The factory publishes RPMs as an OCI image carrying a yum repository; Hummingbird
publishes a plain HTTPS repository. Both are mutable over time, so every claim
about "available" or "missing" needs the snapshot it was measured against.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `ghcr.io/projectbluefin/utah-packages` (digest-pinned per release) | The factory output Utah consumes |
| `https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/` | Hummingbird's own repository (mutable snapshot, never digest-pinned) |
| `skopeo inspect docker://ghcr.io/projectbluefin/utah-packages:latest` | Current factory digest without pulling |

## Querying factory repodata

The image has no shell — mount it and read the repository metadata:

```bash
podman unshare bash -c '
M=$(podman image mount ghcr.io/projectbluefin/utah-packages@sha256:<digest>)
R="$M/repository"; P=$(ls "$R"/repodata/*primary.xml.gz | head -1)
zcat "$P" | grep -o "<name>[^<]*</name>" | sort -u   # published binary names
zcat "$P" | python3 -c "import sys,re  # per-package requires/provides
xml = sys.stdin.read()"'
podman image unmount ghcr.io/projectbluefin/utah-packages@sha256:<digest>'
```

Mount and unmount must happen inside the same `podman unshare` invocation;
the mount does not survive it. Record the image digest, the repomd/primary
checksums, and the fetch time with every answer.

## What publication does and does not prove

- A name in `primary.xml` is published, not installable: dependency closure
  still has to resolve under Utah's permitted repositories (factory plus
  Hummingbird, never Fedora/negativo17 at runtime).
- A static provides-match is a preflight, not proof. The real test is a solver
  dry-run (`dnf install --assumeno` with exactly the permitted repos) or,
  conclusively, a lane build in CI.
- Missing from repodata plus missing from Hummingbird means a factory build is
  owed (or an explicit wontfix). Missing from one but present in the other is
  a Utah-side consumption task, not a build.
- Utah repo `excludepkgs`/`includepkgs` filters can hide published names
  (`grub2*` today). A name that fails the static repo filter is not
  consumable no matter what the metadata says.

## Hummingbird snapshots

Hummingbird's repodata is fetched over HTTPS: save `repomd.xml` plus the full
`primary`/`filelists`/`other` files with response headers and checksums, and
label the result with the fetch timestamp. Never present a Hummingbird answer
without one — the repository moves under you.
