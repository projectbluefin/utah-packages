# No, please don't break the linker.  Thanks.
%undefine _auto_set_build_flags

Name: gnu-efi
Epoch: 1
Version: 3.0.18
Release: %autorelease
Summary: Development Libraries and headers for EFI
License: BSD-2-Clause AND BSD-2-Clause-Patent AND BSD-3-Clause AND BSD-4-Clause AND GPL-2.0-or-later AND GPL-2.0-only
URL: https://sourceforge.net/projects/gnu-efi/

Source0: https://sourceforge.net/projects/gnu-efi/files/gnu-efi-%{version}.tar.bz2

# upstream this breaks non-GNU LD, Heinrich Schuchardt asked us not to do this:
# "The correct approach is to adjust the loader script to put non-static
# data into a different section than the code and to make the .text section RX."
#Patch0048: 0048-ld-Don-t-warn-about-RWX-segment-maps.patch

# use --output-target with objcopy
Patch0048: 0049-objcopy-use-output-target-instead-of-target.patch

ExclusiveArch: %{efi}
BuildRequires: binutils
BuildRequires: efi-srpm-macros >= 5-4
BuildRequires: gcc
BuildRequires: git git-core

# We're explicitly *not* requiring glibc-headers, because it gets us
# cross-arch dependency problems in "fedpkg mockbuild" from x86_64.
# BuildRequires: glibc-headers
%ifarch x86_64
# So... in some build environments, glibc32 provides some headers.  In
# others, glibc-devel.i686 does.  They have no provides in common, as
# file provides in /usr/include or /usr/lib are not usable with dnf5.
BuildRequires: (glibc-devel(x86-32) or glibc32)
%endif
BuildRequires: make

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
%autosetup -S git_am

%build
%undefine _hardened_ldflags
# Package cannot build with %%{?_smp_mflags}.
make LIBDIR=%{_prefix}/lib
make apps

%install
make PREFIX=%{_prefix} LIBDIR=%{_prefix}/lib INSTALLROOT=%{buildroot} install
mkdir -p %{buildroot}/%{efi_esp_dir}/%{efi_arch}
mv %{buildroot}/usr/lib/gnuefi/apps/*.efi %{buildroot}%{efi_esp_dir}/%{efi_arch}/

%ifarch x86_64 aarch64 riscv64
mkdir -p %{buildroot}%{_libdir}
mv %{buildroot}%{_prefix}/lib/pkgconfig %{buildroot}%{_libdir}
%endif

# delete useless file
rm %{buildroot}/usr/lib/gnuefi/apps/debughook.efi.debug

%pretrans devel -p <lua>
-- Handle replacing a symlink to a directory with an actual directory
-- https://docs.fedoraproject.org/en-US/packaging-guidelines/Directory_Replacement/
path = "/usr/include/efi/x86_64"
st = posix.stat(path)
if st and st.type == "link" then
  os.remove(path)
end

%files
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
