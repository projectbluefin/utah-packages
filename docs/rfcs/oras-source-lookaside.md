# RFC: Content-addressed ORAS source lookaside

**Status:** Draft  
**Tracking issue:** [#26](https://github.com/projectbluefin/utah-packages/issues/26)

## Decision to make

Define a last-resort Project Bluefin source lookaside for archived or
unreliably hosted source artifacts, without making it a substitute for the
upstream projects or Fedora's dist-git lookaside.

## Current source policy

1. A package recipe is copied from a pinned Fedora dist-git commit.
2. Its `Source0` is fetched from the upstream project whenever possible.
3. The factory verifies the immutable SHA-512 recorded in
   `config/upstream-sources.json`, plus upstream signatures/checksum manifests
   where available.
4. Fedora's content-addressed lookaside may be an explicit transport fallback
   for source inputs in Fedora dist-git.

The source pipeline never accepts a file whose configured SHA-512 differs,
regardless of which URL delivered it.

## Proposal

Add an **explicit, digest-pinned ORAS fallback** only when both upstream and
an applicable Fedora lookaside object are unavailable. It must use an OCI
artifact reference by digest, never a mutable tag.

The intended precedence is:

1. Upstream release URL.
2. Explicit Fedora lookaside fallback.
3. Explicit Project Bluefin ORAS fallback.

The ordinary build workflow must only consume the cache. A distinct, manually
approved cache-publication workflow would be the only writer.

## Artifact and provenance contract

One cached source artifact must contain:

- the source file with its original filename;
- a machine-readable provenance statement containing package name, version,
  original upstream URL, optional Fedora lookaside URL, retrieval time,
  SHA-512, and upstream signature/checksum evidence when present;
- the originating Fedora dist-git commit and tree when the recipe came from
  Fedora;
- the OCI artifact digest and keyless signature identity.

Consumer configuration must record both the OCI digest and the source
SHA-512. Retrieval verifies the OCI digest, extracts only the declared file,
and verifies the SHA-512 before the build can use it.

## Cache publication requirements

The cache-publication workflow must:

1. Require a human-approved dispatch containing the target package/source.
2. Fetch the source from its primary upstream or explicit Fedora fallback.
3. Verify SHA-512 and any configured upstream signature/checksum evidence.
4. Generate and attach provenance before publication.
5. Push an OCI artifact under an immutable digest and keylessly sign it.
6. Emit a reviewable receipt that can be copied into source configuration.

It must not update ordinary package configuration or a mutable cache tag.

## Fail-closed behavior

- A successful download with a checksum mismatch is a hard failure; no later
  mirror may be tried.
- A missing ORAS artifact, bad signature, bad OCI digest, missing provenance,
  or SHA-512 mismatch is a hard failure.
- The build must state the resolved transport URL/artifact digest in its source
  report.

## Non-goals

- Implementing or populating this cache in this RFC.
- Mirroring all upstream releases.
- Changing Fedora dist-git recipe provenance.
- Permitting unpinned `latest`/branch references for cached source retrieval.

## Open questions

1. Should cached sources live in one repository with package/version labels or
   in one OCI repository per package?
2. What retention policy protects reproducibility while permitting removal of
   accidental or legally invalid uploads?
3. Which sigstore identity and repository policy should consumers require?
4. Should an SBOM-style attestation supplement the source provenance statement?

## Acceptance criteria for a later implementation

- [ ] Document the final OCI layout and provenance schema.
- [ ] Add cache-publication authorization and a keyless signing policy.
- [ ] Add digest-pinned ORAS retrieval with fail-closed tests.
- [ ] Prove upstream-first, Fedora-second, ORAS-third selection.
- [ ] Prove a checksum mismatch never falls through to another transport.
- [ ] Demonstrate recovery for an unavailable upstream source without changing
      the accepted source bytes.
