# Local build feedback

Use the same entry point as the Actions package lane:

```sh
just build python-argcomplete
just build-deps localsearch
bash tools/build-package.sh flac --keep-container
```

`build-deps` fetches and verifies sources, installs static and generated
BuildRequires, and runs source preparation. It stops before compilation, so it
does not prove a package builds or that its runtime dependencies resolve.
Use `just build PACKAGE` for that package's complete RPM build, including its
existing `%check`. Publication still requires the repository's runtime gates.

Podman is the default; CI uses `--engine docker --work work --no-fetch` after
its source-verification step. Both execute `tools/build-rpm.sh` in Fedora 44
with the configured Hummingbird repository. Root installs build dependencies;
`mockbuild` runs rpmbuild and tests. This is the factory's existing container
build path, not Hummingbird's hermetic mock implementation.

Each package uses `work/local/PACKAGE`. DNF downloads and any opted-in compiler
cache survive fresh containers. Logs include the failed phase, elapsed time,
and the original exit status. Old RPM results move to `previous.*` before a
retry, so a failed build cannot claim yesterday's RPM as a success. A lock
prevents two local builds from sharing one work directory concurrently.

For a later-stage build, copy the required previously built RPMs into that
package's `prior/` directory. Preserve their subpackages as a complete set.
Do not test a desktop consumer against an empty prior directory and conclude
its in-factory dependencies are missing upstream. CI seeds the accumulator
first and overlays the current run's artifacts last.

`--keep-container` preserves a stopped container on failure. The command
prints its name and the command to copy `/builddir/rpmbuild` out for inspection.
Do not restart it just to inspect logs: that reruns the build command.

The source locks are immutable, but repository metadata and the Fedora image
tag can move. Cached downloads make retries fast; they do not establish
bit-for-bit reproducibility. Record the build log and use the same staged RPMs
when comparing failures.

## Why this path exists

On 2026-09-05, local `python-argcomplete` built in 92 seconds with a cold DNF
cache and 13 seconds with a warm cache. After changing to the unprivileged
build user it built in 14 seconds; dependency-only verification took 11 seconds.
FLAC's complete build took 236 seconds and passed all ten tests. These are
package-container timings, not a claim about WebKit's compile time.

[Run 33945305235](https://github.com/projectbluefin/utah-packages/actions/runs/33945305235)
failed FLAC's read-only-file tests with "are you running as root?". Supplying
the normal build user corrects that environment rather than changing FLAC's
tests. The same run's localsearch, waypipe, and pipewire-libs-extra failures
all reached a stale FFmpeg requiring `liboapv.so.2` while the successful FFmpeg
job 101257198998 in that very run installed OpenAPV 0.3 from `stages` and
produced a dependency on `liboapv.so.3`. The existing `stage0_late` ordering
already accounts for that ABI change; accumulator copy order must preserve its
fresh output.

Hummingbird's authoritative guides describe
[preserving and debugging local build environments](https://hummingbird-project.io/docs/operating/debugging-build-failures/)
and [ordering the buildroot and toolchain](https://hummingbird-project.io/docs/operating/rebasing-buildroot-to-new-fedora/).
Read those and the commit history before changing recipes or staging.

## Compose Utah locally

After a package build or a recovered candidate is available locally, compose
Utah before requesting a long CI run:

```sh
# In utah-packages: merge the stable factory baseline and current candidate.
just local-repo

# In the sibling utah checkout: run the complete main-flavor transaction.
just build-local local-test localhost/utah-packages:local-merged
```

`build-local` executes Utah's production Containerfile and its RPM contract;
it changes only the source of the copied package repository to an image in
local containers-storage. The result is `localhost/utah:local-test`. A failure
at the package transaction is therefore actionable factory closure evidence,
not a CI environment difference.
