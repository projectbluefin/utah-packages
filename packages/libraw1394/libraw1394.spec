Summary:        Library providing low-level IEEE-1394 access
Name:           libraw1394
Version:        2.1.2
Release:        %autorelease
License:        LGPL-2.1-or-later
Source:         https://www.kernel.org/pub/linux/libs/ieee1394/%{name}-%{version}.tar.xz
URL:            https://ieee1394.docs.kernel.org/en/latest/libraw1394.html
# https://bugzilla.redhat.com/show_bug.cgi?id=2012630
ExcludeArch:    s390 s390x
BuildRequires:  gcc
BuildRequires:  kernel-headers
BuildRequires:  make

%description
The libraw1394 library provides direct access to the IEEE-1394 bus.
Support for both the obsolete ieee1394 interface and the new firewire
intererface are included, with run-time detection of the active stack.

%package devel
Summary:        Development libs for libraw1394
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Development libraries needed to build applications against libraw1394.

%prep
%setup -q

%build
%configure --disable-static
%make_build

%install
%make_install
rm -f %{buildroot}%{_libdir}/libraw1394.la

%files
%license COPYING.LIB
%doc README NEWS
%{_bindir}/dumpiso
%{_bindir}/sendiso
%{_bindir}/testlibraw
%{_libdir}/libraw1394.so.11*
%{_mandir}/man1/dumpiso.1*
%{_mandir}/man1/sendiso.1*
%{_mandir}/man1/testlibraw.1*
%{_mandir}/man5/isodump.5*

%files devel
%doc doc/libraw1394.sgml
%{_includedir}/libraw1394/
%{_libdir}/libraw1394.so
%{_libdir}/pkgconfig/libraw1394.pc


%changelog
%autochangelog
