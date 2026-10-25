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
zcat "$P" | python3 -c "import sys, re
xml = sys.stdin.read()
for pkg in re.findall(\"<package>(.*?)</package>\", xml, re.S):
    name = re.search(\"<name>([^<]*)</name>\", pkg).group(1)
    reqs = re.findall(\"<rpm:requires>(.*?)</rpm:requires>\", pkg, re.S)
    req = sorted(set(re.findall(\"entry name=\\\"([^\\\"]*)\\\"\", reqs[0]))) if reqs else []
    print(name + \": \" + (\", \".join(req) if req else \"(no requires)\"))"  # per-package requires/provides
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

## Libraries loaded at runtime

A package-name dependency can be essential even when no ELF SONAME edge
appears. Since libkrun 1.11, the guest-kernel library libkrunfw is loaded at
runtime rather than linked at build time. Retain the explicit
`Requires: libkrunfw >= 5.0.0` in libkrun, and request `crun-krun` in the
runtime contract so publication tests the command and both libraries together.
Until both recipes have built and appeared in a successful publication, also
list `crun-krun` in `[unavailable]`: an unproven runtime request must not block
publication of unrelated packages. Remove the exception once that publication
is verified (#457). There is no BuildRequires ordering edge between these two
recipes.

For the headless agent-container use case, disable libkrun's `gpu` bcond
in the recipe itself; a one-off build flag does not describe the published
default. This avoids the virglrenderer runtime dependency while preserving
virtual-machine isolation. Sound remains enabled, using the factory's PipeWire.
Fedora's vendor archive is only used by the RHEL recipe branch; the Fedora
build uses packaged Rust crates, so do not fetch the unused vendor archive
through the factory's unconditional secondary-source manifest.
