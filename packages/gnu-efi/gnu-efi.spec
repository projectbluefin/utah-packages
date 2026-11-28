# No, please don't break the linker.  Thanks.
%undefine _auto_set_build_flags

Name: gnu-efi
Epoch: 1
Version: 4.0.4
Release: %autorelease
Summary: Development Libraries and headers for EFI
License: BSD-3-Clause AND (GPL-2.0-or-later OR BSD-3-Clause) AND BSD-3-Clause-Patent AND LGPL-3.0-or-later
URL: https://github.com/ncroxon/gnu-efi

# Upstream moved from SourceForge to GitHub and attaches no release asset to
# its releases, so the source is the archive of the release tag:
#   git archive --prefix gnu-efi-4.0.4/ -o ../gnu-efi-4.0.4.tar.gz 4.0.4
Source0: https://github.com/ncroxon/gnu-efi/archive/%{version}/%{name}-%{version}.tar.gz

ExclusiveArch: %{efi}
BuildRequires: binutils
BuildRequires: efi-srpm-macros >= 5-4
BuildRequires: gcc
BuildRequires: make

# We're explicitly *not* requiring glibc-headers, because it gets us
# cross-arch dependency problems in "fedpkg mockbuild" from x86_64.
# BuildRequires: glibc-headers
%ifarch x86_64
# So... in some build environments, glibc32 provides some headers.  In
# others, glibc-devel.i686 does.  They have no provides in common, as
# file provides in /usr/include or /usr/lib are not usable with dnf5.
BuildRequires: (glibc-devel(x86-32) or glibc32)
%endif

# added 2020-01-24, so time is up...
Obsoletes: %{name}-compat < 1:3.0.11-12

# rpmlint, shut up.
%define lib %{nil}lib%{nil}

%define debug_package %{nil}

# brp-strip-static-archive will senselessly /add/ timestamps and uid/gid
# data to our .a and make them not multilib clean if we don't have this.
%undefine __brp_strip_static_archive
%global __brp_strip_static_archive find '%{buildroot}' -name '*.a' -print -exec %{__strip} -gDp {} \\;

%description
This package contains development headers and libraries for developing
applications that run under EFI (Extensible Firmware Interface).

%package devel
Summary: Development Libraries and headers for EFI
Obsoletes: gnu-efi < 1:3.0.2-1
Requires: gnu-efi = %{epoch}:%{version}-%{release}

%description devel
This package contains development headers and libraries for developing
applications that run under EFI (Extensible Firmware Interface).

%package utils
Summary: Utilities for EFI systems

%description utils
This package contains utilities for debugging and developing EFI systems.

%prep
%autosetup -n %{name}-%{version}

%build
%undefine _hardened_ldflags
# Package cannot build with %%{?_smp_mflags}.
#
# 4.0.4 builds the library, the headers, the EFI runtime and the sample
# applications from one top level "make": the tree's own Makefile orders the
# subdirectories, and the sample applications link against the runtime that
# was just built. VERSION= overrides the tree's own, which still reads 4.0.3
# and would stamp that into gnu-efi.pc.
make LIBDIR=%{_prefix}/lib VERSION=%{version}

%install
make PREFIX=%{_prefix} LIBDIR=%{_prefix}/lib INSTALLROOT=%{buildroot} VERSION=%{version} install
mkdir -p %{buildroot}/%{efi_esp_dir}/%{efi_arch}
mv %{buildroot}/usr/lib/gnuefi/apps/*.efi %{buildroot}%{efi_esp_dir}/%{efi_arch}/

%ifarch x86_64 aarch64 riscv64
mkdir -p %{buildroot}%{_libdir}
mv %{buildroot}/%{_prefix}/lib/pkgconfig %{buildroot}%{_libdir}
%endif

# delete useless file
rm %{buildroot}/usr/lib/gnuefi/apps/debughook.efi.debug

# Upstream states the terms of every directory in its LICENSE file and ships
# the texts it refers to. LGPL-3.0-or-later covers inc/subst/elf.h, which
# upstream relicensed under section 3 of the LGPLv3; the GPLv3 text it points
# at travels with it.
mkdir -p %{buildroot}%{_licensedir}/%{name}
install -m 644 LICENSE %{buildroot}%{_licensedir}/%{name}/LICENSE
install -m 644 licenses/LICENSE.* %{buildroot}%{_licensedir}/%{name}/

%pretrans devel -p <lua>
-- Handle replacing a symlink to a directory with an actual directory
-- https://docs.fedoraproject.org/en-US/packaging-guidelines/Directory_Replacement/
path = "/usr/include/efi/x86_64"
st = posix.stat(path)
if st and st.type == "link" then
  os.remove(path)
end

%files
%license %{_licensedir}/%{name}/LICENSE
%license %{_licensedir}/%{name}/LICENSE.*
%{_prefix}/lib/*.o
%{_prefix}/lib/*.lds

%files devel
%doc README.*
%{_includedir}/efi
%{_prefix}/lib/libefi.a
%{_prefix}/lib/libgnuefi.a
%{_libdir}/pkgconfig/gnu-efi.pc

%files utils
%dir %attr(0700,root,root) %{efi_esp_dir}/%{efi_arch}/
%attr(0700,root,root) %{efi_esp_dir}/%{efi_arch}/*.efi

%changelog
%autochangelog
