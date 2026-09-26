---
name: supply-chain-provenance
description: >-
  Buildroot locking, live package NEVRA snapshots, recipe provenance
  validation, and the factory manifest published beside the OCI digest.
metadata:
  type: procedure
---

# Supply chain provenance and buildroot locking

A factory rebuild is only reviewable if it can say what it consumed. Three
inputs decide the output — the recipe, the source archive, and the build root —
and each of them used to be described by something mutable. This is what pins
them and what the run publishes about them.

## The buildroot lock

[`config/buildroot-lock.json`](../../config/buildroot-lock.json) is the
declarative record of which image a buildroot is, pinned by digest. It carries
`fedora-44` because that is the only root the rebuild runs; entries nothing
consumes are decoration, so do not add one ahead of its caller.

`tools/buildroot_lock.py`:

- `image <name>` prints the locked reference, for inspecting the lock without
  parsing it.
- `snapshot <name> --output <path>` writes every package NEVRA in the image,
  the digest the run resolved (`image`), and the digest the lock expected
  (`locked_image`). `--packages-from <file>` reads `rpm -qa` output captured
  elsewhere instead of running `rpm` here. The lock is never used as the
  resolved image: with no `--image`, `--digest` or `BUILDROOT_DIGEST` the
  snapshot records `image: null` and warns, so an empty digest cannot quietly
  re-assert the lock's provenance. Those three are the *only* inputs — in
  particular `BUILDROOT_IMAGE` is not read: prepare sets it from the pin, and
  `tools/validate.py` forces the lock to equal the pin, so reading it would
  re-assert that pin through a second door.
- `--strict` turns a digest mismatch, and any divergence from a non-empty
  locked package list, into a failure.
- An inventory line that is not three tab-separated fields is dropped, but
  never silently: `parse_packages` warns on stderr naming the dropped lines,
  and `--strict` refuses the snapshot outright. A truncated or corrupted
  `rpm -qa` capture makes the snapshot under-report the root's contents, and a
  snapshot that under-reports cannot answer the question `--strict` asks — the
  packages it could not read might be the divergence.
- A lock entry with no `nevra` is reported as a malformed lock, not as a
  missing package. `load_lock` only checks that `packages` is a list (the
  per-entry requirement lives in `tools/validate.py`), so running this module
  standalone against a hand-edited lock can reach the comparison with an
  unusable entry; it names the defect instead of raising.

**The rebuild does not pass `--strict`, deliberately.** With the factory
mirror pin (`ghcr.io/projectbluefin/utah-buildroot`) prepare pulls the exact
digest or fails, so the resolved and locked digests agree. A legacy
`quay.io/fedora/fedora:44` pin pulls the moving tag and only warns when it
moved, because failing on it recreates the outage
[`repeated-mistakes.md`](repeated-mistakes.md) section 7 records — thirty-seven
jobs dead mid-run on a pin that was correct when the run started. The snapshot
follows prepare and records the drift; `--strict` is for an operator asking
whether a root is exactly what was locked.

**The digest is written twice** — in the lock and in
[`config/buildroot-image`](../../config/buildroot-image), the pin prepare
pulls — because the manifest needs the declarative record and the pin file
holds exactly one reference and nothing else. Two copies of one digest drift,
so:

- `tools/buildroot_pin.py set`, which the weekly `refresh-buildroot.yml` runs,
  moves both. It reads the lock first, so a lock it cannot parse fails the
  move instead of leaving the pin moved alone. A locked `packages` list is left
  as it was: it described the old root, and `snapshot --strict` should say so.
- `tools/validate.py` fails `just check` when any locked buildroot is not
  exactly the pinned reference, tag and digest, or when there is no pin.

Renovate does not track either copy. It used to move `quay.io/fedora/fedora:44`
in the workflow; the factory now mirrors that image itself, and a quay.io
digest pin rots (`tests/test_renovate_coverage.py`).

## What the snapshot describes

The snapshot is the pinned image's own package set: preflight runs `rpm -qa`
first, before it adds repositories or installs anything. That is the set the
recorded digest names, so the NEVRA list and the digest beside it make one
claim about one thing.

It is not the root any package was built in, and it does not pretend to be.
The hermetic lane resolves each package's root in mock from its real
BuildRequires and uploads it, NEVRA by NEVRA with its URL, as
`lock-s<N>-<package>` (`buildroot_lock.json`, with the image recorded as the
bootstrap by digest). The container lane installs `@buildsys-build` and the
BuildRequires on top of this image, and its post-builddep `rpm -qa` is what
the package cache key hashes. Read the snapshot as the shared base those roots
start from.

## The snapshot runs on the runner

`rpm -qa` runs inside the build root; the JSON is assembled outside it. The
root is a Fedora container that carries no interpreter this factory may assume,
and installing one so the root can inventory itself would change the set being
inventoried. Extend `parse_packages`, not the container.

## Recipe provenance

Every recipe in `packages/<name>/` carries `.hummingbird-upstream.json`, and
`tools/validate.py` rejects the tree without it:

- **`branch: rawhide`** — the Fedora dist-git snapshot, pinned by full
  40-character `commit` and `tree` SHAs. An abbreviated SHA is not a pin: it
  is ambiguous and it is not what `git` resolved at import.
- **`branch: upstream`** — imported from the project's own release repository,
  so it carries a non-empty `remote` and no dist-git `commit`/`tree`. Its
  source lock lives in `config/upstream-sources.json` instead.

Do not hand-edit these files. Re-import; editing provenance makes a recipe
claim an origin it does not have.

## Source verification reporting

`tools/source_pipeline.py` records how each accepted source was verified:

| `verification` | `checksum_only` | Meaning |
| --- | --- | --- |
| `signature` | `false` | Upstream supplied a signature and it verified |
| `sha256-manifest` | `true` | Upstream published checksums, not a signature |
| `sha512` | `true` | Only the locked SHA-512 stands behind the bytes |

A checksum is not a signature. `tools/factory_manifest.py` counts each kind and
names the packages in the checksum-only classes under `source_verification`, so
the exceptions are a list to shorten rather than a property to grep for.

## The manifest

`tools/factory_manifest.py` writes `manifest.json` beside the repository: the
published RPMs, the source reports and their verification summary, the
buildroot snapshots, the lock itself, and the published OCI reference and
digest. Every publication in `.github/workflows/publish-repository.yml` writes
it twice — once before the container build, so it ships inside the image, and
once after, when the OCI digest exists — and uploads it as
`factory-manifest` (the final publication) or `factory-manifest-wave<N>` (an
early one), prefixed like every other artifact of the run.

Its sources are `repository/reports`, so those reports move the way the RPMs
do. `publish_gate.py assemble` decides which packages this publication
replaced; their fresh reports come from `built/reports` (each package's
`rpm-s<N>-<package>` artifact), a failed or losing package keeps the report it
was published with, and a pruned source loses its report with its RPMs.

Reports are classified by shape, not by filename: a buildroot snapshot is
`schema`+`name`+`packages`, a source report carries `package`. Unrelated JSON
published beside the repository is not folded in.

### A buildroot snapshot has to belong to the run that publishes it

`buildroots` is the one part of the manifest that attests rather than
describes: it says which root *this* run built in. That claim has a way of
going stale. Publish seeds `repository/` from the previously published factory
image, that image was built `COPY repository /repository` with the last run's
`reports/` inside it, and preflight — which writes the replacement — is skipped
outright when `build_list` is `[]` and downloads `continue-on-error`. So a
cleanup-only run, or any run whose preflight failed, can reach the manifest
step with last week's snapshot on disk and nothing marking it as someone
else's.

Two things stop it, and they are independent on purpose:

* the seed step deletes `repository/reports/buildroot-*.json` straight after
  the `podman cp`, so only this run's `preflight-buildroot` artifact can put
  one back. Source reports are left alone — they describe the seeded RPMs,
  which really are in the repository being published;
* `factory_manifest.py --buildroot-digest` keeps a snapshot only when the image
  it resolved carries the digest `prepare` resolved. Anything else is named
  under `buildroots_discarded` with a reason, and warned about on stderr.
  `rebuild-rpms.yml` hands that digest to every publication as
  `buildroot_digest`, and every publication `needs: preflight`, so an early
  one cannot run before the snapshot it would attest has been uploaded.

Withheld, not silently dropped: "no root was measured" and "a root was measured
and not attested" are different answers to the question asked after a bad
package ships. With no `--buildroot-digest` — standalone use, or a run whose
own digest resolution failed — nothing can be judged and nothing is discarded;
that case is covered by the prune, not by the tool.
