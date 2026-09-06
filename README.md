# utah-packages

GNOME 51 and the rest of the desktop stack, built from verified upstream sources
for [Fedora Hummingbird](https://packages.redhat.com), and published as an OCI
image for [projectbluefin/utah](https://github.com/projectbluefin/utah) to
consume.

Hummingbird supplies a hardened, fast-moving bootable base and no desktop at
all. This is where the desktop comes from.

## Related repositories

Utahraptor is two repositories, the same way `common` and `brew` already work:

| Repository | What it does |
|---|---|
| [`projectbluefin/utah`](https://github.com/projectbluefin/utah) | Composes the image. |
| [`projectbluefin/utah-packages`](https://github.com/projectbluefin/utah-packages) | This one. Builds GNOME 51 and the rest of the desktop stack from verified upstream sources, and publishes them as an OCI image. |

The seam between them is a digest, not a branch: this repository publishes
`ghcr.io/OWNER/utah-packages`, and Utah consumes it with `COPY --from=` pinned
by digest. Every branch here publishes under its own name, so Utah can be built
against a package set before either side is merged.

**Experimental pre-alpha**, alongside Utah itself.

It does **not** rebuild Fedora Rawhide. Fedora dist-git seeds the RPM recipes and
patches; the sources are then fetched from upstream and verified against recorded
digests, built on GitHub-hosted runners against a Hummingbird plus Fedora 44 build
root, and published as a coherent overlay.

## What it produces

`ghcr.io/OWNER/utah-packages` — an image whose only content is the
`createrepo_c` output, consumed with `COPY --from=` pinned by digest, the same
way Utah already pulls `projectbluefin/common` and `ublue-os/brew`. `main`
publishes `:latest`; every other branch publishes under its own name, so an
image can be built against a package set before either is merged.

A GitHub Pages mirror used to be published alongside it. It was removed: it
could only deploy from `main`, nothing consumed it, and the OCI image is the
contract.

Packages are tagged `.hum1.bfin` — the vendor release and dist, then our suffix,
following AlmaLinux's convention. See
[docs/targeting-hummingbird.md](docs/targeting-hummingbird.md) for the ordering
rules and the `precedence` job that enforces them.

## Initial scope

`config/bootstrap-packages.txt` is a dependency-first recipe-seeding set
covering the Fedora components that blocked Utah: FUSE, NTFS, device-mapper
persistent data, UDisks, librsvg, glycin, GVFS, GNOME, Firefox, and Distrobox.

The RPM workflow locks source checksums, rebuilds each package in staged
matrix jobs, creates repodata, keylessly signs `repomd.xml` using GitHub
OIDC/Cosign, and publishes the result as an OCI image. Pull requests from
forks never publish RPMs or images.

The build does **not** currently run in Mock, despite installing it. See
*Agreed direction* in [docs/architecture.md](docs/architecture.md).

## Hummingbird-compatible freshness model

Rawhide and Fedora dist-git can be behind upstream: a maintainer may not have
pushed a spec change yet, or its build may not have completed. This factory
therefore follows Hummingbird's direct-source model for **every RPM it builds**:

1. The Fedora spec and patches are a bootstrap seed, never the release-update
   feed.
2. `source_pipeline.py` fetches each configured release archive or signed git
   tag directly from its upstream URL. It records SHA-512, verifies a configured
   checksum/signature, writes a report, and fails closed before the source is
   allowed into a build.
3. A package lacking a direct-source policy is not eligible for builds or
   publication. Fedora Rawhide is retained solely as a compatibility build root
   while the factory becomes self-hosting.

The source watcher runs at a best-effort cadence; GitHub does not guarantee
execution time for scheduled jobs. A source candidate is built, tested, and only
then published. Failed verification leaves the previous source unchanged.

## Import and fork upstream packages

`Import Rawhide package` imports a Fedora dist-git's `rawhide` branch into
`packages/<name>/`, recording its remote, immutable commit, tree ID, and import
time in `.hummingbird-upstream.json`. It is the initial spec/patch seed only;
the direct source pipeline owns all later source updates. The workflow opens a
pull request so downstream patches are explicit and reviewable before the
package enters a rebuild set.

`config/upstream-sources.json` is the allow-list for packages that need to lead
Fedora. Each entry supplies its release URL, immutable SHA-512, and, whenever
the upstream offers it, a release-signature URL plus pinned GPG key. It
deliberately contains no entries until each package has an agreed source URL
and verification policy; that is a deliberate admission gate, not a Rawhide
fallback.

Each release-tracked entry uses `version` plus `url_template` (with
`{version}`), and a `renovate` object containing its `datasource` and `depName`.
Renovate therefore proposes updates from the real upstream. Its
`upstream-source` PRs can automerge only after the verified RPM build gate; the
pipeline refuses publication until the PR also records the newly downloaded
source digest (and signature result, when configured).

This is an in-factory fork with upstream provenance. Mirroring each source into
an independent GitHub repository is intentionally optional: GitHub Actions'
`GITHUB_TOKEN` cannot create repositories. It can be added later with a
dedicated, narrowly scoped repository-creation credential.

See [architecture](docs/architecture.md) and [contributing](docs/contributing.md).

## Working on this repository

Humans start at [contributing](docs/contributing.md). Agents start at
[`AGENTS.md`](AGENTS.md), then the skill router at
[`docs/SKILL.md`](docs/SKILL.md).

This repository is onboarded to the Project Bluefin factory model.
`projectbluefin/common` supplies the factory-wide contract as a sidecar pinned
by commit in [`config/factory-contract.json`](config/factory-contract.json);
`AGENTS.md` remains authoritative for anything local. `just check` enforces the
parts of that contract the tree can prove: the skill router indexes every
skill, skills carry front-matter, `AGENTS.md` states the self-improvement
mandate, no changelog or session-notes file is committed, and every relative
documentation link resolves.

```sh
just check   # factory contract + package configuration
just test    # pytest
```

## Hummingbird availability measurement

`Recalculate Hummingbird package gaps` runs every six hours. It pulls the
Hummingbird bootc image to inspect its installed RPM database, queries the live
Hummingbird repository separately, and compares their union to Bluefin's
package contract. Its artifact distinguishes packages already installed in the
base image, packages newly available from the repository, and genuine gaps.

## Rawhide bootstrap policy

Fedora Rawhide is permitted only inside an isolated buildroot: it supplies the
compiler, build macros, and bootstrap BuildRequires needed to introduce a
Hummingbird gap. Package source archives still come directly from their
upstreams and are verified before build; the resulting repository, not Rawhide,
is used by consumer images and subsequent cross-package builds.
