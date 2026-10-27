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

## Accessibility and speech output reconciliation

For [the six-name accessibility audit (#510)](https://github.com/projectbluefin/utah-packages/issues/510),
reuse the existing factory outputs. The recipes landed in
[PR #466](https://github.com/projectbluefin/utah-packages/pull/466), followed by
[the ICU build fix (#470)](https://github.com/projectbluefin/utah-packages/pull/470).
All six names already have closing records pointing to #466 in
`config/factory-build-backlog.toml`; do not expand the immutable original audit
or import another recipe for these binary names.

### Source-to-binary map

Use the [audit issue (#510)](https://github.com/projectbluefin/utah-packages/issues/510)
and its linked PR for dated publication and solver evidence. Re-query before
quoting current suppliers, NEVRAs, digests or metadata checksums; keep those
snapshots in the issue or PR evidence rather than this reusable guide.

| Binary output | Source recipe |
| --- | --- |
| `brlapi` | `packages/brltty/brltty.spec` |
| `brltty` | `packages/brltty/brltty.spec` |
| `espeak-ng` | `packages/espeak-ng/espeak-ng.spec` |
| `orca` | `packages/orca/orca.spec` |
| `speech-dispatcher` | `packages/speech-dispatcher/speech-dispatcher.spec` |
| `speech-dispatcher-utils` | `packages/speech-dispatcher/speech-dispatcher.spec` |

`brlapi` is a subpackage of `brltty` with its own version;
`speech-dispatcher-utils` is a subpackage of `speech-dispatcher`. Search
`sourcerpm` in primary metadata rather than assuming the binary name or
version identifies a separate source recipe.

### Resolution evidence and downstream boundary

Test all six names in one solver transaction, including `brltty`, against the
exact factory digest being handed downstream and a dated Hummingbird snapshot:

```bash
dnf install --assumeno --disablerepo='*' --enablerepo=factory,hbird \
  brlapi brltty espeak-ng orca speech-dispatcher speech-dispatcher-utils
```

Point `factory` at the repository extracted from that digest, and `hbird` at
the permitted Hummingbird repository. Record the base image or empty install
root, enabled repositories, command and transaction result with the digest.
An expected nonzero exit from `--assumeno` is not enough: require a transaction
summary (or `Nothing to do`) and reject dependency or repository errors.
Historical solver checks of older pins and checks of Utah's install set do
not prove all six resolve from a newly cited digest: the install set can omit
`brltty`. An empty-root check proves dependency closure, while checking in
Utah's pinned base also tests compatibility with its installed RPM database.

Whether Utah should name dependency-installed packages directly or document
dependency reliance, and whether it should install `brltty`, belong to
[Utah's integration work (#263)](https://github.com/projectbluefin/utah/issues/263).
Publication, dependency resolution, installed presence and direct manifest
membership are four separate claims. A downstream planned-inventory entry
alone is not evidence that a new factory build is needed.
