# GNOME recipes vs gnome-build-meta audit

- GNOME release: `51.0` @ `a50b8c9de35f51c6a646c8178cde3c2c176725b6`
- factory revision audited: `b77cd7cd5b885880006e21b9d705459ccc5b9bda`

Every difference is classified, not treated as an automatic defect. `needs_review` entries carry evidence for a human to re-classify as intentional Fedora/RPM integration, intentional Hummingbird/downstream policy, or actionable drift.

## Summary

- **aligned**: 14
- **needs_review**: 12

## mutter → `core/mutter.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/mutter/51/mutter-51.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 31

## gnome-shell → `core/gnome-shell.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-shell/51/gnome-shell-51.0.tar.xz`
- Factory patches: gnome-shell-favourite-apps-firefox.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 32

## gnome-control-center → `core/gnome-control-center.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-control-center/51/gnome-control-center-51.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 37

## gnome-session → `core/gnome-session.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-session/51/gnome-session-51.0.tar.xz`
- Factory patches: 0001-Fedora-Set-grub-boot-flags-on-shutdown-reboot.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 10

## gnome-settings-daemon → `core/gnome-settings-daemon.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gnome-settings-daemon/51/gnome-settings-daemon-51.0.tar.xz`
- GBM dependency edges: 25

## gnome-desktop3 → `core/gnome-desktop.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.alpha vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.alpha`
- GBM primary source: `https://download.gnome.org/sources/gnome-desktop/51/gnome-desktop-51.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 13

## gnome-bluetooth → `core/gnome-bluetooth.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `47.2`
- GBM primary source: `https://download.gnome.org/sources/gnome-bluetooth/47/gnome-bluetooth-47.2.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 13

## nautilus → `core/nautilus.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `51~beta`
- GBM primary source: `https://download.gnome.org/sources/nautilus/51/nautilus-51.0.1.tar.xz`
- Factory patches: default-terminal.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 20

## gjs → `sdk/gjs.bst`

- Classification: **needs_review**
- Reason: release line 1.89 (factory) vs 1.90 (gbm)

- Factory version: `1.89.2`
- GBM primary source: `https://download.gnome.org/sources/gjs/1.90/gjs-1.90.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 8

## gtk3 → `sdk/gtk+-3.bst`

- Classification: **needs_review**
- Reason: factory carries 2 local patch(es); gbm none

- Factory version: `3.24.52`
- GBM primary source: `https://download.gnome.org/sources/gtk/3.24/gtk-3.24.52.tar.xz`
- Factory patches: 9852_export_xdg_toplevel.patch, 9956_pointer_focus.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 24

## gtk4 → `sdk/gtk.bst`

- Classification: **needs_review**
- Reason: release line 4.23 (factory) vs 4.24 (gbm)

- Factory version: `4.23.3`
- GBM primary source: `https://download.gnome.org/sources/gtk/4.24/gtk-4.24.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 26

## libadwaita → `sdk/libadwaita.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `1.10.beta.1`
- GBM primary source: `https://download.gnome.org/sources/libadwaita/1.10/libadwaita-1.10.0.tar.xz`
- Factory patches: fix-sassc-requirement-for-tarball-builds.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 9

## gdk-pixbuf2 → `sdk/gdk-pixbuf.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `2.44.8`
- GBM primary source: `https://download.gnome.org/sources/gdk-pixbuf/2.44/gdk-pixbuf-2.44.8.tar.xz`
- Factory patches: CVE-2026-16768.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 10

## pango → `sdk/pango.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `1.58.2`
- GBM primary source: `https://download.gnome.org/sources/pango/1.58/pango-1.58.2.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 13

## cairo → `sdk/cairo.bst`

- Classification: **needs_review**
- Reason: factory carries 1 local patch(es); gbm none

- Factory version: `1.18.4`
- GBM primary source: `https://gitlab.freedesktop.org/cairo/cairo.git`
- Factory patches: cairo-multilib.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 9

## librsvg2 → `sdk/librsvg.bst`

- Classification: **needs_review**
- Reason: release line 2.62 (factory) vs 2.63 (gbm); factory carries 3 local patch(es); gbm none

- Factory version: `2.62.3`
- GBM primary source: `https://download.gnome.org/sources/librsvg/2.63/librsvg-2.63.0.tar.xz`
- Factory patches: 0001-Fedora-Drop-dependencies-required-for-benchmarking.patch, 0002-Fedora-Drop-dependencies-and-references-to-mutation-.patch, 0003-Fedora-Drop-windows-specific-dependencies.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 14

## gsettings-desktop-schemas → `sdk/gsettings-desktop-schemas.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.beta vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.beta`
- GBM primary source: `https://download.gnome.org/sources/gsettings-desktop-schemas/51/gsettings-desktop-schemas-51.0.tar.xz`
- GBM dependency edges: 4

## glib-networking → `sdk/glib-networking.bst`

- Classification: **aligned**
- Reason: release line 2.90 matches; factory 2.90~alpha vs gbm 2.90.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `2.90~alpha`
- GBM primary source: `https://download.gnome.org/sources/glib-networking/2.90/glib-networking-2.90.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 7

## gvfs → `sdk-deps/gvfs.bst`

- Classification: **needs_review**
- Reason: release line 1.61 (factory) vs 1.62 (gbm)

- Factory version: `1.61.91`
- GBM primary source: `https://download.gnome.org/sources/gvfs/1.62/gvfs-1.62.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 28

## gvfs-client → `sdk/gvfs-client.bst`

- Classification: **aligned**
- Reason: gbm element is an filter aggregating shared sources; membership aligned (no independent source identity to compare)

- Factory version: `1.61.91`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 4

## gvfs-daemon → `core/gvfs-daemon.bst`

- Classification: **aligned**
- Reason: gbm element is an filter aggregating shared sources; membership aligned (no independent source identity to compare)

- Factory version: `1.61.91`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 28

## gnome-online-accounts → `core-deps/gnome-online-accounts.bst`

- Classification: **aligned**
- Reason: source identity and release line aligned

- Factory version: `3.58.1`
- GBM primary source: `https://download.gnome.org/sources/gnome-online-accounts/3.58/gnome-online-accounts-3.58.1.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 14

## evolution-data-server → `core-deps/evolution-data-server.bst`

- Classification: **needs_review**
- Reason: release line 3.61 (factory) vs 3.62 (gbm); factory carries 1 local patch(es); gbm none

- Factory version: `3.61.3`
- GBM primary source: `https://download.gnome.org/sources/evolution-data-server/3.62/evolution-data-server-3.62.0.tar.xz`
- Factory patches: Make-DBUS_SERVICES_PREFIX-runtime-configurable.patch
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 18

## localsearch → `core-deps/localsearch.bst`

- Classification: **aligned**
- Reason: release line 3.12 matches; factory 3.12~beta vs gbm 3.12.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `3.12~beta`
- GBM primary source: `https://download.gnome.org/sources/localsearch/3.12/localsearch-3.12.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 30

## tinysparql → `core-deps/localsearch.bst`

- Classification: **aligned**
- Reason: release line 3.12 matches; factory 3.12~beta vs gbm 3.12.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `3.12~beta`
- GBM primary source: `https://download.gnome.org/sources/localsearch/3.12/localsearch-3.12.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 30

## xdg-desktop-portal-gnome → `core-deps/xdg-desktop-portal-gnome.bst`

- Classification: **aligned**
- Reason: release line 51 matches; factory 51.alpha vs gbm 51.0 (factory tracks the dev/rawhide bump within the same line)

- Factory version: `51.alpha`
- GBM primary source: `https://download.gnome.org/sources/xdg-desktop-portal-gnome/51/xdg-desktop-portal-gnome-51.0.tar.xz`
- Feature options: see JSON report for the full diff.
- GBM dependency edges: 8


_This is a non-gating evidence report. It is safe to regenerate for a newer GNOME release without rewriting the tool._
