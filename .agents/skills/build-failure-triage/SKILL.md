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

## When to Use

A job in `rebuild-rpms.yml` or `build-stage.yml` failed, someone asks why a
package did not build, or a failure has to be attributed to this repository,
to Fedora, or to the build environment.

## When NOT to Use

- The run was **cancelled**. It was superseded by a later push. Nothing broke.
- The job is `preflight`. It is `continue-on-error` and its output is a
  worklist, not a gate; a package it flags as unsatisfied may simply be built
  by a later wave.
- The failure is `prepare` reporting a wave with no job. The solved
  BuildRequires chain got deeper than `rebuild-rpms.yml`'s fourteen waves;
  add a wave, it is not a build failure.
- Nothing failed and the question is what the factory *should* do. That is
  `docs/architecture.md`, not this skill.

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

### The job name in the run list is the chunk, not the package

A stage is split into chunks, so the Actions UI renders a failure as

```
rebuild6 (["gnome-desktop3", "libadwaita", ...]) / build (nautilus-python)
```

The name in the matrix brackets is the chunk's **first** package. The package
that failed is the one in the trailing `build (...)`. Issue #212 was filed as
"fix gnome-desktop3" from the bracketed name; gnome-desktop3 had built fine in
that very run and the failure was `nautilus-python`. Before triaging, confirm
which package it is:

```sh
gh api repos/projectbluefin/utah-packages/actions/runs/<run>/jobs --paginate \
  --jq '.jobs[] | select(.conclusion=="failure") | "\(.id)\t\(.name)"'
```

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
| `No match for argument: <pkg>` where `<pkg>` is in `config/upstream-sources.json` | Build ordering: the graph did not see this edge, so the provider was not in an earlier wave. Usually a `%generate_buildrequires` requirement, which rpmspec cannot see, or a spec rpmspec failed to parse (`spec not parsed` warning in `prepare`) | Check the `build-graph` artifact for both packages. A missing generated edge is a `tools/build_graph.py` gap; do not paper over it with a `stage`, which only orders cycle members |
| `Found X but need: '>= Y'` where the package is one of ours | Same — ordering, not a missing dependency | As above |
| `Failed to resolve the transaction`, naming a Fedora package that a same-stage recipe BuildRequires and an earlier stage's output in the same chain | Ordering again, with no `No match` line to give it away. The earlier stage's RPM is excluded from Fedora by name and pins a soname (ICU is the recurring one), so Fedora's copy of the *same-stage* package can no longer install | Raise the consumer's `stage` above the package it BuildRequires, and add the pair to `tests/test_icu_staging.py` |
| `No match for argument: <pkg>` where `<pkg>` is a Fedora package | Genuine gap: Fedora predates what the source needs | Import and pin it, like `wayland-protocols` and `accountsservice` |
| Error inside `/usr/share/cargo/registry/...` or another Fedora-packaged dependency | Fedora packaging bug | Verify it affects more than one Fedora release before calling it release-specific. Do not work around it in the spec |
| A package fails on the hermetic lane (`Build offline from the lock`) but built on the container lane | The clean mock root lacks something the hand-built container root supplies: a running service, a staged sysusers entry, working loopback (`tools/hermetic_build.sh` brings `lo` up in its network namespace because git's HTTP tests serve on 127.0.0.1). Read `lock-s<N>-<pkg>`: the lock says exactly what the root contained | Fix the recipe or give the root what the test needs in `tools/mock_config.py`. Only if neither is possible, add `"build_lane": "container"` with a `build_lane_reason` naming the gap. **Never** skip the test |
| `are you running as root?` or `Cannot run ... tests as root` on the hermetic lane | mock was run as root, so the build ran as root | `tools/hermetic_build.sh` runs mock as `mockbuilder`; a change that drops the `runuser` brings this back |
| An issue *Utah install set: <pkg> does not resolve*, or a `Utah cannot install` warning on `publish` | Something Utah installs does not resolve against the published factory plus Hummingbird. The issue quotes dnf's problem line, e.g. `xdg-desktop-portal … requires libfuse3.so.4()(64bit), but none of the providers can be installed` | Follow the named requirement to the package that should provide it, and fix that package; the issue closes itself on the first run in which it resolves. The check is advisory by design and does not block publication |
| `flaky %check retry` warning, then `flaky %check` (passed on retry) | `build-stage.yml` reran the whole build once after a `%check` failure, and the second attempt passed. The first attempt's logs are in the `check-s<N>-<pkg>` evidence only if the retry also failed; otherwise they are in the job log | A flaky test, not a fixed one. Open an issue naming the test; do not rely on the retry for a test that fails most runs. A `%check` that fails twice fails the package as before |
| `Bad exit status ... (%check)` needing a bus, display or device | The container lacks a service the test needs | Give the container the service. **Never** skip or disable the test |
| One test `killed by signal 14 SIGALRM`, no output, at the same second on every run | The test armed its own `alarm(N)` and hung inside it | A hang, not slowness. Prove it by serializing `%check` before theorising about starvation, then root-cause the hang. Raising the alarm only moves the deadline |
| rpmbuild exit **11**, `*.buildreqs.nosrc.rpm` written | Dynamic BuildRequires (`%generate_buildrequires`, all Rust packages) | Install what the generated SRPM declares, then retry, bounded |
| `undefined: json.SkipFunc` in vendored `go-json-experiment/json` | Go toolchain's experimental `encoding/json/v2` API drift vs vendored shim | Export `GOEXPERIMENT=nojsonv2` in `%build` to use vendored implementation |
| `Transaction failed: Rpm transaction failed.` then `file ... from install of <new-pkg> conflicts with file from package <old-pkg>`, both from Hummingbird, same version, different release | Hummingbird moved a file to a newly split package without `Obsoletes`/`Conflicts`. The root already holds the pre-split owner, builddep asks only for the new one, dnf never upgrades the old one, and rpm refuses. libxml2 -> libxml2-16 at 2.15.4-1.1 took out 14 packages at once in run 36032253217 | A showstopper, not a package bug: every recipe reaching that library fails. Add the old name to the `for split in ...` upgrade loop in both containers of `build-stage.yml`, so it moves to the split release (pulling the new package) before builddep. Report the missing `Obsoletes` to Hummingbird |
| Exit **125**, `manifest unknown` | A container image digest was pruned upstream (quay.io repushes `latest` and prunes old digests, several times a day for `fedora:44`) | For the build root: nothing. `prepare` pulls it once by tag and shares it as an artifact (`f1f1e4e`); a per-job registry pull is the bug, and `tests/test_buildroot_sharing.py` rejects it. For any other image still pulled by digest in a job, repin, and note that three repins died in five days before the build root moved to the shared artifact |
| Exit **125**, log under ~1 KB (transient) | `docker run` failed before the build; infrastructure | Not the package. Re-run once at most |
| `Signature verification failed` after a clean download | The repo's `gpgkey` is a multi-key bundle and one key in it fails to import | Point `gpgkey` at the single release key. Verify its fingerprint against the one the failing transaction named. **Keep `gpgcheck=1`** |
| `wrong key?` on a third-party repo whose content the build does not need | A repo signed by a key the image does not trust | Disable that repo for the build |
| A package is listed in *Factory: packages failing on main*, or a `package not published` error on the `report` job | It failed this run (build, or lost precedence) and consumers still get its previous build, or nothing if it never built. The other packages published | Triage it like any build failure. It stays in the issue until a run builds it; the issue closes itself on the first run with no failures. A `Not published.` line means the Hummingbird-only transaction refused the whole candidate: fix that first, since nothing moves until it resolves |
| `cosign verify` fails in `publish`'s "Verify and seed repository" step | The image at `:latest` (or the branch tag) is not signed by this workflow's own keyless OIDC identity -- either GHCR served a tampered image, or the certificate-identity ref (`refs/heads/main` for `latest`, the branch ref otherwise) no longer matches how `Sign the published image` signs | **Do not weaken or drop the check to unblock a run.** Confirm who/what pushed to the GHCR package outside this workflow; if the identity itself is wrong, fix the `--certificate-identity` construction, not the fact that it is enforced |

### A hanging test is not a starved test

`%check` failures that report **no output at all** and land on the same
wall-clock second every run are hangs. The clue is the signal: `SIGALRM` is
not something the test runner sends, so the test armed `alarm(N)` on itself
and never reached the line that would have disarmed it.

PipeWire's `pw-test-endpoint` (issue #132) is the worked example.
`src/tests/test-endpoint.c` arms `alarm(5)`, then drives five sequential
`pw_main_loop_run` round trips through a `pw_context` with
`module-session-manager` loaded. Meson recorded an empty `<failure />` at
`5.0048s`, which says only that the process died — not why.

The first hypothesis was starvation: one process per core on a 4-vCPU runner.
Re-running `%check` with `--num-processes 1` disproved it. Serialized, with
the whole runner to itself, the same test failed at `5.00s`, while in that
same run `pw-test-filter` was handed **18 seconds** and passed. Wall-clock
capacity was never the constraint.

The order matters more than the conclusion: **measure before theorising, and
believe the measurement over the fix you already wrote.** Serializing is a
diagnostic, not a remedy, and it belongs in a workflow dispatch rather than in
a recipe. Raising the test's own `alarm()` is not a remedy either — a hung
test fails at 60 seconds exactly as it fails at 5, having burned 60.

### Touching a recipe is what schedules its rebuild

`prepare` in `.github/workflows/rebuild-rpms.yml` decides the matrix with

```python
if full or name in changed or name not in published or norm(published[name]) != norm(version):
```

`changed` is `git diff --name-only BASE_SHA..HEAD` mapped through
`^packages/([^/]+)/`, and it is tested **before** the published repository is
consulted. So:

- A package the published repository already carries at the same version is
  skipped — which is why a broken `%check` can sit unnoticed until something
  touches the recipe.
- Restoring a recipe byte-for-byte to the published build's contents does
  **not** restore the skip. The pull request still changed
  `packages/<name>/`, so it still schedules the rebuild and still hits the
  failure. A revert cannot freeze a package; only leaving it alone can.
- The version compared is the one in `config/upstream-sources.json`, not the
  spec's `Version:`.

### `tests_nonfatal` is gated, and here is why

Fedora's audio recipes end `%check` with
`%{!?tests_nonfatal:exit $TESTS_ERROR}`, so one `%global tests_nonfatal 1`
above it turns any failing suite green while still printing `test failed` into
the log. For `pipewire` that would have published a desktop image whose audio
stack had a known hang in it, and nothing downstream would have said so:
Hummingbird ships no `pipewire` at all, this factory is its only source, and
`pipewire-libs-extra` — which `config/bluefin-packages.toml` does install —
carries `Requires: pipewire >= %{version}`, so the recipe cannot be dropped
either.

`tools/check_suppressed_tests.py` now refuses any new definition of
`tests_nonfatal`, and `tools/validate.py` runs it. `pulseaudio` is recorded
there as the one inherited case — Fedora's own, arch- and release-gated, not
added here. The gate fails if that recipe stops defining it, and
`tests/test_check_suppressed_tests.py` fails if the recipe is dropped, so the
exception cannot quietly outlive its reason either way.

The gate is a tripwire on the likeliest route, not proof that no recipe
silences its tests. It greps for a definition line in `packages/*/*.spec`, so
deleting the `%{!?tests_nonfatal:exit $TESTS_ERROR}` guard outright, appending
`|| :` to the test command, or defining the macro in an `%include`d source
file all still pass it. Those are covered by **Never** below, which is prose —
read the `%check` diff rather than trusting a green gate.

## Verify against primary sources

Do not infer a version from what Rawhide ships or from a package name.

- **What a source actually requires** — read its `meson.build` from the release
  tarball. GNOME 51 needs glib `2.86`, not the `2.89` Rawhide carries; assuming
  the latter sent one attempt down a dead end.
- **What a repository actually has** — read its `repodata/primary.xml`.
- **Binary versus source names** — `wayland` the source RPM ships as
  `libwayland-server` and `wayland-devel`. A name lookup that misses is not a
  missing package.
- **Direct-upstream vs Fedora dist-git** — packages like `pipewire-libs-extra`,
  `liblc3plus`, and `libfreeaptx` carry `branch: upstream` in
  `.hummingbird-upstream.json`. They are built by the factory from upstream
  releases, not imported from Fedora dist-git. Do not triage them as Rawhide
  import gaps or declare them unavailable in the runtime contract.

## Never

- Skip, disable or quarantine a test to make a build pass.
- Define `tests_nonfatal`, or any other macro whose only effect is to stop a
  failing `%check` failing the build.
- Treat a content-restoring revert as a way to skip a package's rebuild.
- Push an empty commit, or close and reopen, to re-trigger CI.
- Report a package as fixed without a green job to point at.

## Common Rationalizations

| Thought | Reality |
| --- | --- |
| "The last line of the log says what failed." | It usually says what gave up. The cause is 40-70 lines earlier. Rule 0 exists because acting on the last line produced several wrong conclusions. |
| "The test is flaky, skip it." | Twice it was the build root missing something mock would have supplied — a system bus for libratbag, `USER` for just. Supply what a real build root has. |
| "The test is starved, give it the machine." | Measure it. Serialized, `pw-test-endpoint` failed at the same 5.00s while a neighbour was handed 18s and passed. A constant failure time is a hang, and a hang does not care how much machine it gets. |
| "Reverting the recipe restores the skip." | `changed` is tested before `published` in `prepare`. The pull request touched `packages/<name>/`, so it rebuilds either way. |
| "This one package can be `tests_nonfatal`, it is only tests." | For `pipewire` it is the audio stack of a desktop image, and this factory is its only source. `tools/check_suppressed_tests.py` refuses it. |
| "It is a mock configuration problem." | There is no mock. It is installed and never invoked; the root is hand-simulated. See Rule 1. |
| "The artifact uploaded, so the package built." | Every artifact also carries `work/reports/*.json`, so one file always matches and the upload reports success while shipping no RPM. Rule 4. |
| "This package is missing from Fedora." | Check whether it is one of ours in an earlier wave, and whether you are searching for a binary name that its source package does not use. |
| "Rawhide resolver reports a package as unavailable from Fedora Rawhide." | Check if the package is maintained directly by the factory (e.g. `pipewire-libs-extra` with `.hummingbird-upstream.json` `branch: upstream`). The Rawhide import resolver must skip factory-sourced packages rather than flagging them as missing Rawhide sources or recording them as contract debt in `runtime-contract.toml`. |
| "Re-running will fix it." | Only for transient infrastructure exit 125 with a sub-kilobyte log, and only once. Exit 125 with `manifest unknown` means a digest was pruned upstream; for the build root the answer is the once-per-run pull in `prepare`, not a new digest (see `docs/skills/repeated-mistakes.md`, pattern 7). |

## Red Flags

Signs the triage is going wrong, not the build:

- Reading fewer than 40 lines of log before forming a conclusion.
- Editing a spec to work around what turns out to be a Fedora packaging bug.
- Editing a package unrelated to the one that failed to make its build green.
- Pointing a source lock at a Fedora tarball to unblock a checksum failure.
- Concluding "flaky" without naming what the build root lacked.
- Explaining a failure without saying which build root produced it.

## Verification

Before reporting a cause:

- [ ] Read at least 40 lines around the failure, not the tail.
- [ ] Confirmed the build root: `buildroot openssl` reads `3.5.x`, not `4.x`.
- [ ] Confirmed the run is for the current head commit, not a superseded push.
- [ ] Classified the failure against the table above, and it fits a row.
- [ ] For an ordering failure, named the wave that has to build it first.
- [ ] For a claimed fix, have a green job to point at.
