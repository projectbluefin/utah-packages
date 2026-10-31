---
name: factory-build-backlog
description: Track the factory build backlog from projectbluefin/utah-packages#308 — the catalog, the auditor, and the per-area rollup.  Live totals live in the report; do not hard-code them.
---

# Factory build backlog

The Bluefin-vs-Utah bare-metal audit on 2026-09-30 found a set of names
in neither the pinned factory repo nor the Hummingbird supply (the
audit's original total — 551 — is the starting point; live totals
live in `reports/factory-build-backlog.json` and shift every time a
gap closes or a recipe lands). Each name is a candidate factory build
or an explicit wontfix. The backlog catalog
(`config/factory-build-backlog.toml`) is the source of truth: every name
lives in exactly one of the ten issue-aligned areas, and leaving the
backlog requires a matching `[resolved]` or `[wontfix]` entry.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `config/factory-build-backlog.toml` | The catalog: names grouped by area (see the report for the live count) |
| `tools/factory_build_backlog.py` | Auditor: classifies each name against the live repo state |
| `reports/factory-build-backlog.json` | Committed snapshot; live totals (backlog / pending / already_recipe / manifest_wants / resolved / wontfix) — regenerate with `just regenerate-inventory` |
| `Justfile` `regenerate-inventory` recipe | Writes Packit configuration, architecture counts, then the backlog snapshot from the combined inventory |
| `Justfile` `factory-build-backlog` recipe | Runs `--check` against the working tree (wired into read-only `check` so every PR that drifts the report fails before merge) |

The snapshot is deterministic: the report carries no wall-clock field, so a
run that changes nothing rewrites the file byte-for-byte and leaves the tree
clean.

After combining current `main` and PR source changes, run
`just regenerate-inventory`. It runs `python3 tools/render_packit_config.py
--write`, `python3 tools/render_architecture_counts.py --write`, and
`python3 tools/factory_build_backlog.py`, in that order. The individual
commands and `just factory-build-backlog` remain available; `just check`
does not regenerate files. Never resolve generated conflicts by selecting a
stale branch's counts or report: both branches' source changes must be
represented before regeneration, even when generated files auto-merge.

`--check` also runs as a gate in `.github/workflows/validate.yml`.

Not wired yet — follow-up work, do not go looking for it:
`.github/workflows/recalculate-factory-build-backlog.yml` (periodic recalc).

## Partitions

The auditor classifies each catalog name into exactly one state:

| State | Meaning |
| --- | --- |
| `already_recipe` | A directory exists under `packages/<name>/`, or the name is an unconditionally built `%package` subpackage of such a spec |
| `already_locked` | `config/upstream-sources.json` has a lock entry |
| `already_packit` | `.packit.yaml` has a package block |
| `manifest_wants` | `config/bluefin-packages.toml` lists the name |
| `pending` | None of the above; a factory build is owed |

Wontfixed names are not a state: leaving the backlog removes the name from
every area, and the auditor rejects a catalog where an area name is also in
`[wontfix]`. `[wontfix]` shows up in `totals`, never in `states`.

Order is significant: the strongest signal wins. Reordering the
`_classify` function silently changes counts and is a contract break.

## Closing a backlog gap

For a partial batch PR, use `Refs #<issue>` in the PR description. Reserve
GitHub closing keywords for a PR that satisfies the entire batch issue's
close condition, including required build and runtime evidence or linked
blocking decisions for every named output. Before pushing a review fix,
check the entire PR description for closing keywords: an automatically added
footer can contradict an earlier partial-progress statement. After editing the body,
read it back with `gh pr view <pr> --json body --jq .body` and verify the
saved description, including any generated footer; local prose alone does not establish
that the live PR will keep the batch open. A branch push alone does not correct the PR description.
Once the PR number is known, fill in the recipe record's `pr` field so reviewers can trace the partial import.
Keep package-specific comment blocks adjacent to the entries they describe;
insert unrelated records before the block rather than between it and its entries.

Two edits — never one, never none:

- Remove the entry from `[areas.<area>].packages`.
- Add the entry to either:
  - `[resolved].packages` (`{ name = "<n>", commit = "<sha>", pr = <n>, published_run = <run-id>, published_nevra = "<n>-<e>:<v>-<r>.<arch>" }`) —
    a recipe was imported. `commit` and `pr` are both informational; the
    closing record is the import PR (the one this two-edit move ships in)
    and `_catalog_totals` in `tools/factory_build_backlog.py` only reads
    `entry["name"]` from the resolved records.
    Do not pre-fill `commit` with a SHA from a future commit that does not
    exist yet at PR-open time, and do not let a rebase or squash-merge
    invalidate it. The `pr` field links the entry to its closing PR for
    cross-referencing.
    Once the import PR has a number, populate `pr` before requesting review;
    `--check` validates names and report drift, not this provenance field.
    For a recipe-only record, use `{ name = "<n>", pr = <n> }` and omit
    `commit` until a stable commit is known; do not retain an empty `commit`
    or `pr = 0` placeholder after opening the PR.
  - `[wontfix].packages` (`{ name = "<n>", reason = "..." }`) — Utah decided
    not to carry it, with a link to the decision issue. `reason` is also
    informational and not validated. Catalog comments should describe the
    structure rather than current list occupancy, since decisions accumulate.

The catalog's `[resolved]` record closes **recipe-import accounting**, not a
batch issue's build, publication, dependency-resolution, or runtime acceptance.
For a partial source-family PR, keep the batch issue open and list the remaining
outputs and missing evidence explicitly.

A 404 on a guessed dist-git name is not evidence that a source was removed
from Fedora. Resolve the binary's actual source package first (the
`sourcerpm` of the binary in Fedora's repodata): `python3-pyaudio` comes from
`pyaudio` and `python3-pskc` from `python-pskc`; #506 once recorded these as
"removed from dist-git" because `PyAudio` and `python-libpskc` 404.

For the audited `libell` binary, Fedora Rawhide's source package is named
`libell`. Do not import the similarly named `ell` source package: its current
recipe builds an unrelated, header-only EBNF library and does not provide
`libell`. Check the binary's `sourcerpm` before inferring a source name from a
shared prefix.

Before importing an audit name, read Utah's current `baselines/triage.toml` and
pin the decision's commit when reconciling an existing `waived` entry into
`[wontfix]`. The audit can include deliberately absent X11 client utilities
(`xrandr`, `xset`, `xdriinfo`) or an updater installed directly from a pinned
release (`uupd`); their absence is not permission to reverse those decisions.
Do not extend a client-tool waiver to an X11 library such as `xcb-util-cursor`:
Wayland sessions still run applications through Xwayland. Check each exact
binary name, not a shared prefix.

`[resolved]` is the only closing record. A recipe import PR makes this
two-edit move in the same PR; `already_recipe` is the auditor's observation
of an area name whose move is still owed (for example a recipe that landed
before the name was catalogued), not an alternative way to close it, and the
next PR that touches the name sweeps it into `[resolved]`. A pull request
that advances only one source family of a multi-package batch issue — or leaves
its entry in `already_recipe` pending hosted build and runtime verification —
must link the tracking issue with `Refs #<n>`, never `Closes #<n>`, so merging
does not auto-close the batch while other outputs remain open.

If the base branch imports the same recipe while a PR is open, reconcile the
merge instead of appending another record: keep one source-lock entry and one
catalog entry, retain the base's source fallback and publication metadata, and
regenerate the report from the merged catalog.

For font and language batches, follow
[Reconcile consumer decisions before importing](font-package-recipes.md#reconcile-consumer-decisions-before-importing).
A partial waiver PR should reference the batch issue and name the remaining
outputs so it stays open. Note any in-repo recipe that requires a waived name.

For partial source-family work, distinguish this recipe-import closing record
from the parent issue's runtime acceptance. Keep the batch issue open until
all named outputs have publication and permitted-repository dependency
evidence; use `Refs`, not an auto-closing keyword, in a partial PR's
description. A `[resolved]` entry alone proves neither publication nor
installability.

### Import records and runtime acceptance

A `[resolved]` entry records the recipe import; it does not establish that
the output is published or usable. For a bounded batch issue, keep the issue
open when importing only one source family, and name the remaining outputs
in the PR. Record the upstream recipe commit and source digest separately
from the hosted build run, binary NEVRA, factory image digest, and runtime
exercise. Missing build or runtime evidence must remain explicit rather than
being inferred from a green inventory check.

For the partial Tesseract source family in PR #836, use `Refs #507` and
preserve both `tesseract` and `tesseract-tessdata` source locks, recipe
provenance and patches when integrating inventory changes. Recipe-import
accounting does not close #507: hosted OCR builds and publication, dependency
resolution, and a runtime OCR exercise using the English tessdata remain
explicit acceptance gaps until evidence is recorded. Regenerating inventory
does not establish any of that build or tessdata runtime evidence.

Use the consumer issue named by the batch assignment when the area's
`consumer_issue` is stale. Check the consumer's triage for each binary:
`planned` records intent, while `untriaged` is not a waiver. For existing
outputs, inspect current published repodata by binary name and its source
RPM before importing a second recipe.

The `Import Rawhide package` workflow does **not** make this move: its pull
request carries the recipe, lock, `.packit.yaml` and counts, but leaves the
name in its area. Before merging one, add the `[resolved]` entry (with that
PR's number) and run `just regenerate-inventory`, or `--check` reports
`entries drift` on `main`. Two such PRs open at once also conflict on the
lock's last entry and the `docs/architecture.md` counts: rebase the existing
PR branch onto current `main`, keep both lock entries, and run
`just regenerate-inventory` from the combined inventory. Resolve generated
conflicts by regeneration, not by selecting either branch's stale totals.
Use `git rebase --signoff` to preserve DCO coverage, then push to the same PR
branch with `--force-with-lease` after validation. Inspect auto-merged catalog
records as well as conflicted files: fill in the existing PR number for new
recipe records, and retain the base branch's publication fields.

The catalog test (`tests/test_factory_build_backlog.py::CatalogConsistencyTests`)
pins the count and sorted-name SHA-256 against the original audit. The auditor
checks that same digest across area, resolved and wontfix entries. A one-for-one
substitution fails even when all counts remain unchanged; moving an existing
name to a closing record preserves the digest. The baseline was verified
against the pinned gist's `nowhere-551.txt`; changing it requires a new audit. The auditor
itself fails when the catalog totals do not reconcile with the report.

### Smart-card Python bindings

The `pyscard` source recipe provides `python3-pyscard`; do not import a
second recipe for the binary name. It uses `pcsc-lite-devel` at build time
and `pcsc-lite` at runtime, and is a dependency of the YubiKey manager in
#479. The catalog move records the recipe import, not a successful hosted
build, publication, or runtime dependency closure.

### Font parity decisions do not waive input methods

Before importing a font from the `fonts-i18n` area, check the
[Utah maintainer decision](https://github.com/projectbluefin/utah/issues/393#issuecomment-5920428811)
rejecting bulk font parity. Move a font requested only for that parity to
`[wontfix]` with the decision URL; a deliberate individual addition needs
its own accepted proposal. This includes all audited binary names in a font
family, not just the source-package name (for example, JetBrains Mono's
regular, all-fonts and non-ligature outputs).

That decision explicitly distinguishes IBus input-method engines from fonts.
Do not use it to waive engines, language data, dictionaries, or their required
libraries merely because they share the `fonts-i18n` area. Those names are not
accepted by that decision either: they need their own accepted proposal before
implementation, and stay pending until that proposal plus recipe, dependency
and publication evidence exist.
A mixed batch can therefore be reconciled in a partial PR: name every remaining
output and keep the tracking issue open. Use `Refs #<issue>` in the PR
description and remove any automatic closing keywords for that batch issue.

### Build dependencies imported by another PR

An input-method library can BuildRequire a library that a different batch
imports. `libpinyin` (#495) BuildRequires `kyotocabinet-devel`, whose recipe
arrived in the long-tail PR #767 (`kyotocabinet-libs`, #501). Pull-request CI
only validates configuration, and the post-merge rebuild orders packages by
BuildRequires, so the dependent recipe can be reviewed in parallel. Name the
providing PR in the PR body and the `[resolved]` comment, and merge it first:
merged alone, the dependent recipe fails its first hosted build on a missing
BuildRequires. `m17n-lib` likewise waits on its providers in #788.

### Reconcile sibling library outputs

Check every binary from an imported source family when reconciling a batch.
For example, `ding-libs` produces `libdhash` as well as `libini_config`, and
`nfs-utils` produces `libnfsidmap`; neither needs a separate recipe import.
An earlier closing record for another sibling does not close these names.
Move each remaining audited name explicitly and cite the original import PR.
Verify the binary name and source RPM in the published primary metadata using
`tools/package_index.py` before reporting publication. Record the OCI digest,
metadata checksum, and binary epoch/version/release in the reconciliation PR;
keep runtime installation and behavior claims separate from catalog closure.
When a reconciliation PR resolves only part of a multi-output batch issue, link
the issue with `Refs #<n>` rather than `Closes #<n>` so the remaining batch
outputs stay open.
For a partial batch PR, use `Refs #<issue>` throughout the PR description.
Check the final rendered body, including generated footers, for closing keywords
such as `Closes`, `Fixes` or `Resolves`: they automatically close the batch
issue on merge even when the summary says work remains. Use a closing keyword
only when every named output meets the issue's acceptance criteria or has an
explicitly linked blocking decision.
### Reconciling recipes imported before the audit

For a name still marked `already_recipe`, verify the original import PR is
merged and its commit is on the target branch before moving the name to
`[resolved]`. Record that existing PR and commit rather than importing the
same source again. This closes the recipe catalog record only: keep the
tracking issue open when publication, runtime dependency resolution, or a
representative command has not been verified. A reconciliation PR must state
those remaining checks explicitly; `[resolved]` is not installability proof.

### D-Bus helper services

`oddjob-mkhomedir` is an unconditional subpackage of `oddjob.spec`; one
`oddjob` import closes both names. Its `Source0` host, `releases.pagure.org`,
is gone and the project has published no new release location, so the lock
keeps the pagure URL as primary with the SHA-512-verified Fedora lookaside in
`fallback_urls` (see
[dead upstream hosts](supply-chain-provenance.md#dead-upstream-hosts-releasespagureorg)).
Before relying on the Fedora 44 build root, check the runtime `Requires`
against Hummingbird's primary metadata by name, file and SONAME provide:
`dbus`, `dbus-tools` (`/usr/bin/dbus-send`), `psmisc`, `systemd` (provides
`systemd-sysv`), `pam-libs`, `openldap`, `cyrus-sasl-lib`, `krb5-libs` and
`libxml2` (`libxml2.so.16`) all resolve there. That static check is not a
transaction: home-directory creation still needs a login on an enrolled host.

### Legacy service wrapper waiver

`initscripts-service` comes from the `initscripts` source recipe, but Utah's
[committed consumer triage](https://github.com/projectbluefin/utah/blob/1bc07242296d039bca80412ec2b0e68579a61d3e/baselines/triage.toml#L384-L386)
already waives it as a legacy SysV service shim. Reconcile that exact binary
into `[wontfix]` with the pinned decision instead of importing the parent
legacy-init suite. This is an existing consumer decision, not a new policy
exclusion or evidence of publication. The existing `autofs` recipe still
requires `/sbin/service` in its preun/postun scriptlets; preserve and report
that dependency when reconciling the waiver rather than silently deleting it
or claiming runtime closure. Do not extend the waiver to other pending
long-tail names; each needs its own disposition. Keep the batch issue open
when other outputs or their build/runtime evidence remain outstanding.

### Virtual machine guest integration

`spice-webdavd` is a binary subpackage of **phodav**, alongside
`libphodav`, `libphodav-devel`, and `chezdav`; there is no separate
`spice-webdavd` dist-git recipe. Import `phodav` once and lock its GNOME
release archive. Keep its Meson virtual-directory tests enabled in `%check`
and let configuration failures stop the build. Its explicit runtime
requirement is `avahi`; inspect the built RPM's generated library requirements
before claiming dependency closure. A runtime test needs a SPICE guest with
the WebDAV virtio channel and a host-shared directory: verify a file transfer
through that channel, not just service startup or the standalone `chezdav`
server. Recipe accounting does not establish guest file sharing.

Confirm `avahi-gobject-devel`, `gtk-doc`, and `xmlto` against the repositories
enabled by `tools/mock_config.py` before asserting build dependency availability.
Other recipes declaring the same BuildRequires are not availability evidence.
Record the repository snapshot or release and the published package versions in
the PR; a metadata match still needs a successful Mock dependency lock and build
in the pinned environment before claiming solver success.

`spice-vdagent` BuildRequires `spice-protocol` headers. Import the protocol
source alongside the agent when neither build root nor factory supplies it;
the graph can then place the headers before the agent from the package-name
BuildRequires. The protocol recipe disables its Windows cross-build by default;
that does not remove Linux headers. A successful build alone does not prove
clipboard or display integration: test those in a SPICE guest after publication.

### Touchscreen library imports

`tslib` builds its SDL2 test utilities with `SDL2-devel`. The factory
recipe providing that build dependency is `sdl2-compat`, whose devel
subpackage explicitly provides `SDL2-devel`; do not import a second SDL2
source recipe. The main `tslib` binary contains both the filtering plugins
and touchscreen tools. A successful package build does not establish touch
input or calibration behavior: exercise those tools with a real input device
in the consumer image before claiming hardware parity.

### Reconciling recipes imported before the catalog

For an existing source recipe, check the published OCI repodata for each
audited binary before moving its closing record. `pcsc-lite-libs`, for
example, is an unconditional subpackage of `pcsc-lite`; it does not need a
second recipe. Record the original import PR and commit in `[resolved]`,
and cite the observed image digest and binary versions in the reconciliation
PR. This closes the recipe backlog record only: publication does not prove
runtime dependency resolution or hardware operation, so leave the consumer
validation task open until those checks have evidence.

When a PR resolves only part of a batch issue, use `Refs #<issue>` in its
description. Reserve `Closes #<issue>` for a batch whose named outputs and
acceptance requirements are all resolved or explicitly blocked by linked
decisions, as required by that issue. Check the entire description for closing
keywords before pushing: a trailing `Closes` still auto-closes the issue even
when the summary describes partial progress. Repeat the live-body readback after
the push and any automation that rewrites the description. If a closing footer
returns, replace it with `Refs` in the saved PR body and read it back again;
a new branch head does not by itself resolve a description-only review finding.

### Collection-library imports

`libgee` produces `libgee` and `libgee-devel` from one source recipe; do not
import the development output separately. Its upstream archive includes C
sources, but the Fedora recipe touches the Vala inputs and explicitly enables
Vala regeneration for compiler compatibility. Retain the `vala` BuildRequires,
`--enable-vala`, and the real `make check` step when importing it. A source lock
and catalog closing record establish the recipe import only; scoped hosted
build, publication and runtime evidence are still required for the output batch.

### Locking sources for a hand import

For Linux-only library imports, inspect optional Windows cross-build bconds
before locking the build root. `libdeflate` enables MinGW by default in
Rawhide; disable its `mingw` bcond locally to keep the native library, tools
and upstream CTest suite without adding Windows cross-toolchain dependencies.
Its `mingw_utils` bcond only controls Windows tools, so disabling that alone
does not remove the cross-build. Keep the imported provenance unchanged.

For GNU recipes such as `bison`, preserve the detached signature in `sources`,
its dist-git keyring, and the recipe's `%{gpgverify}` invocation. Lock the
upstream release archive as the primary source and compare both archive and
signature SHA-512 values with `sources`; `source_pipeline.py` stages the
additional manifest sources. Check ignored files before staging the import:
losing the keyring makes `%prep` fail even when the archive lock is valid.
Bison's runtime `m4 >= 1.4` is supplied by Hummingbird; it does not require a
second factory recipe. A `[resolved]` move records the recipe import only;
publication and a permitted-repository runtime transaction still need their
own evidence.

`bootstrap_upstream_sources.py` accepts `http://` `Source0` URLs that
`tools/validate.py` then rejects; before committing, swap `http://` for
`https://` (SourceForge, `download.dymo.com`) and confirm the digest still
matches. Rewrite a dist-git `sources` file that still carries MD5 lines as
`SHA512 (<file>) = <hex>`, the format the lock reads. A GitHub URL such as
`archive/v6.2.8/<name>.tar.gz` can answer "the given path has multiple
possibilities" when a branch and a tag share the name: lock
`archive/refs/tags/v<version>.tar.gz` and set `filename` to the name the spec
expects. When upstream no longer serves the bytes (a GitHub release with no
assets, a rolling `openprinting.org` snapshot, a dead FTP host or pagure
archive), keep the upstream URL as the primary `url` and put Fedora's lookaside
URL in `fallback_urls`: `tools/source_pipeline.py` tries the fallbacks after
the primary fails, and `tools/validate.py` rejects a Fedora primary `url` for
any name outside the shrink-only `config/fedora-primary-sources.txt` ratchet
(`fedora-workstation-backgrounds` is locked this way). Lock the lookaside URL
as primary and add the name to that ratchet only when no upstream URL for the
archive ever existed, as for `hyperv-daemons`, whose `tools-hv` kernel snapshot
is published only to Fedora's lookaside.
A runtime `Requires` that resolves only in Fedora (for example
`libieee1284.so.3` for `sane-backends`) must be imported in the same PR, since
the published repository is installed from the factory plus Hummingbird alone.

For `liblouisutdml`, import the source family once: it also builds
`liblouisutdml-utils`. The utilities require `antiword` and `poppler-utils`;
check both runtime providers rather than just the library's BuildRequires.
When an original release host disappears (`antiword`'s `winfield.demon.nl`),
check the maintained upstream mirror's release-import commit before using a
lookaside primary. `grobian/antiword` commit
`3f371a2fd2e8b7ba3c0793381e1a1df0d561f961` contains the unchanged 0.37
release tree plus only `LICENSE` and `README.md` (compare with the original
archive). Lock that archive by SHA-512, update `sources`, and set `%setup -n`
to its commit-based directory; do not reuse the original archive's digest.
This source-tree comparison is not a package build or runtime closure test.

The `liblouisutdml` recipe builds a PDF manual with `texinfo-tex`, whose
Fedora TeX Live dependency chain needs ICU 77 in the build root. Like
`liblouis`, it opts in to that build-only dependency; its configure script
links liblouis and libxml2, not ICU directly. Do not remove the manual or the
upstream test suite to avoid the dependency. A successful build is still
needed: inspect every built RPM's requirements for ICU 77 and resolve the
runtime transaction using only Hummingbird and the factory. The opt-in does
not prove the outputs are safe or published.

The `python-h11` source archive has no runtime dependencies; its recipe runs the bundled pytest suite. Recipe coverage still requires a hosted build and a factory-plus-Hummingbird installation test before claiming publication or installability.

A Python wheel's runtime closure is not in its `Requires`. `python-pillow`
links `libraqm.so.0` (hence `libraqm`, imported with it) and its
`python3-pillow-qt` subpackage needs `python3-qt5`, which neither Hummingbird
nor the factory carries, so the recipe builds with `%bcond_with qt` and
`%bcond_with mingw` (Utah-local). Always run `rpm -qp --requires` over the
built RPMs against factory plus Hummingbird before closing the import.
`net-snmp` fails to link `libnetsnmptrapd.la` under Hummingbird's libtool 2.6
because `libnetsnmpmibs.la` no longer passes `libnetsnmpagent` on; the recipe
names it next to `MIBLIB` in `apps/Makefile`.

An `ftp://` `Source0` (`libutempter`) is rejected by the lock step as "not a
direct HTTP(S) URL"; check whether the same host serves the file over `https://`
(`ftp.altlinux.org` does) and lock that after comparing the SHA-512 with
`sources`. Before importing a package for one missing soname, walk the
providing recipe's own runtime `Requires` against factory plus Hummingbird: `pcp`
(sysstat's `libpcp.so.4`) is a 118-subpackage monolith whose runtime closure
reaches roughly 84 more Fedora source packages (libvirt, mysql8.4, libarrow,
the perl stack, bpftrace), and even every `disable_*` switch the spec offers
leaves about 62. Drop the optional consumer feature instead -- `sysstat` builds
with `--disable-pcp`, which only removes `sadf`'s PCP output format. When
upstream merges libraries into one source (`ding-libs` 0.7.0 folds
libcollection, libbasicobjects, libpath_utils and libref_array into
`libini_config` through `Obsoletes:`), the retired binary names still leave the
backlog with the import. `usb_modeswitch` and `usb_modeswitch-data` declare a
mutual runtime `Requires:` and both carry `http://www.draisberghof.de/...` in
`Source0` (served with matching SHA-512 over `https://`), so import and lock
them together. When an upstream host answers `HTTP 503` (`ibiblio.org` for
`symlinks`), keep the HTTPS primary `url` and put Fedora's SHA-512 lookaside URL
in `fallback_urls` instead of growing `config/fedora-primary-sources.txt`.
`usbip` requires `kernel-modules-extra` and `kmod(usbip-*.ko)` /
`kmod(vhci-hcd.ko)` at runtime and extracts its archive from the kernel source
tree (`extract_usbip.sh`). The [approved kernel-policy decision](https://github.com/projectbluefin/utah-packages/issues/491#issuecomment-6475648707)
keeps both `usbip` and `kernel-modules-extra` in `[wontfix]`: Utah's D4
excludes the extra modules until a named use case is accepted. Do not import
the userspace tool while its mandatory kernel providers are excluded.
Reconcile both catalog names against that explicit decision, not an assumed
waiver for every kernel-related package. Consumer triage belongs in the Utah
repository; a factory catalog change does not update that separate ledger or
prove runtime acceptance of the other outputs in the batch.

The remaining kernel outputs of that batch (`kernel-devel-matched`,
`kernel-tools`, `kernel-tools-libs`) are binaries of Fedora's `kernel` source
package; Hummingbird ships only `kernel-headers` and the RPM macros. Importing
the full kernel recipe, or splitting the tools out of it, is a kernel-policy
decision that the usbip decision does not cover: keep them pending until a
maintainer records one, even though Utah triages `kernel-tools` as `planned`.

### SSSD client libraries, terminal graphics and LSB query

The `libsss_*` outputs (`libsss_autofs`, `libsss_certmap`, `libsss_idmap`,
`libsss_nss_idmap`, `libsss_sudo`) are unconditional `%package -n`
subpackages of `sssd.spec`; import the `sssd` source once. Its Rawhide recipe
verifies `Source2` (the release `.asc`) against the committed `pubkey.asc`,
which the root `.gitignore` already tracks through `!packages/*/*key*.asc`.
`libcaca` disables Ruby bindings on Fedora 40 and later, so `ruby` is not a
build dependency; its library links factory `libglvnd`, `freeglut`, `mesa-libGLU` and
`slang`. The `caca-utils` subpackage additionally requires `libImlib2.so.1` and
`toilet`, which neither Hummingbird nor the factory carries: the audited
`libcaca` output does not depend on it, but do not claim `caca-utils` is
installable. `lsb_release` (from `thkukuk/lsb-release_os-release`) needs only
`getopt`, `sed` and `tr` at runtime, all in Hummingbird.

This is partial recipe coverage for `Refs #487`, not completion of the
system-core batch: the kernel outputs above still require their own policy
decision, and hosted builds, publication and runtime proof remain outstanding.
The same SSSD source also makes `sssd-client`, `sssd-common`, `sssd-kcm`,
`sssd-krb5-common` and `sssd-nfs-idmap` visible as `already_recipe` for #490;
keep those sibling observations distinct from a resolved catalog record or
evidence that the security-auth batch is complete.

### Optional changelog viewer

Utah's plain-Markdown fallback for `changelogs` (projectbluefin/utah#394)
is resilience, not a decision to exclude `glow` from the factory backlog.
The `glow` source builds the binary of the same name; use its Fedora
`go-vendor-tools.toml` and SHA-512-pinned supplementary vendor archive via
`source_pipeline.bundled_sources`, as for `gum`. Source0 still comes directly
from the upstream release. Keep a noninteractive stdin-rendering smoke check
in `%check`, alongside the version, vendor-license and upstream test checks.
A recipe closing record does not establish publication or runtime closure;
record the lane result and published repository identity separately.
### Flex binary names and smoke test

The `flex` source recipe builds `flex`, `libfl2`, `libfl-devel`, and
`libfl-static`; `flex-devel` is a compatibility provide, not a second source
recipe. The command requires `m4` at runtime. After the permitted-repository
transaction succeeds, verify more than `flex --version`: generate a scanner
from a minimal rule file, compile its C output, and feed it a matching token.
The imported recipe also retains its upstream `%check` suite.
### Compression measurements on Btrfs

The `compsize` source produces the binary of the same name. Its upstream
snapshot uses the full commit in the archive URL and extracted directory,
but the imported manifest uses the seven-character commit in the filename;
keep the lock's `filename` aligned with that manifest. The carried include
patch supports newer `btrfs-progs` headers; `btrfs-progs-devel` is a build
dependency, not a reason to import a second Btrfs recipe.

Runtime acceptance needs a Btrfs filesystem: install using only Hummingbird
and the factory, write a compressible file with compression enabled, then run
`compsize <file>` and check that its report includes the selected compression
type and disk usage. Running it on the runner's ordinary non-Btrfs workspace
only tests the unsupported-filesystem error. A recipe or successful build
alone must not be presented as a working compression measurement; keep the
batch open until publication, dependency solving and that payload probe are
recorded.

### Security key sign-in (Yubico)

Yubico C releases (`libyubikey`, `ykclient`, `ykpers`) still declare `http://opensource.yubico.com/...` `Source0` URLs in Fedora Rawhide, and `libyubikey` and `ykclient` still carry legacy MD5 `sources` lines: repin `sources` to `SHA512 (<file>) = <hex>`, lock `https://opensource.yubico.com/...` as the primary `url`, and pair `https://developers.yubico.com/<project>/Releases/<file>` with Fedora's `/md5/<md5>/` lookaside path in `fallback_urls`. `ykpers` builds and links against `libyubikey` (`libyubikey.so.0`), so import `libyubikey` in the same PR. When a recipe carries a committed OpenPGP keyring whose filename does not match `*key*.asc`, `*keyring*.asc`, or `[0-9A-F]*.asc` (`packages/pkcs11-provider/simo_redhat.asc`, `packages/bc/kevin_pizzini.asc`), unignore it explicitly in the root `.gitignore` (`!packages/<pkg>/<name>.asc`) so `git add` tracks `SourceN` for `%{openpgpverify}`.

By contrast, `yubikey-manager` (`python3-yubikey-manager`) is a `pyproject`
package whose `[project].dependencies` generate runtime `python3dist(...)`
`Requires` across multiple backlog areas. `python3-click`, `python3-pyscard`,
`python3-pskc` and the `jaraco` libraries already have recipes in `[resolved]`;
`python3-fido2` and `python3-keyring` (with `secretstorage`/`jeepney`) are still
pending in `dev-tools`. Its recipe landed in #839 as recipe coverage only (both
names moved to `[resolved]`); hosted build, publication and runtime proof stay
blocked on those remaining Python providers and are tracked on #479.

The `pam-u2f` source recipe also produces `pamu2fcfg`; its detached
signature is a separate SHA-512-locked source and its bundled keyring is
used during `%prep`. Recipe coverage does not prove that authentication works.

### Python recipe names and dependency evidence

For `python3-six` and `python3-dateutil`, import the source recipes
`python-six` and `python-dateutil`, not a second recipe named after the binary.
Their `%pypi_source` archives are upstream releases on
`files.pythonhosted.org`; compare the downloaded SHA-512 with the dist-git
`sources` file before registering the lock. If the bootstrap tool cannot
expand the macro without `rpmspec`, that is not evidence the source is missing.
Do not replace it with a Fedora-primary URL.

Do not infer dependency edges from upstream Python metadata alone:
Rawhide's `python-dateutil` recipe carries `remove-six.patch`, which removes
its dependency on six. Preserve the imported patch set and let the build graph
read the actual recipe; no manual stage is needed for these two imports.
Keep their default test suites enabled. A `[resolved]` entry records recipe
coverage, not successful publication or a working import in the consumer;
keep those outstanding proofs on the implementation issue until a pinned
factory build and permitted-repository runtime check establish them.
For `python3-pexpect`, import `python-pexpect` together with its build and
runtime dependency `python-ptyprocess`; the graph can order the recipes from
the explicit `BuildRequires`. The Rawhide 4.9.0 recipe points at an upstream
`4.9.0` archive that no longer exists; upstream's tag is `4.9`. The 4.9 tag
archive and Fedora's pinned 4.9.0 archive have identical file contents but
not identical compressed bytes. Lock the upstream tag's own SHA-512, adjust
`Source0` and `%autosetup` to its filename and directory, and preserve the
Rawhide patches and test configuration. A successful source-tree comparison
is not a package build or runtime test.

### Audio fingerprinting library

The `chromaprint` source recipe produces `libchromaprint` and uses
`fftw-devel`; check Hummingbird's repodata before adding an FFTW recipe.
The default tools subpackage also BuildRequires `ffmpeg-free-devel`. The
factory's ffmpeg disables its chromaprint integration to break the reverse
edge; importing this recipe does not enable that integration or prove either
package builds. Keep the existing cycle break until a separately validated
build plan addresses it. Verify published binary dependencies and exercise
fingerprinting before claiming runtime closure.

### BSD compatibility library closure

Import `libbsd` with `libmd`: the former BuildRequires `libmd-devel`, its
shared library links to `libmd.so.0`, and `libbsd-devel` also requires
`libmd-devel` at runtime. Treat `libmd` as a required cross-area dependency
(the audit places it in `long-tail`), not an optional extra. The build graph
orders these from the existing BuildRequires; no manual stage is needed.
Both recipes carry detached signatures in `sources` and a checked-in signing
key. Preserve their `%{gpgverify}` checks and SHA-512 signature pins when
locking the release tarballs from `libbsd.freedesktop.org`.

For `python-pskc`, Fedora carries the detached signature and signing key in
dist-git rather than its lookaside manifest. Keep both beside the spec: the
recipe verifies them in `%prep`, while the upstream archive remains SHA-512
locked. Neither `arthur.asc` nor `python_pskc-<version>.tar.gz.asc` matches the
root `.gitignore` keyring exceptions, so keep `!packages/python-pskc/*.asc`
there; without it a renamed signature on a version bump is silently skipped by
`git add`. Verify the signing key independently before treating it as trusted.

### ifuse dependencies and device test

The `ifuse` recipe builds against the existing `libimobiledevice`,
`libimobiledevice-glue`, and `libplist` recipes and needs `usbmuxd` at
runtime. An imported recipe alone does not prove a device can be mounted;
verify the published package and its runtime dependencies on a real device.

### iwd and the Embedded Linux Library

Fedora builds `iwd` with `--enable-external-ell`, so it links `libell.so` at
runtime and Hummingbird does not ship it. Import the `libell` source package
alongside it. Fedora's `ell` dist-git is an unrelated header-only C++ grammar
library; do not import it for `pkgconfig(ell)`. The `libell-devel` `%files`
list `ell.pc`, so the build graph orders `libell` before `iwd` without a
`stage`. Fedora's `iwd` `.gitignore` ignores `iwd.spec` and `sources`: stage
them with `git add -f`, or the import commits an empty recipe.

Two other names in the same batch have no straightforward import. Fedora
retired `fuse-encfs` in Rawhide (`dead.package`), and the `hfsplus-tools`
`Source0` host returns 404 while dist-git still pins an MD5 `sources` entry.
Each needs its own source decision rather than a Rawhide import.
### Block-cache tools and safe validation

`bcache-tools` is one source family, including the `bcache-status` Python
helper. Fedora's `Source0` is a bare filename, but the upstream kernel.org
`colyli/bcache-tools.git/snapshot/bcache-tools-1.1.tar.gz` archive matches
its SHA-512 manifest exactly; use that direct upstream URL rather than a
Fedora-primary lock. The supplementary `bcache-status-20140220.tar.gz` is a
packager-created gist snapshot staged by `source_pipeline.bundled_sources`;
retain its separate manifest pin and the imported Python 3 patches.

The explicit runtime `libblkid >= 2.24` and generated library/Python
requirements need checking against Hummingbird plus the factory after a hosted
build. A catalog import is not a working disk cache. Do not run `make-bcache`
on host disks: payload validation must use disposable virtual disks and record
their identities. Kernel support and a successful cache exercise remain consumer
acceptance requirements; importing these userspace tools changes no kernel policy.

### WebDAV filesystem runtime closure

`davfs2` uses the `neon` HTTP/WebDAV library; its default build in turn links
`libntlm` for authentication. Check both libraries in the current factory and
Hummingbird metadata before importing the filesystem helper. When neither
repository supplies them, import all three sources together and let the
BuildRequires graph order `libntlm` before `neon` before `davfs2`. Retain
`davfs2`'s detached upstream signature and bundled verification keyring;
verify the signature download against its own `sources` digest as well as
checking the main archive. Recipe-level closing records do not establish
publication, runtime dependency resolution, or a working WebDAV mount.

### Encoding detection library imports

`uchardet` is both the source recipe and the runtime binary name; the same
recipe also builds `uchardet-devel`. Keep its CTest `%check` and the imported
CMake policy compatibility setting when registering the source. For runtime
acceptance, exercise the installed detector with known non-ASCII input (for
example UTF-8 text) and record its reported encoding alongside the permitted
repository transaction. Matching an upstream archive checksum proves source
identity, not that the installed detector works.

### Handwriting models share the recognizer recipe

`zinnia-tomoe-ja` is an unconditional subpackage of `zinnia`, not a separate
Fedora source package. Its model is trained during the build from the `tomoe`
build dependency's XML dictionary, using `Makefile.tomoe` and `tomoe2s.pl`
carried in the pinned dist-git tree. Keep both binary names tied to the same
source lock and validate model loading as well as the Python binding import.
`tomoe` is a build-time input here; it is not a runtime requirement of the
recognizer or generated model. Do not add a runtime recipe just because a
BuildRequires is absent from Hummingbird (the build root also uses Fedora).

## Diagnosing drift

- `--check` compares the whole live report with the committed snapshot —
  totals, states, the per-area rollup and every entry — so a name moving
  between areas fails the gate even though the counts are unchanged.
- When a rebase conflicts in `reports/factory-build-backlog.json`, resolve the
  catalog and recipe changes against current `main` first, then run
  `just regenerate-inventory` from the combined inventory. Do not choose one
  side's generated totals: that can discard resolutions or recipe imports
  from the other branch. Stage the regenerated files before continuing the rebase.
  If the catalog conflict is two independent additions to `[resolved]`, keep
  both sets of records; neither supersedes the other. Preserve unrelated skill
  sections added on `main` when the reconciliation guidance conflicts too.
- A `pending` count that grows means a name was added to the catalog
  without a recipe; run `just regenerate-inventory` and inspect
  `reports/factory-build-backlog.json`.
- A `pending` count that shrinks without a commit means someone dropped a
  name from the catalog without recording the decision; `git log -p
  config/factory-build-backlog.toml` is the fastest trace.
- `already_recipe` for a binary subpackage (`libavcodec`, `libavformat`,
  ...) means the source package's recipe declares it with a `%package`
  line: read the recipe, not the binary name. The auditor resolves both
  `%package -n NAME` and `%package SUFFIX` (which names `<spec>-SUFFIX`),
  and only when the `%package` is reached by the default build. A binary
  name no `%package` line declares — such as `ffmpeg-libs`, which RPM
  never builds under that name here — stays `pending` until the operator
  closes it in `[resolved]` or `[wontfix]`.
- A `%package` behind a disabled or undecidable `%if` does not count.
  `packages/gstreamer1-plugins-good/` declares `%package qt6` under `%if
  %{with qt6}` while the spec sets `%bcond_with qt6` and nothing in the
  factory passes `--with qt6`, so `gstreamer1-plugins-good-qt6` is
  `pending`: the factory build does not produce it. `packages/ffmpeg/`
  declares its `libav*` subpackages under `%if ! %{with freeworld_lavc}`,
  which is true by default, so those are `already_recipe`. Conditions the
  auditor cannot decide without a build target (`%ifarch`, `0%{?fedora}`)
  are treated as not taken — an extra `pending` name is visible work, a
  false `already_recipe` hides a gap. A `%bcond` declared inside such a
  branch is likewise not applied: under an untaken branch it is ignored,
  under an undecidable one (`%if 0%{?fedora} %bcond_without X %else
  %bcond_with X %endif`, as with `wget2-wget`'s `as_wget`) or when written with
  curly-brace macro syntax (`%{bcond_without whois_enables_mkpasswd}` in
  `whois.spec`) the bcond is left unknown, so any `%if %{with X}` it guards is
  undecidable too and its subpackage must be closed explicitly in `[resolved]`
  by the batch that owns it.

After a recipe PR lands, run `just regenerate-inventory`; the inventory-driven
gate deliberately rejects a snapshot made before that import. When preparing
concurrent PRs, combine current `main` and PR catalog, recipe, and source-lock
changes first, then regenerate all derived files before `just check`. A
conflict resolution can leave valid package entries but stale architecture
counts; regenerate even if the document itself had no conflict. Choosing
either branch's generated report wholesale can discard the other's updates.

For Python recipes, check both the upstream project metadata and explicit RPM
requirements when assessing runtime closure. For example, Click's upstream
metadata only requires colorama on Windows, but its Fedora recipe also
requires `less` for the default terminal pager. Recipe coverage alone does not
prove that dependency resolves in an installed factory build.

The AWS client libraries in the dev-tools area form one dependency chain:
`python3-boto3` needs `python3-botocore` and `python3-s3transfer`, and
`python3-botocore` needs `python3-jmespath` and `python3-dateutil` at runtime.
Import the leaves first (`python-jmespath`, then `python-botocore`) so each
recipe's runtime requirements already have a factory recipe when it lands.

When concurrent disposition PRs conflict during rebase, retain each distinct
`[resolved]` and `[wontfix]` record in the catalog, then run
`just regenerate-inventory`. Do not choose one side of the generated JSON:
it must reflect both sets of catalog changes. Verify the result with
`just factory-build-backlog` before continuing the rebase.

### Reconciling published batches

A failed aggregate rebuild can still publish successful packages and retain older
RPMs from its seed repository. Reconcile each binary against the published
repodata and digest, rather than treating the run conclusion or a newer failed
rebuild as evidence that it is absent. Keep publication evidence separate from
current build health and consumer validation. An approved consumer waiver also
applies to a session subpackage whose source would reintroduce excluded shell
extensions; link that decision in its `[wontfix]` record.

`published_run` / `published_nevra` are optional and also informational (the
tool reads only `name`); set them from the publication run's repodata when
reconciling a published batch. The image's run label identifies its publisher,
not necessarily the run that built each retained RPM. A registry digest can
already be readable while that run is still in progress; report the observed
publication without calling the workflow successful. For example, the #486
reconciliation observes eight binaries in one image, but that does not prove
eight fresh builds or successful device/service tests. Preserve the original
recipe-import `pr` fields when adding this evidence, and leave the auditor
snapshot unchanged when regeneration produces no diff. Record any known newer
failed rebuilds by package name and run in the catalog comments so publication
evidence does not hide current build health.

Read both from one image: `python3 tools/package_index.py --image
projectbluefin/utah-packages:latest --output <file>` writes the manifest
digest, the publishing `run` and the source `revision` under `image`, and every
binary with its source package and epoch/version/release under `packages`.
Check that `revision` is on the target branch before citing it. The primary
metadata checksum is in `repository/repodata/repomd.xml` inside the image's
first layer (`fetch_image` in the same tool returns it). An import PR that
left its name `already_recipe` pending evidence (`tslib`, #643) moves to
`[resolved]` in a later reconciliation PR once that image carries the binary;
cite the original import PR and merge commit rather than the reconciliation.
### X11 resource library imports

The audited `libXres` binary is the main output of source recipe `libXres`;
its SONAME uses different capitalization (`libXRes.so.1`). The same recipe
emits `libXres-devel`, with the `xres.pc` pkg-config module. Do not import
another recipe for the SONAME or the development output. The release archive
comes from X.Org's `pub/individual/lib` directory; its `sources` SHA-512 must
match the upstream download. Snapshot-only `Source1` and `Source2` entries
are behind the disabled `gitdate` condition and are not release downloads.

For runtime acceptance, install the built library using only Hummingbird
plus the factory and exercise `XResQueryExtension` against a running X11
server. Loading `libXRes.so.1` alone checks linkage, not server interaction.
This import PR moves `libXres` from its area to `[resolved]`. That entry
records the recipe import only; it does not claim the batch issue's build and
runtime acceptance, which stays tracked on the issue.
When rebasing a recipe PR, resolve catalog and recipe inputs against current
`main`, run `just regenerate-inventory`, then verify with
`just factory-build-backlog`; choosing either generated report can discard
another import's state.

### Langtable source archives and schema checks

`langtable` builds both `langtable` and `python3-langtable`; import the source
once and reconcile both audit names. Its `%check` invokes `xmllint`, so declare
`BuildRequires: libxml2` explicitly instead of relying on the container image.

The upstream 0.0.71 release asset has SHA-256
`f9d39c06d5182ea14eb4576bf1da8875af1d44efb166e55d6865b3b59b8ac617`,
as recorded by GitHub's release asset API. Its SHA-512 differs from Fedora's
`sources` pin. Comparing both tarballs showed the same 39 members, file bytes,
modes and link targets; archive metadata differs. The factory locks the upstream
asset's SHA-512 in both `sources` and the source lock, with no Fedora fallback
because Fedora's archive has different bytes. Do not generalize this comparison
to later releases: investigate any future mismatch before changing a pin.

### Broadcom firmware extraction tool

`b43-fwcutter` is the standalone source and binary for extracting firmware;
`b43-openfwwf` is a separate firmware source, not its subpackage or a required
runtime dependency. Importing the extraction tool does not supply firmware or
establish that a wireless adapter works. Keep those acceptance claims separate.

The recipe verifies the release archive with a detached signature and the
checked-in `757FAB7CED1814AE15B4836E5FB027474203454C.gpg` key. Despite its
`.gpg` suffix, that file is ASCII-armored. Preserve both `sources` SHA-512
entries and `%{gpgverify}`; the source pipeline stages the signature from the
manifest alongside the archive. When verifying manually with `gpgv`, dearmor
the key into a temporary keyring first. For runtime acceptance, install from
only Hummingbird plus the factory, run `b43-fwcutter -l`, and extract a supported
user-supplied firmware image into a disposable directory. Record the input
identity, extraction result and output files; a version check alone is not
firmware extraction proof. Do not bundle a proprietary input into the recipe.

### Shell prompt test dependencies

`bash-color-prompt` enables its Bats tests by default. Import `bats` and
GNU `parallel` together when neither supplier publishes them: Bats requires
Parallel at build time and runtime, even though the prompt payload itself is
shell code. Keep the tests enabled. GNU Parallel's detached signature is
locked in `packages/parallel/sources` and fetched through the lookaside path
with the tarball; its signing key and patch come from the pinned dist-git
recipe. A recipe import leaves the prompt in `already_recipe` until
hosted builds and installation evidence establish the runtime result.
## Boot-screen output reconciliation

Plymouth's boot animation, core and graphics libraries, label and two-step
plugins, scripts, default-theme selector and spinner theme all come from
`packages/plymouth/plymouth.spec`. Reconcile those binary names together;
do not import a recipe per plugin. The `plymouth-system-theme` package is a
selector: the spinner theme supplies its versioned `plymouth(system-theme)`
requirement. Check both binary names in published primary metadata even when
the selector has no installed payload.

A catalog closing record can cite the existing merged recipe/source-lock PR
when reconciling a later audit. Record the observed image digest, publication
run and all requested binary identities in the reconciliation PR. This closes
recipe accounting only: a metadata listing does not prove the theme's dependency
transaction or graphical boot behavior. Keep those acceptance items open in the
batch issue and hand them to Utah's consumer tracking.

For `pam_yubico`, the Fedora source recipe requires `ykclient-devel`,
`libyubikey-devel`, and `ykpers-devel`; all three source families must precede
it in the build graph. A recipe and verified source do not prove authentication
works: verify the hosted RPM, dependency transaction, and configured hardware.

### Long-tail package output reconciliation

When auditing a long-tail batch, check each output against the published
primary repodata (see "Reconciling published batches" above) before touching
the catalog: an output may already sit in `[resolved]` without `published_run`
/ `published_nevra`; fill those in rather than re-importing. Recipes merged on
main but not yet in the published image stay in `[resolved]` without
publication fields until a run ships them. Partial reconciliation PRs must
link the tracking issue with `Refs #<issue>`, not a closing keyword.

When rebasing an import over other backlog changes, retain the base branch's
publication evidence and add only the new recipe's closing record. Run
`just regenerate-inventory` after combining the catalog and recipe inputs
with current `main`; neither side's old report or architecture counts describe
the combined inventory.

Use `parse_primary(primary_from_layer(blob))` from `tools/package_index.py`
when recording each binary's NEVRA. The rendered site's `packages` entries
are grouped by source RPM: their version and release come from that source,
and their epoch comes from the group's leading binary. Those values are not
necessarily the identity of every sibling binary. Read each binary's own
metadata (including epoch and architecture), and retain the image digest and
primary checksum with the catalog evidence. Fetch by that digest when checking
the raw metadata so a moving `latest` tag cannot mix two publications.
Metadata publication is independent of the workflow's aggregate conclusion;
it does not establish a successful runtime transaction or payload exercise.

The `passwdqc` source also builds `libpasswdqc` through `%package -n
lib%name`. The inventory auditor does not expand that concatenated macro, so
this output can appear `pending` even with a registered, source-locked recipe.
Verify the expanded binary name and `passwdqc` source RPM in published metadata
before reconciling it; do not import a second recipe named `libpasswdqc`.
Its merged import is #676 (which adopted the closed #644), so use the merged
PR and its target-branch commit for provenance rather than the earlier proposal.
Publication of the library does not verify password policy or PAM integration;
keep those consumer checks separate from catalog accounting.

A closed import PR is not necessarily a rejected import: maintainers can adopt
its commits in another PR. Follow its closing comment, verify the adoption PR
is merged and its merge commit is on the target branch, then use that merged
PR and stable commit for the catalog record. For example, `passwdqc` came
through #676 (adopting #644), and `portaudio` through #752 (adopting #748).
The `passwdqc` source emits `pam_passwdqc`, `passwdqc`, and `passwdqc-utils`;
check all three binary versions in primary metadata before filling publication
fields. Updating optional publication fields does not change the auditor's
name-only snapshot; rerun it anyway and expect no report diff when no names
or recipe classifications changed. Publication still does not prove password
policy integration, audio-device operation, or a permitted-repository install.

### Microsoft CAB library imports

`libmspack` is both the source recipe and the audited binary; the same
recipe builds `libmspack-devel`. Fedora's `Source0` still points at
`http://www.cabextract.org.uk/`; the `https://` URL serves the same
`<version>alpha` archive bytes as the `sources` SHA-512, so lock that in
`config/upstream-sources.json` and keep the Fedora lookaside in
`fallback_urls`. As with `libev`, leave the imported spec's `Source0`
verbatim: the lock, not the recipe, carries the HTTPS URL, and a later
re-import then reproduces the recipe unchanged. The recipe applies its CVE backport
with `%autosetup -S git` because the patch carries binary test fixtures:
keep `BuildRequires: git` and the upstream `make check`. The library has no
runtime `Requires` beyond glibc. For runtime acceptance, install from only
Hummingbird plus the factory and extract a known `.cab` file through a
libmspack consumer (for example `cabextract`, itself still outside the
factory) or the bundled examples; loading `libmspack.so.0` alone checks
linkage, not decompression.

### Paper-size library imports

`libpaper` is both the source recipe and the audited binary; the same
recipe builds `libpaper-devel` and the `paper` CLI. Fedora's `Source0` is
already the upstream GitHub tag archive, whose bytes match the `sources`
SHA-512, so lock that URL directly with the Fedora lookaside in
`fallback_urls`. The recipe carries `Epoch: 1` (it replaced Fedora's old
separate `paper` package), so the published NEVRA reads `libpaper-1:…`;
record it with the epoch. `%prep` re-bootstraps against the system gnulib:
`gnulib-devel` and `help2man` are build-time only and resolve from the
buildroot, not the factory. The library has no runtime `Requires` beyond
glibc. For runtime acceptance, install `paper` from only Hummingbird plus the
factory and run `paper --all` (lists the size catalogue from
`/etc/paperspecs`) and `paper` (prints the default size); loading
`libpaper.so.2` alone checks linkage, not the catalogue.

### Kyoto Cabinet library imports

`kyotocabinet-libs` comes from source recipe `kyotocabinet`, which also
builds the command-line tools, development files and API documentation. The
recipe enables LZO and LZMA compression; check `lzo`, `xz-libs`, and the zlib
provider in Hummingbird before importing additional runtime dependencies.
Hummingbird's `zlib-ng-compat-devel` provides `zlib-devel`; match capabilities,
not just package names. Keep the upstream `make check` enabled. Dist-git also
carries an old random-failure suppression patch, but the imported spec does not
declare it: do not enable it to turn a failing build green.

After a hosted build and permitted-repository installation, exercise persistent
storage rather than only loading the library: use `kchashmgr create test.kch`,
`kchashmgr set test.kch key value`, `kchashmgr get test.kch key` (expect
`value`), then `kchashmgr check test.kch`. These tools come from the main
`kyotocabinet` binary and link the library subpackage. Record the transaction,
NEVRAs and command results separately from the recipe closing record.

### slirp4netns recipe review

Rawhide's slirp4netns 1.3.1 recipe at
`efddb3c622619b516a5b2850dae14d1e52035688` retains Go-template macros
(`golang_arches_future`, `built_tag_strip`, `import_path`) and an empty
`devel` subpackage, but upstream's `configure.ac` and `Makefile.am` describe
one C executable, not a Go library. Use the archive's
`slirp4netns-<version>` directory, remove the irrelevant template restrictions,
and build the default target before installation; `generate-man` alone does
not compile the program. Keep the generated provenance record unchanged and
explain these local recipe repairs in the spec.

Reuse the existing `libslirp` recipe for `libslirp-devel`; the build graph
orders this ordinary BuildRequires edge without a hand-assigned stage.
Upstream's integration suite needs network namespaces and external connectivity.
Version/help smoke checks in `%check` establish executable startup only, not
container networking. Hosted namespace tests, a Hummingbird-plus-factory runtime
transaction, and publication evidence remain separate acceptance requirements.

### S-Lang library imports

The `slang` source produces the audited `slang` library and a separate
`slang-slsh` interpreter. Its Fedora recipe enables Oniguruma conditionally
on the target's `%{?fedora}` macro; check the actual pinned buildroot and
resulting RPM dependencies rather than assuming the conditional is on or off.
The upstream test suite covers terminal capabilities, syntax parsing, and
UTF-8 support; run it on every recipe bump.

### NILFS utilities signature sources

For `nilfs-utils`, the release archive and detached signature are separate
`Source` entries. Verify both against `sources` and the bundled signing key;
the source pipeline stages the signature from the digest-addressed lookaside.
The catalog records the recipe import, not proof of installation or publication.

## Firewall connection monitor acceptance

`iptstate` is a standalone source and binary, not an `iptables` subpackage.
Its recipe requires `iptables` at runtime plus automatically detected ncurses
and libnetfilter_conntrack libraries. Check virtual provides as well as binary
names when locating the `iptables` supplier. A metadata match alone is not a
successful solver transaction.

After a hosted build, resolve installation against only Hummingbird and the
factory, then run `iptstate --single` with access to the kernel connection
tracking table (CAP_NET_ADMIN in the tested network namespace). Record the
namespace and result. `--help` only tests program startup; it does not exercise
connection tracking. A permissions error is not a successful runtime probe.

### Long-tail batch #503: reconcile before importing

`libvarlink` (#519) was `already_recipe` and published, so it moved to
`[resolved]` with its NEVRA and image digest rather than a second import.
`lockdev` stays pending: no upstream serves its MD5-pinned 2011 snapshot (see
[`repeated-mistakes.md` section 17](repeated-mistakes.md#17-cups-2x-and-cups-filters-2x-package-split)), and moving it to
`[wontfix]` needs a linked maintainer decision. `lrzsz` is a hand import:
Fedora pins it by MD5, so confirm the `https://www.ohse.de/` bytes match that
pin, repin `sources` to SHA-512, and use the `/md5/<md5>/` lookaside path as
the fallback. `liburing` locks only `Source0`; like `dnsmasq`, its `.asc`
signature is fetched from Fedora's lookaside by its `sources` SHA-512.

`librabbitmq` and `libwmf-lite` (a subpackage of `libwmf`) lock their GitHub
tag archives directly: those bytes equal the dist-git SHA-512 pins. Check the
archive bytes against the pin before you lock a source.

`libslirp` and `librtmp` (source `rtmpdump`) have no release file, so their
locks are `generate` entries in `GIT_ARCHIVE_SOURCES`
(`tools/generated_sources.py`): fetch the tag, check that it still resolves
to the pinned commit, and `git archive --format=tar --prefix=<name>-<version>/`.
To find out how Fedora made such a tarball, decompress its lookaside copy and
compare the raw tar with `git archive`. Then try each compressor setting.
`libslirp`'s tar is GitLab's archive, and Python's `lzma` preset 6 (CRC64)
reproduces Fedora's `.tar.xz` pin exactly, so `sources` is unchanged. For
`rtmpdump`, the tar is byte-identical but Fedora's gzip stream is not: it is
zlib-ng output, which neither GNU gzip nor Python's zlib reproduces. So it is
`gzip -n -9`, and `sources` is repinned to the generated digest.
`git.ffmpeg.org/rtmpdump.git` advertises refs to the all-zero object, which
makes `git clone` fail with `upload-pack: not our ref 0000…`. Fetch only
`refs/tags/<tag>` into an empty repository instead.

### Audio-plugin discovery library closure

`lilv-libs` comes from `lilv`; its supporting source recipes are `lv2`,
`serd`, `zix`, `sord`, and `sratom`. Reuse existing `serd` and `zix` recipes.
Preserve the pkg-config BuildRequires: the graph solver orders `sord` after
`serd` and `zix`, `sratom` after `sord` and `lv2`, and `lilv` after `sratom`.
This chain is acyclic, so do not add source-lock stages.

Drobilla's release signatures are available alongside the release archives at
`https://download.drobilla.net/`. Its key at
`https://drobilla.net/drobilla.gpg` is ASCII-armored despite its extension:
dearmor it before passing it to `gpgv --keyring`. Preserve the imported
signature pins and the recipe's verification step. Match both archive and
signature digests against `sources`; a valid signature does not replace the
factory SHA-512 lock. LV2 release archives use `https://lv2plug.in/spec/`.

A `[resolved]` catalog entry for this family records recipe availability,
not publication. Record hosted build NEVRAs and the repository digest before
claiming closure, then resolve `lilv-libs` and its runtime dependencies using
only Hummingbird plus the factory. Exercise `lv2ls` and load the library;
local configuration tests do not prove that transaction.

### GNOME apps batch #484: terminal outputs and publication reconciliation

The terminal and terminal-widget outputs (`ptyxis`, `vte291`, `vte-profile`,
`vte291-gtk4`) were imported in #413 (`ptyxis.spec` and `vte291.spec`), with
`vte-profile` and `vte291-gtk4` produced as subpackages of `vte291`. When
reconciling batch outputs against published image repodata, verify their NEVRAs
in `ghcr.io/projectbluefin/utah-packages:latest` and move them from
`[areas.gnome-apps]` to `[resolved]` citing import PR #413 and merge commit
`ded82d6174382a397a2d7ddc066daeabe2e31232`.

Previously resolved GNOME outputs (`gtkmm4.0`, `pangomm2.48`, `gtksourceview5`,
`libhandy`, `libspelling`) also populate their observed `published_run` and
`published_nevra` fields. `imath` and `rygel` were imported as source recipes
with upstream SHA-512 locks (`Imath-3.1.12.tar.gz`, `rygel-46.1.tar.xz`); their
hosted build, publication and runtime proof remain on #484, recorded in
`[resolved]` as recipe-import-only. Until a hosted run publishes them, the
batch issue stays open with `Refs #484`.


### Image-processing library

`leptonica` builds its image-processing library from its own source recipe.
Its optional gnuplot and MinGW build requirements depend on target macros;
check the pinned buildroot and resulting binaries rather than assuming they
are enabled. Recipe accounting does not establish publication or image-processing
behavior; verify both with the hosted build and a representative image.

`libwnck3` is the X11 window-list library (GTK 3); Orca `Recommends` it and
Utah triages it as `planned`. Fedora's source package is `libwnck3` but the
upstream tarball is `libwnck`: lock
`download.gnome.org/sources/libwnck/43/libwnck-<version>.tar.xz`, not a
`libwnck3` path. The Rawhide recipe ships five patches with their `Patch`
lines commented out (an unmerged upstream MR); import them unchanged and do
not re-enable them. Its build and runtime dependencies (`gtk3`, `libXres`,
`startup-notification`) are already factory recipes, so no extra source
family is needed.

`libmediaart` also emits `libmediaart-devel` from the same recipe. Rawhide
1.9.7 carries `21.patch` to use Glycin instead of GdkPixbuf; keep that patch,
`pkgconfig(glycin-2)`, `-Dimage_library=glycin`, and `%meson_test` together.
The existing `glycin` recipe provides the development files and the runtime
`glycin-libs` / `glycin-loaders` outputs; no second source import is needed.
Runtime acceptance must exercise JPEG extraction/cache creation with the
published Glycin loaders, not just load `libmediaart-2.0.so.0`. A recipe-only
closing record does not prove sandboxed image decoding or publication.

`imath` is the C++ vector/matrix library OpenEXR builds on; `openexr-libs`
itself has no factory recipe yet and is still pending in `[areas.long-tail]`.
The Rawhide recipe ships two patches that disable failing Python bindings tests
(`imath-disable-python-testPlane.patch`,
`imath-disable-python-testM44fArray.patch`); keep them unchanged. Its build
requires `boost-devel` and `python3-devel`, which have no factory recipes and
come from the Fedora 44 buildroot, and it ships the `imath` and `python3-imath` binaries from one source. A catalog record
for the recipe does not prove the shared library or the Python module was built
or importable.

`rygel` is a UPnP/DLNA home media server that pulls the largest dependency set
in this batch. `gupnp-1.6`, `gupnp-dlna-2.0`, `gst-editing-services-1.0`,
`gee-0.8`, `libmediaart-2.0`, `libsoup-3.0` and `gtk4` have factory recipes;
`sqlite3` and `tinysparql-3.0` have none and come from the Hummingbird base. Its
`pkgconfig(gupnp-av-1.0)` BuildRequires is a concrete blocker: `gupnp-av` has no
factory recipe and is still pending in `[areas.long-tail]`
(projectbluefin/utah#396), so rygel cannot build until `gupnp-av` is imported.
It emits a `rygel-localsearch` subpackage that obsoletes `rygel-tracker`, and
installs a systemd user service; keep the `localsearch` `%files` section. The
Rawhide donor omits the `%post` header before `%systemd_user_post`; preserve
Utah's added header when re-importing so user-unit preset handling belongs to
the installed RPM's post-install scriptlet, not the build's `%install` script.
Use the pinned Packit image's `rpmspec --parse` and binary-header query to
verify that boundary before building. A correct scriptlet does not establish
that the UPnP MediaServer responds or the user service starts; those still
require a published package and a user-session runtime probe.

### NTFS system compression plugin

The `ntfs-3g-system-compression` source produces a plugin for the existing
`ntfs-3g` driver, not a second driver recipe. Its build requires
`pkgconfig(libntfs-3g)`, so keep the existing source in the factory graph.
A catalog record for the recipe does not prove the plugin has been built,
published, or loaded with the driver.

### Perl modules split out of Hummingbird's perl

Fedora splits dual-life core modules such as `perl-Unicode-Normalize` into
their own source recipes. Hummingbird's `perl` metapackage still requires
`perl-Unicode-Normalize` but does not ship it, so a full `perl` install needs
the factory output; check `perl(...)` provides in Hummingbird's primary
metadata before assuming a module is supplied. The Fedora recipe builds from
the older CPAN archive (`base_version`) plus an upgrade patch, so its source
lock pins that CPAN archive while `version` stays the RPM `Version:`. Its
`-tests` subpackage requires `perl-Test-Harness`, which Hummingbird lacks;
the audited name is the main package, and runtime acceptance is
`perl -MUnicode::Normalize=NFD,NFC -e` round-tripping a composed string.

### ImageMagick recipe (codecs-media, #474)

`ImageMagick.spec` builds both `ImageMagick` and `ImageMagick-libs` (its
`%package libs`), so one import resolves both names. It was imported without
`rpmspec` or a container: the `Source0` SHA-512 in `packages/ImageMagick/sources`
was checked against the upstream tarball before locking it. Its BuildRequires
(libheif, libjxl, libuhdr, jasper and others) are separate graph dependencies;
a catalog record does not prove the build succeeds. The ffmpeg family,
`LCEVCdec`, `davs2-libs` and `gstreamer1-plugins-good-qt6` stay pending in
`[areas.codecs-media]`, so `#474` stays open.

## Hand-locking an import without `rpmspec`

When the import workflow cannot be dispatched, import with
`tools/import_rawhide.py`, download `Source0`, and confirm its SHA-512 equals
the digest in the recipe's `sources` before adding the lock entry. Some Fedora
specs use `http://kernel.org/...`; lock the `https://cdn.kernel.org/...` URL
instead, since `tools/validate.py` rejects plain-http locks. Then run
`just regenerate-inventory`.
Hosted build evidence is still owed; a lock alone does not resolve a runtime gap.

## IP set package family

The `ipset` source builds both the command and `ipset-libs`; track both
outputs from the same recipe. Its optional `ipset-service` subpackage also
requires `iptables-services`, so check that provider when verifying the full
built RPM set. Runtime verification needs a network namespace with the kernel
IP set support and `CAP_NET_ADMIN`: create a set, add and query an address,
then destroy the set. A version or help command does not exercise that path.

## JBIG2 decoder library

`jbig2dec-libs` is an output of the `jbig2dec` source recipe, not a separate source. Ghostscript currently builds its bundled copy, so that does not establish availability of the separate library. The upstream recipe warns that consumers of its shared library must be rebuilt together on version changes; verify the hosted build, dependency transaction, and representative decoding before claiming runtime closure.

## Windows domain enrollment (adcli)

A spec using `%global with_selinux 1` can emit a SELinux subpackage even when the backlog auditor cannot evaluate its `%{with selinux}` guard. Check the default RPM expansion and retain build and publication verification as separate evidence; a recipe classification alone does not prove an installable binary.

The adcli recipe BuildRequires `libnetapi-devel` from the factory samba recipe. Keep its recorded stage later than samba for the ICU staging guard, and verify the generated build graph still orders the dependency before adcli.

## Serd source verification

The `serd` recipe checks a detached upstream signature using the signing key
carried in the recipe directory. Preserve the signature entry in `sources`
and compare its SHA-512 independently from the release archive; a source lock
for the archive alone does not establish that the signature is available.

## HFS+ filesystem tools

`hfsplus-tools` is the source recipe and binary name; its payload is
`diskdev_cmds-540.1.linux3.tar.gz`, Matthew Garrett's Linux port, rather than
an unmodified Apple release. The imported Fedora recipe also carries the
APSL license text as `apsl-2.0.txt`; keep that tracked file for `Source100`
instead of downloading the license again during the build.

The author's `cavan.codon.org.uk` archive URL can return HTTP 404. The source
pipeline already tries `fallback_urls` on transport failure, then checks the
same SHA-512; an unavailable primary does not require promoting Fedora to
`url` or expanding the Fedora-primary ratchet. The historical Fedora mirror
is addressed by the original MD5 directory, but the lock and `sources` must
still use SHA-512. Check the downloaded bytes against both the imported
manifest and an independent strong digest, such as
[Alpine's recorded SHA-512](https://git-old.alpinelinux.org/aports/commit/testing/hfsprogs?id=2adeba433d4de964a51ba73fad56b32397569462).
A mirror supplies availability, not an upstream signature; record the failed
primary and successful fallback explicitly in review evidence. A wrong digest
must still fail without trying another mirror.

Do not exercise `mkfs.hfsplus` or repair with `fsck.hfsplus` on a host disk.
After a hosted build, test them against a disposable filesystem image in the
permitted runtime environment, and record the binary identity and results.
Recipe coverage alone does not establish filesystem safety or installation.

## Libev event loop library

The `libev` source package provides the audited `libev` shared library, `libev-devel`,
`libev-source`, and the compatibility header package `libev-libevent-devel`.
Note that `libev-libevent-devel` declares an explicit `Conflicts: libevent-devel`
to protect the shared `event.h` header; `libev-devel` alone does not conflict.
Its `Source0` URL in the imported spec is plain `http://` (kept verbatim from Fedora);
the source lock in `config/upstream-sources.json` fetches the same archive over
`https://dist.schmorp.de` and the Fedora lookaside fallback, matching the SHA-512 in `sources`.
An imported recipe record alone does not establish publication or runtime
acceptance in Utah; those remain tracked with the #502 batch.

## uvg266 VVC encoder library

Fedora dist-git has no `uvg266`, so `uvg266-libs` comes from the negativo17
recipe imported with `tools/import_rawhide.py --branch master
--remote-template 'https://github.com/negativo17/{package}.git' uvg266`; the
provenance keeps the `master` branch, commit and tree (see the multimedia
closure skill's codec-tail rules). The same recipe builds `uvg266` (CLI),
`uvg266-libs` (`libuvg266.so.0`) and `uvg266-devel`; do not add a second
recipe under the binary name. negativo17 carries no `sources` file, so the
GitHub release archive is locked only in `config/upstream-sources.json`. The
recipe has no `%check`: upstream tests need the `greatest` submodule, which
the release archive omits, so a hosted build proves compilation only. For
runtime acceptance, install `uvg266` from Hummingbird plus the factory and
encode a short raw YUV clip (`uvg266 -i in.yuv --input-res 64x64 -o out.266`).

The kernel-module names in the same long-tail batch (`v4l2loopback`,
`ublue-os-akmods-addons`, `virtualbox-guest-additions`) are out-of-tree
kernel module packages. The #491 decision covers only `kernel-modules-extra`
and `usbip`; do not extend it to these names. They stay pending until a
maintainer records a kernel-module policy decision for them.
