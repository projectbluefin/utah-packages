---
name: terminal-emulator-recipes
description: >-
  What it takes to ship a terminal emulator on Hummingbird: Hummingbird
  carries no VTE at all, so every VTE-based terminal needs a complete dependency closure with
  vte291 first, plus the build ordering and source-lock shape for the GTK4
  desktop closure; Ghostty instead needs the Zig toolchain recipe. Load when
  importing ptyxis, gnome-console, kgx, vte291, ghostty, zig, or any other
  terminal recipe.
metadata:
  type: procedure
---

# Terminal Emulator Recipes on Hummingbird

Utah shipped no terminal emulator at all (utah-packages#224). The reason is
not the terminal recipe: **Hummingbird's public repository carries no VTE
library**, so a terminal recipe alone builds but installs nowhere. This file
records the measurement and the ordering that follows from it.

## Hummingbird has no VTE — measure it, do not assume it

Verified 2026-09-22 against
`https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/`:
20,351 packages, and **zero** names matching `vte*`, `ptyxis`, `gnome-console`
or `kgx`. Hummingbird is a base-OS overlay; VTE is desktop stack, and the whole
desktop stack is a gap by definition (see
[`targeting-hummingbird.md`](../targeting-hummingbird.md)).

Reproduce the measurement rather than trusting this paragraph. `repomd.xml`
answers `302` on that host, so `curl` needs `-L`, and the metadata is
zchunk-disabled, so the classic `primary.xml.gz` path is the one to read:

```sh
curl -sSL https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/repodata/repomd.xml \
  | grep -oE 'href="repodata/[^"]*primary\.xml\.gz"'
curl -sSL "https://packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/<that href>" \
  | zcat | grep -oE '<name>vte[^<]*</name>' | sort -u
```

An empty result is the finding. Confirm the query is live by grepping for a
name you expect (`glib2`) in the same stream — a pipeline that fails and a
repository that is empty both print nothing.

## Verify the complete terminal closure

Ptyxis requires the GTK4 VTE library, which in turn BuildRequires
`pkgconfig(simdutf) >= 7.2.1`. VTE removes its bundled subprojects before
building, so an import of only Ptyxis and VTE omits a required provider.
Carry simdutf as a third recipe unless the enabled repositories demonstrably
provide a sufficient version. The imported simdutf 9.0.0 recipe is pinned to
Rawhide commit `6666acdef39a1c9660e235a949c09c23a054ac84`; fresh upstream
archive bytes match the SHA-512 in its sources manifest.

The factory solves build waves from actual BuildRequires. Prove the chain
`simdutf -> vte291 -> ptyxis` in the pinned Packit runner, then verify the
Hummingbird-only consumer transaction. Hand-assigned stages do not prove
provider availability, ABI compatibility, or published runtime closure.

For a first import, generated `pkgconfig()` provides are absent from published
metadata and `rpmspec --provides` cannot infer them. Add the corresponding
explicit devel-package BuildRequires alongside the pkgconfig constraint.
This exposes the same dependency to the graph before initial publication.
Without those edges, Ptyxis and VTE ran alongside their providers and Ptyxis
selected Fedora's VTE, which required an incompatible ICU soname.


## Spec and source-lock shape

- ptyxis and vte291 both resolve `Source0` from `download.gnome.org` using the
  `%gnome_major_version` / `%gnome_major_minor_version` and
  `%gnome_tarball_version` macros that `%gnome_check_version` defines. Those
  macros resolve in this factory's build root — `gdm`, `gnome-shell` and
  `gnome-session` already rely on them — so the imported spec needs no local
  edit for them. Verify against those recipes before patching a spec for a
  macro that is in fact available.
- gnome.org publishes `<name>-<version>.sha256sum` beside every tarball. Carry
  it as `sha256_url` and the Fedora lookaside copy as `fallback_urls`, matching
  the existing `gtk4` lock entry. `tools/upstream_bump.py` regenerates
  `sha256_url` from the gnome.org layout, so omitting it makes the entry a
  special case for no reason.
- Verify both digests before writing the lock: the SHA-512 must equal the pin
  in the recipe's dist-git `sources` manifest, and the SHA-256 must equal the
  upstream `.sha256sum`. They are independent claims and only one of them is
  checked by the recipe.
- Do not point the lock's `url` at `src.fedoraproject.org`. Fedora
  infrastructure is the fallback transport, never the primary source.

## Inventory counts

Adding recipes updates the data-driven inventory checks, listed in
[`font-package-recipes.md`](font-package-recipes.md). Note that
`tests/test_source_inventory.py` tracks the recipe count *minus the
Hummingbird-supplied ones* it skips, so it is one lower than the other three
and moves by the same delta, not to the same number.

Refresh the generated backlog report when importing terminal recipes; each newly provided binary changes its inventory-derived state even when the audit total stays fixed.

## Ghostty needs the factory's own Zig

Ghostty builds with `zig build`, and each Ghostty release sets a
`minimum_zig_version` in `build.zig.zon` that its `build.zig` enforces. Zig
breaks compatibility between minor releases, so the toolchain has to match
the release's minor series exactly. Neither Hummingbird nor Fedora can supply
it: Hummingbird carries only `zig-srpm-macros`, and Rawhide's `zig` trailed
(0.16.0 when Ghostty 1.4.0 required 0.17.0).

`packages/zig` therefore repackages the official ziglang.org release binary,
as Dakota's `elements/bluefin/zig.bst` does, on the `tailscale` binary-repack
precedent: the upstream tarball is `Source0`, SHA-512-locked, cross-checked
against the SHA-256 that `https://ziglang.org/download/index.json` publishes.
The binary is static and stripped, with no GNU build-id note, so the recipe
disables debuginfo, stripping and the missing-build-id failure. It installs
the library at `%{_prefix}/lib/zig`, the path Zig searches beside
`<exe>/../lib/zig`, so no `ZIG_LIB_DIR` is needed. The lock has no `feed`:
move it by hand together with Ghostty, to the newest patch release of the
series Ghostty's `minimum_zig_version` names. Utah never installs it; it is a
BuildRequires only.

## Ghostty's Zig packages are one generated Source0

`zig build` downloads every package in Ghostty's dependency graph (37 for
1.4.0), and the hermetic build is offline. Only `Source0` comes from upstream
(`tools/source_pipeline.py` fetches any other `sources` entry from Fedora's
lookaside), so the archives cannot be separate `SourceN` lines. Instead
`tools/generated_sources.py` (`_ghostty_generate`) reads the graph Ghostty
publishes for packagers, `build.zig.zon.json` in the release tarball, fetches
each archive (a `git+` URL becomes its forge's commit archive), and adds them
byte for byte under `ghostty-<version>/zig-deps/`, as Dakota's generated
`ghostty.bst` block does. `GHOSTTY_INPUT_SHA512` pins the release and every
archive by Zig package hash; a graph that names a package the pins do not, or
any byte change, fails closed. For 1.4.0 every archive's SHA-256 matched
Dakota's pin.

The recipe then seeds Zig's cache offline: unpack each archive, strip a lone
top-level directory as Zig's own fetcher does, and `zig fetch` the directory
(`zig fetch <archive>` keeps the top directory and fails the package hash).
At build time Zig checks every package against the hash `build.zig.zon`
names, a second integrity check independent of the pins.

Build options follow Dakota: `-Doptimize=ReleaseFast -Dcpu=baseline -Dpie=true
-Demit-docs=false`, and `--libc` pointing at the system glibc. Ghostty
defaults `gtk4-layer-shell` to the system library, so the recipe
BuildRequires `gtk4-layer-shell-devel`; the other C libraries build from the
bundled archives, as in Dakota. Add `--build-id=sha1`: Zig emits no build-id
by default, and RPM fails the build without one. Ghostty sets
`TERM=xterm-ghostty` and always installs its compiled terminfo
(`-Demit-terminfo` only adds the source). Hummingbird's `ncurses-term` 6.6
ships the `g/ghostty` alias but not `x/xterm-ghostty`, so the recipe deletes
its own `g/ghostty` (a file conflict otherwise) and keeps `x/xterm-ghostty`.
The tarball ships the compiled GTK resources, so no `blueprint-compiler` is
needed.
Dakota's light/dark theme patch changes the `/etc/skel` config from
projectbluefin/common, not the package, so it ships with Utah's configuration.
