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
    `--check` validates names and inventory consistency, not this provenance field.
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

The `python-pysocks` Rawhide recipe disables its upstream tests because the
`test_server` module is not packaged (see its `%check`). A successful RPM
build does not exercise SOCKS connections: validate the installed
`python3-pysocks` payload against a test proxy as separate runtime evidence.

The `python-more-itertools`, `python-shtab` and `python-html2text` recipes are
noarch with no runtime dependencies, so their `[resolved]` records close the
recipe import only; hosted build, publication and a permitted-repository
runtime import remain outstanding on #489. `python-shtab`'s `sources` file
carries both the 1.7.2 and 1.8.0 archives; the lock pins 1.8.0 to match the
spec version. `shtab` only generates shell completion, so exercise it after
publication by sourcing the installed `shtab` output in a shell to confirm the
completion for at least one command is emitted.

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

`kpartx` is a binary subpackage of `device-mapper-multipath`, not a
separate source recipe. The imported multipath recipe uses a primary upstream
release archive and a second, SHA-512-pinned Fedora configuration file
(`multipath.conf`) from lookaside. Both must be staged before building. Recipe
coverage does not establish that the build, publication, dependency
transaction, or partition mapping command succeeds; verify those separately.

The `kf6` source recipe supplies `kf6-filesystem` and `kf6-rpm-macros`.
Its macro and license files are tracked in the imported packaging tree rather
than an upstream release archive. Its lock uses `no_upstream_source`; the
pinned dist-git provenance identifies those files. Recipe coverage alone does
not establish a build, publication, or runtime dependency closure.

Before importing an audit name, read Utah's current `baselines/triage.toml` and
pin the decision's commit when reconciling an existing `waived` entry into
`[wontfix]`. The audit can include deliberately absent X11 client utilities
(`xrandr`, `xset`, `xdriinfo`) or an updater installed directly from a pinned
release (`uupd`); their absence is not permission to reverse those decisions.
Do not extend a client-tool waiver to an X11 library such as `xcb-util-cursor`:
Wayland sessions still run applications through Xwayland. Check each exact
binary name, not a shared prefix.

A waiver applies only to the exact binary in Utah's triage record; do not
extend it to sibling outputs from the same source package. For example,
Utah's `rpm-ostree` waiver does not waive `rpm-ostree-libs`, which stays
pending without its own decision.

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
catalog entry, and retain the base's source fallback and publication metadata.

For font and language batches, follow
[Reconcile consumer decisions before importing](../font-package-recipes.md#reconcile-consumer-decisions-before-importing).
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

`PackageKit-glib` is a subpackage of the `PackageKit` source recipe, not a
separate source. The Rawhide recipe builds the DNF5 backend too and needs
`pkgconfig(libdnf5) >= 5.4.3.0` at build time. Its GLib library does not
require the PackageKit service by package name; a recipe import alone proves
neither that the backend builds in the pinned root nor that the library can be
installed and used from the published factory repository.

The `Import Rawhide package` workflow does **not** make this move: its pull
request carries the recipe, lock and `.packit.yaml`, but leaves the name in
its area. Before merging one, add the `[resolved]` entry (with that PR's
number); `just factory-build-backlog` lists a name left behind as
`already_recipe`. When two such PRs conflict, rebase the existing PR branch
onto current `main`, keep both sides' lock and catalog entries, and run
`just regenerate-inventory` from the combined inventory. Resolve generated
conflicts by regeneration, not by selecting either branch's copy.
Use `git rebase --signoff` to preserve DCO coverage, then push to the same PR
branch with `--force-with-lease` after validation. Inspect auto-merged catalog
records as well as conflicted files: fill in the existing PR number for new
recipe records, and retain the base branch's publication fields.

The catalog test (`tests/test_factory_build_backlog.py::CatalogConsistencyTests`)
pins the count and sorted-name SHA-256 against the original audit. The auditor
checks that same digest across area, resolved and wontfix entries. A one-for-one
substitution fails even when all counts remain unchanged; moving an existing
name to a closing record preserves the digest. The baseline was verified
against the pinned gist's `nowhere-551.txt`; changing it requires a new audit.
`--check` also fails when the catalog drops the `audit_names_sha256` pin.

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
BuildRequires. PR #788 imports the `libotf`, `libXaw`, `gd`, and
`anthy-unicode` prerequisites, not `m17n-lib` itself. Re-check referenced
provider PRs against the selected base before carrying a historical "waiting"
note forward. Preserve all four source locks and the anthy checksum when
integrating current main; union independent catalog records and regenerate
inventory instead of restoring stale workflow or Packit pins. The provider
recipes were merged first; `m17n-lib` was imported recipe-only in #856 and
still needs hosted build, publication, and runtime proof (#495). Configuration
checks establish neither hosted build success nor input-method runtime
acceptance. Keep build, publication, and runtime evidence separate.

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
[dead upstream hosts](../supply-chain-provenance.md#dead-upstream-hosts-releasespagureorg)).
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

### intel-vaapi-driver import; kmod-v4l2loopback stays pending

Neither name may move to `[wontfix]` on a dist-git 404. `intel-vaapi-driver`
(the i965 VA driver) has no Fedora dist-git, and its upstream
`github.com/intel/intel-vaapi-driver` is archived, so it is imported from
`github.com/negativo17/intel-vaapi-driver` with `tools/import_rawhide.py
--branch master --remote-template 'https://github.com/negativo17/{package}.git'
intel-vaapi-driver` (see the uvg266 section). That recipe's `Source0` is the
maintained `irql-notlessorequal/intel-vaapi-driver` fork (Epoch 1, release
archive locked in `config/upstream-sources.json`), not the archived Intel
repository; keep the fork as the primary URL. The recipe is `ExclusiveArch:
%{ix86} x86_64` and carries the AppStream helper sources (`*.metainfo.xml`,
`*.py`, `*.svg`) beside the spec. Its `%check` validates only the metainfo, so
runtime acceptance means installing it from Hummingbird plus the factory and
running `vainfo` on Intel GEN graphics (Gen 8 or older) with
`LIBVA_DRIVER_NAME=i965`.
`kmod-v4l2loopback` is a binary output of RPM Fusion's `v4l2loopback-kmod`
source package (built via kmodtool); the userspace `v4l2loopback` package is
tracked separately, so a `rpms/kmod-v4l2loopback` 404 says nothing about it
(resolve the source package first, as described above). It is an out-of-tree
kernel module and stays pending with `v4l2loopback` under the kernel-module
policy gate in the uvg266 section.

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

For VMware guests, `open-vm-tools-desktop` is an unconditional subpackage of
`open-vm-tools`; import the source family once. Its CAB library `libmspack`
is already a factory recipe (#846, published); do not import a second copy. Its
`pkgconfig(libmspack)` BuildRequires gives the build graph the ordering edge; no
manual stage is needed. The guest-tools recipe also BuildRequires
`xmlsec1-openssl-devel`, `pkgconfig(libtirpc)`, `rpcgen`, `procps-devel` and
`pkgconfig(gtkmm-4.0)`. None needs a recipe here: Hummingbird provides
`xmlsec1-openssl-devel`, `libtirpc-devel` and `procps-ng-devel` (which provides
`procps-devel` and `pkgconfig(libproc2)`), Fedora 44 provides `rpcgen` (not
in Hummingbird), and the factory provides `gtkmm4.0-devel`. Published `quota`,
`nfs-utils`, `oath-toolkit` and `igt-gpu-tools` already build against the same
providers. Check a new BuildRequires against both repositories' primary
metadata before importing a provider. The main recipe explicitly requires
`xmlsec1-openssl`; match that provider in Hummingbird rather than importing a
duplicate XML security library.

The imported guest-tools recipe has no `%check`: its comment explains that
`make check` regenerates a documentation font. Record that inherited limitation;
do not describe configuration tests as guest integration tests. Runtime
acceptance needs an actual VMware guest: verify `vmtoolsd`, query
`vmware-toolbox-cmd stat hosttime`, and exercise desktop resizing and clipboard
transfer. A version command on a generic runner cannot establish host/guest
integration. Recipe catalog closure does not establish those results or
publication.

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

`braille-printer-app` is a separate source from `liblouisutdml`: its current
recipe installs classic CUPS filters and drivers, not a standalone printer
application. Its required utilities include `liblouisutdml-utils`, CUPS
filters, ImageMagick, poppler-utils and unzip. Check the complete runtime
transaction and an actual Braille print path before claiming functionality;
the imported recipe and source pin alone do not establish either.

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
The same SSSD source also builds `sssd-client`, `sssd-common`, `sssd-kcm`,
`sssd-krb5-common` and `sssd-nfs-idmap` for #490. Those names were swept from
`already_recipe` into `[resolved]` with the recipe PR (`pr = 848`), not by a
second import. That record is recipe accounting only and does not complete
#490: hosted build, publication and runtime proof are still owed. Runtime
resolution is unproven: `sssd-common` requires `libldb` and `sssd-krb5-common`
requires `cyrus-sasl-gssapi`, and neither is checked against Hummingbird plus
the factory yet.

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
`python3-pskc`, the `jaraco` libraries and `python3-keyring` (with
`secretstorage`/`jeepney`) already have recipes in `[resolved]`.
`python3-fido2`'s recipe landed in #949 as recipe coverage only (moved to
`[resolved]`); its hosted build, publication and runtime proof remain
outstanding on #489. The `yubikey-manager` recipe landed in #839 as recipe
coverage only (both names moved to `[resolved]`). A later successful hosted build and publication
covered both outputs; runtime dependency resolution and device validation
remain separate on #479. Record the observed run and binary identities in the
catalog, and recheck the current image before making publication claims:
merging a recipe and publishing its next factory run are separate events.

For the VPN/YubiKey outputs in #479, `stoken-libs` is the `libs` subpackage
from the `stoken` source recipe, while `yubikey-manager` produces both the
command-line tool and `python3-yubikey-manager`. Verify each binary by name in
published primary metadata; do not infer publication from the source recipe
or count a subpackage as a separate source import.

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

Qt 6 submodule specs (`qt6-qtdeclarative`, `qt6-qttranslations`,
`qt6-qtwayland`) define `%global majmin %(echo %{version} | cut -d. -f1-2)` and
expand `%{majmin}` inside `Source0`,
which `bootstrap_upstream_sources.py` reports as `needs explicit mapping`
without `rpmspec`; write the resolved `https://download.qt.io/official_releases/qt/...`
entry and Fedora lookaside `fallback_urls` directly in
`config/upstream-sources.json`. Pass `--ref <commit>` to
`tools/import_rawhide.py` for the `rawhide` ancestor matching the intended
Qt family. The imported recipes use 6.11.2; do not infer the buildroot's
selected version from that source pin or an old Hummingbird snapshot.

Qt private libraries use `Qt_6.<minor>_PRIVATE_API` symbol versions. Hummingbird
can retain several QtBase versions with incompatible private symbols. The
factory's downstream specs therefore require `qt6-qtbase-devel`, its private
and static companions where used, the Qt RPM macros, and the other Qt build
tools/modules at `= %{version}`. Keep those constraints together when updating
the family. The generated buildroot in `tools/mock_config.py` excludes Fedora's
`qt6-qtbase` and prefers Hummingbird; a digest-pinned bootstrap image does not
freeze the remote RPM repositories used to solve BuildRequires. An unavailable
matching dependency must fail resolution rather than silently select a newer
Qt minor. The declarative and Wayland runtime requirements derived from
`%{_qt6_version}` must correspond to that selected QtBase.

Before claiming compatibility, inspect each package's hermetic
`buildroot_lock.json` for the resolved Qt NEVRAs, then verify the emitted RPMs
in a Hummingbird-plus-factory install transaction, including
`qt6-qtwayland-adwaita-decoration`. Record the factory digest and current
Hummingbird metadata checksums per [repo inspection](../repo-inspection.md).
A green inventory check or Canary with skipped builds supplies neither proof;
keep all four `[areas.unblockers]` names and its assigned `consumer_issue`
until the review's build and runtime acceptance requirements are met.
`qt6-qtwayland.spec` ships the decoration via `%package adwaita-decoration`
(not the standalone `qadwaitadecorations` package).
