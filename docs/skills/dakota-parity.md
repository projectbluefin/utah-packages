---
name: dakota-parity
description: >-
  Maps every element of Dakota's BuildStream graph (projectbluefin/dakota on
  gnome-build-meta and freedesktop-sdk) to the RPM that provides it on Utah,
  with a disposition per element, and turns the gap into an ordered import
  queue. Load before importing or writing a recipe for a Dakota component,
  re-pinning the Dakota revision, deciding an element's disposition, or
  answering "does the factory cover what Dakota ships?".
metadata:
  type: reference
---

# Dakota parity: element -> RPM

Utah's parity target is Dakota, GNOME OS built with BuildStream. Dakota has no
RPM database, so parity is measured element by element:
`tools/audit_dakota.py` maps each of the ~1,200 elements in Dakota's SBOM to
the RPM source package that provides it, and reports what the factory still
owes.

## Owner policy

- **Upstream components follow Fedora, then Dakota.** Import Fedora's Rawhide
  recipe, then align it to the Dakota/gnome-build-meta element: the same
  version or ref, the same patches, the same configure/meson options. Write a
  spec from the `.bst` only where Fedora has no recipe (`new-spec`).
- **Config elements become config subpackages built from the project's own
  files.** A Dakota element that only installs files is a `dakota-config-<element>`
  subpackage of `packages/dakota-config`, built from projectbluefin/dakota at
  the pinned commit, so the file content is Dakota's verbatim. gnome-build-meta's
  `files/` get the same treatment in `gnome-os-config-<element>`. Utah installs
  those subpackages instead of hand-copied `system_files`.

## Inputs

| File | What it is |
| --- | --- |
| `config/dakota-elements.tsv` | The element snapshot: one row per SBOM element, with its primary source (`version`, `url`), patch count, and how many files, desktop entries, systemd units and `/usr/bin` commands it owns **in the published image**. |
| `config/dakota.json` | `source`: the pinned Dakota revision, the publish run whose `sbom-dakota` artifact is the snapshot, the image digest, the junction refs. `aliases`, `overrides`, `config_subpackages`: reviewer decisions. `elements`: the generated mapping, one entry per element (`disposition`, `rpm`, `fedora`, `hummingbird`, `evidence`). |
| `config/gnome-build-meta.json` | Reused: its `mapping` names the RPM for GNOME renames (`sdk/gtk.bst -> gtk4`), so the two audits never disagree on a GNOME name. |
| `reports/audit-dakota.{json,md}` | The audit: counts, import queue, version drift, structural and config tables, stale mappings, config-package gaps. |

"In the image" is measured, not guessed: chunkah writes the owning element of
every file into the `user.component` xattr, and `--import-sbom` reads it from
each layer of the pinned image. An element that owns no file (a toolchain, a
`-devel`-only library, a bootstrap stage, a stack) is **build-only** and needs
no RPM for Utah's image; it is `not-applicable` with that reason. Do not key
"build-only" on element names: freedesktop-sdk's `bootstrap/glibc.bst`,
`bootstrap/bash.bst` and `bootstrap/ncurses.bst` ship in the image.

## Dispositions

Precedence, first match wins:

1. a reviewer `override` (`structural`, `not-applicable`, `dakota-config`,
   `gnomeos-config`, `new-spec`), each with a `reason`; `structural` names a
   Utah parity issue (#1222-#1235, or the epic #1236);
2. `not-applicable`: build-only;
3. `dakota-config` / `gnomeos-config`: a Dakota element with no upstream
   source, or a gnome-build-meta element whose sources are all `local`
   (a gbm element with no sources at all is usually a `filter` splitting a
   component, such as `core-deps/systemd.bst`);
4. `factory` (a recipe for the RPM is in `packages/`), then `hummingbird`
   (Hummingbird's repository builds the source package), then
   `fedora-importable` (Rawhide builds it), then `new-spec`.

`factory`, `hummingbird` and `fedora-importable` are measured, never asserted:
the pin refuses them as overrides. To point an element at a different Fedora
name, add an `aliases` entry instead.

## Commands

```sh
# Offline: the mapping and snapshot are committed; CI runs exactly this.
python3 tools/audit_dakota.py

# Re-resolve Fedora and Hummingbird online and rewrite config/dakota.json.
# Reads Rawhide's and Hummingbird's primary.xml and HEADs each resolved
# https://src.fedoraproject.org/rpms/<name>; --rawhide-primary /
# --hummingbird-primary take saved copies.
python3 tools/audit_dakota.py --refresh

# Re-pin Dakota: set source.revision, publish_run, sbom, image_digest in
# config/dakota.json, then rebuild the snapshot from that run's SBOM and image.
gh run download <run> -R projectbluefin/dakota -n sbom-dakota -D /tmp/sbom
skopeo copy docker://ghcr.io/projectbluefin/dakota@<digest> oci:/tmp/dakota-oci:testing
python3 tools/audit_dakota.py --import-sbom /tmp/sbom/dakota.sbom.json \
    --image-layout /tmp/dakota-oci --refresh
```

`--import-sbom` refuses an SBOM whose `documentNamespace` is not the pinned
revision and an OCI layout that does not hold the pinned digest.
`.github/workflows/audit-dakota.yml` runs the offline audit weekly (non-gating)
and uploads the report; dispatch it with `refresh` to get a re-resolved
`config/dakota.json` as an artifact to review and commit.

## Working the import queue

The report lists `fedora-importable` and `new-spec` elements without a
recipe, one row per RPM, in the order a user notices them: elements owning a
desktop entry, then a systemd unit, then a command, then libraries and data.

1. Take the next row. Check the `rpm` against the element: the resolver tries
   aliases, the element name and its Fedora spellings (`python3-x ->
   python-x`, `xorg-lib-xft -> libXft`, `avahi-libs -> avahi`,
   `gstreamer-* -> gstreamer1-*`), then the project name from the source URL.
   The URL name can be a different project: `sdk/mozjs.bst` resolved to
   `firefox` and `sdl3-image` to SDL 1's `SDL_image` until aliases named
   `mozjs140` and `SDL3_image`. A wrong match gets an `aliases` entry.
2. Import the recipe ([`contributing.md`](../contributing.md), Import Rawhide
   package) and finish it on the branch
   ([`repeated-mistakes.md`](repeated-mistakes.md) #23).
3. Align it to the element: Dakota's version is in the report; the patches
   and options are in the `.bst` (Dakota, or gnome-build-meta/freedesktop-sdk
   at the junction refs in `source.junctions`). For a GNOME module, the
   gnome-build-meta audit diffs patches and `-D` options
   ([`gnome-build-meta-audit.md`](gnome-build-meta-audit.md)).
4. Rerun the audit. Until `--refresh` runs, the landed recipe shows under
   **Stale mappings** (recorded `fedora-importable`, now `factory`). Commit the
   refreshed `config/dakota.json` and report with the import, not later.

A `new-spec` row is written from the element: Source0 is the element's source
URL at its ref, locked like any upstream source; the build follows the
element's `kind` and variables. Follow the factory-authored recipe rules in
[`contributing.md`](../contributing.md). Before writing one, confirm Fedora
really has none: `dist-git rpms/<name> exists but is retired from Rawhide`
in the reason (gnupg, procps, gstreamer, libusb, libnl) means Fedora renamed
or replaced it, so the fix is an alias, not a spec.

## Version drift

For every `factory` element the report compares the source lock's version
with the element's by release line, with the gnome-build-meta audit's
`release_line` (GNOME cycle numbers >= 40 compare the major; libraries
compare `major.minor`). `needs_review` says which side leads. `not_compared`
means Dakota's source carries no version (a bare commit or checksum). A split
element with no source of its own (`bluez-libs`, `pipewire-daemon`) takes the
version of the element that builds the same RPM, and says which.

## Config packages

The **Config packages** section lists the expected subpackage of every config
element plus `config_subpackages`: the config part of a component element
(the preset Dakota writes next to rpcbind or tailscale, the dconf part of a
shell extension, gnome-build-meta's firewalld lax zone). `config_gaps` reads
the `%package` lines of `packages/dakota-config` and `packages/gnome-os-config`
and names any expected subpackage the recipe lacks. A config element the
config packages deliberately exclude gets a `not-applicable` or `structural`
override saying why (a file another package owns, a GNOME OS image mechanism,
a parity issue), so it leaves the gap list.

## Pitfalls

- The SBOM's element list (`elements.tsv` in Utah's baselines) has empty
  versions: versions live on the per-element source packages
  (`GENERATED_FROM`), and the primary source is the first one that is not a
  patch, a local file or a vendored crate/module.
- mdapi's `pkg/<binary>` echoes the binary name as `basename`; it does not
  resolve binary -> source. Rawhide's `primary.xml` `sourcerpm` does.
- A dist-git repository exists for retired packages; Rawhide's repodata is
  the authority for "importable", dist-git HEAD only confirms the repository.
- Keep `reports/audit-dakota.json` under the 500 KB `check-added-large-files`
  limit: build-only elements are listed by name and drift is only in `drift`.
