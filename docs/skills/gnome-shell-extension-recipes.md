---
name: gnome-shell-extension-recipes
description: >-
  The shared layout of the gnome-shell-extension-* recipes written from
  Project Bluefin Dakota's shell-extension elements: naming, source pins,
  install paths, global schemas, file modes and the build-time checks Utah's
  extension contract relies on. Load when adding, bumping or reviewing one.
metadata:
  type: procedure
---

# GNOME Shell extension recipes from Dakota elements

Dakota (projectbluefin/dakota) builds each Bluefin GNOME Shell extension from
`elements/bluefin/shell-extensions/<element>.bst`. Where Fedora packages the
extension (appindicator, blur-my-shell, caffeine, dash-to-dock, gsconnect),
the factory imports Fedora's recipe. The others have no Fedora recipe, so
each gets a hand-written recipe from its element
(projectbluefin/utah-packages#1028). They all follow one layout, so that the
RPMs satisfy what Utah's `scripts/build-gnome-extensions.sh` and
`scripts/verify-gnome-extensions.py` require of an installed extension.

| Element | Recipe | UUID |
| --- | --- | --- |
| `bazaar-companion` | `gnome-shell-extension-bazaar-companion` | `bazaar-integration@kolunmi.github.io` |
| `budslink-companion` | `gnome-shell-extension-budslink-companion` | `BudsLink-Companion@maniacx.github.com` |
| `custom-command-menu` | `gnome-shell-extension-custom-command-menu` | `custom-command-list@storageb.github.com` |
| `fuzzy-application-search` | `gnome-shell-extension-fuzzy-application-search` | `fuzzy-application-search@mkhl.codeberg.page` |
| `gradia-capture` | `gnome-shell-extension-gradia-capture` | `gradia-integration@alexandervanhee.github.io` |
| `power-status-color` | `gnome-shell-extension-power-status-color` | `power-status-color@projectbluefin.io` |
| `quicksettings-audio-devices-hider` | `gnome-shell-extension-quicksettings-audio-devices-hider` | `quicksettings-audio-devices-hider@marcinjahn.com` |
| `quicksettings-audio-devices-renamer` | `gnome-shell-extension-quicksettings-audio-devices-renamer` | `quicksettings-audio-devices-renamer@marcinjahn.com` |
| `syncthing-toggle` | `gnome-shell-extension-syncthing-toggle` | `syncthing-toggle@projectbluefin.io` |
| `tailscale-qs` | `gnome-shell-extension-tailscale-qs` | `tailscale-gnome-qs@tailscale-qs.github.io` |
| `tilingshell` | `gnome-shell-extension-tilingshell` | `tilingshell@ferrarodomenico.com` |

## Recipe layout

- **Name**: `gnome-shell-extension-<element>`, `BuildArch: noarch`,
  `Requires: gnome-shell`. The header comment names the element and the Dakota
  commit it was read from.
- **Source**: the element's `ref`, and nothing newer. A tag ref locks the tag
  archive and uses the tag as `Version`. A branch commit locks the GitHub (or
  Codeberg) commit archive with `Version: 0^<commit date>git<shortcommit>`.
  An extensions.gnome.org `zip` source locks the same `version_tag` download
  (its SHA-256 equals the element's `ref`) and uses the metadata
  `version-name`, or `version` when there is none. RPM cannot name a file
  after a query string, so `Source0` ends in `#/%{name}-%{version}.zip`.
- **Patches**: the element's `kind: patch` sources, copied from Dakota's
  `patches/` unchanged, applied with `%autosetup -p1`.
- **Files**: the files the element copies into
  `%{_datadir}/gnome-shell/extensions/<uuid>`. `README.md` and `LICENSE`
  become `%doc` and `%license` instead of extension files.
- **Schemas**: every `schemas/*.gschema.xml` goes to
  `%{_datadir}/glib-2.0/schemas`, the way Fedora's extension RPMs do it, and
  the extension directory gets no `schemas/` at all: neither the XML nor a
  `gschemas.compiled` (extensions.gnome.org zips ship one). An
  extension-local schema directory wins over the system one in
  `Extension.getSettings()`, so gschema overrides would not apply to it, and
  Utah's verifier fails on it. glib2's file trigger compiles the system
  directory on install; the recipe never runs `glib-compile-schemas` into the
  buildroot.
- **Modes**: `%install` sets every directory under the extension to `0755`
  and every file to `0644`. extensions.gnome.org zips carry a `0600`
  `metadata.json`, which GNOME Shell (running as the user) cannot read, and
  tilingshell's carries `0777` files. No extension needs an executable bit:
  helpers such as syncthing-toggle's `service.js` run through `gjs -m`.
- **`%check`**: `metadata.json` declares the expected UUID, the extension
  directory has no `schemas/`, and an extension with schemas passes
  `glib-compile-schemas --strict --dry-run` on the installed copy.

## GNOME 51 and `shell-version`

The recipes do not rewrite `shell-version`. Several pinned releases stop at
GNOME 50, as they do in Dakota. Dakota and Utah both turn off extension
version validation (`disable-extension-version-validation=true`: Dakota's
`disable-ext-validator.bst`, Utah's `zz3-bluefin-unsupported-stuff.gschema.override`),
and Utah's verifier accepts a missing `51` only while that override is in
place. Where Dakota makes the extension declare 51 itself (tilingshell's
GNOME 51 patch), `%check` asserts that `51` is present, as the element does.

## Runtime requirements

`Requires` follow the element's `depends`/`runtime-depends` where Utah ships
an equivalent. `gnome-shell-extension-tailscale-qs` requires
`dakota-config-tailscale-setup`, the desktop app Dakota's
`tailscale-setup.patch` launches. `gnome-shell-extension-syncthing-toggle`
requires what its helper runs (`gjs`, `podman`, `systemd`, `coreutils`,
`xdg-user-dirs`) and libsoup 3. It does not require `syncthing`: Dakota keeps the
native unit only to migrate existing Dakota installs, and Utah ships none.
The dconf keyfiles from the custom-command-menu element are
`dakota-config-custom-command-menu-dconf` (see
[`config-packages.md`](config-packages.md)), not part of the extension recipe.

## Moving a pin

Move a pin only to the `ref` of a newer Dakota element. Update the commit,
date and version, relock the source in `config/upstream-sources.json` and the
recipe's `sources`, and diff the element's install commands and patches against
the recipe. A new schema, file or directory in the element shows up as an
unpackaged file or as a missing path in `%files`.
