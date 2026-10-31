---
name: multimedia-closure
description: >-
  How Bluefin's multimedia override and codec transaction is inventoried here,
  how the full codec closure is mapped to target negativo17 multimedia and RPM
  Fusion specs (the recipes themselves are Fedora imports today), why half of it
  is invisible to the manifest, and what to check before
  claiming a codec requirement is satisfied. Load before adding a recipe for a
  codec, syncing config/bluefin-packages.toml, or answering "does the factory
  cover Bluefin's multimedia?".
metadata:
  type: reference
---

# The Bluefin multimedia closure

Bluefin's codec surface is assembled by
[`build_files/base/03-packages.sh`](https://github.com/projectbluefin/bluefin/blob/main/build_files/base/03-packages.sh),
and only half of it is in a file this factory mirrors.

## The half the manifest does not carry

`config/bluefin-packages.toml` is a copy of Bluefin's `base.toml`, kept
separately so its sections can be diffed against upstream. `base.toml` holds
`[multimedia_overrides]` — the twelve packages Bluefin distro-syncs from
negativo17 and then version-locks — and nothing else about codecs.

The rest is written inline on the `dnf5 install` line in the same script:

```sh
ffmpeg{,-libs} libavcodec @multimedia \
gstreamer1-plugins-{bad-free,bad-free-libs,good,base} \
lame{,-libs} libfdk-aac libjxl ffmpegthumbnailer
```

Nothing here had ever read that line. `tools/rawhide_sources.py` imports what
the manifest names, so ffmpeg, lame and jpegxl arrived by other routes and
ffmpegthumbnailer had never arrived at all — and no tool could say which,
because "the multimedia requirements" existed as a shell line and not as data.

`config/multimedia-closure.toml` is that line, expanded, with the
`[multimedia_overrides]` half read out of the Bluefin manifest rather than
copied. `tools/multimedia_closure.py --check` is the gate; it also writes
`reports/multimedia-closure.json`, which `tests/test_multimedia_closure.py`
holds to the current tree.

## `@multimedia` is the larger half

`@multimedia` is a comps group, and a comps group is two separate questions:

- **Does the name resolve?** Against this factory, never. Groups live in
  repository metadata, and `createrepo_c` writes none, so the group is a
  standing exception no amount of building can clear.
- **Are its members built?** That is the measurable question, and the group
  expands to sixteen of them — more names than the explicit install line
  carries. Six were already covered by pipewire and wireplumber; five are
  tracked exceptions; `PackageKit-gstreamer-plugin` is excluded by the very
  install line that asks for the group, via `-x PackageKit*`.

Conditional members are not requirements. comps declares
`gstreamer-plugins-espeak` as `type="conditional" requires="gstreamer"`, so it
arrives only when the legacy `gstreamer` package is already in the
transaction, which on Utah it is not; it is recorded in `conditional_members`
and inventoried nowhere else — counting it would manufacture a gap.

## Codec closure sourcing from negativo17 and RPM Fusion

Utah cannot enable third-party repositories at runtime or build time. Under
issue `projectbluefin/utah-packages#230` (parent goal `#24`), the multimedia
closure inventory tracks target upstream spec sources for every multimedia
override binary and codec component:

- **negativo17 fedora-multimedia** specs are the target upstream spec source
  for the mesa, libva, Intel media stack, and libheif binaries:
  `intel-gmmlib`, `intel-mediasdk`, `intel-vpl-gpu-rt`, `libheif`, `libva`,
  `libva-intel-media-driver` (`intel-media-driver`), and all six `mesa-*` binaries.
- **RPM Fusion free + nonfree** specs are the target upstream spec source
  for codec packages that Fedora cannot ship directly: full `ffmpeg`,
  `gstreamer1-plugins-ugly-free`, `gstreamer1-plugin-libav`, and `libfdk-aac`.

This contract and mapping inventory track target parity for Utah to install the
functional codec surface without third-party repositories enabled at build or runtime.
The report surfaces both the declared target upstream spec source and the current recipe
provenance from `.hummingbird-upstream.json`, making migration progress visible.

### `built` is a label, `codec_parity` is the measurement

`[built]` says only that a factory recipe emits a binary of that name. It says
nothing about which spec built it, and today every one of them is a Fedora
dist-git import whose codec set is deliberately narrower: `packages/mesa`
passes no `-Dvideo-codecs`, `packages/libheif` disables the HEVC plugins,
`intel-media-driver-free` is the free variant. Reading `built` as codec parity
with negativo17 or RPM Fusion is the mistake the `[equivalent]` rule already
warns about, one layer up.

So every requirement carries a separate `codec_parity` in the report, derived
by comparing the recipe's `.hummingbird-upstream.json` provenance against the
target source named in `[upstream_spec_sources]`:

- `upstream` — built from the named negativo17 or RPM Fusion spec.
- `fedora-restricted` — built from a Fedora dist-git import
  (`src.fedoraproject.org`), which is every override in the tree today; the
  restriction is stated in `[parity.<recipe>].reason` in
  `config/multimedia-closure.toml` and copied into the report as `parity_note`.
- `divergent` — built from some third source that is neither the named
  upstream nor a Fedora import. Nothing is labelled this today; it exists so
  the Fedora label stays a statement about Fedora's codec policy rather than a
  catch-all for "not upstream". It needs a `[parity]` reason on the same terms.
- `unknown` — built from a recipe with no recorded provenance.
- `null` — no upstream spec source is named for it in
  `[upstream_spec_sources]`, so there is nothing to measure against. That is
  every `[exception]`, which this factory does not build at all, and also the
  `built` entries outside the override set — `lame{,-libs}`, the
  `gstreamer1-plugins-*` family, the `pipewire-*` binaries. `null` is "not
  measured", not "not at parity"; only the 16 named sources are counted in
  `upstream_parity`, `fedora_restricted` and `divergent`.

`--check` fails when a divergence carries no `[parity]` entry, so a
Fedora-restricted build cannot pass as upstream parity by wearing the `built`
label, and it prints the requirements still short of parity. It also fails when
a `[parity.<recipe>].status` disagrees with the parity derived from the
provenance: the declaration is a second opinion, so it has to agree, or a table
explaining a Fedora restriction would keep passing after the recipe moved to a
third spec and the derivation turned `divergent`. It does not fail
on the divergence itself: the migration under `#230` has not run, so `0
upstream_parity, 15 fedora_restricted` is the honest current state, not a
regression to block on.

The inventory maps the targets; it does not source anything from negativo17 or
RPM Fusion yet. Every override recipe still carries `src.fedoraproject.org`
provenance, so `#230` stays open until `upstream_parity` starts rising — this
contract is the measurement that will show it, not the work it measures.

## Before claiming a requirement is satisfied

- **Name the binary, resolve the source.** `libjxl` is built by `jpegxl`,
  `libva-intel-media-driver` by `intel-media-driver-free`, `libavcodec` by
  `ffmpeg`. Searching `packages/` for the binary name finds nothing and proves
  nothing; this is the trap [`../contributing.md`](../contributing.md) opens
  with.
- **A rename is not a gap, and not a pass either.** Fedora's `ffmpeg-free`
  carries no `Provides: ffmpeg`. It supplies every soname `ffmpeg` does, so
  consumers resolve; a transaction naming the literal string does not. Record
  it under `[equivalent]` with the reason, never under `[built]`.
- **Check the family version before importing a plugin.** Fedora's
  `gstreamer1-plugin-libav` requires `gstreamer1-devel >= %{version}`, and
  Rawhide head is a release ahead of the gstreamer1 family pinned here, so
  importing head adds a BuildRequires nothing satisfies —
  [`repeated-mistakes.md`](repeated-mistakes.md) #2, a package and its family
  pinned separately. Import the dist-git commit whose `Version:` equals the
  pin instead (`git log` the dist-git repo; libav at 1.28.6 is the "Rebuilt
  for FFmpeg 9" commit 73e9b14, as ugly-free is at 207f329) rather than
  bumping the whole family for one plugin.
- **Camera RAW support is not FireWire transport.** `LibRaw` supplies
  `libraw.so` and `libraw_r.so` for decoding camera image files; it is not
  `libraw1394`, the FireWire library needed by the `libavc1394` family.
  Resolve these as separate source families, even when they share a media
  backlog batch. LibRaw's default recipe enables JPEG, LCMS, zlib and
  OpenMP, and emits `LibRaw`, `LibRaw-devel`, `LibRaw-static` and
  `LibRaw-samples`; its upstream release is served directly under
  `https://www.libraw.org/data/`. `libavc1394` BuildRequires
  `libraw1394-devel`, and its devel package requires it too, so import and
  publish `libraw1394` first. These recipes do not enable the disabled
  FireWire feature in ffmpeg or establish hardware functionality; both need
  separate validation. Fedora's imported manifests for these two older
  releases use MD5: compare upstream bytes to that pin, then record their
  SHA-512 digests in `sources` and the source lock.
- **Recipe reconciliation is not runtime closure.** A `[resolved]` backlog
  record required by an import tracks recipe coverage only. Keep the batch
  issue open until the hosted build, published binary identities,
  factory-plus-Hummingbird dependency transaction and representative payload
  checks exist. In particular, `already_recipe` for ffmpeg libraries does
  not replace checking those binaries in current primary metadata.
- **"Present in the factory repository" means published, not committed.**
  `tools/multimedia_closure.py --repodata <dir>` reads a published
  repository's `primary.xml` and fills in each requirement's NEVRA, epoch
  included. A recipe on disk that no run has built is not coverage, and the
  report says so by leaving the NEVRA null.

  The file is located through `repomd.xml` and decompressed by extension —
  gzip, zstd or plain. Do not glob for `primary.xml.gz`: that is createrepo_c
  &lt; 1.0's default, the workflow installs `createrepo-c` unpinned via
  `apt-get`, and createrepo_c ≥ 1.0 writes zstd. `tools/rebuild_matrix.py`
  reads the published repository the same way.
- **The publish-time report does not gate the publish, and that is enforced,
  not merely intended.** The step is in `.github/workflows/publish-repository.yml`
  — the reusable publish workflow, not `rebuild-rpms.yml`, which only calls it
  — and it carries `continue-on-error: true`. Without it, the step's exit code
  fails the publish job before the consumer-transaction validation and the
  image push — and the `--repodata` half runs only there, so no PR check can
  catch a failure in it. If you want the closure to block a publish, that is a
  deliberate widening: say so in the PR, and take the flag off on purpose
  rather than by accident.

## Adding to the inventory

A new name in Bluefin's `[multimedia_overrides]`, or a new package on the
install line, fails `--check` until it has an entry:

- `[built]` — a recipe here emits a binary of exactly that name.
- `[equivalent]` — a recipe here emits the same capability under another name.
  Needs `source`, `binary` and `reason`.
- `[exception]` — nothing here satisfies it. Needs `reason`, and the reason
  should say what would close it, or that nothing will.
- `[upstream_spec_sources]` — every multimedia override binary must carry a named
  upstream spec source URL from negativo17 or RPM Fusion. Key it by the
  requirement name, or by the factory source recipe when one spec answers
  several binaries; the requirement key wins when both are present.

Then regenerate the report:

```sh
python3 tools/multimedia_closure.py --output reports/multimedia-closure.json
```

When `repomd.xml` exists, its primary metadata location is authoritative.
A missing or malformed indexed file must fail the report rather than select
a stale primary file left in the directory. Use an XML parser so namespace
formatting and single-quoted attributes do not change which file is read.

When another recipe lands during review, refresh Packit inventory and architecture counts after merging main; keep both the multimedia and backlog gates in the combined Justfile.

`reports/multimedia-closure.json` records locked upstream versions for codec recipes. Any automated workflow that bumps upstream version locks (`.github/workflows/bump-upstream-sources.yml`) must regenerate `reports/multimedia-closure.json` and include it in `add-paths` so validation tests pass and the refreshed report is committed alongside the lock bump.

Stack concurrent recipe imports when they edit the same generated inventory reports; regenerate against the combined recipes and retarget the dependent PR only after its prerequisite merges to main.

## Importing the codec tail

Fedora does not carry every full-codec source. Query the packaging repositories
in RPM Fusion (`https://github.com/rpmfusion/<source>.git`) and negativo17
(`https://github.com/negativo17/<source>.git`) before declaring a binary
unavailable. Use `tools/import_rawhide.py --branch master --remote-template`
with the appropriate URL template: its snapshot writer records the actual
branch, commit and tree. Validation accepts `master` only for those recipe
owners and a remote whose repository name matches the source package; full
commit and tree hashes remain mandatory. Never relabel that provenance as
Fedora `rawhide` or a direct-upstream import to pass validation.

Upstream archives still supply the payload. A packaging snapshot script may
repack a VCS checkout even when the same commit has a first-party archive.
For x264, lock the full VideoLAN commit archive, adjust the unpack directory,
and retain the packaging repository's matching `version.h` and patches. The
default bootstrap build emits the encoder library without the optional GPAC
and FFmpeg CLI demuxers, breaking the FFmpeg build dependency cycle and
avoiding an RPM Fusion-only runtime package. Its assembly tests still run.

Inspect every `Source` entry, including test data, before registering a recipe.
A valid primary archive does not cover a missing auxiliary archive. Keep the
output pending until every payload has a verified fetch path; do not remove
its tests or import a second source recipe under the binary name. A moved
backlog entry records recipe availability, while publication, dependency
resolution and a representative runtime command require separate evidence.

RPM Fusion's auxiliary lookaside is `pkgs.rpmfusion.org`, not Fedora's host
or the binary download mirror. For vvdec's `bitstreams.tar.xz`, set
`lookaside: "rpmfusion-free"` on the source lock. This selects the fixed HTTPS
lookaside template only for auxiliary files; the primary archive still comes
from upstream, and each auxiliary file must match its SHA-512 `sources` pin.
The test archive is required by `%check`; do not disable tests to avoid it.

### Test failure propagation is not build evidence

Read imported `%check` bodies before trusting their green builds. Every test
that runs must propagate failure: an unconditional `|| :` or `|| true` after
a test runner makes the result advisory, not successful. In x265, run
`test/TestBench` without a success fallback in every built 8-, 10- and 12-bit
directory; a failure in an earlier directory must not be hidden by a later
`popd` or a passing variant. Keep tests for architectures that build only the
8-bit library rather than requiring absent high-depth directories.

`tools/check_suppressed_tests.py`, called by `tools/validate.py`, ratchets
known direct test-command success fallbacks as well as `tests_nonfatal`
definitions. Its exact inherited counts preserve already-carried main
exceptions, not permission to add more. Probe commands (`test -f`, `grep`),
failure-log reads and help/version queries are not test execution. The
tripwire does not interpret arbitrary shell or RPM control flow; review
wrappers, compound commands and conditional fallbacks separately.

A clean guard or unit-test run proves this failure-propagation boundary, not
that x265 or any other named codec builds. Require a hosted package build
against the pinned environment for each named recipe before claiming build
success, and separate publication, installability and representative codec
execution evidence from both the guard result and the recipe build.

## Shader compiler dependency order

The audited `libshaderc` binary comes from the `shaderc` source recipe,
not a separate source of that name. Its unbundled build needs `glslang-devel`,
`spirv-headers-devel` and `spirv-tools-devel`. The existing `spirv-tools`
recipe also needs `spirv-headers-devel`; register the missing source recipes
and let their BuildRequires establish build order. Match glslang's Vulkan SDK
version to the carried SPIR-V tools SDK (1.4.357.0 here), rather than
importing a newer Rawhide head independently. The selected SPIR-V headers
commit matches shaderc's upstream `DEPS`; Fedora temporarily changed its
package version for that same commit and reverted it, so use its earlier
1.5.5 recipe instead of the reverted version bump. This alignment is a
preflight, not proof that the unbundled combination builds: the Fedora shaderc recipe
already disables its upstream tests when unbundled. Verify the hosted build
and compile a representative shader with `glslc`, then validate its SPIR-V
output after installation from the permitted repositories.

## Disc-reading dependency order

`libbluray` 1.4.0 uses the external `libudfread-devel >= 1.2.0` and removes
its bundled copy during preparation. Import and lock both source recipes;
let the BuildRequires graph place `libudfread` first rather than assigning a
stage. The VideoLAN `libudfread` tag archive and `libbluray` release archive
match their Fedora `sources` SHA-512 pins. Keep the Blu-ray recipe's Java
navigation support and utility subpackages when checking build dependencies;
a successful library source download proves neither those builds nor runtime
closure. A lane against the published factory needs `libudfread` published
before it can build `libbluray`.

## FireWire camera library

`libdc1394` provides camera-control libraries and tools. Its Fedora recipe
requires `libraw1394-devel`, supplied by the existing `libraw1394` recipe;
the BuildRequires graph orders the builds. Its upstream SourceForge archive
matches the Fedora SHA-512 source manifest. A recipe and source lock do not
prove that the package builds, publishes, or controls a camera: verify the
hosted build and exercise a compatible device after installation.

## FireWire streaming library

`libiec61883` BuildRequires `libraw1394-devel`, so the existing
`libraw1394` recipe must build first. The upstream 1.2.0 gzip archive
and Fedora lookaside archive have different compressed hashes but unpack
to identical file trees; lock the upstream bytes and update the source
manifest to match. Fedora's channel-allocation patch preserves its fallback
when the IRM cannot be reached, allowing capture to proceed. A recipe does not
prove streaming or hardware support; verify the behavior with a device.
