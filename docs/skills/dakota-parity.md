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
| `config/dakota-build-facts.json` | The build facts: for every in-image element, its `kind`, its patch sources (`patch` and `patch_queue`, each with its `Subject:` and a hash of its changed lines) and its option variables (`meson-local`, `meson-extra`, `cmake-local`, `cmake-extra`, `conf-local`, `conf-extra`, `conf-args`, with the element's own `%{...}` variables expanded), read from the `.bst` at the pinned refs. A `filter` records the element it splits under `build`. `refs` names the four commits it was read at. |
| `config/gnome-build-meta.json` | Reused: its `mapping` names the RPM for GNOME renames (`sdk/gtk.bst -> gtk4`), so the two audits never disagree on a GNOME name. |
| `reports/audit-dakota.{json,md}` | The audit: counts, import queue, version drift, structural and config tables, stale mappings, config-package gaps. Derived, git-ignored and never committed: every recipe import moves it, so a tracked copy would go stale or make concurrent import PRs conflict (#309). Every `validate.yml` run publishes the live report as the `dakota-audit` artifact and in its job summary. |

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
# Offline, writes reports/audit-dakota.{json,md} (git-ignored).
python3 tools/audit_dakota.py

# The gate (`just dakota-audit`, part of `just check`, and validate.yml's
# "Dakota element audit" job): builds the report in memory, writes nothing,
# and fails when config/dakota.json's mapping does not name exactly the
# snapshot's elements, or an override, alias or config_subpackages entry names
# an element the snapshot lacks. Stale dispositions do not fail it.
python3 tools/audit_dakota.py --check

# Re-resolve Fedora and Hummingbird online and rewrite config/dakota.json.
# Reads Rawhide's and Hummingbird's primary.xml and HEADs each resolved
# https://src.fedoraproject.org/rpms/<name>; --rawhide-primary /
# --hummingbird-primary take saved copies.
python3 tools/audit_dakota.py --refresh

# Rewrite config/dakota-build-facts.json from checkouts at the pinned refs.
# Each checkout's HEAD must be the pinned commit; freedesktop-sdk-extra's is
# read from gnome-build-meta's junction element.
python3 tools/dakota_repin.py checkout --into /tmp/src
python3 tools/audit_dakota.py --import-build-facts \
    --dakota-dir /tmp/src/dakota --gbm-dir /tmp/src/gnome-build-meta \
    --fdsdk-dir /tmp/src/freedesktop-sdk --fdsdk-extra-dir /tmp/src/freedesktop-sdk-extra

# Re-pin Dakota by hand (refresh-dakota.yml does this daily, below): find the
# run and write the new source, then rebuild the snapshot from that run's SBOM
# and image.
python3 tools/dakota_repin.py resolve --out /tmp/repin.json
python3 tools/dakota_repin.py apply /tmp/repin.json
gh run download <run> -R projectbluefin/dakota -n sbom-dakota -D /tmp/sbom
skopeo copy --preserve-digests docker://ghcr.io/projectbluefin/dakota@<digest> \
    oci:/tmp/dakota-oci:testing
python3 tools/audit_dakota.py --import-sbom /tmp/sbom/dakota.sbom.json \
    --image-layout /tmp/dakota-oci --refresh
```

`--import-sbom` refuses an SBOM whose `documentNamespace` is not the pinned
revision and an OCI layout that does not hold the pinned digest.

### Automatic re-pin

`.github/workflows/refresh-dakota.yml` runs daily (05:37 UTC) and on
dispatch, from `main` only. `tools/dakota_repin.py resolve` takes the newest
successful `publish.yml` run whose `head_branch` is `testing` (merge-queue
publishes push only a `:SHA` tag and are skipped), that still has unexpired
`sbom-dakota` and `digest-default` artifacts, and whose commit
`compare/<sha>...testing` reports `identical` or `ahead`. The revision and
digest come from `digest-default`'s `digest.json` (`variant: default`,
`image: ghcr.io/projectbluefin/dakota`, `sha` equal to the run's), and the
junction refs from `elements/{gnome-build-meta,freedesktop-sdk}.bst` at that
commit, in the committed shape (`<track> <ref>`, or the ref alone when it
already names the track). When revision and digest equal the pin, the job
stops. Otherwise it writes the source, copies the image with
`skopeo copy --preserve-digests` (about 3.6 GB), runs `--import-sbom ...
--refresh`, fetches the four projects with `dakota_repin.py checkout` and
runs `--import-build-facts`, and opens or force-updates one pull request on
`chore/dakota-repin` with only `config/dakota.json`,
`config/dakota-elements.tsv` and `config/dakota-build-facts.json`. The body has the disposition counts before and
after, the drift totals, the `needs_review` rows, the patch and option
classification counts before and after, and any `contract_problems`
(an override or alias naming an element the new snapshot dropped makes
`just dakota-audit` fail until it is fixed on that branch). It never merges or
arms auto-merge. The work runs in two jobs. `repin` fetches and parses the
third-party content (it `git apply`s Dakota's patches to compare them) with
read-only permissions and no secret, then uploads only the three config files
and the PR body. `open-pr` starts from a fresh checkout, checks that those
files are well-formed, and is the only job that mints the mergeraptor app
token, like `refresh-buildroot.yml`, so the pull request's CI runs. Dakota's
runs, artifacts and image are read with the workflow's own token, since
Dakota is public.
`.github/workflows/audit-dakota.yml` runs the offline audit weekly (non-gating)
and uploads the report; dispatch it with `refresh` to get a re-resolved
`config/dakota.json` as an artifact to review and commit.

Hand-edit only `aliases`, `overrides` and `config_subpackages` in
`config/dakota.json`; `elements` is written by `--refresh`. Keep the file's
shape (2-space JSON, one key per element) so a refresh diff stays reviewable.

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
   at the junction refs in `source.junctions`). Once the recipe is `factory`,
   the report's **Patches and build options** section lists the element's
   patches the recipe lacks and the options both set differently (below).
4. Rerun the audit. Until `--refresh` runs, the landed recipe shows under
   **Stale mappings** (recorded `fedora-importable`, now `factory`); its live
   disposition is already `factory`. That is expected and does not fail
   `--check`. Leave `config/dakota.json` alone in an import PR, so
   concurrent imports do not conflict; the next refresh records it.

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

## Patches and build options

For every `factory` element the report compares the build facts with the
recipe, offline (`build_intent` in the JSON, its own Markdown section):

- **patches**: the element's `patch` and `patch_queue` files against the
  spec's `Patch:` lines. A pair matches by name (directory, number prefix and
  suffix dropped: `0002-Fix-Build.patch` is `fix-build`), by `Subject:`, or by
  the hash of the added and removed lines when the patch file is in
  `packages/<rpm>/`. Fedora names the same backport differently
  (`svn-r6564.patch` is `libmp3lame-symbols.patch`), so the subject and the
  hash do most of the matching.
- **options**: `-D` options from the meson and cmake variables against the
  spec's `%meson`/`%cmake` blocks, and `--enable/--disable/--with/--without`
  switches from the conf variables against the spec's `%configure` and
  `./configure` blocks. Every value the spec passes is kept (webkitgtk passes
  `-DUSE_GTK4=OFF` and `ON` for its two builds; the gnome-build-meta audit's
  `meson_options` keeps only the first), and an option conflicts only when
  Dakota's value matches none of them. `--disable-x` is `enable-x=no`; `true`
  equals `enabled`. A value that is still a macro or variable reference on
  either side, or an option inside `%{?macro:...}`, is not a conflict.

`needs_review`: Dakota carries a patch the recipe lacks, or both sides set an
option differently. Options only Dakota sets are counted and kept in the
JSON, but do not trigger review on their own: most restate a default or turn
off docs and tests. `aligned`: neither. `not_compared`: no build facts for the
element, a `.bst` that did not parse, no spec, or a `filter`/`stack` whose RPM
no element builds. A `filter` is compared through the element it splits
(`bluez-libs` through `_private/bluez-base`), once per build.

Dakota's junction patch queues (`patches/freedesktop-sdk-dakota`,
`patches/gnome-build-meta`) are applied to copies of the junctioned checkouts
before reading, because they change elements: `0002-ffmpeg-enable-all-native-codecs.patch`
rewrites ffmpeg's `conf-extra`. An element a queue patch touches records it
in `dakota_junction_patches`. `(?)` conditionals in variables are not
evaluated; such an element has `conditional_variables: true`.

The section is report-only: `--check` never fails on it. When the facts were
read at another Dakota revision than the pin, the section says so; re-run
`--import-build-facts`.

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

## Elements that overwrite another element's files

A BuildStream compose keeps whichever element stages last, so Dakota replaces
a component by overwriting its paths (`overlap-whitelist`). RPM cannot: two
packages may not own one path with different content. Carry such an element as
a `-replace` subpackage that owns the overwritten paths, `Provides:` what the
replaced package provides and `Conflicts:` with it, so dnf swaps them in one
transaction (`dnf swap`, or Utah's `[swap]` table). Whatever Dakota keeps from
the overwritten element needs its own package.

`bluefin/uutils-coreutils.bst` is the example. `uutils-coreutils-replace`
links GNU coreutils' programs (the names in `coreutils-single`) to uutils,
adds Dakota's `uutils-<utility>` names, provides `coreutils` and conflicts with
`coreutils-single`. Dakota keeps GNU's `env` for pkexec, so `gnu-env` builds
GNU's `env` alone from the coreutils release, and the replacement requires it.
The list of program names is explicit in the spec, and the build fails if
uutils lacks one, so `Provides: coreutils` never drops a program silently.
Version that Provides (the GNU release Hummingbird ships): an unversioned
Provides also matches every versioned `Conflicts:`, and util-linux has
`Conflicts: coreutils < 8.20`. For the same reason `gnu-env` conflicts with
the arch-qualified `coreutils%{?_isa}`, which only GNU's packages provide.
`bluefin/sudo-rs.bst` overwrites C sudo's `/usr/bin/sudo`, but C sudo stays
installed for its PAM stacks and sudoers. It is protected in dnf too, so Utah
makes that swap in its image build instead.

## Pitfalls

- The SBOM's element list (`elements.tsv` in Utah's baselines) has empty
  versions: versions live on the per-element source packages
  (`GENERATED_FROM`), and the primary source is the first one that is not a
  patch, a local file or a vendored crate/module.
- mdapi's `pkg/<binary>` echoes the binary name as `basename`; it does not
  resolve binary -> source. Rawhide's `primary.xml` `sourcerpm` does.
- A dist-git repository exists for retired packages; Rawhide's repodata is
  the authority for "importable", dist-git HEAD only confirms the repository.
- The report is published as an artifact, not committed, so its size is not
  bound by `check-added-large-files`; build-only elements are still listed by
  name and drift only in `drift`, to keep it readable.
