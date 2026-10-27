---
name: font-package-recipes
description: >-
  Conventions and naming subtleties for font package recipes, including
  dist-git source names versus subpackage provides, spec structure under
  fonts-rpm-macros, and source verification. Load when importing or updating
  font recipes.
metadata:
  type: procedure
---

# Font Package Recipes and Dist-Git Naming

Font packages in Fedora have specific packaging conventions driven by
`fonts-rpm-macros`. This guide captures subtleties encountered when resolving
dependencies and importing font recipes into `utah-packages`.

## Reconcile consumer decisions before importing

[Utah's font decision](https://github.com/projectbluefin/utah/issues/393#issuecomment-5920428811)
rejects bulk font parity with Bluefin classic. A font's presence in the
original audit is not approval to import it: record the rejected parity
request in `[wontfix]` with that decision link, preserving the audit name,
and regenerate `reports/factory-build-backlog.json`. A deliberate individual
font addition needs its own proposal. This does not remove existing recipes
or claim their binaries are published.

Do not extend that font decision to character mappings or input-method data.
In particular, `adobe-mappings-*`, `anthy-unicode`, and
`cldr-emoji-annotation*` remain separate functionality work; the maintainer
explicitly distinguishes input methods from fonts. Likewise, an existing
variable-font recipe is not proof that an older, differently named binary
is provided. Check its actual provides and published metadata rather than
closing a name based on a similar recipe directory.

## Source package names vs. provided binary subpackages

When satisfying a runtime or metapackage font requirement (e.g., from
`default-fonts-*` in `langpacks`), the required package name is frequently a
subpackage or virtual provide rather than the dist-git repository name.

- **Example**: `default-fonts-core-emoji` requires `google-noto-emoji-color-fonts`.
  Querying Fedora dist-git for `rpms/google-noto-emoji-color-fonts` returns 404
  because the upstream source package is named `google-noto-color-emoji-fonts`.
  Its spec explicitly declares:
  ```spec
  %global fontpkgheader0 %{expand:
  Provides: google-noto-emoji-color-fonts = %{epoch}:%{version}-%{release}
  }
  ```
- **Rule**: Always verify which source package provides a given font capability
  in Fedora before importing via `tools/import_rawhide.py`. Import the source
  RPM name, never the subpackage name.

## Specs driven by `fonts-rpm-macros` often omit `Name:`

Specs using `fonts-rpm-macros` generate binary package definitions using
`%fontpkg -a` or `%fontpkg -z ...` and derive the package name from
`%global fontname` or `%global fontfamily` (for example, `stix-fonts.spec` and
`google-noto-sans-cjk-vf-fonts.spec`).

- Tools parsing specs must not rely solely on top-level `Name:` fields.
- `tools/package_inventory.py` relies on the recipe directory name under
  `packages/<name>/` and matches it against `config/upstream-sources.json` and
  `.packit.yaml`.

## Source verification and forge macros

- Font upstreams commonly publish release tarballs on GitHub (e.g., `stix-fonts`
  via `stipub/stixfonts` with `%forgemeta`).
- Direct source URLs can be locked in `config/upstream-sources.json` against the
  canonical release tag archives and matched against the dist-git `sources`
  SHA-512 manifest.
- Always include Fedora lookaside URLs in `fallback_urls` for mirror redundancy.

## Ghostscript resources and desktop parity

Utah rejected bulk desktop font parity in
[utah#393](https://github.com/projectbluefin/utah/issues/393#issuecomment-5920428811).
Reconcile optional desktop faces against that decision, but inspect runtime
consumers before applying it to printing resources: `ghostscript`'s `libgs`
requires `urw-base35-fonts` only when system resources are enabled, and Utah's
`packages/ghostscript/ghostscript.spec` currently builds with
`%bcond system_resources 0` (bundled `Resource/` tree). No factory recipe
consumes URW until a follow-up flips that switch. One URW source
recipe emits the metapackage, common files, ten font families and build macros;
do not import each family separately. Its custom `%fontfamily_subpkg` macro
hides those names from the backlog's static `%package` scan.

The modern URW release includes Type 1, AFM and OTF files used by Ghostscript.
The separate `legacy` subpackage contains old PFB/PFM files for X11 clients;
it is disabled by default here because its archive is a lookaside-only source
and legacy is not a requested output, so it is not locked here. Do not replace
the modern Type 1 files with OTF alone: the recipe documents Ghostscript PDF
conversion problems with that substitution. Enabling legacy requires adding a
lookaside source lock for that archive first.

Check virtual provides before importing dependencies: Hummingbird's
`fonts-filesystem` provides `fontpackages-filesystem`, and `fonts-rpm-macros`
provides `fontpackages-devel`; the old `fontpackages` dist-git is retired.

A font's publishing run is often not the run that built it: an image built from
cached RPMs lists the package build jobs as skipped. Record the build job (it may
sit in an aggregate run that failed on other packages) and the publishing run
separately, with the image digest. Without `dnf`, a static check that every
`Requires` of each output is provided by the factory layer or a dated Hummingbird
`primary.xml` is dependency-closure evidence only. It is not a solver
transaction (see `repo-inspection`) and does not prove font rendering.

## Refreshing the inventory

After importing a font source, regenerate `.packit.yaml` with
`python3 tools/render_packit_config.py --write` and architecture counts with
`python3 tools/render_architecture_counts.py --write`. Inventory tests now
read the recipe set; do not restore old hardcoded package counts.
