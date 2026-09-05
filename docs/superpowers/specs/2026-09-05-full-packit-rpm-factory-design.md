# Full Packit RPM factory

## Status

Approved for implementation by the maintainer's explicit instruction to stop
planning-only work, move directly on `main`, make Packit fully operational, and
prove that every RPM builds.

## Definition of done

The factory is complete only when one recorded run proves all of the following:

1. All 193 package recipe directories have a SHA-512-locked source definition
   and a root Packit monorepo entry.
2. Packit produces a source RPM for every recipe without changing any verified
   source after the verification gate.
3. Packit invokes Mock for every source RPM against the Hummingbird-compatible
   build root.
4. The existing dependency stages complete in order and later stages consume
   the repository produced by earlier stages.
5. Every expected source package reports a successful binary build, every
   emitted RPM is queryable, repository metadata is valid, and a clean
   dependency-closure transaction resolves against the final repository.
6. The final repository is published through the existing OCI and Pages paths
   with a manifest tying every package result to source hashes, Packit image
   digest, Mock configuration, workflow run, and repository digest.

An SRPM-only run is useful evidence but does not satisfy this definition.

## Current gap

- 193 package directories contain specs.
- 180 packages are present in `config/upstream-sources.json`.
- 54 packages are present in the root `.packit.yaml`.
- The existing binary workflow uses five dependency stages but calls
  `rpmbuild` directly in a Fedora container.
- These 13 recipes do not yet have source locks:
  `dracut`, `evolution-ews`, `firewalld`, `fish`, `gcc`, `git`,
  `intel-media-driver-free`, `ntfs-3g`, `openssh`, `rust-bootupd`,
  `shared-mime-info`, `tailscale`, and `zsh`.

The 54-package Argo SRPM lane is proven independently: run
`utah-srpm-cjzrv` completed 54/54 packages successfully in 93 seconds across
`ghost` and `exo-0`.

## Considered approaches

### 1. Keep the existing binary builder and use Packit only for SRPMs

This is the lowest-risk migration, but it does not make Packit the operational
build interface. The hand-written `rpmbuild -br`/`-ba` implementation remains
the real factory, so failures can diverge between the Packit proof lane and
published RPMs.

### 2. Split Packit SRPM generation from Packit Mock builds

This is the selected design. Packit first creates a source RPM from verified
sources. The workflow verifies source integrity and SRPM metadata, then passes
that exact file to `packit build --srpm <file> in-mock`. This keeps the source
gate independently testable, permits SRPM reuse on Mock retries, and makes
Packit the interface for both source and binary builds without coupling the
two failure domains.

### 3. Adopt Packit Service, Copr, or Koji

Rejected. The repository already owns source verification, Hummingbird build
root composition, dependency staging, signing, and publication. Moving those
responsibilities to Fedora services would weaken the factory's provenance
model and prevent branch-local repository testing.

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

The 13 missing locks are imported from their upstream release artifacts and
verified with SHA-512. Fedora lookaside may supply an availability mirror or
an auxiliary source, but Fedora dist-git remains the recipe donor rather than
the primary payload source.

### Source RPM phase

For each package:

1. Fetch and verify Source0, signatures/checksum manifests where configured,
   and every auxiliary Fedora lookaside source.
2. Stage those files beside the package spec.
3. Run `packit srpm --preserve-spec`.
4. Re-hash every staged source after Packit exits.
5. Validate the SRPM with `rpm -qp`.
6. Record package, NEVRA, source hashes, SRPM digest, Packit image digest, and
   status in a machine-readable result.

Packit's default Git-archive behavior is never used. A successful Packit exit
without matching post-run hashes is a hard failure.

### Mock build phase

The source RPM is the only input to the binary build:

```text
packit build --srpm <package.src.rpm> in-mock \
  --root <generated-hummingbird-mock.cfg> \
  --resultdir <result-directory>
```

The Mock configuration is checked into `config/` and derived from
Hummingbird's authoritative buildroot contract:

- Fedora 44 repositories;
- public Hummingbird packages at higher priority;
- the repository produced by completed earlier stages;
- network isolation for the build itself after dependencies are resolved;
- the Hummingbird-compatible macros and release policy already enforced by
  this factory.

Each package gets an isolated Mock root. Dynamic BuildRequires remain bounded
by Mock rather than by the workflow's current hand-written retry loop.

### Dependency stages and artifact flow

Stages 0 through 4 retain their current ordering. Packages within one stage
build in parallel; stage N+1 cannot start until stage N has:

1. validated every package result;
2. created repository metadata;
3. published an immutable stage repository artifact.

The lab has no shared RWX filesystem. Stage repositories and per-package
results therefore use the writable local Zot as OCI artifacts. Each artifact
is addressed by workflow UID, stage, package, and content digest. Build pods
on either node pull prior-stage repository artifacts from Zot; pod CIDR
traffic between `ghost` and `exo-0` automatically follows the configured
40-Gbps USB4 route. The workflow does not add a brittle USB4 admission gate:
if the link is unavailable, Kubernetes networking may continue over Ethernet,
while correctness remains unchanged.

### Scheduling and performance

- SRPM validation: 12 concurrent package pods, matching the proven live lane.
- Mock builds: begin with eight concurrent builders, four per node through a
  `ScheduleAnyway` hostname topology spread.
- Each Mock pod requests resources appropriate to its package class. Large
  packages such as Firefox, GCC, Mesa, GTK, and Mutter use a larger class;
  ordinary packages use the default class.
- The digest-pinned Packit image is mirrored into local Zot and pulled with
  `IfNotPresent`.
- Source archives and package-manager metadata use node-local
  content-addressed caches. Final outputs never depend on those caches.
- Cross-workflow semaphores cap SRPM and Mock concurrency independently so
  overlapping runs cannot exhaust the cluster.

Concurrency is raised only from observed CPU, memory, I/O, and duration data.
The proof run records per-package duration and node placement.

### Publication and cutover

The new Packit/Mock lane initially publishes a candidate repository under a
run-specific OCI reference. The existing builder remains intact during parity
testing.

After one complete green proof:

1. compare package inventory and NEVRAs with the old pipeline;
2. run the clean dependency-closure transaction;
3. promote the Packit-built repository through the existing signed OCI
   `latest` path and Pages mirror;
4. make the Packit/Mock workflow the publishing source of truth;
5. retain the old workflow temporarily as a manual fallback, then remove its
   duplicated binary-build implementation after a second green scheduled run.

No empty commits, skipped tests, or package exclusions are accepted as proof.

## Failure handling

- Source transport failures use the existing bounded retries.
- Digest, signature, missing-source, and post-Packit mutation failures are
  deterministic and are never retried into a green result.
- Mock infrastructure failures receive one bounded retry with the same SRPM.
- Package failures do not cancel peers in the same stage.
- A stage repository is not published unless every package in that stage is
  successful.
- The final workflow fails if any of the 193 package records is absent, any
  RPM is empty or unqueryable, repository metadata is invalid, or dependency
  closure resolution fails.

## Proof output

The final manifest contains:

- expected and completed package counts;
- one record per source package and every emitted binary RPM;
- source and SRPM SHA-512/SHA-256 digests;
- NEVRA, stage, node, duration, and retry count;
- Packit image and Mock configuration digests;
- stage repository digests;
- final repository OCI digest;
- dependency-closure transaction result.

The run URL plus this manifest is the evidence that all RPMs build.

## Non-goals

- Packit Service, Copr, Koji, Bodhi, or Testing Farm integration.
- Replacing Hummingbird's authoritative buildroot policy.
- Publishing partial repositories.
- Treating successful SRPM creation as proof of a successful binary package.
