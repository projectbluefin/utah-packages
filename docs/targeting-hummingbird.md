# Targeting Hummingbird

This page exists because the same questions kept being re-derived from
repository metadata instead of read. It records what "build targeting
Hummingbird" means concretely, and what is verified fact versus still open.

## What this factory forks

We fork **Fedora Rawhide's RPM recipes**, not Fedora's binary packages.

| input | source | role |
| --- | --- | --- |
| spec + patches | Fedora dist-git `rawhide` branch | bootstrap recipe, pinned by commit and tree in `.hummingbird-upstream.json` |
| source archive | the project's own upstream release | the only payload allowed into a build, SHA-512 locked |
| build root | see below | supplies compiler, macros, BuildRequires |

Rawhide is never a source of package payloads and never a repository a
consumer image enables. It is a recipe donor and a bootstrap build root.

We track **the latest upstream release**, not whatever Fedora happens to have
tagged. That is the point of the direct-source pipeline: Fedora can lag
upstream, and a spec is a build recipe, not a release feed.

## What "targeting Hummingbird" means

Hummingbird is not a Fedora release. It is an overlay of rebuilt packages on
top of a Fedora release, with its own disttag and ABI.

Verified against `packages.redhat.com/api/pulp-content/public-hummingbird/x86_64/`
and the `bootc-os` image on 2026-08-29:

- **Disttag `hum1`** — uniform across all 18,458 published subpackages.
- **Release convention `.N` immediately before `%{?dist}`**, so a Hummingbird
  rebuild sorts above the Fedora build it derives from and below the next
  upstream version. `Release: 3%{?dist}` becomes `Release: 3.1%{?dist}`.
  Seen in practice: `openssl-libs-3.5.6-0.1.hum1`, `glibc-2.42-11.1.hum1`,
  `bootupd-0.2.36-3.hum1`.
- **3,510 packages, base OS only.** It carries openssl, glibc, python3, bootc.
  It carries **no desktop stack at all** — no gnome-shell, mutter, gtk4,
  libadwaita, not even pipewire. Every desktop package is a gap by definition.
- **Paired with Fedora 44.** `images/variables.yml` in
  `redhat/hummingbird/containers` maps `default_variant_repos.rawhide` to
  `fedora-44.repo`. Hummingbird's "rawhide" distro variant is pinned to
  Fedora 44; it does not follow the rolling Rawhide.
- **Builder image** `quay.io/hummingbird-ci/hummingbird-builder:latest`.

### The ABI that matters

| | Hummingbird | Fedora 44 | Rawhide (46) |
| --- | --- | --- | --- |
| openssl | 3.5.6 (`libcrypto.so.3`) | 3.5.5 (`libcrypto.so.3`) | **4.0.1 (`libcrypto.so.4`)** |
| glibc | 2.42 | 2.43 | 2.44.9000 |
| python3 | 3.14 | 3.14 | **3.15** |

This is not academic. An RPM built in a Rawhide root can acquire dependencies
that Hummingbird cannot satisfy. A worked example: `gnome-shell` built on
Rawhide pulls in `pipewire-libs`, which there requires `libcrypto.so.4`.
Hummingbird provides `libcrypto.so.3`. The package installs nowhere.

**A package is ported only when its whole dependency closure resolves on
Hummingbird** — not when it merely compiles.

## The build root, per Hummingbird's own documentation

Hummingbird builds in **mock hermetic mode** (network-isolated, dependencies
pre-fetched). Its `mock/mock.cfg` composes the root from the `[fedora]` and
`[fedora-updates]` repositories of a pinned Fedora release, with Hummingbird's
own Pulp repositories shadowing them by priority. Their rebase runbook warns
that if "Hummingbird's own Pulp repos still serve the _old_ toolchain at a
higher priority than the new Fedora repos during the transition window, this
becomes a real chicken-and-egg problem" -- priority ordering is load-bearing.

A rebase rebuilds the core toolchain in strict order: glibc, gcc, llvm,
annobin, libtool.

This factory mirrors that composition: Fedora 44 plus `public-hummingbird` at
higher priority. Measured in the build itself, that root reports

```
buildroot openssl: 3.5.7-2.fc44          -> libcrypto.so.3, matching Hummingbird
177 packages from public-hummingbird-x86_64-rpms
python3-3.14.7-1.hum1                    -> not Rawhide's 3.15
gio-2.0 2.89.3, graphene 1.10.8, pixman 0.46.2
```

Each build prints its root's `openssl-libs`, so the ABI a package compiled
against is visible in the log rather than assumed. That check is what caught
the Rawhide root producing packages needing `libcrypto.so.4`.

## Build order is part of the port

Several ported packages BuildRequire each other, so a flat parallel matrix
cannot build them:

```
mutter       needs gsettings-desktop-schemas >= 51.alpha   (found 50.1)
gnome-shell  needs mutter-devel >= 51~alpha                (no match)
gtk4, mutter needs wayland-protocols >= 1.48
libadwaita, gnome-control-center  need gtk4 >= 4.23.x
```

Builds therefore run in stages, each stage publishing its RPMs into a local
repository the next stage resolves against:

| stage | packages |
| --- | --- |
| 0 | everything with no in-set dependency, plus `wayland-protocols`, `accountsservice`, `gsettings-desktop-schemas` |
| 1 | `gtk4` |
| 2 | `libadwaita`, `mutter`, `gnome-desktop3` |
| 3 | `gnome-shell`, `gnome-session`, `gnome-settings-daemon`, `xdg-desktop-portal-gnome`, `malcontent-bootstrap` |
| 4 | `malcontent`, `gnome-control-center` |

`malcontent` is in the set for a reason worth recording, because it is the
first package pulled in by an ABI break rather than by a version floor.
`accountsservice` 26.27.3 bumped its library soname from
`libaccountsservice.so.0` to `.so.1`. Fedora 44's `malcontent-libs` is built
against `.so.0`, so once the Fedora build of accountsservice is excluded in
favour of ours, nothing provides what malcontent needs:

```
package malcontent-libs-0.14.0-1.fc44 from fedora requires
  libaccountsservice.so.0, but none of the providers can be installed
package accountsservice-libs-23.13.9-16.fc44 from fedora is filtered out
  by exclude filtering
```

Fedora has already made this transition: Rawhide ships the same malcontent
0.14.0 at release 7, rebuilt against accountsservice 26. So this is a rebuild,
not a version bump -- exactly the case the `.N` convention exists for.

Rebuilding it is not enough on its own, though, because malcontent transitively
BuildRequires itself:

```
package flatpak-libs-1.18.1-1.fc44 from updates requires
  libmalcontent-0.so.0, but none of the providers can be installed
```

`malcontent` BuildRequires `pkgconfig(flatpak)`; `flatpak-devel` needs
`flatpak-libs`; and `flatpak-libs` needs `libmalcontent-0.so.0`, which only
malcontent provides. In Fedora that closes, because Fedora's own
`malcontent-libs` installs. Here it cannot, for the soname reason above -- so
neither malcontent nor `gnome-control-center` could resolve a buildroot at all.

It breaks the way upstream intended. `flatpak` appears exactly once in
malcontent's build, in `libmalcontent-ui/meson.build`, which meson enters only
under `if get_option('ui').enabled()`; upstream separates the two deliberately
and ships a `use_system_libmalcontent` option described in `meson_options.txt`
as "used in distros to break a dependency cycle". So `malcontent-bootstrap`
builds the same sources with `-Dui=disabled` at stage 3, needing no flatpak,
and produces a `malcontent-libs` linked against accountsservice 26. At stage 4
that is in `[stages]`, `flatpak-libs` resolves against it, and the full
malcontent and `gnome-control-center` both build.

The bootstrap's release is `0.bootstrap`, which sorts below the real `1.hum1.bfin`:
at stage 4 it is the only malcontent available and so is used, and anywhere both
exist the full build wins on version. `publish` deletes it regardless, since a
malcontent with no parental controls UI should not reach anyone's system.

This is the same shape as Hummingbird's toolchain ordering, one layer up.

## How the packages are published

The repository is published twice, and only one of them is meant to be consumed.

**As an OCI image**, `ghcr.io/<owner>/utah-packages`, which is what images
should use. That is how everything else in this ecosystem ships build output --
Utah own Containerfile already pulls `projectbluefin/common` and `ublue-os/brew`
exactly this way, pinned by digest:

```dockerfile
FROM ghcr.io/hanthor/utah-packages@sha256:... AS packages
COPY --from=packages /repository /etc/utah-packages
```

A registry beats a Pages site on three counts, and the third is the one that was
actually blocking:

- it works from any branch, so an image can be built against a package set
  before either of them is merged;
- it is addressable by digest, so an image records exactly which packages went
  into it rather than whatever the site happened to be serving;
- provenance is a signature over that digest rather than an unsigned directory
  of RPMs served over HTTPS.

`main` publishes `:latest`. Every other ref publishes under its own branch name,
which is the point: GitHub Pages can only deploy from the default branch, so
until this existed nothing could be consumed until a merge had already happened,
and an image could never be tested against the packages it was meant to use.

**As a Pages site**, still, for anything that wants a plain HTTP repository.
That deploy is a separate job so the registry push does not inherit the
`github-pages` environment, which normally carries a deployment branch rule and
would have blocked the push on precisely the branches it exists to serve.

## Release numbering

Packages built here are tagged the way AlmaLinux tags its rebuilds: keep the
vendor release and dist, then append. Their `dnf` is `4.14.0-34.el9_8.alma.1`
against Red Hat's `34.el9_8`, and both `.alma` and `.alma.N` appear in their
repositories.

The vendor here is **Hummingbird**, not Fedora:

```
pango-1.58.2-1.hum1.bfin        built for Hummingbird, by this factory
pango-1.58.2-1.hum1.bfin.1      ... and rebuilt again against the same base
```

These packages are built for Hummingbird and installed on Hummingbird. Fedora 44
is the other half of the buildroot, the way a compiler is -- not what the output
targets. An earlier version of this tagged them `.fc44.bfin`, which named the
distribution they are not for.

`hum1` is read from the Hummingbird packages present in the buildroot rather than
hardcoded, so a move to `hum2` carries itself. A buildroot with none of them is a
repository misconfiguration -- the exact failure this factory exists to catch --
so the build stops rather than quietly tagging something else.

The `.N` counter is per package, as `"dist_bump": 1` beside the package's source
entry in `config/upstream-sources.json`. Most never need one; it is for when the
base we derive from has not moved but our own build of it has to.

Verified against rpm's ordering rather than assumed -- the comparison was
reimplemented from rpmvercmp's rules and every row checked, including the ones we
lose:

| ours | theirs | winner |
| --- | --- | --- |
| `1.hum1.bfin` | `1.fc44` | ours |
| `1.hum1.bfin` | `1.hum1` | ours |
| `1.hum1.bfin` | `1.hum1.bfin.1` | the `.1` rebuild |
| `1.hum1.bfin` | `2.fc44` | **theirs** |
| `1.hum1.bfin` | `2.hum1` | **theirs** |
| `2.hum1.bfin` | `2.hum1` | ours |

Losing to a `2.` release is the ordinary case of the thing we forked moving on.
The answer is to rebase the spec, which raises the leading segment. No disttag
can fix that one, because the leading segment comes from the spec.

Note what changed with the vendor tag. Under `.fc44.bfin` we *lost* to `.hum1` at
equal release, and that was being relied on to surface packages we should not be
building at all -- the remit is the desktop stack Hummingbird does not ship, so a
name in both sets is a mistake. `.hum1.bfin` outranks `.hum1`, which is correct
for an overlay but means ordering no longer reveals the overlap. So `precedence`
now reports it directly, as a note rather than a failure: it lists any name the
`public-hummingbird` repository also provides.

The gate itself is unchanged and still enforces the invariant the disttag only
approximates. `precedence` resolves every RPM the run produced against Fedora 44
and Hummingbird -- with our own output deliberately absent from the repository
set -- and fails if what they offer ranks at or above ours. A package that loses
still installs; dnf simply installs the other build, so the rebuild we went to
the trouble of making is never used and nothing says so. It passed on its first
run, over all 48 packages run 38 produced.

`malcontent-bootstrap` is exempt: its `0.bootstrap` release is meant to lose to
the real build, and `publish` deletes it.

## The bootstrap ladder

Restating it here because the ordering is what keeps getting lost:

1. A new gap is introduced using the **Rawhide build root** — its compiler,
   macros, and BuildRequires establish the first RPM.
2. That RPM is published to the factory's own repository.
3. **Subsequent builds use the factory repository** as the gap-filler for
   cross-package dependencies, so Rawhide supplies progressively less.
4. Consumer images enable the factory repository and Hummingbird. Never
   Rawhide.

Step 3 is what makes the Rawhide root safe: it is a scaffold that is meant to
be designed out, not a permanent dependency source. Bootstrapping in Rawhide
without ever doing step 3 leaves Rawhide's ABI baked into the output, which is
exactly the failure described above.

## Worked example: GNOME 51

Minimums were read from the GNOME 51 release tarballs' `meson.build`, not
inferred from what Rawhide happens to ship.

Already satisfied by Fedora 44 plus Hummingbird:

```
glib2 2.88.0 >= 2.86.0     gjs 1.88.0 >= 1.87.1     pipewire 1.6.2 >= 1.6.0
libei 1.5.0 >= 1.3.901     wayland 1.24.0 >= 1.24   libdrm 2.4.131 >= 2.4.118
graphene 1.10.8 >= 1.10.2  libinput 1.31.0          harfbuzz 12.3.2 >= 8.4.0
cairo 1.18.4 >= 1.18.2     meson 1.10.2 >= 1.8.0    libnm 1.56.0 >= 1.52.0
upower 1.91.1 >= 1.90.6    libdisplay-info 0.3.0    g-i 1.86.0 >= 1.84
```

Genuine gaps, which must themselves be built:

| package | available | GNOME 51 needs | required by |
| --- | --- | --- | --- |
| `gsettings-desktop-schemas` | 50.1 | >= 51.alpha | mutter |
| `accountsservice` | 23.13.9 | >= 26.27.3 | gnome-control-center |
| `pango` | 1.57.1 | >= 1.58.0 | gtk4 |
| `gnome-desktop3` | 44.5 | >= 51.alpha | gnome-control-center |

`wayland-protocols` was previously listed here as a gap at 1.47. That is no
longer true: Fedora 44 carries 1.49, the same version we fork, so gtk4's
`>= 1.48` resolves without us. We still build it, which costs nothing and
keeps it under this factory's control, but it is not what is blocking anything.

The `gnome-desktop3` row is the fourth and, so far, last of these. Fedora's
source package is `gnome-desktop3` even though what needs it is the
`gnome-desktop-4` pkg-config module, which is why searching for the latter finds
nothing to fork. Upstream has no 51.beta, so we build 51.alpha, which is exactly
what the requirement asks for.

Neither it nor the `pango` row was predicted from the meson files. Both were
found by a build failing -- pango at stage 1 on `No match for argument:
pkgconfig(pango) >= 1.58.0`, and gnome-desktop at stage 4 on

```
Dependency gnome-desktop-4 for host machine found: NO. Found 44.5 but need: '>= 51.alpha'
```

That is the expensive way to learn it, and note that `preflight` cannot catch
this class: the BuildRequires is `pkgconfig(gnome-desktop-4)` with no version, so
the buildroot resolves and only meson objects. A version floor that lives in
meson rather than in the spec is invisible until the build configures. The `preflight` job in
`rebuild-rpms.yml` now resolves every recipe's BuildRequires in the real build
root on each run, so the whole gap list arrives at once rather than one entry
per half-hour round. Its output is a worklist, not a gate: a later-stage
package requiring something an earlier stage has not built yet shows up there
too, and is not a gap.

Note that `glib2` is **not** a blocker. GNOME 51 asks for 2.86, not the 2.89
that Rawhide ships; assuming otherwise sent an earlier attempt down a dead end.

## What the factory declines to build

Three decisions worth reading rather than re-deriving, because each one looks
like an omission from the outside.

**ffmpeg and anaconda-webui are in scope.** Both entered the manifest to close
the consumer transaction -- `pipewire-libs-extra` links `libavcodec.so.62` and
Hummingbird ships no libav at all, and `anaconda-live` requires
`anaconda-webui` -- and both were flagged for a second opinion when they went
in, because Utah deliberately does not enable `fedora-multimedia` and because
ISO tooling is not the desktop runtime. Settled: build them. They are part of
the vanilla Fedora stack, and that is the bar, whether or not Utah ends up
installing with Anaconda. The recipes are Fedora's, so this builds
`ffmpeg-free` and `libavcodec-free` -- Fedora's own codec policy, not
RPMFusion's.

**cockpit is not, and anaconda-live leaves the runtime contract with it.**
Cockpit's own `test-auth` fails on `/auth/userpass-header-check` with

    GLib-FATAL-WARNING: g_hmac_new: GLib HMAC is disabled for FIPS compliance

which is not a property of the build container. Unpacking
`glib2-2.89.3-1.hum1` from Hummingbird's own repository and reading
`libglib-2.0.so.0.8903.0` shows that string present, `gnutls` absent from the
binary entirely, and no `fips_enabled` anywhere: the disablement is
unconditional, compiled in, and applies at runtime on every Hummingbird
system regardless of whether FIPS is actually enabled. Fedora's glib2 carries
`gnutls-hmac.patch` and routes `GHmac` through GnuTLS precisely so it keeps
working; Hummingbird builds without that backend, and the fallback is a stub
that warns and returns NULL.

`cockpit-ws` uses `GHmac` on its authentication path, so a cockpit built here
would install and fail to authenticate. Skipping the test would have shipped
exactly that. So `anaconda-live` joins `slitherer` in the `[unavailable]` list
in `config/runtime-contract.toml` -- it pulls `anaconda-webui`, which pulls
four cockpit subpackages -- and `cockpit`, `python-bugzilla` and `firefox`,
which entered the manifest only to serve that chain, come back out. Utah
installs through the bootc-installer live path, which is what the `slitherer`
exception already said.

The factory still builds `anaconda-webui`, as a vanilla Fedora package. The
exception says only that Utah's runtime does not install it.

**This is a finding against Hummingbird, not a decision about it.** Every
`GHmac` consumer on that platform is affected, not just cockpit: libsoup's
digest authentication, evolution-data-server, gvfs and gnome-online-accounts
all reach for it. It is worth reporting upstream, with the binary evidence
above, and revisiting here the moment Hummingbird's glib2 gains a working
backend.

**libbluray is not.** Rawhide dist-git has moved to 1.5.0, which is
`libbluray.so.4`, while the composed repository the build root resolves
against still ships 1.4.0 and everything in it -- Fedora's own
`libavformat-free` included -- links `so.3`. Building 1.5.0 excludes Fedora's
1.4.0 by name, which is how the factory keeps Fedora from answering for what
it rebuilds, and then nothing provides `so.3`: `libavformat-free` becomes
uninstallable and takes every build root that wants it with it. The factory
cannot rebuild Fedora's compose ahead of Fedora. So gvfs sets `-Dbluray=false`
unconditionally where Fedora sets it only on RHEL, ffmpeg carries a
`libbluray` bcond defaulting off, and no entry exists. Blu-ray disc navigation
is not a feature a Utah machine has a drive for. This is not a version pin:
when rawhide's compose carries 1.5.0, `tools/track_upstream.py` proposes the
entry back, and it can be taken then.

**vapoursynth is not**, for a smaller reason: ffmpeg's spec build-requires it,
Hummingbird has no provider, and satisfying it would pull in zimg and a Python
extension to serve a `BuildRequires` whose output nothing in the runtime
contract links. It is a frameserver, not a codec. `%bcond vapoursynth 0`.

The general shape: where the factory and the Fedora compose disagree about a
soname, the factory declines the feature rather than getting ahead of the
compose it builds against. Adding the newer library is the move that strands
Fedora's own packages.

## Open, and deliberately not asserted

- **libgudev drops one upstream test, and the reason is not fully understood.**
  `test-gudevdevice` is the only one of its four tests that does not use
  umockdev; it builds a device out of environment variables and asserts that
  `udev_device_new_from_environment` accepts them. Against the systemd this
  factory targets that call returns NULL with EINVAL, so no tags come back and
  the assertion fails. What the test pins is therefore a libudev contract
  rather than libgudev behaviour -- `_g_udev_device_new` just propagates the
  NULL -- and libgudev's own behaviour stays covered by the three umockdev
  tests, which drive real devices and pass. Fedora does not hit this: rawhide
  pairs libgudev 238 with systemd 262~rc1 and carries no patches, while the
  build root here resolves Hummingbird's systemd 261.2. That difference has
  not been root-caused. The test is dropped by a downstream patch carrying the
  full reasoning, and this is the one place in the 237 where the factory ships
  a package whose upstream suite it does not run in full. Revisit when either
  systemd moves; the hardcoded `UDEV_DATABASE_VERSION 1` in the test looks
  worth reporting upstream regardless.

- **Step 3 of the ladder is implemented but only partly proven.**
  `rebuild-rpms.yml` now builds in a Fedora 44 container with Hummingbird's
  Pulp repository layered over it, and the job prints `buildroot openssl` as
  its own check: run 33243934353 reported `3.5.7-2.fc44`, which is
  `libcrypto.so.3` — Hummingbird's ABI, not Rawhide's `libcrypto.so.4`. What
  is not proven is that output linked against that root installs cleanly on a
  Hummingbird image; nothing has tested that yet.
- **Release numbering is settled.** See *Release numbering* above. Builds carry
  `.hum1.bfin` -- AlmaLinux's append-don't-replace convention, applied to the
  vendor these packages actually target -- and a `precedence` job enforces the
  invariant the disttag only approximates.

  This section previously claimed the disttag decided nothing, because "dnf
  priority does, and the factory repository sits above both Fedora and
  Hummingbird -- the disttag is provenance, not precedence." That was wrong, and
  this factory produced the counter-example. Priority did not stop Fedora's
  accountsservice being chosen over the 26.27.3 an earlier stage had just built,
  even with `[stages]` at priority 1; `excludepkgs` is what settled it. Priority
  expresses a preference between repositories that both offer an installable
  package. It is not a guarantee, so version ordering has to be right on its
  own, and the `precedence` job is what checks that it is.

  One consequence to keep in view: `1.hum1.bfin` outranks `1.hum1`, so a package
  we rebuild takes precedence over Hummingbird's own build of it. That is right
  for an overlay, but we should not be rebuilding base OS packages Hummingbird
  owns in the first place -- the desktop stack it does not ship is the whole
  remit -- so `precedence` reports any such overlap as a note.
- **GNOME 51 has not yet compiled end to end.** The Fedora 44 plus
  Hummingbird root is confirmed correct. Run 33243934353 built
  `gnome-session`, `gnome-settings-daemon` and `xdg-desktop-portal-gnome`,
  but that does not demonstrate staging: those three resolve entirely against
  Fedora 44. Staging was broken twice over, by the same kind of mistake in two
  places. The guard deciding whether to build the local `[stages]` repository
  used a non-recursive glob against a directory where `download-artifact` had
  nested the RPMs one level down, so it silently found nothing. Fixing that
  exposed the second: `rpmbuild --define "_rpmdir /work/result"` writes to
  `/work/result/<arch>/`, but the upload declared `work/result/*.rpm`, also
  non-recursive. Every artifact this workflow ever produced held only its JSON
  report -- pango built five RPMs and its artifact was 397 bytes.
  `if-no-files-found: error` could not catch it, because the artifact also
  carries `work/reports/*.json`, so one file always matched and the upload
  reported success while shipping nothing. Both globs now recurse and the build
  fails outright if it produced no RPM. The mechanism is still unproven until a
  later-stage package is observed consuming an earlier stage's output.

  That has now happened. Run 33246174021 resolved a stage 3 build against
  earlier stages, and the transaction table names the repository per package:

  ```
  gtk4                       x86_64 0:4.23.3-1.fc44       stages
  gtk4-devel                 x86_64 0:4.23.3-1.fc44       stages
  libadwaita                 x86_64 0:1.10~beta.1-1.fc44  stages
  gsettings-desktop-schemas  x86_64 0:51~beta-1.fc44      stages
  ```

  gtk4 4.23.3 and libadwaita 1.10.beta.1 are this factory's own builds; Fedora
  44 has 4.22.4 and 1.9.3. mutter 51.beta built against that gtk4, and
  gnome-control-center configured against both. Staging is demonstrated.
- **TunaOS Hummingbird (`repo.tunaos.org`) is a different, abandoned project.**
  It is not Red Hat Hummingbird and must not be used. Any leftover reference
  to it is a bug.
