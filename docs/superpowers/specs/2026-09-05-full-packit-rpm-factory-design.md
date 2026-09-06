# Full Packit RPM factory

## Status

Approved for implementation by the maintainer's explicit instruction to make
GitHub Actions the factory and make Packit fully operational. GitHub Actions is
this factory's Copr replacement. Packit runs as a CLI inside the workflow; no
hosted Packit service is involved.

## Definition of done

The factory is complete only when one recorded GitHub Actions run proves all of
the following:

1. All 193 package recipe directories have a SHA-512-locked source definition
   and a root Packit monorepo entry.
2. Packit produces a source RPM for every recipe without changing any verified
   source after the verification gate.
3. Packit invokes Mock for every source RPM against the Hummingbird-compatible
   build root.
4. The five dependency stages complete in order, and later stages consume the
   repositories transferred from earlier stages as workflow artifacts.
5. Every expected source package reports a successful binary build, every
   emitted RPM is queryable, repository metadata is valid, and a clean
   dependency-closure transaction resolves against the final repository.
6. The final repository is published through the GitHub Actions OCI and Pages
   paths with a manifest tying every package result to source hashes, the
   Packit image digest, the Mock configuration digest, the workflow run URL,
   and the final repository digest.

An SRPM-only run is useful evidence but does not satisfy this definition.

## Current gap

The inventory gap described in the earlier version of this document is
closed. The verified counts are:

| inventory | result |
| --- | ---: |
| `packages/*/` recipe directories | 193 |
| entries under `packages` in the root `.packit.yaml` | 193 |
| entries under `packages` in `config/upstream-sources.json` | 193 |

The source validator also succeeds for the complete inventory:

```text
$ ls -d packages/*/ | wc -l
193

$ python3 tools/validate.py
validated 193 source RPMs
```

The earlier claims of 180 source entries, 54 Packit entries, and 13 named
packages without locks are wrong. There are no named source-lock omissions in
the current `config/upstream-sources.json`.

The remaining gap is the binary lane. The existing
[`rebuild-rpms.yml`](../../../.github/workflows/rebuild-rpms.yml#L226-L443)
still invokes `rpmbuild` directly in a Fedora 44 container. Its five-stage
artifact and gating mechanics are the model to retain, but Packit and Mock
must replace that direct build path.

The current source pilot is
[`packit-srpm-pilot.yml`](../../../.github/workflows/packit-srpm-pilot.yml#L42-L98).
It currently discovers all package entries on `ubuntu-24.04`, fans out one
matrix job per package with `fail-fast: false`, runs
`tools/source_pipeline.py`, runs `packit srpm --preserve-spec` inside the
digest-pinned Packit image, verifies staged sources again, queries the SRPM,
checks that the file is non-empty, and uploads it with
`if-no-files-found: error`. That lane does not yet feed the SRPMs into Mock,
dependency staging, or publication. The target factory lane is
`ubuntu-26.04`; the pilot must be rerun after the runner migration before its
result is treated as 26.04 evidence. The earlier statement about a 54-package
Argo run is not evidence for this design and is removed.

## Execution environment

All source RPM generation, Mock builds, repository composition, and publication
run on GitHub-hosted `ubuntu-26.04` runners. The runner executes the pinned
build container with Docker or Podman; there is no second execution substrate.

| concern | implementation |
| --- | --- |
| build capacity | one GitHub-hosted `ubuntu-26.04` runner per matrix job |
| build container | upstream `quay.io/packit/packit`, pinned below |
| tools in the container | `packit`, `mock`, and `createrepo_c` |
| workflow transport | `actions/upload-artifact` and `actions/download-artifact` |
| publication | GHCR OCI image, with Pages as the `main` mirror |

The upstream Packit image is rebuilt daily and already contains the required
toolchain. The pin used by this factory is:

```text
quay.io/packit/packit@sha256:149e6e06d3e5fb2f10d19760c8a0031c7d8825e7bb91a5f4a7ab9b927c947494
```

PRs #36--#40 and closed issue #35 settle the final decision: this
repository does not maintain a second Packit image. The local `packit-sdk`
image was removed in favour of the upstream image, which is pinned above.
The factory must not install Packit with `pip` or rebuild the toolchain in a
workflow job.

There is no Argo cluster, Kubernetes scheduler, local Zot registry, FSDK
container, USB4 route, or `ghost`/`exo-0` build node in this design. GitHub
Actions artifacts are the only cross-job transport.

### Runner migration

The repository's workflow files currently pin `runs-on: ubuntu-24.04`. Moving
the factory to `ubuntu-26.04` is explicit work, not a cosmetic label change:

1. Replace every `runs-on: ubuntu-24.04` under `.github/workflows/` with
   `runs-on: ubuntu-26.04`, including `rebuild-rpms.yml`,
   `packit-srpm-pilot.yml`, and `validate.yml`.
2. Rerun the validation workflow, the Packit SRPM pilot, and the staged binary
   workflow after the label migration. Their current 24.04 runs do not prove
   26.04 behaviour.
3. Re-prove Mock on the new runner: loop-device access, `/dev/shm` sizing,
   privileged-container flags, and nested-container behaviour are runner-OS
   sensitive. A working `quay.io/packit/packit` image does not establish that
   those runner capabilities carry over.

The Packit image supplies the Packit, Mock, and `createrepo_c` userland. The
runner supplies the kernel, disk, and container runtime. That boundary is why
the migration has to test Mock rather than merely change the workflow label.

For public repositories, GitHub's
[runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories)
gives the standard Linux allocation as 4 vCPUs, 16 GB RAM, and 14 GB SSD.
The same table includes `ubuntu-24.04` and `ubuntu-26.04`; it does not publish
a 26.04-specific hardware measurement. Its private-repository standard row is
2 vCPUs, 8 GB RAM, and 14 GB SSD. GitHub's
[Actions limits](https://docs.github.com/en/actions/reference/limits#existing-system-limits)
list a six-hour execution limit for every GitHub-hosted job. These are
published standard-runner figures, not measurements from this repository.

GitHub announced `ubuntu-26.04` and `ubuntu-26.04-arm` as public-preview
images on 2026-06-11 in the
[runner-images changelog](https://github.blog/changelog/2026-06-11-new-runner-images-in-public-preview/)
and [actions/runner-images#14226](https://github.com/actions/runner-images/issues/14226).
Public preview is a production-factory risk: the image can change its
pre-installed environment or be withdrawn. The mitigation is that the build
toolchain lives in the digest-pinned `quay.io/packit/packit` container rather
than on the bare runner, so runner-image churn moves less than it would in a
bare-runner design. This is not immunity. The runner still supplies the kernel
and container runtime, which are exactly what Mock is sensitive to.

`ubuntu-26.04-arm` exists, but this factory currently builds `x86_64` only.
The Hummingbird content measured by this repository is the
`public-hummingbird/x86_64` repository. Whether Hummingbird publishes an
aarch64 repository suitable for a future ARM lane is unverified; no aarch64
build plan is asserted here.

## Considered approaches

### 1. Keep the existing binary builder and use Packit only for SRPMs

Rejected. The hand-written `rpmbuild -br`/`-ba` implementation would remain the
real factory, so failures could diverge between the Packit proof lane and the
published RPMs. The current binary workflow is evidence of the gap, not the
target architecture.

### 2. Split Packit SRPM generation from Packit Mock builds

This is the selected design. Packit first creates a source RPM from verified
sources. The workflow verifies source integrity and SRPM metadata, then passes
that exact file to:

```text
packit build --srpm <package.src.rpm> in-mock \
  --root <generated-hummingbird-mock.cfg> \
  --resultdir <result-directory>
```

This keeps the source gate independently testable, permits SRPM reuse on Mock
retries, and makes Packit the interface for both source and binary builds
without coupling their failure domains.

### 3. Adopt Packit Service, Copr, or Koji

Rejected. The repository owns source verification, Hummingbird build-root
composition, dependency staging, signing, and publication. A hosted Fedora
service would move those decisions outside the factory and would not provide
the required branch-local test.

The branch-local point is concrete. The repository's
[`targeting-hummingbird.md`](../../targeting-hummingbird.md#how-the-packages-are-published)
records that a Copr or Pages repository cannot be consumed by digest before a
merge. The OCI image can be consumed by digest on any ref: `main` publishes
`:latest`, while every other ref publishes under its branch name. That is
required to test an image and its package set before either is merged.

### 4. Keep Argo and Kubernetes as the execution substrate

Rejected. Artifact transfer, repository composition, publication, and gating
are already GitHub Actions primitives. A second execution substrate would
split the failure domain and duplicate scheduling and publication state without
adding a required capability.

## Architecture

### Package inventory and configuration

A generator creates the root Packit monorepo configuration from
`config/upstream-sources.json` plus the package recipe directories. Generated
entries contain the package path, spec path, names, and the common
`create-archive` action that returns the already verified Source0.

Configuration validation fails when:

- a spec directory lacks a source lock;
- a source lock lacks a spec directory;
- Packit coverage differs from the 193-recipe inventory;
- a declared auxiliary source lacks a SHA-512 entry in the Fedora `sources`
  manifest;
- stage values are invalid or refer to a package outside the inventory.

All 193 source entries are currently present and validated. Fedora lookaside
may supply an availability mirror or an auxiliary source, but Fedora dist-git
remains the recipe donor rather than the primary payload source.

### Source RPM phase

For each package:

1. Fetch and verify Source0, signatures/checksum manifests where configured,
   and every auxiliary Fedora lookaside source.
2. Stage those files beside the package spec.
3. Run `packit srpm --preserve-spec` in the pinned Packit image.
4. Re-hash every staged source after Packit exits.
5. Validate the SRPM with `rpm -qp`.
6. Record package, NEVRA, source hashes, SRPM digest, Packit image digest, and
   status in a machine-readable result.

Packit's default Git-archive behaviour is never used. A successful Packit exit
without matching post-run hashes is a hard failure. The non-empty SRPM test is
also explicit; an artifact upload is not trusted to detect an empty result by
itself.

### Mock build phase

The source RPM is the only package input to the binary build. Packit invokes
Mock from the same pinned image used for SRPM generation. The Mock root
contains:

- Fedora 44 repositories;
- public Hummingbird packages at the required precedence;
- the repository artifacts from completed earlier stages;
- the Hummingbird-compatible macros and release policy;
- network isolation after dependencies are resolved.

The workflow materialises the exact root configuration for each run and hashes
it before invoking Mock. That digest is part of every package result. Each
package gets an isolated Mock root, and dynamic BuildRequires remain bounded
by Mock rather than by a hand-written direct-`rpmbuild` loop.

### Dependency stages and artifact flow

Stages 0 through 4 retain their current ordering:

- stage 0 contains packages with no in-set dependency. It also contains
  `wayland-protocols`, `accountsservice`, and
  `gsettings-desktop-schemas`;
- stage 1 contains `gtk4`;
- stage 2 contains `libadwaita`, `mutter`, and `gnome-desktop3`;
- stage 3 contains `gnome-shell`, `gnome-session`,
  `gnome-settings-daemon`, `xdg-desktop-portal-gnome`, and
  `malcontent-bootstrap`;
- stage 4 contains `malcontent` and `gnome-control-center`.

`prepare` computes `stage0` through `stage4`, and `rebuild0` through `rebuild4`
consume those outputs as independent matrices. The structure is visible in
[`rebuild-rpms.yml`](../../../.github/workflows/rebuild-rpms.yml#L42-L130)
and the five job definitions
([`rebuild0`](../../../.github/workflows/rebuild-rpms.yml#L226-L443),
[`rebuild1`](../../../.github/workflows/rebuild-rpms.yml#L443-L652),
[`rebuild2`](../../../.github/workflows/rebuild-rpms.yml#L652-L861),
[`rebuild3`](../../../.github/workflows/rebuild-rpms.yml#L861-L1070),
and
[`rebuild4`](../../../.github/workflows/rebuild-rpms.yml#L1070-L1288)).

Workflow artifacts, not a shared filesystem, carry the stage repositories.
Each stage aggregation step:

1. collects the RPMs and reports from its package jobs;
2. runs `createrepo_c` and validates the resulting metadata;
3. uploads the repository tree, `repodata`, and a stage manifest as an
   immutable, run-scoped artifact.

Stage N+1 downloads every prior stage artifact into its runner-local
directory, points a local `[stages]` DNF repository at that directory, and
passes the exact stage manifest into the build record. The existing workflow
demonstrates the artifact hand-off with `download-artifact` and the local
`file:///work/prior` repository
([lines 455--512](../../../.github/workflows/rebuild-rpms.yml#L455-L512)).

Recursive RPM globs are a hard requirement. `rpmbuild --define
"_rpmdir /work/result"` writes to `/work/result/<arch>/`. The incident recorded
in [`targeting-hummingbird.md`](../../targeting-hummingbird.md#L366-L378)
showed that `work/result/*.rpm` silently uploaded no RPMs, while a JSON report
still matched the same artifact. `if-no-files-found: error` therefore reported
success. Both the prior-stage search and the artifact paths must recurse. The
required form is:

```text
work/result/**/*.rpm
work/reports/**/*.json
```

The build itself must also fail if no RPM exists:

```text
test -n "$(find /work/result -name '*.rpm' -type f -print -quit)"
```

The workflow now carries both the recursive upload glob and the explicit
no-RPM test
([lines 423--441](../../../.github/workflows/rebuild-rpms.yml#L423-L441)).
The Packit lane must retain the same rule.

`excludepkgs`, not DNF priority alone, makes an earlier staged build win over
Fedora. The accountsservice failure is the worked example: Fedora's
`accountsservice-libs-23.13.9-16.fc44` was selected even while the stage
repository had `26.27.3` and `[stages]` had priority 1. The recorded failure
was:

```text
cannot install both accountsservice-libs-26.27.3 from stages
and accountsservice-libs-23.13.9-16.fc44 from fedora
```

Stage package names are obtained with `rpm -qp` and passed to the appropriate
repository's `excludepkgs` setting. Priority remains useful for preference; it
is not the correctness gate. This is also documented in
[`targeting-hummingbird.md`](../../targeting-hummingbird.md#L350-L355).

### Scheduling and performance

The target unit of capacity is one GitHub-hosted `ubuntu-26.04` runner. The
published public-repository standard allocation is 4 vCPUs, 16 GB of memory,
14 GB of SSD, and a six-hour job limit. The documentation does not measure
26.04 separately from 24.04, and the allocation is not a measurement of this
factory after migration. Ubuntu 26.04 is in public preview.

PR #32 records the current 24.04 measurement: WebKitGTK took 5 hours 1 minute
as one job, against the six-hour limit. That timing is not 26.04 evidence and
must be re-measured after the runner migration.

The workflow rules are:

- fan out one package per matrix job with `fail-fast: false`;
- retain the free-disk guard using `df --output=avail`, the 20 GiB threshold,
  and conditional 12 GiB swap allocation, then re-prove its threshold on
  26.04. The current guard is in the 24.04 workflow
  ([lines 237--250](../../../.github/workflows/rebuild-rpms.yml#L237-L250));
- shard packages that exceed the runner envelope. PR #32 is the merged
  WebKitGTK precedent: its GTK 4 and GTK 3 ports run on two runners at about
  2.5 hours each instead of one five-hour build;
- shard or cache the large Firefox, GCC, and Mesa workloads rather than
  assuming that a single runner can absorb them;
- use compiler caches only as acceleration inputs. A cache hit must not change
  sources, dependencies, NEVRA, test results, or emitted artifacts.

PR #33 records the cache requirement: the compiler cache must live outside the
build container and survive its exit. The cache is opt-in and may reduce
duration, but a cache miss must produce the same result. The cache rollout and
the individual shard plans for packages other than WebKitGTK remain open
engineering work.

No pod scheduling, node placement, topology spread, pod CIDR, or cross-node
networking is part of this design.

### Workflow gates

`preflight` resolves BuildRequires for packages selected by `prepare` and
uploads a worklist. It is deliberately `continue-on-error: true` and does not
gate a build; later-stage requirements can be absent before their own stage
has completed
([`preflight`](../../../.github/workflows/rebuild-rpms.yml#L132-L225)).

`precedence` waits for all selected rebuild stages, downloads their artifacts,
and fails if a produced RPM does not outrank what Fedora 44 or Hummingbird
already provides. It reports overlaps with Hummingbird separately
([`precedence`](../../../.github/workflows/rebuild-rpms.yml#L1288-L1362)).

`publish` is the publication gate. It requires `precedence` to succeed and
every selected `rebuild0` through `rebuild4` job to succeed or be skipped.
It seeds the repository, removes the bootstrap RPM, creates and signs metadata,
executes the Hummingbird-only consumer transaction, publishes the OCI image,
and uploads the repository artifact
([`publish`](../../../.github/workflows/rebuild-rpms.yml#L1364-L1548)).

### Publication and cutover

The Packit/Mock lane first publishes a candidate repository under a run-scoped
OCI reference. `main` publishes the consumer tag `:latest`; every other ref
publishes under a sanitised branch name
([lines 1488--1533](../../../.github/workflows/rebuild-rpms.yml#L1488-L1533)).
The OCI digest is the primary consumer input. Pages remains a `main`-only
plain-HTTP mirror.

After one complete green proof:

1. compare package inventory and NEVRAs with the existing published repository;
2. run the clean dependency-closure transaction;
3. promote the Packit-built repository through the signed OCI path and Pages
   mirror;
4. make the Packit/Mock workflow the publishing source of truth;
5. remove the duplicated direct-`rpmbuild` binary implementation after a
   second green scheduled run.

No empty commits, skipped tests, or package exclusions are accepted as proof.

## Failure handling

- Source transport failures use the existing bounded retries.
- Digest, signature, missing-source, and post-Packit mutation failures are
  deterministic and are never retried into a green result.
- A Mock infrastructure failure may receive one bounded retry with the same
  SRPM and the same root-configuration digest.
- Matrix peers continue after one package fails because `fail-fast` is false;
  the stage still fails unless every expected package has a valid result.
- A stage repository is not uploaded unless its package count, RPM queries, and
  `repodata` are valid.
- A missing RPM is a build failure, even when a report file exists in the same
  artifact.
- The final workflow fails if any of the 193 package records is absent, any
  RPM is empty or unqueryable, repository metadata is invalid, precedence
  fails, or dependency closure resolution fails.
- `publish` never replaces the coherent repository with a partial matrix.

## Open, and deliberately not asserted

- The current Packit pilot proves the 193-package SRPM lane only. The full
  Packit-to-Mock-to-OCI run described here has not yet been recorded.
- This branch does not contain a checked-in `config/mock.cfg`. The final
  workflow must materialise the exact Hummingbird-compatible Mock root and
  record its digest; equivalence to Hummingbird's own root is not asserted
  until that evidence exists.
- WebKitGTK sharding is proven by PR #32. The shard boundaries for Firefox,
  GCC, and Mesa, and the production cache rollout described by PR #33, are not
  yet proven.
- No final Packit/Mock workflow run URL or final repository OCI digest exists
  as evidence until the binary lane is wired and executed.

## Proof output

The final GitHub Actions run records:

- the workflow run URL and commit/ref;
- expected and completed package counts;
- one artifact manifest per package and per dependency stage;
- one record per source package and every emitted binary RPM;
- source, SRPM, and emitted RPM SHA-512/SHA-256 digests;
- NEVRA, stage, duration, retry count, and runner identity;
- the pinned Packit image digest;
- the exact Mock root-configuration digest;
- stage repository and `repodata` digests;
- the final GHCR repository OCI digest and signature result;
- the Hummingbird-only dependency-closure transaction result.

The run URL, artifact manifests, image digest, Mock configuration digest, and
final OCI digest are the evidence that all RPMs build and that the published
repository is the one that was tested.

## Non-goals

- Packit Service, Copr, Koji, Bodhi, or Testing Farm integration.
- Argo or Kubernetes execution.
- Self-hosted runners.
- A local Zot registry, FSDK containers, USB4 networking, or named build
  nodes.
- Replacing Hummingbird's authoritative buildroot policy.
- Publishing partial repositories.
- Treating successful SRPM creation as proof of a successful binary package.
