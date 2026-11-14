## Diagnosing drift

- There is no committed snapshot to drift from. `--check` fails only on a
  broken catalog contract (a repeat, an overlap, names that do not hash to
  the audit digest) or a backlog recipe without a source lock; totals moving
  with an import is expected and never a failure.
- When a rebase conflicts in `config/factory-build-backlog.toml`, resolve the
  catalog and recipe changes against current `main`, then verify with
  `just factory-build-backlog`. Do not choose one side's catalog wholesale:
  that can discard resolutions or recipe imports from the other branch.
  If the catalog conflict is two independent additions to `[resolved]`, keep
  both sets of records; neither supersedes the other. Preserve unrelated skill
  sections added on `main` when the reconciliation guidance conflicts too.
  If an older commit edits the former monolithic skill, retain the split
  index from `main` and move only the incoming guidance to its owning file.
  Check the pre-rebase PR diff for documentation moved by earlier merge
  resolutions: a linear rebase does not replay those merge commits.
- A `pending` count that grows means a name was added to the catalog
  without a recipe; run `just factory-build-backlog` for the per-area
  summary, or add `--output <path>` to `python3 tools/factory_build_backlog.py`
  for every entry.
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
  `gstreamer1-plugins-good-qt6` is `pending`: its `%package qt6` is guarded
  by `%if %{with qt6}` and the default is `%bcond_with qt6`. Keep it disabled
  until matching Qt declarative and Wayland prerequisites are published and a
  hosted `--with qt6` build verifies the dependency closure. Enabling it
  prematurely can prevent the entire parent package from building.
  `packages/ffmpeg/`
  declares its `libav*` subpackages under `%if ! %{with freeworld_lavc}`,
  which is true by default, so those are `already_recipe`. An
  `already_recipe` name still listed under an area is not done until a batch
  moves it to `[resolved]` with the recipe's PR (ffmpeg's split `libav*` and
  `libsw*` rows cite `pr = 70`). Conditions the
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

After a recipe PR lands, nothing backlog-related needs regenerating: the
auditor recomputes every state from the tree. When preparing concurrent PRs,
combine current `main` and PR catalog, recipe, and source-lock changes first,
then run `just regenerate-inventory` before `just check`, even if
`.packit.yaml` itself had no conflict.

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
`[resolved]` and `[wontfix]` record in the catalog, then verify with
`just factory-build-backlog` before continuing the rebase.

### Dev-tools Python recipes that import but do not build

A clean Rawhide import is not a build. The first factory run after the #489
imports (run 42397089583) failed six of them, each on a build-root
difference rather than a code bug. Read the `check-s<N>-<package>` artifact's
`build.log` (or the job log for a lock-resolve failure) before changing a
recipe:

| Recipe | Failure | Fix |
| --- | --- | --- |
| `python-SecretStorage`, `python-keyring` | `%check` runs `xwfb-run`, which finds no `weston` | `BuildRequires: weston`, as `libayatana-ido` and `libglvnd` already do |
| `python-regex` | Rawhide's spec has `%autochangelog` with no `%changelog` header, so its entries are read as `%files` paths | Add the `%changelog` line |
| `python-dns` | Hummingbird's idna 3.20 dropped UTS #46 transitional mapping; two upstream tests assert it | Backport the test-only part of dnspython `6af77d7e` as a patch |
| `python-rapidfuzz` | 3.14.6 wants rapidfuzz-cpp 3.3.4; Fedora 44 supplies 3.3.3 and CMake falls back to the deleted `extern/` copy | Import Rawhide's `rapidfuzz-cpp` 3.3.4 recipe |
| `python-more-itertools` | 11.2.1 asks for `flit_core >=4`; the build root has 3.12.0 (Rawhide moved flit-core 4 to a separate `python-flit-core` source) | Relax the floor in `%prep`; 3.12 builds byte-identical modules |

Do not import `python-flit-core` 4 to satisfy one recipe: the factory repo
would then hand flit-core 4 to every Python build, including the ones whose
`pyproject.toml` caps it below 4.

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
recipe-import `pr` fields when adding this evidence; publication fields do
not change any auditor state. Record any known newer
failed rebuilds by package name and run in the catalog comments so publication
evidence does not hide current build health.

Read both from one image: `python3 tools/package_index.py --image
projectbluefin/utah-packages:latest --output <file>` writes the manifest
digest, publishing `run` and source `revision` under `image`. Its `packages`
are grouped by source, with binary names and architectures in each entry's
`rpms` list. For an exact binary NEVRA, read the binary's own primary metadata
entry instead of assuming the source entry's version or epoch applies to every
subpackage. Check that `revision` is on the target branch before citing it. The primary
metadata checksum is in `repository/repodata/repomd.xml` inside the image's
first layer (`fetch_image` in the same tool returns it). An import PR that
left its name `already_recipe` pending evidence (`tslib`, #643) moves to
`[resolved]` in a later reconciliation PR once that image carries the binary;
cite the original import PR and merge commit rather than the reconciliation.

The same image's `org.projectbluefin.factory.state` label names the sources
whose latest attempt failed at their current input digest (`failed`); their
published RPMs are older retained builds. Check every source you cite against
it and compare each binary's primary `buildtime`. In the #488 reconciliation
`mtr`, `ntfs-3g-system-compression` and `open-vm-tools` were in `failed`, so
the catalog comment records that their publication evidence is a retained
build, not current build health.
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
`just factory-build-backlog`.

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

### Broadcom firmware extraction tool and open firmware

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

`b43-openfwwf` is the open firmware for the 4306, 4311 (rev 1), 4318 and 4320
chips. Its upstream host `netweb.ing.unibs.it` serves the 2009 release only over
plain HTTP, which `tools/validate.py` rejects in the source lock. The lock's
primary URL is the Internet Archive capture of that exact upstream URL
(`web/20231025104009id_/`, the raw-bytes form), with Fedora's SHA-512 lookaside
path as the fallback; both served bytes matching Fedora's `sources` pin. Do not
relabel the lookaside as primary: an upstream release exists. The recipe
assembles the firmware with `b43-asm` from `b43-tools`, which the Fedora half
of the build root supplies, so it is a BuildRequires only and needs no factory
recipe. For runtime acceptance, install it from Hummingbird plus the factory,
confirm `/lib/firmware/b43-open/ucode5.fw` and the `modprobe.d` options file
are present, and load `b43` with `fwpostfix=-open` on a supported adapter.
Without that hardware, record file presence only; it is not driver proof.

### Fedora-only catalog and branding outputs

Two long-tail names have no upstream outside Fedora and conflict with Utah's
own choices, so neither is importable without a maintainer decision:

- `appstream-data` packages Fedora's weekly catalog of Fedora repository
  applications, built by Fedora infrastructure and downloaded from
  `dl.fedoraproject.org`; Fedora is its only source. It feeds RPM software
  centres (`gnome-software`, PackageKit), while Utah excludes
  `gnome-software` and ships the Flatpak store Bazaar.
- `desktop-backgrounds-gnome` is a subpackage of Fedora's `desktop-backgrounds`
  source. It sets the Fedora release wallpaper as the GNOME default and
  requires `fNN-backgrounds-gnome`; its other archives are MD5-pinned,
  lookaside-only tarballs. Utah's desktop contract pins Bluefin's wallpaper.

Keep both pending until a maintainer records a `[wontfix]` decision or an
accepted use case; do not import them merely to satisfy parity.

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

Some batch names can never appear in published metadata. `libbasicobjects`
(#501) is retired upstream: `ding-libs` 0.7.0 folds it into `libini_config`
through `Obsoletes: libbasicobjects <= 0.1.1`, so no RPM carries the name.
Record it as resolved by the import, cite the `Obsoletes:` line and the
replacement's published NEVRA, and do not fill `published_nevra` with
another binary's identity. Also check each record's `pr` before adding
publication fields: a closed proposal (`iptstate` #697, `libXres` #646)
should point at the merged adoption PR (#714, #690) instead. A recipe merged
after the image's `revision` (`intel-vaapi-driver`, #953) stays without
publication fields even when its sibling batch outputs are present.

When rebasing an import over other backlog changes, retain the base branch's
publication evidence and add only the new recipe's closing record. Run
`just regenerate-inventory` after combining the catalog and recipe inputs
with current `main`; neither side's old `.packit.yaml` describes the combined
inventory.

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
name-only classification; rerun `just factory-build-backlog` anyway and expect
unchanged totals when no names or recipe classifications changed. Publication still does not prove password
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
When reconciling `slang`, check the library binary itself in published
primary metadata: the separately packaged interpreter is not proof that the
audited library was published. Publication does not prove that the library
resolves against the permitted repositories or can be loaded at runtime.

### Solaar and sos imports

`solaar-udev` is the udev-rules subpackage of the `solaar` source recipe;
import `solaar`, not a separate recipe for the rules. Both `solaar` and `sos`
lock their GitHub tag archives directly: those bytes equal the dist-git
SHA-512 pins. Their Python BuildRequires (including `%pyproject_buildrequires`
extras such as `hid-parser`) come from the Fedora 44 half of the build root;
that is not proof the runtime `Requires` resolve on Hummingbird plus the
factory. Verify the udev rules file and `sos report --help` against the
permitted repositories before claiming runtime acceptance.

`uavs3d-libs` is the `%package libs` subpackage of the negativo17 `uavs3d`
recipe imported for issue #507. It has no Fedora dist-git recipe (`rpms/
uavs3d` does not exist), so it was imported from that source recipe rather
than via `tools/import_rawhide.py`, and it is source-locked in
`config/upstream-sources.json`. negativo17's `uavs3d-devel` required the
`uavs3dec` CLI package; the factory points it at `uavs3d-libs`, which owns
`libuavs3d.so.1`, matching `davs2` and `xeve` (issue #935). Keep that on a
re-import. Hosted build, publication and runtime proof remain outstanding on
#507. `shim-ia32` is a Secure Boot-signed bootloader binary and still needs an
explicit maintainer decision before any recipe work.

### NILFS utilities signature sources

For `nilfs-utils`, the release archive and detached signature are separate
`Source` entries. Verify both against `sources` and the bundled signing key;
the source pipeline stages the signature from the digest-addressed lookaside.
The catalog records the recipe import, not proof of installation or publication.
