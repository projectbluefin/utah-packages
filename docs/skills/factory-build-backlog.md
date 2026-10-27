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
| `reports/factory-build-backlog.json` | Committed snapshot; live totals (backlog / pending / already_recipe / manifest_wants / resolved / wontfix) — regenerate with a plain run of the auditor |
| `Justfile` `factory-build-backlog` recipe | Runs `--check` against the working tree (wired into `check` so every PR that drifts the report fails before merge) |

The snapshot is deterministic: the report carries no wall-clock field, so a
run that changes nothing rewrites the file byte-for-byte and leaves the tree
clean.

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

Use the consumer issue named by the batch assignment when the area's
`consumer_issue` is stale. Check the consumer's triage for each binary:
`planned` records intent, while `untriaged` is not a waiver. For existing
outputs, inspect current published repodata by binary name and its source
RPM before importing a second recipe.

The `Import Rawhide package` workflow does **not** make this move: its pull
request carries the recipe, lock, `.packit.yaml` and counts, but leaves the
name in its area. Before merging one, add the `[resolved]` entry (with that
PR's number) and rerun the auditor, or `--check` reports `entries drift` on
`main`. Two such PRs open at once also conflict on the lock's last entry and
the `docs/architecture.md` counts: merge `main` into the second, keep both lock
entries, and regenerate the counts (`tools/render_packit_config.py --write`,
`tools/render_architecture_counts.py --write`).

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

### Virtual machine guest integration

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
when the summary describes partial progress.

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
tree (`extract_usbip.sh`), so it remains `pending` on kernel policy (#487).

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
Yubico C releases (`libyubikey`, `ykclient`, `ykpers`) still declare `http://opensource.yubico.com/...` `Source0` URLs in Fedora Rawhide, and `libyubikey` and `ykclient` still carry legacy MD5 `sources` lines: repin `sources` to `SHA512 (<file>) = <hex>`, lock `https://opensource.yubico.com/...` as the primary `url`, and pair `https://developers.yubico.com/<project>/Releases/<file>` with Fedora's `/md5/<md5>/` lookaside path in `fallback_urls`. `ykpers` builds and links against `libyubikey` (`libyubikey.so.0`), so import `libyubikey` in the same PR. When a recipe carries a committed OpenPGP keyring whose filename does not match `*key*.asc`, `*keyring*.asc`, or `[0-9A-F]*.asc` (`packages/pkcs11-provider/simo_redhat.asc`, `packages/bc/kevin_pizzini.asc`), unignore it explicitly in the root `.gitignore` (`!packages/<pkg>/<name>.asc`) so `git add` tracks `SourceN` for `%{openpgpverify}`. By contrast, `yubikey-manager` (`python3-yubikey-manager`) is a `pyproject` package whose `[project].dependencies` generate runtime `python3dist(...)` `Requires` across multiple backlog areas (`python3-click`, `python3-fido2`, `python3-keyring` plus `secretstorage`/`jeepney`/`jaraco` in `dev-tools`, and `python3-pyscard`, `python3-pskc` in `long-tail`); keep `yubikey-manager` and `python3-yubikey-manager` pending until those Python runtime providers land in the factory.
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

### ifuse dependencies and device test

The `ifuse` recipe builds against the existing `libimobiledevice`,
`libimobiledevice-glue`, and `libplist` recipes and needs `usbmuxd` at
runtime. An imported recipe alone does not prove a device can be mounted;
verify the published package and its runtime dependencies on a real device.
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

## Diagnosing drift

- `--check` compares the whole live report with the committed snapshot —
  totals, states, the per-area rollup and every entry — so a name moving
  between areas fails the gate even though the counts are unchanged.
- When a rebase conflicts in `reports/factory-build-backlog.json`, resolve the
  catalog changes first, then run `python3 tools/factory_build_backlog.py` to
  regenerate the snapshot from the merged inventory. Do not choose one side's
  generated totals: that can discard resolutions or recipe imports from the
  other branch. Stage the regenerated report before continuing the rebase.
  If the catalog conflict is two independent additions to `[resolved]`, keep
  both sets of records; neither supersedes the other. Preserve unrelated skill
  sections added on `main` when the reconciliation guidance conflicts too.
- A `pending` count that grows means a name was added to the catalog
  without a recipe; re-run `tools/factory_build_backlog.py` and inspect
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

After a recipe PR lands, regenerate `reports/factory-build-backlog.json`; the inventory-driven gate deliberately rejects a snapshot made before that import. Refresh it together with recipe and Packit inventory changes when preparing concurrent PRs. If a rebase conflicts in this generated report, resolve the catalog and recipe inputs first, then run `python3 tools/factory_build_backlog.py`; choosing either report wholesale can discard the other branch’s backlog updates.

After combining recipe inventories during a rebase, also rerun `python3 tools/render_packit_config.py --write` and `python3 tools/render_architecture_counts.py --write` before `just check` to reconcile derived package lists and counts.
After a recipe PR lands, regenerate `reports/factory-build-backlog.json`; the inventory-driven gate deliberately rejects a snapshot made before that import. Refresh it together with recipe and Packit inventory changes when preparing concurrent PRs.

When concurrent disposition PRs conflict during rebase, retain each distinct
`[resolved]` and `[wontfix]` record in the catalog, then regenerate the report
with `python3 tools/factory_build_backlog.py`. Do not choose one side of the
generated JSON: it must reflect both sets of catalog changes. Verify the result
with `python3 tools/factory_build_backlog.py --check` before continuing the rebase.

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
reconciling a published batch. Record any known newer failed rebuilds by package
name and run in the catalog comments so publication evidence does not hide
current build health.

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
When rebasing a recipe PR, resolve conflicts in this generated report by rerunning
`python3 tools/factory_build_backlog.py` against the combined inventory, then
verify with `--check`; choosing either side can discard another import’s state.

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
