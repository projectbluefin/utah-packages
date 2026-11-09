## QR-code library source recovery

`qrencode-libs` is an unconditional binary subpackage of `qrencode`, alongside
the command and development files; import the source recipe once. Its old
`fukuchi.org` release URL returns HTTP 404, but Fedora's lookaside preserves
the original `qrencode-4.1.1.tar.bz2` matching the recipe's SHA-512. Keep the
HTTPS upstream URL as primary and the checksum-addressed lookaside URL in
`fallback_urls`; an unavailable primary does not require a Fedora-primary
ratchet exception. Preserve the recipe's `%check`, which runs the upstream
library tests independently of the optional SDL viewer.

The [maintainer decision on #506](https://github.com/projectbluefin/utah-packages/issues/506#issuecomment-6741419743)
authorizes this source recovery only. `python3-perf` remains tied to the
kernel-tools decision on #487, and the Qt5 outputs remain pending a product
decision; do not move them into `[wontfix]` as part of the library import.
Recipe accounting does not establish hosted build, publication or runtime
acceptance. After publication, install from Hummingbird plus the factory and
exercise `qrencode -t PNG -o qr.png 'Utah'`; record the binary identity and
result separately from source verification.

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
[`repeated-mistakes.md` section 17](../repeated-mistakes.md#17-cups-2x-and-cups-filters-2x-package-split)), and moving it to
`[wontfix]` needs a linked maintainer decision. `lrzsz` is a hand import:
Fedora pins it by MD5, so confirm the `https://www.ohse.de/` bytes match that
pin, repin `sources` to SHA-512, and use the `/md5/<md5>/` lookaside path as
the fallback. `liburing` locks only `Source0`; like `dnsmasq`, its `.asc`
signature is fetched from Fedora's lookaside by its `sources` SHA-512.

`libreport-filesystem` is the directory-only subpackage of `libreport`, not
a separate source recipe. The full source build needs `satyr-devel`; import
`satyr` as well and let BuildRequires order the builds. A recipe registration
does not prove either package was built or published: verify the filesystem
RPM and its directory ownership in the hosted build and an installation using
the permitted repositories. `mdadm` deliberately disables its optional ABRT
hook; importing the directories does not re-enable that hook.

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
a catalog record does not prove the build succeeds. `LCEVCdec`, `davs2-libs`
and the default-disabled `gstreamer1-plugins-good-qt6` stay pending in
`[areas.codecs-media]`, so `#474` stays open. For the Qt sink, inspect the
hosted buildroot's Qt NEVRAs and the resulting RPMs before enabling the
default; verify publication and `qml6sink` at runtime separately.

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

## Checkpoint/restore package family

`criu` and `criu-libs` come from one `criu` source recipe (`%package libs`);
the same spec also builds `criu-devel`, the amdgpu and CUDA plugins,
`python3-criu`, `crit` and `criu-ns`. Recipe coverage does not establish that
the build, publication or a checkpoint/restore round trip works. Runtime
verification needs a privileged environment (`CAP_SYS_ADMIN`/`CAP_CHECKPOINT_RESTORE`):
checkpoint and restore a simple process; `criu check` alone does not exercise it.

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

## davs2 AVS2 decoder library

Fedora dist-git has no `davs2`, so `davs2-libs` comes from the negativo17
recipe imported with `tools/import_rawhide.py --branch master
--remote-template 'https://github.com/negativo17/{package}.git' davs2`; the
provenance keeps the `master` branch, commit and tree. The recipe builds
`davs2` (CLI), `davs2-libs` (`libdavs2.so.16`) and `davs2-devel`; do not add a
second recipe under the binary name. negativo17 carries no `sources` file, so
the pinned upstream commit archive is locked only in
`config/upstream-sources.json`. Recipe coverage does not establish a hosted
build, publication or a representative AVS2 decode. `LCEVCdec` is still
pending: the negativo17 recipe needs `CLI11`, `range-v3`, `plutovg-devel` and
`libavdevice` build prerequisites that have no recipe here yet.
