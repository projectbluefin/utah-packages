# RFC: Content-addressed ORAS source lookaside

**Status:** Proposed (design only)
**Tracking issue:** [#26](https://github.com/projectbluefin/utah-packages/issues/26)

## Decision

Add a digest-pinned Project Bluefin source cache as the last availability
fallback for a direct upstream source. The cache is not a second source of
truth: the configured source SHA-512, upstream evidence, and Fedora recipe
provenance remain authoritative.

This RFC defines the contract only. It does not add an ORAS client, publish an
artifact, or add an ORAS entry to `config/upstream-sources.json`.

## Source precedence and invariants

A source lock has one integrity contract and an ordered set of transports:

1. the direct upstream release URL;
2. explicitly configured Fedora dist-git lookaside URL(s), when the recipe is
   from Fedora dist-git;
3. one explicitly configured ORAS artifact, addressed by its OCI manifest
   digest.

The order is availability-only. A lower-precedence transport is eligible only
when the higher-precedence transport is unavailable. It is never a second
attempt to repair an integrity failure.

The future source-lock shape is illustrative; this RFC adds no live `oras`
blocks:

```json
{
  "name": "example",
  "version": "1.2.3",
  "url": "https://upstream.example/releases/example-1.2.3.tar.xz",
  "filename": "example-1.2.3.tar.xz",
  "sha512": "<128 lowercase hexadecimal characters>",
  "fallback_urls": [
    "https://src.fedoraproject.org/repo/pkgs/rpms/example/example-1.2.3.tar.xz/sha512/<sha512>/example-1.2.3.tar.xz"
  ],
  "oras": {
    "artifact": "ghcr.io/projectbluefin/utah-source-cache/example@sha256:<64 lowercase hexadecimal characters>",
    "provenance": "ghcr.io/projectbluefin/utah-source-cache/example@sha256:<64 lowercase hexadecimal characters>"
  }
}
```

`fallback_urls` remains explicit configuration; the consumer must not invent a
Fedora URL from a package name. The `oras.artifact` and `oras.provenance`
references must contain `@sha256:...`, never a tag. The digest in each
reference is the digest the consumer verifies; no `latest`, branch, or mutable
version reference is accepted. The source filename and top-level SHA-512 are
copied into the provenance and must agree with the lock.

Generated sources and recipes with `no_upstream_source` are outside this RFC.
They have different provenance contracts and must not silently become ORAS
inputs.

### Fallback decision table

| Result from the current transport | Action |
| --- | --- |
| DNS failure, timeout, connection failure, HTTP 404/410, or HTTP 5xx | Try the next explicitly configured transport. |
| Bytes received but SHA-512 differs | Reject the source and stop. Do not try another transport. |
| Configured upstream signature or checksum evidence fails | Reject the source and stop. Do not try another transport. |
| Invalid source-lock shape or malformed URL | Reject the configuration and stop. Do not hide the error with a fallback. |
| Unauthorized response, HTTP 401/403 | **Required future change.** Reject the configuration and stop. Do not hide the error with a fallback. |
| ORAS artifact is missing or any OCI/provenance/signature check fails | Reject the source and stop. There is no fourth transport. |

The 401/403 row does not describe today's pipeline. `fetch`
(`tools/source_pipeline.py`) catches `urllib.error.URLError`, and
`urllib.error.HTTPError` is a subclass of it, so a 401 or 403 is currently
retried like a transport failure and then re-raised as a `RuntimeError`, which
`fetch_with_fallbacks` treats as grounds for trying the next mirror. Making an
authorization failure stop the run requires distinguishing `HTTPError` status
codes in `fetch` and raising a non-retriable error that `fetch_with_fallbacks`
does not absorb. That change, with its tests, is a prerequisite for the first
`oras` source-lock block and is not delivered by this RFC.

A candidate is written to a temporary path. It is renamed into the build input
only after all applicable checks pass; every rejected candidate is removed.
The source report records the accepted transport and, for ORAS, both pinned
artifact references.

## OCI artifact layout

The cache stores the original source bytes without unpacking, recompressing, or
renaming them. One source object is an OCI artifact manifest with:

- `artifactType`: `application/vnd.projectbluefin.source.v1`;
- an empty OCI config descriptor;
- exactly one layer containing the raw source bytes;
- the layer annotation
  `org.opencontainers.image.title=<source filename>`;
- the layer media type `application/vnd.projectbluefin.source.v1`; and
- the layer's normal OCI SHA-256 blob digest and byte size.

The digest pinned in the source lock is the SHA-256 digest of this OCI
**manifest**, not the SHA-512 source digest and not merely the layer digest.
The consumer must fetch by that digest, hash the returned canonical manifest,
and compare the result to the configured `@sha256:...` before reading the
layer. The ORAS client must also verify the layer digest while downloading.

The signed provenance is a separate OCI referrer to the source manifest:

```text
ghcr.io/projectbluefin/utah-source-cache/example@sha256:<source-manifest-D>
  └── source artifact manifest D
      └── one raw-source layer

provenance referrer P
  ├── subject: source-manifest-D
  ├── artifactType: application/vnd.projectbluefin.source-provenance.v1
  └── one JSON provenance layer
```

Separating the provenance referrer avoids an impossible self-reference: a
manifest cannot contain its own digest because changing the provenance bytes
would change the manifest digest. The source lock therefore pins both the
source artifact digest and the provenance referrer digest. The provenance
referrer's OCI `subject.digest` and its `cache.artifact_digest` field must both
equal `D`.

The consumer accepts exactly one source layer and the declared filename. It
rejects extra layers, a missing or ambiguous title, path separators in the
filename, and any archive extraction attempt. The source archive is a blob,
not an OCI filesystem to unpack.

Both `D` and the pinned provenance referrer are signed with Sigstore Cosign.
Verification requires a valid transparency-log bundle and the publication
workflow identity defined below. A signature over an unpinned tag is not
sufficient.

## Provenance schema

The provenance layer is UTF-8 JSON with no unknown top-level or nested fields.
Its schema version is part of the signed bytes. The required shape is:

```json
{
  "schema": "https://projectbluefin.io/schemas/source-provenance/v1",
  "schema_version": 1,
  "source": {
    "package": "example",
    "version": "1.2.3",
    "filename": "example-1.2.3.tar.xz",
    "upstream_url": "https://upstream.example/releases/example-1.2.3.tar.xz",
    "sha512": "<128 lowercase hexadecimal characters>"
  },
  "retrieval": [
    {
      "kind": "upstream",
      "url": "https://upstream.example/releases/example-1.2.3.tar.xz",
      "attempted_at": "2026-09-18T12:00:00Z",
      "outcome": "unavailable"
    },
    {
      "kind": "fedora-lookaside",
      "url": "https://src.fedoraproject.org/repo/pkgs/rpms/example/example-1.2.3.tar.xz/sha512/<sha512>/example-1.2.3.tar.xz",
      "attempted_at": "2026-09-18T12:00:04Z",
      "outcome": "accepted"
    }
  ],
  "integrity_evidence": {
    "signature": null,
    "checksum_manifest": {
      "url": "https://upstream.example/releases/SHA256SUMS",
      "algorithm": "sha256",
      "entry": "<64 lowercase hexadecimal characters>  example-1.2.3.tar.xz",
      "verified_at": "2026-09-18T12:00:05Z"
    }
  },
  "fedora_dist_git": {
    "commit": "<40 lowercase hexadecimal characters>",
    "tree": "<40 lowercase hexadecimal characters>"
  },
  "cache": {
    "artifact_digest": "sha256:<64 lowercase hexadecimal characters>",
    "published_at": "2026-09-18T12:00:10Z"
  }
}
```

The schema rules are:

- `source.package`, `source.filename`, `source.upstream_url`, and
  `source.sha512` are required. `source.version` is required when the source
  lock has a version and is `null` only for a lock that has none.
- `source.upstream_url` is the original configured URL, not a redirect target
  or an ORAS URL. `source.sha512` is the build lock's expected digest.
- `retrieval` is an ordered, non-empty record of every upstream and explicitly
  configured Fedora attempt made by the publisher. Each entry has an RFC 3339
  UTC `attempted_at`; exactly one entry has `outcome: accepted`, and its bytes
  are the bytes in the source layer. An unavailable attempt is retained rather
  than erased, so the upstream/fallback retrieval timestamps are auditable.
- `integrity_evidence.signature` and
  `integrity_evidence.checksum_manifest` are nullable because upstreams do not
  all publish both. When the source lock configures either one, the matching
  object is required and its verification timestamp and evidence URL must be
  present. SHA-512 verification is mandatory even when both are null.
- `fedora_dist_git` is the exact `commit` and `tree` from the recipe's
  `.hummingbird-upstream.json`, or `null` for a non-Fedora recipe. It is never
  copied from an unpinned branch name.
- `cache.artifact_digest` is `D`, the source OCI manifest digest. It must agree
  with the source-lock artifact reference and the provenance referrer's
  `subject.digest`.
- All digest strings are lowercase and algorithm-qualified where they are
  OCI digests. Timestamps are UTC. Unknown fields, duplicate retrievals, a
  second accepted transport, or mismatched package/filename/hash values are
  verification failures.

The provenance object does not contain a digest of itself. Its referrer
manifest is pinned separately, and the source artifact digest is the signed
subject that it records.

## Authorized publication workflow

A separate `workflow_dispatch` workflow is the only cache writer. It runs only
from the reviewed repository workflow on `main`, uses a protected
`source-cache-publication` environment with required human reviewers, and has
no `pull_request`, `push`, schedule, or reusable-workflow trigger. Its job
permissions are limited to repository read, `packages: write`, and
`id-token: write`; normal build and validation workflows receive neither
package write nor signing-token permission.

The dispatch inputs identify a package and source lock, not arbitrary bytes or
a mutable tag. The workflow:

1. reads the reviewed lock and Fedora provenance at the selected commit;
2. tries the direct upstream URL and explicit Fedora fallback using the
   availability-only rules above;
3. verifies the configured SHA-512 and every configured signature/checksum
   requirement before staging anything;
4. records all retrieval attempts and produces the provenance JSON;
5. publishes the exact bytes as the one-layer source artifact;
6. resolves the resulting manifest digest `D`, writes `D` into the provenance
   referrer, and publishes that referrer;
7. signs `D` and the provenance referrer with Cosign keylessly, requiring the
   GitHub OIDC issuer
   `https://token.actions.githubusercontent.com` and the certificate identity
   for
   `projectbluefin/utah-packages/.github/workflows/publish-source-cache.yml`
   on `refs/heads/main`;
8. emits a receipt containing the two digest-pinned references, signature
   identities, source SHA-512, and provenance; and
9. removes any run-scoped staging tag before finishing.

The staging tag is an implementation detail of the registry upload and is
never written to consumer configuration. The receipt is reviewed separately;
only that review may add the digest pins to a source-lock PR. The publication
workflow never edits normal package configuration and never reads an existing
ORAS artifact as its source bytes.

If neither upstream nor an explicit Fedora fallback can provide verifiable
bytes, publication stops. A maintainer must restore an independently
verifiable input before an artifact can be created; the workflow cannot be
used to bless an unchecked upload.

### Retention and deletion

- A source artifact referenced by any merged source lock or release is retained
  indefinitely. There is no age-based deletion of a referenced digest.
- An unreferenced run-scoped upload is deleted after 30 days. Failed or
  unsigned uploads are not eligible for consumer configuration.
- A digest with legal, security, or provenance problems is quarantined
  immediately. Deletion requires a maintainer-approved audit record and a
  source-lock change removing every reference; the digest is never silently
  replaced by a mutable tag.
- Maintainers review the unreferenced inventory at least quarterly. Registry
  garbage collection is not treated as a reproducibility mechanism; referenced
  digests must remain addressable in GHCR for the life of their locks.

## Fail-closed verification tests

This RFC does not add an ORAS implementation or contact GHCR. The existing
source-pipeline tests already establish the integrity boundary — a fetched
source that is present but wrong never falls through to another transport — and
the fallback-bytes test records the unavailable-upstream demonstration without
network access:

- `SourcePipelineTests.test_uses_upstream_without_touching_fallback` proves
  upstream success does not consult a fallback.
- `SourcePipelineTests.test_uses_fallback_only_after_upstream_transport_failure`
  simulates an unavailable upstream, accepts a deterministic fallback payload,
  and verifies the exact bytes and SHA-512 delivered to the candidate path.
- `FetchRetryTests.test_a_digest_mismatch_never_falls_back_to_another_url`
  proves a successful but wrong source fails closed instead of trying a later
  transport.
- `BundledSourceTests.test_digest_mismatch_rejects_and_leaves_no_candidate_behind`
  proves a mismatched Fedora lookaside object is removed and never staged.
- `SourcePipelineTests.test_rejects_source_overwritten_after_staging`
  proves the build input is re-hashed after the staging boundary.

No existing test covers the 401/403 stop rule, because the pipeline does not
implement it yet.

Before enabling the first `oras` source-lock block, its implementation PR must
add deterministic tests for the following cases using a local registry/client
fixture:

| Case | Required assertion |
| --- | --- |
| Upstream available | Fedora and ORAS are not contacted. |
| Upstream unavailable, Fedora available | The Fedora bytes are accepted; ORAS is not contacted; bytes equal the configured SHA-512. |
| Upstream and Fedora unavailable | The digest-pinned ORAS object is attempted. |
| Any successful transport returns the wrong SHA-512 | The run fails and no lower-precedence transport is contacted. |
| A transport answers HTTP 401 or 403 | The run fails, the error names the authorization failure, and no lower-precedence transport is contacted. |
| OCI manifest or layer digest differs from its configured digest | The run fails and leaves no accepted source. |
| Provenance is missing, unsigned, has the wrong subject, or has mismatched package/filename/hash | The run fails and leaves no accepted source. |
| Source signature/checksum evidence fails | The run fails and does not fall through. |
| All checks pass | The source bytes are unchanged, the report records the transport, and the staged re-hash passes. |

The tests must use fixed bytes and fixed expected digests. They must not rely on
mutable GHCR tags, live upstream availability, or a test-only bypass of
signature or SHA-512 verification.

## Non-goals

- Implementing or populating an ORAS cache in this RFC;
- making the cache a routine mirror or replacing upstream/Fedora lookaside;
- accepting mutable tags for source retrieval;
- permitting normal build workflows to publish cache objects; or
- changing Fedora recipe provenance or generated-source handling.
