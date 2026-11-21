# GNU cp alone, for systems whose coreutils is uutils-coreutils-replace.
#
# uutils-coreutils 0.7.0's `cp -p` fails outright when the destination
# filesystem has no POSIX ACL support: with feat_acl, preserving the mode
# copies the source's ACL with exacl::setfacl, and an EOPNOTSUPP from it is a
# hard error. GNU cp falls back to chmod. bootupd installs the EFI files with
# `cp -rp --reflink=auto` onto the vfat ESP, so bootc install failed with
#   cp: File "/tmp/.tmpXXXXXX/EFI/fedora/grubx64.efi": Operation not supported (os error 95)
# (projectbluefin/utah Post-Testing E2E luks, run 44856113504 onwards).
# uutils fixed it upstream after 0.7.0 (uutils/coreutils#13626, best-effort
# ACL copy, released in 0.10.0). Until the factory's uutils-coreutils carries
# that release, cp stays GNU's, the way env does (gnu-env): this recipe builds
# GNU's cp, and only cp, from the coreutils release Hummingbird ships.
# uutils-coreutils-replace requires it.

Name:           gnu-cp
Version:        9.12
Release:        1%{?dist}
Summary:        GNU cp, for systems that use uutils-coreutils as coreutils

License:        GPL-3.0-or-later
URL:            https://www.gnu.org/software/coreutils/
Source0:        https://ftp.gnu.org/gnu/coreutils/coreutils-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  make
# cp preserves ACLs, extended attributes and SELinux contexts, as
# coreutils-single's cp does.
BuildRequires:  libacl-devel
BuildRequires:  libattr-devel
BuildRequires:  libselinux-devel

# coreutils and coreutils-single own /usr/bin/cp too. Both provide the
# arch-qualified coreutils(<arch>); plain `coreutils` would also match
# uutils-coreutils-replace's Provides, and that package requires this one.
Conflicts:      coreutils%{?_isa}
Conflicts:      coreutils-single

%description
cp from GNU coreutils, built on its own. It copies files and directories.
uutils-coreutils-replace, which puts uutils-coreutils at the GNU coreutils
paths, requires it so that /usr/bin/cp stays GNU's: bootupd copies the EFI
files onto the vfat ESP with `cp -rp`, which uutils-coreutils 0.7.0 fails.

%prep
%autosetup -n coreutils-%{version}

%build
# cp needs ACL, xattr and SELinux support and none of coreutils' other
# optional libraries. coreutils' configure refuses to run as root, which the
# factory's container lane is; the check only guards tests of mknod
# behaviour that cp does not use.
export FORCE_UNSAFE_CONFIGURE=1
%configure \
    --disable-nls \
    --enable-acl \
    --enable-xattr \
    --disable-libcap \
    --disable-systemd \
    --with-selinux \
    --without-openssl \
    --without-gmp
# `make all` generates gnulib's replacement headers (BUILT_SOURCES) before
# compiling anything; a lone src/cp target does not, so generate them first.
printf 'gnu-cp-built-sources: $(BUILT_SOURCES)\n' \
    | %{make_build} -f Makefile -f - gnu-cp-built-sources
%make_build src/cp

%install
install -Dpm 0755 src/cp %{buildroot}%{_bindir}/cp

%check
src/cp --version | head -n 1 | grep -Fx 'cp (GNU coreutils) %{version}'
# The features coreutils-single's cp has: a build without them would copy
# silently without ACLs, xattrs or SELinux labels.
grep -Fx '#define USE_ACL 1' lib/config.h
grep -Fx '#define USE_XATTR 1' lib/config.h
grep -Fx '#define HAVE_SELINUX_SELINUX_H 1' lib/config.h
printf 'gnu-cp\n' > check-src
chmod 0640 check-src
src/cp -p check-src check-dst
cmp check-src check-dst
test "$(stat -c %a check-dst)" = 640

%files
%license COPYING
%{_bindir}/cp

%changelog
* Sat Nov 21 2026 Utah Packages <packages@projectbluefin.io> - 9.12-1
- GNU cp from coreutils 9.12, for uutils-coreutils-replace: uutils 0.7.0's
  cp -p fails on filesystems without ACL support, such as the vfat ESP
