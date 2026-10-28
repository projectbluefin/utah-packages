Name:           libell
Version:        0.83
Release:        %autorelease
Summary:        Embedded Linux library
License:        LGPL-2.0-or-later
URL:            https://01.org/ell
Source0:        https://www.kernel.org/pub/linux/libs/ell/ell-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  make

%description
The Embedded Linux* Library (ELL) provides core, low-level functionality for
system daemons. It typically has no dependencies other than the Linux kernel, C
standard library, and libdl (for dynamic linking). While ELL is designed to be
efficient and compact enough for use on embedded Linux platforms, it is not
limited to resource-constrained systems.


%package devel
Summary:        Embedded Linux library development files
Requires:       %{name}%{?_isa} = %{version}-%{release}


%description devel
Headers for developing against libell.


%prep
%autosetup -p1 -n ell-%{version}


%build
%configure
%make_build V=1


%install
%make_install
find %{buildroot} -type f -name "*.la" -delete


%ldconfig_scriptlets


%files
%license COPYING
%doc AUTHORS ChangeLog
%{_libdir}/libell.so.*


%files devel
%{_includedir}/ell
%{_libdir}/libell.so
%{_libdir}/pkgconfig/ell.pc


%changelog
%autochangelog
