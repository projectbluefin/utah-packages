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
- `fedora-restricted` — built from something else, today always a Fedora
  import; the restriction is stated in `[parity.<recipe>].reason` in
  `config/multimedia-closure.toml` and copied into the report as `parity_note`.
- `unknown` — built from a recipe with no recorded provenance.
- `null` — no upstream spec source is named for it in
  `[upstream_spec_sources]`, so there is nothing to measure against. That is
  every `[exception]`, which this factory does not build at all, and also the
  `built` entries outside the override set — `lame{,-libs}`, the
  `gstreamer1-plugins-*` family, the `pipewire-*` binaries. `null` is "not
  measured", not "not at parity"; only the 16 named sources are counted in
  `upstream_parity` and `fedora_restricted`.

`--check` fails when a divergence carries no `[parity]` entry, so a
Fedora-restricted build cannot pass as upstream parity by wearing the `built`
label, and it prints the requirements still short of parity. It does not fail
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
  `gstreamer1-plugin-libav` requires `gstreamer1-devel >= %{version}` and is a
  release ahead of the gstreamer1 family pinned here, so importing it alone
  adds a BuildRequires nothing satisfies — [`repeated-mistakes.md`](repeated-mistakes.md)
  #2, a package and its family pinned separately.
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
  not merely intended.** The step in `rebuild-rpms.yml` carries
  `continue-on-error: true`. Without it, the step's exit code fails the publish
  job before the consumer-transaction validation and the image push — and the
  `--repodata` half runs only there, so no PR check can catch a failure in it.
  If you want the closure to block a publish, that is a deliberate widening:
  say so in the PR, and take the flag off on purpose rather than by accident.

## Adding to the inventory

A new name in Bluefin's `[multimedia_overrides]`, or a new package on the
install line, fails `--check` until it has an entry:

- `[built]` — a recipe here emits a binary of exactly that name.
- `[equivalent]` — a recipe here emits the same capability under another name.
  Needs `source`, `binary` and `reason`.
- `[exception]` — nothing here satisfies it. Needs `reason`, and the reason
  should say what would close it, or that nothing will.
- `[upstream_spec_sources]` — every multimedia override binary must carry a named
  upstream spec source URL from negativo17 or RPM Fusion.

Then regenerate the report:

```sh
python3 tools/multimedia_closure.py --output reports/multimedia-closure.json
```
