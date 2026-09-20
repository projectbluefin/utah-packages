---
name: package-build-cache
description: >-
  Correctness contract for preserving successful package builds across failed
  factory runs. Load before changing cache identity, eligibility, OCI storage,
  restore ordering, or publication in the RPM rebuild workflow.
metadata:
  type: reference
---

# Per-package RPM cache contract

The package cache preserves completed work across factory runs. It exists
because publication is intentionally atomic: one failed package or final
transaction gate must not advance the consumer repository, but that must not
force every successful package to compile again on the next attempt.

This is a correctness mechanism with a performance benefit, not a second
publication path. Keep these two witnesses separate:

| Witness | Answers | Contents | May consumers install from it? |
| --- | --- | --- | --- |
| `ghcr.io/<owner>/utah-packages` | Is the complete repository coherent and published? | The signed repository | Yes |
| `ghcr.io/<owner>/utah-packages-cache:<key>` | Was this exact package already built under these exact inputs? | One package's RPM output | No |

The cache never decides whether a package needs rebuilding. `rebuild_plan.py`
does that first. A cache hit only changes how a selected package's RPMs are
obtained. The restored RPMs enter `work/result`, are uploaded as the ordinary
stage artifact, and pass through the same precedence, transaction, signing and
publication gates as a fresh build.

## Lifecycle

For each selected, cache-eligible package, `build-stage.yml`:

1. Resolves its BuildRequires against the prepared build root, the published
   factory witness, and RPMs from earlier stages.
2. Records the resolved RPM NEVRAs and derives the Hummingbird disttag.
3. Computes the key with `tools/package_cache_key.py`.
4. Pulls `utah-packages-cache:<key>`.
5. On a hit, copies `/rpms` into `work/result` and skips compilation.
6. On a miss, builds normally and immediately pushes `/rpms` under that key.
7. Uploads `work/result` as the normal stage artifact in either case.

Publishing a miss happens per package, immediately after a successful build.
It does not wait for the stage or factory run to finish. If stage 4 fails after
100 earlier packages succeeded, those 100 entries are available to the rerun.

Cache authentication, pull and push failures are availability failures. They
warn and fall back to compilation; they never invalidate a valid RPM build.
An entry that pulls but contains no RPM is not a hit and must fail loudly.

## Key and invalidation

The key is the first 32 hexadecimal characters of a SHA-256 over canonical
JSON containing:

- cache schema version;
- source-package name;
- digest of every file and relative path in `packages/<name>/`;
- prepared build-root image digest;
- prepare-time factory image digest;
- sorted, de-duplicated resolved build-root NEVRAs;
- complete disttag, including any local rebuild suffix.

Every field can change the binary. Removing one can serve an RPM built from a
different recipe or ABI. An empty resolved root is therefore an error, never a
cacheable value. Bump the schema whenever the meaning or collection of any
field changes.

The tag is the bare hexadecimal key. Do not prefix it with the RPM name: RPM
names such as `gtk+` are legal but are not legal OCI tag components. The
package name is already bound inside the hash.

## Eligibility is separate from identity

`tools/rebuild_plan.cacheable()` narrows the selected build list for cache
lookup. Two selected classes must compile:

- A directly changed recipe. Its recipe digest should already miss, but a real
  build is part of the review contract and does not rely on that assumption.
- A stale published package whose binaries require a capability no repository
  now provides. Its recipe may be unchanged, so an old cache entry can match;
  restoring it would reproduce the defect the run is trying to repair.

Dependency-closure rebuilds may use the cache only when their full key matches.
The resolved earlier-stage RPMs change the root portion of the key when the
dependency actually changed.

## Invariants future changes must preserve

- Never share the consumer image's tag namespace with cache entries.
- Never seed the final repository directly from the package cache.
- Never let cache presence decide the rebuild plan.
- Never restore stale or directly changed packages.
- Never compute a key before dependency resolution or from an empty root.
- Never omit recipe paths, the build-root digest, factory digest, resolved
  NEVRAs, or disttag from the key.
- Never treat a cache outage as a package-build failure.
- Never delay cache publication until the final atomic publish job.
- Never remove the final precedence and Hummingbird-only transaction gates for
  cached RPMs.
- Keep the dependency-resolution probe aligned with the actual container build
  policy. A repository, exclusion, stage-input or disttag change belongs in
  both paths and in a regression test.
- The mock backend is not cache-enabled until it records and keys its own mock
  root. A container-lane entry must not be reused by mock merely because the
  source recipe matches.

## Proving progress survives

The useful test is two runs of the same factory inputs, not one green build:

1. Start a run with an empty cache and allow several packages to finish.
2. Cancel or let a later package fail before final publication.
3. Rerun the same commit and prepared inputs.
4. Verify those completed packages log `cache hit`, contain RPMs in their stage
   artifacts, and do not execute the compile step.
5. Verify changed and stale packages log a real build even if an older cache
   entry exists.
6. Verify the final repository still passes precedence and the consumer
   transaction before publication.

A full matrix containing cache-hit jobs is acceptable; a full recompilation is
not. The distinction is the compile step and cache-hit evidence, not the number
of matrix jobs GitHub displays.
