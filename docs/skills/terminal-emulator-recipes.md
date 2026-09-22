---
name: terminal-emulator-recipes
description: >-
  What it takes to ship a terminal emulator on Hummingbird: Hummingbird
  carries no VTE at all, so every VTE-based terminal is a two-recipe job with
  vte291 first, plus the stage ordering and source-lock shape for the GTK4
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

## Consequence: a VTE terminal is two recipes, and vte291 comes first

`vte291` is Fedora's source package name for VTE. Both `ptyxis` and
`gnome-console` BuildRequire `pkgconfig(vte-2.91-gtk4)` and at runtime link
`libvte-2.91-gtk4.so.0`, which only the `vte291-gtk4` subpackage provides.
Import both recipes; importing the terminal alone produces an RPM whose
dependency closure does not resolve on Hummingbird, which is the failure mode
[`targeting-hummingbird.md`](../targeting-hummingbird.md) calls "installs
nowhere".

vte291's own runtime `Requires` (fribidi, glib2, gnutls, gtk3, libicu, pango,
pcre2, systemd-libs) are all either base-OS packages Hummingbird ships or
recipes this factory already builds, so vte291 is the bottom of the new stack.

## Stage ordering

Stage N resolves against stages `< N` only, so each new recipe goes strictly
above its highest factory-built dependency. Read the real stages out of
`config/upstream-sources.json` before choosing — the worked example in
`targeting-hummingbird.md` is older than the current numbering, and `gtk4` is
no longer at stage 1.

For utah-packages#224:

| recipe | highest factory dependency | stage |
| --- | --- | --- |
| `vte291` | `gtk4` (stage 4) | 5 |
| `ptyxis` | `libadwaita` (stage 6), `libportal` and `vte291` (stage 5) | 7 |

`gnome-console` would take the same slot as `ptyxis`: same `vte291` dependency,
same `libadwaita` floor.

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

Adding two recipes moves four assertions, listed in
[`font-package-recipes.md`](font-package-recipes.md). Note that
`tests/test_source_inventory.py` tracks the recipe count *minus the
Hummingbird-supplied ones* it skips, so it is one lower than the other three
and moves by the same delta, not to the same number.
