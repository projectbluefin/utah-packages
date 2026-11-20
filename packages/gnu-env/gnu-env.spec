# GNU env alone, for systems whose coreutils is uutils-coreutils-replace.
#
# Project Bluefin Dakota links every uutils utility over its GNU name except
# env (projectbluefin/dakota elements/bluefin/uutils-coreutils.bst): pkexec
# realpath()s its target and the uutils multicall binary dispatches on the
# executed path, so a symlinked env breaks `pkexec -u <user> /usr/bin/env
# <cmd>`, which uupd runs. Dakota keeps GNU coreutils staged underneath, so its
# env stays GNU. An RPM system cannot keep coreutils-single installed beside
# uutils-coreutils-replace (both own /usr/bin/<prog>), so this recipe builds
# GNU's env, and only env, from the same coreutils release Hummingbird ships.
# uutils-coreutils-replace requires it.

Name:           gnu-env
Version:        9.12
Release:        1%{?dist}
Summary:        GNU env, for systems that use uutils-coreutils as coreutils

License:        GPL-3.0-or-later
URL:            https://www.gnu.org/software/coreutils/
Source0:        https://ftp.gnu.org/gnu/coreutils/coreutils-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  make

# coreutils and coreutils-single own /usr/bin/env too.
Conflicts:      coreutils
Conflicts:      coreutils-single

%description
env from GNU coreutils, built on its own. It runs a program in a modified
environment. uutils-coreutils-replace, which puts uutils-coreutils at the GNU
coreutils paths, requires it so that /usr/bin/env stays GNU's.

%prep
%autosetup -n coreutils-%{version}

%build
# env needs none of coreutils' optional libraries. coreutils' configure
# refuses to run as root, which the factory's container lane is; the check
# only guards tests of mknod behaviour that env does not use.
export FORCE_UNSAFE_CONFIGURE=1
%configure \
    --disable-nls \
    --disable-acl \
    --disable-xattr \
    --disable-libcap \
    --disable-systemd \
    --without-selinux \
    --without-openssl \
    --without-gmp
# `make all` generates gnulib's replacement headers (BUILT_SOURCES) before
# compiling anything; a lone src/env target does not, so generate them first.
printf 'gnu-env-built-sources: $(BUILT_SOURCES)\n' \
    | %{make_build} -f Makefile -f - gnu-env-built-sources
%make_build src/env

%install
install -Dpm 0755 src/env %{buildroot}%{_bindir}/env

%check
test "$(src/env -i GNU_ENV_CHECK=1 src/env)" = GNU_ENV_CHECK=1
src/env --version | head -n 1 | grep -Fx 'env (GNU coreutils) %{version}'

%files
%license COPYING
%{_bindir}/env

%changelog
* Fri Nov 20 2026 Utah Packages <packages@projectbluefin.io> - 9.12-1
- GNU env from coreutils 9.12, for uutils-coreutils-replace
