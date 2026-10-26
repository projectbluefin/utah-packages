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

## Accessibility and speech output reconciliation

For [the six-name accessibility audit (#510)](https://github.com/projectbluefin/utah-packages/issues/510),
reuse the existing factory outputs. The recipes landed in
[PR #466](https://github.com/projectbluefin/utah-packages/pull/466), followed by
[the ICU build fix (#470)](https://github.com/projectbluefin/utah-packages/pull/470).
All six names already have closing records pointing to #466 in
`config/factory-build-backlog.toml`; do not expand the immutable original audit
or import another recipe for these binary names.

### Publication snapshot

Queried on 2026-10-26 at 06:13 UTC using `tools/package_index.py`'s registry
reader and the Hummingbird HTTPS metadata endpoint above. Factory image:

```text
ghcr.io/projectbluefin/utah-packages@sha256:2ae7b475632f416b759c3160d27ceef62c087089ebf54bb3e2a6961f4d85f222
```

The image identifies revision `8990424b4028b5535e4635c323dd7435d4e6afaf` and
[factory run 40265243289](https://github.com/projectbluefin/utah-packages/actions/runs/40265243289).
Its final publication job succeeded; the overall run failed on another
package, `gstreamer1-plugins-good`, the only source in the image's failed map.
None of the four accessibility sources is marked failed.

Each row is a binary found in factory primary metadata. Epoch is explicitly
zero in every NEVRA (name, epoch, version, release and architecture). None of
these six binary names is present in the Hummingbird primary snapshot.

| Binary output | Source recipe | Published NEVRA | Supplier |
| --- | --- | --- | --- |
| `brlapi` | `packages/brltty/brltty.spec` | `brlapi-0:0.8.8-9.hum1.bfin.x86_64` | Factory |
| `brltty` | `packages/brltty/brltty.spec` | `brltty-0:6.9.1-9.hum1.bfin.x86_64` | Factory |
| `espeak-ng` | `packages/espeak-ng/espeak-ng.spec` | `espeak-ng-0:1.52.0-4.hum1.bfin.x86_64` | Factory |
| `orca` | `packages/orca/orca.spec` | `orca-0:51.1-1.hum1.bfin.noarch` | Factory |
| `speech-dispatcher` | `packages/speech-dispatcher/speech-dispatcher.spec` | `speech-dispatcher-0:0.12.1-9.hum1.bfin.x86_64` | Factory |
| `speech-dispatcher-utils` | `packages/speech-dispatcher/speech-dispatcher.spec` | `speech-dispatcher-utils-0:0.12.1-9.hum1.bfin.x86_64` | Factory |

In particular, `brlapi` is a subpackage of `brltty` with its own version;
`speech-dispatcher-utils` is a subpackage of `speech-dispatcher`. Search
`sourcerpm` in primary metadata rather than assuming the binary name or
version identifies a separate source recipe.

Snapshot SHA-256 checksums (factory primary is decompressed XML; Hummingbird
primary, filelists and other are the compressed bytes named by repomd):

| Metadata | SHA-256 |
| --- | --- |
| Factory repomd | `a5a3703d531ce345c4f62b0d9cd80c3fb46b680dd9f0a58920118335a580c353` |
| Factory primary | `e3596acaaa0140ef66b9d34d040ac1ee58232afd2dfa5832ba43d642ada734c5` |
| Hummingbird repomd | `eb56a38f63ab02af3b019c9643e7adb41e5fd475f2ba920a7148460de4675d62` |
| Hummingbird primary | `e28983db652a7c317d51cb54efd75de45b63a4c29e01e0bd9bedb5b46bb6225a` |
| Hummingbird filelists | `3db83a1c47e325349936d272d5b4270b32518c40a86104aa5a2a9f31b9481faa` |
| Hummingbird other | `30ab12a6d641ae173a5d1f08ac84c5fc26722b4ec5f19ab7207db7289458063c` |

Hummingbird's repomd response was dated `Mon, 26 Oct 2026 06:13:57 GMT`,
with `Last-Modified: Sun, 25 Oct 2026 05:09:06 GMT` and an ETag equal to its
quoted repomd SHA-256 above.

### Resolution evidence and downstream boundary

[The maintainer's six-name solver check](https://github.com/projectbluefin/utah-packages/issues/510#issuecomment-6241961819)
on 2026-10-17 resolved every requested name with
`dnf install --assumeno --disablerepo=* --enablerepo=factory,hbird`, without
Fedora or negativo17. That check used Utah testing image `e556a075` and
factory pin `951d030d`; it is historical closure evidence, not a solver test
of the newer digest above.

The newer image's
[final publication job](https://github.com/projectbluefin/utah-packages/actions/runs/40265243289/job/121396157222)
also reports that all 316 names in Utah's install set resolve against factory
plus Hummingbird. This covers the current install set, not an explicit
six-name transaction: do not infer that every requested binary is installed.

[The maintainer's clarification](https://github.com/projectbluefin/utah-packages/issues/510#issuecomment-6241978215)
records five requested names as installed through dependencies, with `brltty`
absent but resolvable. Whether Utah should name those five directly or document
dependency reliance, and whether it should install `brltty`, belong to
[Utah's integration work (#263)](https://github.com/projectbluefin/utah/issues/263).
Publication, dependency resolution, installed presence and direct manifest
membership are four separate claims. A downstream planned-inventory entry
alone is not evidence that a new factory build is needed.
