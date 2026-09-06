---
name: build-failure-triage
description: >-
  Diagnose a failed package build in this factory's GitHub Actions rebuild
  matrix. Use when a rebuild job fails, when asked why a package did not
  build, or when deciding whether a failure belongs to this repository,
  to Fedora, or to the build environment.
---

# Build Failure Triage

This factory forks Rawhide recipes and builds them against Hummingbird. Most
failures are **not** what the last line of the log suggests. This skill exists
because several wrong conclusions were reached by reading too little of a log
and then acting on them.

## Rule 0: read enough of the log

`get_job_logs` with a short `tail_lines` usually returns only rpm's summary and
the runner's cleanup, which is worthless. **Ask for 40-70 lines minimum.** The
real error is typically 20-60 lines above the summary.

Some jobs defeat tailing outright. A repository with git submodules emits a
couple of hundred lines of credential cleanup after the build, so on Utah a
125-line tail still had not reached the failure. When a tail comes back as
nothing but `git config --unset` noise, **do not keep guessing at the depth**:
ask for a deliberately large `tail_lines` (1000+) so the result exceeds the
tool's cap and spills to a file, then grep that file for `error:`,
`##[error]`, `No match for`, `nothing provides` and `Failed to`. Grepping a
spilled log is fast and certain; escalating the tail line by line is neither.

Two wrong calls were made this way: "Fedora 44 cannot satisfy GNOME 51's
BuildRequires" (it was a single missing package we build ourselves), and
"libratbag has no Fedora fix" (its actual failure had moved to a missing
D-Bus session). Both reversed once the full log was read.

## Rule 1: confirm which build root ran

Every job prints this before `builddep`:

```
buildroot openssl: 3.5.7-2.fc44
```

`3.5.x` means `libcrypto.so.3` — the ABI Hummingbird has. If it ever reads
`4.x`, the root has regressed to Rawhide and the resulting RPMs will not
install on Hummingbird, whatever else the log says.

### The build root is not a mock root, despite appearances

`rebuild-rpms.yml` installs `mock` in every stage job and **never invokes it**.
The build is bare `rpmbuild -br` followed by `rpmbuild -ba` in a container that
hand-simulates a build root — the comments say so: *"mirroring Hummingbird
mock.cfg"*, *"mock defines USER in its build root; a bare container does not"*.

Consequences when triaging:

- A failure that looks like a mock configuration problem is not one. There is
  no `/var/lib/mock`, no clean root per build, and no hermetic mode.
- The root is not reset between packages in a matrix job, so contamination
  from an earlier step is possible in a way mock would prevent.
- Anything upstream documents as "mock sets this" is unset here unless the
  workflow sets it by hand. `USER` was one such gap and was patched
  individually; assume there are others rather than that the list is complete.

Moving to real mock is agreed but unbuilt — see *Agreed direction* in
[`docs/architecture.md`](../../../docs/architecture.md). Until it lands, read
the workflow, not mock's documentation.

## Rule 2: check the commit is current

Check-run events arrive for superseded commits. Compare the event's
`head_sha` against the PR's current head before spending time on it. A run
whose conclusion is `cancelled` was superseded by a later push, not broken.

## Rule 3: on a showstopper, kill the runs that cannot pass

A showstopper is a failure that every in-flight job will hit for the same
reason: a bad repository or key, a broken build root, a missing package early
in the ordering. It is not one package failing on its own.

When you identify one, **cancel the runs you already know will not build**,
before writing the fix. Do not let them finish "just in case". Utah's four
image variants each spend roughly twenty minutes reaching an identical GPG
failure; three of them were still grinding toward it when the cause was
already known and understood.

What to cancel:

- Every remaining job in the run whose failure you just diagnosed, when the
  cause is shared rather than package-specific.
- Any run on a commit that later pushes have superseded.

This matters more here than in most repositories because `rebuild-rpms.yml`
sets `cancel-in-progress: false` deliberately, so that a long staged build is
not thrown away by an unrelated push. The cost of that choice is that a doomed
run holds the concurrency group and newer runs queue behind it — and GitHub
keeps only one *pending* run per group, so intermediate ones are dropped. A
stale run left alone does not just waste its own time; it delays the run that
would have answered the question.

Cancelling is not the same as re-running. Never push an empty commit or close
and reopen a PR to kick CI.

## Rule 4: an artifact that uploaded is not an artifact that contains anything

Two separate bugs in this workflow were both a non-recursive glob standing in
for a recursive one, and both were silent for many runs.

`rpmbuild --define "_rpmdir /work/result"` writes to `/work/result/<arch>/`,
not `/work/result/`. `download-artifact` likewise unpacks an artifact under the
common parent of its upload globs. A `*.rpm` pattern misses both; only
`**/*.rpm` matches.

Neither failed loudly. The upload's `if-no-files-found: error` stayed quiet
because the same artifact carries `work/reports/*.json`, so one file always
matched. pango built five RPMs and uploaded a 397-byte artifact containing one
JSON file, and the job went green.

When a later stage cannot see what an earlier stage built, check in this order:

1. Did the earlier job actually write RPMs? Its log ends with `Wrote:` lines
   naming full paths -- read the directory in them.
2. What did the upload say? `With the provided path, there will be N file(s)
   uploaded` is the number that matters, not the step's green tick.
3. What is the artifact's size? A few hundred bytes means metadata only.
4. Only then look at the consuming side.

## Classifying the failure

| What the log shows | What it means | What to do |
| --- | --- | --- |
| `No match for argument: <pkg>` where `<pkg>` is in `config/upstream-sources.json` | Build ordering. The matrix has not built it yet. | Raise its `stage` in `upstream-sources.json` above the package that needs it |
| `Found X but need: '>= Y'` where the package is one of ours | Same — ordering, not a missing dependency | As above |
| `No match for argument: <pkg>` where `<pkg>` is a Fedora package | Genuine gap: Fedora predates what the source needs | Import and pin it, like `wayland-protocols` and `accountsservice` |
| Error inside `/usr/share/cargo/registry/...` or another Fedora-packaged dependency | Fedora packaging bug | Verify it affects more than one Fedora release before calling it release-specific. Do not work around it in the spec |
| `Bad exit status ... (%check)` needing a bus, display or device | The container lacks a service the test needs | Give the container the service. **Never** skip or disable the test |
| rpmbuild exit **11**, `*.buildreqs.nosrc.rpm` written | Dynamic BuildRequires (`%generate_buildrequires`, all Rust packages) | Install what the generated SRPM declares, then retry, bounded |
| Exit **125**, log under ~1 KB | `docker run` failed before the build; infrastructure | Not the package. Re-run once at most |
| `Signature verification failed` after a clean download | The repo's `gpgkey` is a multi-key bundle and one key in it fails to import | Point `gpgkey` at the single release key. Verify its fingerprint against the one the failing transaction named. **Keep `gpgcheck=1`** |
| `wrong key?` on a third-party repo whose content the build does not need | A repo signed by a key the image does not trust | Disable that repo for the build |

## Verify against primary sources

Do not infer a version from what Rawhide ships or from a package name.

- **What a source actually requires** — read its `meson.build` from the release
  tarball. GNOME 51 needs glib `2.86`, not the `2.89` Rawhide carries; assuming
  the latter sent one attempt down a dead end.
- **What a repository actually has** — read its `repodata/primary.xml`.
- **Binary versus source names** — `wayland` the source RPM ships as
  `libwayland-server` and `wayland-devel`. A name lookup that misses is not a
  missing package.

## Never

- Skip, disable or quarantine a test to make a build pass.
- Push an empty commit, or close and reopen, to re-trigger CI.
- Report a package as fixed without a green job to point at.
