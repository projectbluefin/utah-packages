---
name: terminal-emulator-recipes
description: >-
  What it takes to ship a terminal emulator on Hummingbird: Hummingbird
  carries no VTE at all, so every VTE-based terminal needs a complete dependency closure with
  vte291 first, plus the build ordering and source-lock shape for the GTK4
  desktop closure. Load when importing ptyxis, gnome-console, kgx, vte291, or
  any other terminal recipe.
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
