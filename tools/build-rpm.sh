#!/usr/bin/env bash
# Shared by GitHub Actions and tools/build-package.sh. Runs inside the build container.
set -eo pipefail

phase=setup
started=$SECONDS
output_owner=$(stat -c '%u:%g' /work/result)
finish() {
  status=$?
  # Return bind-mounted outputs to the caller, including rootless Podman users.
  chown -R "$output_owner" /work/result /work/sccache || status=1
  printf 'phase=%s status=%s elapsed_seconds=%s\n' "$phase" "$status" "$((SECONDS-started))" >> /work/reports/build-timing.txt
  exit "$status"
}
trap finish EXIT
# Persist downloaded RPMs across local retries. Metadata still follows DNF expiry.
printf '\nkeepcache=True\n' >> /etc/dnf/dnf.conf

# The fedora:rawhide image ships fedora-cisco-openh264 enabled, but
# its packages are signed with Cisco key, which the image does not
# trust -- so any builddep graph reaching gstreamer/pipewire dies on
# "Import of the key did not help, wrong key?". openh264 is a runtime
# codec, never a build requirement, and Fedora own noopenh264 provides
# the same libopenh264.so.8 soname, so disabling the repo resolves.
disable=--disablerepo=fedora-cisco-openh264
# The Fedora container images set tsflags=nodocs, so every %doc file is
# dropped at install time. rand_core ships its crate docs that way and
# its lib.rs does #![doc = include_str!("../README.md")], so rust-just
# failed to compile: rustc could not read ../README.md. Nothing was wrong
# with the Fedora package: mock installs docs into a build root, and
# this container was not. Restore that.
sed -i "/^tsflags=nodocs/d" /etc/dnf/dnf.conf
# Fedora 44 plus Hummingbird, mirroring Hummingbird mock.cfg:
# Fedora release repos with its own Pulp repos shadowing them by
# priority. Proven correct by this job own diagnostic below --
# openssl 3.5.7 means libcrypto.so.3, the ABI Hummingbird has.
# A Rawhide root produced RPMs needing libcrypto.so.4 instead.
cp /repos/hummingbird.repo /etc/yum.repos.d/
# RPMs from earlier stages become a local repo, so a later stage
# can satisfy a BuildRequires on something this run just built.
# The guard must recurse: upload-artifact takes the common parent
# of its path globs as the artifact root, so an artifact declaring
# work/result/*.rpm and work/reports/*.json unpacks as
# prior/result/*.rpm, not prior/*.rpm. A non-recursive glob matched
# nothing, this block was silently skipped in every stage, and
# mutter resolved gsettings-desktop-schemas to Fedora 50.1 instead
# of the 51.beta stage 0 had just built. createrepo_c itself walks
# the tree, so only the test needed fixing.
if [ -n "$(find /work/prior -name "*.rpm" -print -quit 2>/dev/null)" ]; then
  dnf -y $disable install createrepo_c
  # The accumulator can carry a stale RPM linked against an ABI the
  # buildroot no longer offers -- a samba built against libicu 77
  # before the factory moved to 78, say. Left in [stages] it is
  # preferred by priority and drags the excluded ICU 77 back in,
  # so every buildroot that reaches libsmbclient fails to resolve.
  # A source build ships many subpackages that depend on each
  # other by exact NEVR, so dropping only the ICU-linked one
  # leaves its siblings with unmet private-library deps. Identify
  # the stale source packages by ICU 77 soname, then drop every
  # RPM built from those same sources; the current run rebuilds a
  # coherent replacement set with matching filenames.
  # The accumulator is shared across runs and refs and keeps
  # whatever any of them built, including packages the manifest
  # no longer promises. That is not merely stale: the exclusion
  # list below is derived from these very names, so a removed
  # entry goes on excluding the Fedora copy of itself and nothing
  # provides the capability any more. Dropping libbluray from the
  # manifest left the Fedora libbluray excluded by the run before
  # it, which stranded the Fedora libavformat-free too and failed
  # ten stage 0 packages that have nothing to do with Blu-ray.
  # Match on %{SOURCERPM}, as the ICU purge below does and for
  # the same reason: subpackages require each other by exact
  # NEVR, so dropping one and keeping its siblings is worse than
  # dropping none.
  if [ -n "${PROMISED_SOURCES:-}" ]; then
    promised_file=$(mktemp)
    printf "%s\n" "$PROMISED_SOURCES" | sed "/^$/d" > "$promised_file"
    while IFS= read -r -d "" rpm; do
      src=$(rpm -qp --qf "%{SOURCERPM}\n" "$rpm" 2>/dev/null)
      # <name>-<version>-<release>.src.rpm; the name may itself
      # contain dashes, so strip the last two fields, not the first.
      name=$(printf "%s" "$src" | sed "s/\.src\.rpm$//; s/-[^-]*-[^-]*$//")
      if [ -n "$name" ] && ! grep -qxF "$name" "$promised_file"; then
        echo "dropping unpromised artifact from accumulator: $rpm (src $name)"
        rm -f "$rpm"
      fi
    done < <(find /work/prior -name "*.rpm" -type f -print0)
    rm -f "$promised_file"
  fi
  stale_sources=""
  while IFS= read -r -d "" rpm; do
    if rpm -qpR "$rpm" 2>/dev/null | grep -q "libicuuc.so.77\|libicui18n.so.77"; then
      src=$(rpm -qp --qf "%{SOURCERPM}\n" "$rpm" 2>/dev/null)
      [ -n "$src" ] && stale_sources="${stale_sources}${src}\n"
    fi
  done < <(find /work/prior -name "*.rpm" -type f -print0)
  stale_sources=$(printf "%b" "$stale_sources" | sort -u | sed "/^$/d")
  if [ -n "$stale_sources" ]; then
    while IFS= read -r -d "" rpm; do
      src=$(rpm -qp --qf "%{SOURCERPM}\n" "$rpm" 2>/dev/null)
      if printf "%s\n" "$stale_sources" | grep -qxF "$src"; then
        echo "dropping stale artifact from accumulator: $rpm (src $src)"
        rm -f "$rpm"
      fi
    done < <(find /work/prior -name "*.rpm" -type f -print0)
  fi
  createrepo_c /work/prior
  printf "[stages]\nname=stages\nbaseurl=file:///work/prior\nenabled=1\ngpgcheck=0\npriority=1\n" \
    > /etc/yum.repos.d/stages.repo
  # priority alone does not keep Fedora out. gnome-control-center
  # pulled Fedora accountsservice 23.13.9 even though stage 0 had
  # built 26.27.3 and [stages] was priority 1: the Fedora main
  # package entered the transaction and pinned accountsservice-libs
  # to its exact NEVR, so our libs could not be installed and our
  # devel, which needs them, was dropped --
  #   cannot install both accountsservice-libs-26.27.3 from stages
  #                   and accountsservice-libs-23.13.9-16.fc44 from fedora
  # Excluding by name is what settles it: whatever an earlier stage
  # built, Fedora must not answer for. Names come from rpm rather
  # than from parsing filenames, which stops working the moment a
  # disttag changes.
  EXCLUDE=$(find /work/prior -name "*.rpm" -type f -print0 \
    | xargs -0 -r rpm -qp --qf "%{NAME}\n" 2>/dev/null \
    | sort -u | paste -sd, -)
  echo "excluding from Fedora: $EXCLUDE"
fi
# Hummingbird ships newer versions of some names than Fedora 44
# does, and the two must never mix in one transaction. The
# conflicts this prevents are real: libicu 78.3 (hum) vs 77.1
# (fc44) broke samba and evolution-data-server, and Fedora ruby
# 3.3/3.4-default-gems vs Hummingbird ruby4.0-default-gems broke
# webkitgtk, colord, libnotify and zsh. Always prefer the
# Hummingbird copy by excluding these names from Fedora.
# Unconditional: stage 0 has no prior RPMs, so the block above
# never ran and EXCLUDE would otherwise be empty here.
HB_EXCLUDE="ruby-default-gems,ruby3.3-default-gems,ruby3.4-default-gems,libicu,icu,gpgme,qt6-qtbase"
# The Hummingbird overlay currently exposes default gems for
# Ruby 3.3, 3.4, and 4.0. Older versions conflict by file name
# when a recipe merely needs the Ruby toolchain; exclude the
# older overlay packages globally so Ruby 4 remains selectable.
#
# ICU comes entirely from Hummingbird now: its newest libicu is
# 78.3, the same major the desktop stack needs, so the factory no
# longer builds a competing icu. Hummingbird still also ships the
# older libicu-77, and nothing must link it -- a build that picked
# 77 (localsearch, samba) produced RPMs the Hummingbird-only
# runtime could not install. Exclude the exact older Hummingbird
# NEVR globally so only libicu 78 is selectable; Fedora build-only
# consumers that want 77 are rare and not part of the runtime.
#
# The Rust toolchain comes from Fedora, not Hummingbird. Fedora
# builds rustc with an extra x86_64-redhat-linux-gnu target, and
# Mozilla configure looks that host triple up in rustc
# --print target-list; Hummingbird builds upstream rust, which
# only knows x86_64-unknown-linux-gnu, so mozjs140 stopped with
#   ERROR: Don t know how to translate x86_64-redhat-linux-gnu for rustc
# against rust-1.98.0-1.hum1. This is the documented division of
# labour rather than an exception to it: Fedora 44 is the other
# half of the buildroot, the way a compiler is, and Hummingbird
# upstream-first is about what ships at runtime. Nothing in the
# runtime contract carries a Rust toolchain. Version-anchored so
# rust-1.* cannot match rust-std-static or a rust-<crate>.
HB_GLOBAL_EXCLUDE="--exclude=ruby3.3-default-gems --exclude=ruby3.4-default-gems --exclude=libicu-77.*hum1 --exclude=libicu-devel-77.*hum1"
# ...but that NEVR-glob form does not match: mozjs140 still
# installed rust-0:1.98.0-1.hum1 with --exclude=rust-1.*hum1 on
# the command line. Exclude by NAME from the Hummingbird repo
# instead, which is the form already proven to work here -- it is
# what puts "filtered out by exclude filtering" in the resolver
# output for the Fedora side. Name-scoping is safe for the Rust
# toolchain because Fedora is the only other source of it; libicu
# cannot use this form, since 77 and 78 share one name and only
# the older build is unwanted.
HB_GLOBAL_EXCLUDE="${HB_GLOBAL_EXCLUDE} --setopt=public-hummingbird-x86_64-rpms.excludepkgs=rust,rustfmt,cargo,clippy,rust-std-static"
read -r -a hb_args <<< "$HB_GLOBAL_EXCLUDE"
EXCLUDE="${HB_EXCLUDE}${EXCLUDE:+,}${EXCLUDE}"
echo "hummingbird exclusions: $HB_EXCLUDE"
# The plain fedora image is not a build root: it lacks the group mock
# installs, so /usr/bin/echo and friends are missing. Most packages pull
# them in transitively; squashfs-tools calls echo directly from its
# manpage installer and fails without it.
dnf -y $disable "${hb_args[@]}" ${EXCLUDE:+--setopt=fedora.excludepkgs="$EXCLUDE"} \
  ${EXCLUDE:+--setopt=updates.excludepkgs="$EXCLUDE"} install dnf-plugins-core rpm-build @buildsys-build
rpm -q --qf "buildroot openssl: %{VERSION}-%{RELEASE}\n" openssl-libs || true
# The AlmaLinux convention, one distro over. They keep the vendor
# release and dist and append to it -- their dnf is
# 4.14.0-34.el9_8.alma.1 against 34.el9_8 from Red Hat, and both
# .alma and .alma.N appear in their repositories.
#
# The vendor here is Hummingbird, not Fedora. These packages are
# built for Hummingbird and installed on Hummingbird; Fedora 44 is
# only the other half of the buildroot, the way a compiler is. An
# earlier version of this tagged them .fc44.bfin, which named the
# distribution they are not for.
#
# The tag is read from the Hummingbird packages present in the
# buildroot rather than hardcoded, so a move to hum2 carries
# itself. A buildroot containing none of them is a repository
# misconfiguration -- the exact failure this factory exists to
# avoid -- so it stops rather than quietly tagging something else.
HUM_TAG="$(rpm -qa --qf "%{RELEASE}\n" | grep -oE "hum[0-9]+$" | sort -u | head -n1)"
if [ -z "$HUM_TAG" ]; then
  echo "No Hummingbird package in the buildroot; cannot derive a disttag" >&2
  rpm -qa --qf "%{NAME} %{RELEASE}\n" | sort | head -20 >&2
  exit 1
fi
DISTTAG=".${HUM_TAG}.bfin${DIST_BUMP:-}"
echo "disttag: $DISTTAG"
# libratbag %check starts ratbagd, which calls
# Gio.bus_get_sync(Gio.BusType.SYSTEM) and dies with "Could not
# connect: No such file or directory" -- a plain container has no
# system bus socket. Seven of its ten suites already pass and the
# failing one is a real test, so give the build root a bus rather
# than disabling the test. Non-fatal: no other package needs it.
dnf -y $disable install dbus-daemon || true
mkdir -p /run/dbus
dbus-daemon --system --fork || true
# mock defines USER in its build root; a bare container does not.
# just 1.57.0 tests/functions.rs:88 calls env::var("USER").unwrap()
# and panicked with NotPresent -- 1823 tests passed, that one did
# not. Same shape as the missing system bus: supply what a real
# build root has rather than disable the test.
export USER="${USER:-root}"
export LOGNAME="${LOGNAME:-$USER}"
spec=$(find "/packages/$RECIPE" -maxdepth 1 -name "*.spec" -print -quit)
test -n "$spec"
# The defines a shard builds with, applied to every rpm-aware
# step: builddep must resolve the same conditional BuildRequires
# that rpmbuild will evaluate, or a shard installs the other
# port toolchain and resolves what it will never compile.
define_args=()
while IFS= read -r define; do
  [ -n "$define" ] && define_args+=(-D "$define")
done <<< "$RPM_DEFINES"
echo "rpm defines: ${RPM_DEFINES:-none}"
phase=buildrequires
dnf -y $disable "${hb_args[@]}" ${EXCLUDE:+--setopt=fedora.excludepkgs="$EXCLUDE"} \
  ${EXCLUDE:+--setopt=updates.excludepkgs="$EXCLUDE"} builddep -D "_sourcedir /packages/$RECIPE" "${define_args[@]}" "$spec"
# An imported spec keeps its dist-git PatchN and auxiliary SourceN
# files next to itself, while the verified upstream archive lands in
# /work/sources. rpmbuild takes a single _sourcedir, so stage both:
# recipe files first, then the verified archive, which therefore wins
# over anything of the same name carried in the import.
staged=/work/staged/$PACKAGE
rm -rf "$staged"
mkdir -p "$staged"
cp -a "/packages/$RECIPE/." "$staged/"
cp -a "/work/sources/$PACKAGE/." "$staged/"
# Match mock's build user. FLAC's read-only-file tests correctly fail when
# rpmbuild runs as root, which can write files regardless of their mode bits.
useradd --create-home --home-dir /builddir mockbuild
mkdir -p /builddir/rpmbuild/SRPMS /work/sccache
chown -R mockbuild:mockbuild /builddir/rpmbuild "$staged" /work/result /work/sccache
build_rpm() { runuser -u mockbuild -- rpmbuild "$@"; }
# Packages with %generate_buildrequires -- every Rust one -- compute
# their real BuildRequires during the build, so the spec alone does not
# list them and rpmbuild exits 11 asking to be re-run. Install what the
# generated source RPM declares and retry, bounded so an unsatisfiable
# requirement fails instead of looping.
resolved=0
for _ in 1 2 3 4 5; do
  rm -f /builddir/rpmbuild/SRPMS/*.buildreqs.nosrc.rpm
  if build_rpm -br "$spec" --define "_sourcedir $staged" \
       --define "dist $DISTTAG" "${define_args[@]}"; then resolved=1; break; else status=$?; fi
  # Only exit 11 requests additional dependencies. A failed %prep is a real error.
  [[ $status == 11 ]] || exit "$status"
  generated=$(find /builddir/rpmbuild/SRPMS -name '*.buildreqs.nosrc.rpm' -print -quit)
  test -n "$generated"
  dnf -y $disable "${hb_args[@]}" ${EXCLUDE:+--setopt=fedora.excludepkgs="$EXCLUDE"} \
    ${EXCLUDE:+--setopt=updates.excludepkgs="$EXCLUDE"} builddep -D "_sourcedir /packages/$RECIPE" "${define_args[@]}" "$generated"
done
[[ $resolved == 1 ]] || { echo 'Dynamic BuildRequires did not converge after five attempts' >&2; exit 1; }
if [[ ${BUILD_MODE:-build} == deps ]]; then
  echo "BuildRequires and source preparation passed for $PACKAGE; compilation was not requested."
  exit 0
fi
phase=rpmbuild
build_rpm -ba "$spec" \
  --define "_sourcedir $staged" \
  --define "dist $DISTTAG" \
  --define "_rpmdir /work/result" \
  "${define_args[@]}"
find /work/result -name "*.rpm" -type f -print0 | \
  xargs -0 -r rpm -qp --qf "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n"
# A build that produced no RPM must fail here. if-no-files-found on
# the upload cannot catch it: the artifact also carries
# work/reports/*.json, so one file always matches and the upload
# reports success while shipping no packages at all.
test -n "$(find /work/result -name "*.rpm" -type f -print -quit)"
