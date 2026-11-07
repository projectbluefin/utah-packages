---
name: gnome-dependency-floors
description: >-
  Owner decision D9: every minimum version a GNOME module the factory builds
  declares for a dependency must be met by the factory's lock of that
  dependency. Load before reading or acting on a `tools/gnome_dep_floors.py`
  finding, changing that tool, or moving a dependency because a GNOME module
  needs a newer one.
metadata:
  type: procedure
---

# GNOME dependency floors (D9)

A recipe's `BuildRequires` is not where a GNOME module's real floor lives.
nautilus 51.1 failed meson configure with
`gtk4 ... found 4.23.4 but need: '>= 4.24.0'` (#565) while its spec still
said `pkgconfig(gtk4) >= 4.22.0`, so the build root resolved and only meson
knew. The floor is in the module's own build files, so
`tools/gnome_dep_floors.py` reads it from the locked upstream tarball.

```sh
just gnome-dep-floors                      # report; exit 1 on an unmet floor
just gnome-dep-floors --module nautilus    # one module
just gnome-dep-floors --apply              # move every unmet dependency
```

## What it checks

- **Modules**: locks whose primary is download.gnome.org, plus every package
  `config/gnome-build-meta.json` maps (through `factory_alias`), such as
  cairo. Each tarball is streamed into a temporary directory, checked
  against the lock's SHA-512, read, and deleted. A transport error falls back
  to the next `fallback_urls` entry. A digest mismatch stops. `--cache-dir`
  keeps the tarballs between local runs.
- **Floors**: meson `dependency('x', version: ...)`, walked from the top
  `meson.build` through `subdir()` the way meson runs it, so `subprojects/`
  is never read. Versions are evaluated through string variables, `+`,
  `.format()`, f-strings, lists and `+=` (`glib_req = '>= 2.86'`,
  `'>= @0@'.format(glib_min)`). Without a `meson.build`, the tool reads
  `PKG_CHECK_MODULES`/`PKG_CHECK_EXISTS` in configure.ac (shell and
  `m4_define` variables), then `pkg_check_modules` in CMakeLists.txt
  (evolution-data-server). `>=`, `>` and `==` are floors. Ceilings are
  ignored.
- **Who provides a name**: the factory recipe whose published binaries
  provide `pkgconfig(name)` in the factory image's primary.xml (what
  `tools/build_graph.py` reads), or whose spec ships `name.pc`
  (`tools/extract_buildrequires.sh --pc-provides`, so unpublished recipes
  count). That recipe's lock is the version. If no recipe provides the name,
  the tool uses Hummingbird's primary.xml (`config/hummingbird.repo`). The
  build root (`tools/mock_config.py`) ranks the factory first, Hummingbird
  second and Fedora 44 last, so Hummingbird's version is the one a build
  gets. glib, for example, comes from Hummingbird. Fedora is not read.

## Statuses

| Status | Meaning | Fails the check |
| --- | --- | --- |
| `ok` | The lock, or Hummingbird's version, meets the floor | no |
| `unmet` | A factory lock is below the floor; the finding names the move `--apply` makes, or why it cannot | yes |
| `external` | The factory does not build the dependency and Hummingbird's version is below the floor. `--apply` cannot move it; import it into the factory or wait for Hummingbird | yes |
| `unread` | The module's tarball could not be fetched or verified | yes |
| `unmapped` | Neither a factory recipe nor Hummingbird provides the name | no |
| `unlocked` | A factory recipe ships the name but has no source lock | no |
| `unparsed` | The version expression is outside the evaluated subset (`run_command()`, a ternary) | no |

`unmapped` is only reported, not failed, because Fedora is not read. On
2026-11-06 there were 57, for example:

- Dependencies the build root takes from Fedora, because the recipe
  BuildRequires them: totem's `grilo-0.3`, rygel's `gupnp-av-1.0`,
  msgraph's `libuhttpmock-1.0`, gdm's `check`. Fedora decides their
  version. If a GNOME release needs one newer than Fedora ships, import
  the dependency into the factory, and D9 then covers it.
- Names the recipe never asks for: foreign platforms (`gio-windows-2.0`,
  `gtk4-quartz`, `gtk4-android`) and fallbacks behind the name the recipe
  uses (gvfs asks for `libplist` only when `libplist-2.0` is missing, and
  its recipe BuildRequires `libplist-2.0`).

Read the list when it changes: a new name can be a real gap.

## Comparing versions

Versions compare with rpmvercmp, the order pkg-config uses. Both sides are
put in RPM prerelease spelling first: build files and tarballs write
`2.2.alpha.7`, locks write `2.2~beta`, and as written the tilde sorts the
beta below the alpha. Without that, gdk-pixbuf2's
`glycin-2 >= 2.2.alpha.7` read as unmet against glycin `2.2~beta`.

## How `--apply` picks the release

It takes the strongest unmet floor per dependency. A GNOME dependency (a
download.gnome.org primary or explicit `feed`) moves to the newest final of
the **lowest** series that meets the floor. The series is the directory
download.gnome.org files the release under in `cache.json`, so it matches
upstream_bump's `release_cycle()`. Lowest, because that is the series the
floor names, and GNOME version numbers cannot tell a newer stable series
from a development one (pango 1.90; see `cycle_final` in
`tools/upstream_bump.py`). gtk4 at 4.23.4 under nautilus' `>= 4.24.0`
becomes `--cycle 4.24` and moves to 4.24.1, never to 4.25.0. A forge or
Anitya dependency takes the floor's `major.minor` as `--cycle`, which
upstream_bump ignores for those feeds: it moves to the newest release of
the lock's major.

The tool calls `tools/upstream_bump.py` only through its CLI. It runs
`--package <dep> --cycle <series>` without `--apply` first and parses the
proposal (`<dep>: <old> -> <new>`). It refuses the move with the reason
when nothing is proposed (review-only list, a hold, a cross-major forge
release; upstream_bump's own `needs review`/`skipped` line is quoted) or
when the proposal is still below the floor. After `--apply` it checks that
the lock meets the floor. A GNOME module that moved is read again, because
its floors moved with it, for up to five rounds.

After an `--apply`, follow
[`upstream-version-bumps.md`](upstream-version-bumps.md): check the
tarball against GNOME's `.sha256sum`, re-pin the recipe from Rawhide if it
differs only by `Version:` and `sources`, and expect the recipe to need the
changes the new release brings.

## Where it runs

`.github/workflows/bump-upstream-sources.yml` runs the check on the tree its
daily run just bumped, writes the findings to the job summary and as
`::error` annotations, and fails the job at its end, after the pull request
and its gate. An unmet floor is one dependency to move, not a reason to hold
back every other bump. It is not part of `just check`: it downloads about
300 MB of tarballs plus both repositories' metadata (about 20 s on a fast
link), which a pull-request gate should not do.
