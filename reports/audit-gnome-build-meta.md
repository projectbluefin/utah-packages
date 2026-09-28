# GNOME recipes vs gnome-build-meta audit

- GNOME release: `51.0` @ `a50b8c9de35f51c6a646c8178cde3c2c176725b6`
- factory revision audited: `c983402459d4c7a411336515299ef91de56ef7ca`

Every difference is classified, not treated as an automatic defect. `needs_review` entries carry evidence for a human to re-classify as intentional Fedora/RPM integration, intentional Hummingbird/downstream policy, or actionable drift. Record that decision in `classification_overrides` in `config/gnome-build-meta.json` so it survives the next re-run; an override is dropped (and reported) as soon as the tool no longer sees the entry as `needs_review`.

Feature options are diffed (`-D` options parsed from both the gbm element variables and the spec's configure invocation); dependency edges are compared by normalized name, and only unmatched **gbm** edges are counted, because an RPM spec also carries Fedora toolchain/packaging edges that have no gbm element by design. The JSON report holds the full `feature_comparison` and `dependency_comparison` per entry.

## Summary

- **aligned**: 13
- **needs_review**: 12
- **unmapped**: 1

## GNOME-owned factory sources not mapped

- `adw-gtk3-theme`: Third-party libadwaita-for-GTK3 theme; not a GNOME core/sdk component tracked by gnome-build-meta (issue #201 initial scope).
- `adwaita-fonts`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/adwaita-fonts.bst — candidate for a follow-up mapping pass.
- `adwaita-icon-theme`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/adwaita-icon-theme.bst — candidate for a follow-up mapping pass.
- `at-spi2-core`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/at-spi2-core.bst — candidate for a follow-up mapping pass.
- `dconf`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/dconf.bst — candidate for a follow-up mapping pass.
- `gcr`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/gcr.bst — candidate for a follow-up mapping pass.
- `gcr3`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds the 'gcr' module as elements/sdk/gcr.bst while Fedora ships it as 'gcr3' — candidate for a follow-up mapping pass once the release lines are confirmed to correspond.
- `gdm`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core/gdm.bst — candidate for a follow-up mapping pass.
- `geocode-glib`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/geocode-glib.bst — candidate for a follow-up mapping pass.
- `glycin`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/glycin.inc — candidate for a follow-up mapping pass.
- `gnome-autoar`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/gnome-autoar.bst — candidate for a follow-up mapping pass.
- `gnome-initial-setup`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core/gnome-initial-setup.bst — candidate for a follow-up mapping pass.
- `gnome-keyring`: GNOME-owned module with no gnome-build-meta element at the pinned release (GNOME 51.0 integrates gcr/libsecret instead), so there is nothing to audit against.
- `gnome-ponytail-daemon`: GNOME-owned factory source with no gnome-build-meta element at the pinned release (not part of the GNOME 51.0 core/sdk build), so there is nothing to audit against.
- `gnome-tweaks`: GNOME-owned factory source with no gnome-build-meta element at the pinned release (not part of the GNOME 51.0 core/sdk build), so there is nothing to audit against.
- `gobject-introspection`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/gobject-introspection.inc — candidate for a follow-up mapping pass.
- `graphene`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/graphene.bst from github:ebassi/graphene.git — candidate for a follow-up mapping pass.
- `gsound`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/gsound.bst — candidate for a follow-up mapping pass.
- `gssdp`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/gssdp.bst — candidate for a follow-up mapping pass.
- `gtk2`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds the 'gtk' module as elements/sdk/gtk.bst while Fedora ships it as 'gtk2' — candidate for a follow-up mapping pass once the release lines are confirmed to correspond.
- `gtksourceview4`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds the 'gtksourceview' module as elements/sdk/gtksourceview.bst while Fedora ships it as 'gtksourceview4' — candidate for a follow-up mapping pass once the release lines are confirmed to correspond.
- `gupnp`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/gupnp.bst — candidate for a follow-up mapping pass.
- `gweather-locations`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/gweather-locations.bst — candidate for a follow-up mapping pass.
- `json-glib`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/json-glib.bst — candidate for a follow-up mapping pass.
- `libcloudproviders`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/libcloudproviders.bst — candidate for a follow-up mapping pass.
- `libgda`: GNOME-owned factory source with no gnome-build-meta element at the pinned release (libgda is not part of the GNOME 51.0 core/sdk build), so there is nothing to audit against.
- `libgexiv2`: GNOME-owned factory source with no gnome-build-meta element at the pinned release (not part of the GNOME 51.0 core/sdk build), so there is nothing to audit against.
- `libgsf`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/libgsf.bst — candidate for a follow-up mapping pass.
- `libgtop2`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds the 'libgtop' module as elements/core-deps/libgtop.bst while Fedora ships it as 'libgtop2' — candidate for a follow-up mapping pass once the release lines are confirmed to correspond.
- `libgweather`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/libgweather.bst — candidate for a follow-up mapping pass.
- `libgxps`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/libgxps.bst — candidate for a follow-up mapping pass.
- `libmanette`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/libmanette.bst — candidate for a follow-up mapping pass.
- `libnma`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/libnma.bst — candidate for a follow-up mapping pass.
- `libnotify`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/libnotify.bst — candidate for a follow-up mapping pass.
- `libsecret`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/sdk/libsecret.bst — candidate for a follow-up mapping pass.
- `libsoup3`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds the 'libsoup' module as elements/sdk/libsoup.bst while Fedora ships it as 'libsoup3' — candidate for a follow-up mapping pass once the release lines are confirmed to correspond.
- `malcontent`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/malcontent.bst — candidate for a follow-up mapping pass.
- `mobile-broadband-provider-info`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/mobile-broadband-provider-info.bst — candidate for a follow-up mapping pass.
- `msgraph`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/msgraph.bst — candidate for a follow-up mapping pass.
- `startup-notification`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/startup-notification.bst — candidate for a follow-up mapping pass.
- `tecla`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core/tecla.bst — candidate for a follow-up mapping pass.
- `totem-pl-parser`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/totem-pl-parser.bst — candidate for a follow-up mapping pass.
- `xdg-user-dirs-gtk`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/xdg-user-dirs-gtk.bst — candidate for a follow-up mapping pass.
- `zenity`: GNOME-owned module outside issue #201's initial core/sdk mapping scope; gnome-build-meta builds it as elements/core-deps/zenity.bst — candidate for a follow-up mapping pass.

## Unaccounted GNOME-owned factory sources

- none: every GNOME-owned factory source is mapped or explicitly unmapped with a reason.

## mutter → `core/mutter.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/mutter/51/mutter-51.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 2 gbm-only, 0 factory-only
- Dependency edges: 31 gbm / 63 factory; 16 gbm edge(s) matched a factory edge, 15 not matched

## gnome-shell → `core/gnome-shell.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.0.tar.xz`
- Factory patches: gnome-shell-favourite-apps-firefox.patch
- Feature options: 0 same, 0 conflicting, 1 gbm-only, 1 factory-only
- Dependency edges: 32 gbm / 61 factory; 10 gbm edge(s) matched a factory edge, 22 not matched

## gnome-control-center → `core/gnome-control-center.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-control-center/51/gnome-control-center-51.0.tar.xz`
- Feature options: 2 same, 0 conflicting, 0 gbm-only, 3 factory-only
- Dependency edges: 37 gbm / 61 factory; 19 gbm edge(s) matched a factory edge, 18 not matched

## gnome-session → `core/gnome-session.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-session/51/gnome-session-51.0.tar.xz`
- Factory patches: 0001-Fedora-Set-grub-boot-flags-on-shutdown-reboot.patch
- Feature options: 0 same, 0 conflicting, 1 gbm-only, 0 factory-only
- Dependency edges: 10 gbm / 15 factory; 4 gbm edge(s) matched a factory edge, 6 not matched

## gnome-settings-daemon → `core/gnome-settings-daemon.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-settings-daemon/51/gnome-settings-daemon-51.0.tar.xz`
- Dependency edges: 25 gbm / 46 factory; 9 gbm edge(s) matched a factory edge, 16 not matched

## gnome-desktop3 → `core/gnome-desktop.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.alpha vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.alpha`
- GBM primary source: `https://download.gnome.org/sources/gnome-desktop/51/gnome-desktop-51.0.tar.xz`
- Feature options: 2 same, 0 conflicting, 0 gbm-only, 0 factory-only
- Dependency edges: 13 gbm / 24 factory; 11 gbm edge(s) matched a factory edge, 2 not matched

## gnome-bluetooth → `core/gnome-bluetooth.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `47.2`
- GBM primary source: `https://download.gnome.org/sources/gnome-bluetooth/47/gnome-bluetooth-47.2.tar.xz`
- Feature options: 1 same, 0 conflicting, 0 gbm-only, 0 factory-only
- Dependency edges: 13 gbm / 18 factory; 8 gbm edge(s) matched a factory edge, 5 not matched

## nautilus → `core/nautilus.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none; feature options conflict: -Dselinux gbm false vs factory true

- Factory version: `51~beta`
- GBM primary source: `https://download.gnome.org/sources/nautilus/51/nautilus-51.0.1.tar.xz`
- Factory patches: default-terminal.patch
- Feature option conflict: `-Dselinux` = `true` (factory) vs `false` (gbm `-Dselinux`)
- Feature options: 0 same, 1 conflicting, 0 gbm-only, 4 factory-only
- Dependency edges: 20 gbm / 36 factory; 12 gbm edge(s) matched a factory edge, 8 not matched

## gjs → `sdk/gjs.bst`

- Classification: **needs_review**
- Reason: release line 1.89 (factory) vs 1.90 (gbm)

- Factory version: `1.89.2`
- GBM primary source: `https://download.gnome.org/sources/gjs/1.90/gjs-1.90.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 2 gbm-only, 0 factory-only
- Dependency edges: 8 gbm / 20 factory; 4 gbm edge(s) matched a factory edge, 4 not matched

## gtk3 → `sdk/gtk+-3.bst`

- Classification: **needs_review**
- Reason: factory carries 2 local patch(es); gbm none; feature options conflict: -Dprofiler gbm false vs factory true

- Factory version: `3.24.52`
- GBM primary source: `https://download.gnome.org/sources/gtk/3.24/gtk-3.24.52.tar.xz`
- Factory patches: 9852_export_xdg_toplevel.patch, 9956_pointer_focus.patch
- Feature option conflict: `-Dprofiler` = `true` (factory) vs `false` (gbm `-Dprofiler`)
- Feature options: 5 same, 1 conflicting, 6 gbm-only, 4 factory-only
- Dependency edges: 24 gbm / 48 factory; 10 gbm edge(s) matched a factory edge, 14 not matched

## gtk4 → `sdk/gtk.bst`

- Classification: **needs_review**
- Reason: release line 4.23 (factory) vs 4.24 (gbm)

- Factory version: `4.23.3`
- GBM primary source: `https://download.gnome.org/sources/gtk/4.24/gtk-4.24.0.tar.xz`
- Feature options: 4 same, 0 conflicting, 0 gbm-only, 5 factory-only
- Dependency edges: 26 gbm / 62 factory; 9 gbm edge(s) matched a factory edge, 17 not matched

## libadwaita → `sdk/libadwaita.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `1.10.beta.1`
- GBM primary source: `https://download.gnome.org/sources/libadwaita/1.10/libadwaita-1.10.0.tar.xz`
- Factory patches: fix-sassc-requirement-for-tarball-builds.patch
- Feature options: 0 same, 0 conflicting, 2 gbm-only, 1 factory-only
- Dependency edges: 9 gbm / 16 factory; 5 gbm edge(s) matched a factory edge, 4 not matched

## gdk-pixbuf2 → `sdk/gdk-pixbuf.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `2.44.8`
- GBM primary source: `https://download.gnome.org/sources/gdk-pixbuf/2.44/gdk-pixbuf-2.44.8.tar.xz`
- Factory patches: CVE-2026-16768.patch
- Feature options: 0 same, 0 conflicting, 10 gbm-only, 4 factory-only
- Dependency edges: 10 gbm / 15 factory; 4 gbm edge(s) matched a factory edge, 6 not matched

## pango → `sdk/pango.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `1.58.2`
- GBM primary source: `https://download.gnome.org/sources/pango/1.58/pango-1.58.2.tar.xz`
- Feature options: 0 same, 0 conflicting, 2 gbm-only, 3 factory-only
- Dependency edges: 13 gbm / 28 factory; 10 gbm edge(s) matched a factory edge, 3 not matched

## cairo → `sdk/cairo.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `1.18.4`
- GBM primary source: `https://gitlab.freedesktop.org/cairo/cairo.git`
- Factory patches: cairo-multilib.patch
- Feature options: 3 same, 0 conflicting, 0 gbm-only, 7 factory-only
- Dependency edges: 9 gbm / 18 factory; 6 gbm edge(s) matched a factory edge, 3 not matched

## librsvg2 → `sdk/librsvg.bst`

- Classification: **needs_review**
- Reason: release line 2.62 (factory) vs 2.63 (gbm); factory carries 3 local patch(es); gbm none

- Factory version: `2.62.3`
- GBM primary source: `https://download.gnome.org/sources/librsvg/2.63/librsvg-2.63.0.tar.xz`
- Factory patches: 0001-Fedora-Drop-dependencies-required-for-benchmarking.patch, 0002-Fedora-Drop-dependencies-and-references-to-mutation-.patch, 0003-Fedora-Drop-windows-specific-dependencies.patch
- Feature options: 0 same, 0 conflicting, 2 gbm-only, 1 factory-only
- Dependency edges: 13 gbm / 23 factory; 8 gbm edge(s) matched a factory edge, 5 not matched

## gsettings-desktop-schemas → `sdk/gsettings-desktop-schemas.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gsettings-desktop-schemas/51/gsettings-desktop-schemas-51.0.tar.xz`
- Dependency edges: 4 gbm / 6 factory; 3 gbm edge(s) matched a factory edge, 1 not matched

## glib-networking → `sdk/glib-networking.bst`

- Classification: **aligned**
- Reason: release line 2.90 matches; factory 2.90~alpha vs gbm 2.90.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `2.90~alpha`
- GBM primary source: `https://download.gnome.org/sources/glib-networking/2.90/glib-networking-2.90.0.tar.xz`
- Feature options: 1 same, 0 conflicting, 0 gbm-only, 2 factory-only
- Dependency edges: 7 gbm / 15 factory; 6 gbm edge(s) matched a factory edge, 1 not matched

## gvfs → `sdk-deps/gvfs.bst`

- Classification: **needs_review**
- Reason: release line 1.61 (factory) vs 1.62 (gbm)

- Factory version: `1.61.91`
- GBM primary source: `https://download.gnome.org/sources/gvfs/1.62/gvfs-1.62.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 1 gbm-only, 10 factory-only
- Dependency edges: 28 gbm / 43 factory; 19 gbm edge(s) matched a factory edge, 9 not matched

## gvfs-client → `sdk/gvfs-client.bst`

- Classification: **aligned**
- Reason: gbm element is a filter aggregating shared sources; membership aligned (no independent source identity to compare)

- Factory version: `1.61.91`
- Feature options: 0 same, 0 conflicting, 0 gbm-only, 10 factory-only
- Dependency edges: 4 gbm / 43 factory; 1 gbm edge(s) matched a factory edge, 3 not matched

## gvfs-daemon → `core/gvfs-daemon.bst`

- Classification: **aligned**
- Reason: gbm element is a filter aggregating shared sources; membership aligned (no independent source identity to compare)

- Factory version: `1.61.91`
- Feature options: 0 same, 0 conflicting, 0 gbm-only, 10 factory-only
- Dependency edges: 28 gbm / 43 factory; 17 gbm edge(s) matched a factory edge, 11 not matched

## gnome-online-accounts → `core-deps/gnome-online-accounts.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `3.58.1`
- GBM primary source: `https://download.gnome.org/sources/gnome-online-accounts/3.58/gnome-online-accounts-3.58.1.tar.xz`
- Feature options: 0 same, 0 conflicting, 0 gbm-only, 4 factory-only
- Dependency edges: 14 gbm / 28 factory; 8 gbm edge(s) matched a factory edge, 6 not matched

## evolution-data-server → `core-deps/evolution-data-server.bst`

- Classification: **needs_review**
- Reason: release line 3.61 (factory) vs 3.62 (gbm); factory carries 1 local patch(es); gbm none; feature options conflict: -DENABLE_OAUTH2_WEBKITGTK gbm OFF vs factory ON

- Factory version: `3.61.3`
- GBM primary source: `https://download.gnome.org/sources/evolution-data-server/3.62/evolution-data-server-3.62.0.tar.xz`
- Factory patches: Make-DBUS_SERVICES_PREFIX-runtime-configurable.patch
- Feature option conflict: `-DENABLE_OAUTH2_WEBKITGTK` = `ON` (factory) vs `OFF` (gbm `-DENABLE_OAUTH2_WEBKITGTK`)
- Feature options: 3 same, 1 conflicting, 8 gbm-only, 15 factory-only
- Dependency edges: 18 gbm / 49 factory; 10 gbm edge(s) matched a factory edge, 8 not matched

## localsearch → `core-deps/localsearch.bst`

- Classification: **aligned**
- Reason: release line 3.12 matches; factory 3.12~beta vs gbm 3.12.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `3.12~beta`
- GBM primary source: `https://download.gnome.org/sources/localsearch/3.12/localsearch-3.12.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 1 gbm-only, 10 factory-only
- Dependency edges: 30 gbm / 37 factory; 13 gbm edge(s) matched a factory edge, 17 not matched

## tinysparql → `sdk/tinysparql.bst`

- Classification: **unmapped**
- Reason: factory source not present in config/upstream-sources.json

- GBM primary source: `https://download.gnome.org/sources/tinysparql/3.12/tinysparql-3.12.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 3 gbm-only, 0 factory-only
- Dependency edges: 15 gbm / 0 factory; 0 gbm edge(s) matched a factory edge, 15 not matched

## xdg-desktop-portal-gnome → `core-deps/xdg-desktop-portal-gnome.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.alpha vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.alpha`
- GBM primary source: `https://download.gnome.org/sources/xdg-desktop-portal-gnome/51/xdg-desktop-portal-gnome-51.0.tar.xz`
- Feature options: 0 same, 0 conflicting, 1 gbm-only, 1 factory-only
- Dependency edges: 8 gbm / 15 factory; 6 gbm edge(s) matched a factory edge, 2 not matched


_This is a non-gating evidence report. It is safe to regenerate for a newer GNOME release without rewriting the tool._
