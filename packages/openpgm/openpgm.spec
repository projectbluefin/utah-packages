#
Name:          openpgm
Version:       5.3.128
%global name_alias        pgm
%global version_main      5.3
%global version_dash_main 5-3
%global version_dash      %{version_dash_main}-128
Release:       %autorelease
Summary:       An implementation of the PGM reliable multicast protocol

License:       LGPL-2.1-or-later
# New URL is https://github.com/steve-o/openpgm
# The files are now on https://code.google.com/archive/p/openpgm/downloads
URL:           https://github.com/steve-o/%{name}
Source0:       https://github.com/steve-o/%{name}/archive/release-%{version_dash}.tar.gz#/%{name}-%{version}.tar.gz

# All the following patches have been submitted upstream
# as a merge request: https://github.com/steve-o/openpgm/pull/64
Patch2:        openpgm-02-checksum-arch.patch
Patch3:        openpgm-03-pkgconfig.patch
Patch6:        openpgm-configure-c99.patch
Patch7:        openpgm-c99.patch

BuildRequires: make
BuildRequires: libtool automake autoconf
BuildRequires: gcc
BuildRequires: python3
BuildRequires: dos2unix
BuildRequires: perl-interpreter


%description
OpenPGM is an open source implementation of the Pragmatic General
Multicast (PGM) specification in RFC 3208.


%package devel
Summary:       Development files for openpgm
Requires:      %{name}%{?_isa} = %{version}-%{release}

%description devel
This package contains OpenPGM related development libraries and header files.


%prep
%setup -q -n %{name}-release-%{version_dash}/%{name}/%{name_alias}
%patch -P2 -p3
%patch -P3 -p3
%patch -P6 -p3
%patch -P7 -p3
dos2unix examples/getopt.c examples/getopt.h
mv openpgm-5.2.pc.in openpgm-5.3.pc.in

%build
libtoolize --force --copy
aclocal
autoheader
automake --copy --add-missing
autoconf
%configure

# This package has a configure test which uses ASMs, but does not link the
# resultant .o files.  As such the ASM test is always successful, even on
# architectures were the ASM is not valid when compiling with LTO.
#
# -ffat-lto-objects is sufficient to address this issue.  It is the default
# for F33, but is expected to only be enabled for packages that need it in
# F34, so we use it here explicitly
%define _lto_cflags -flto=auto -ffat-lto-objects

%make_build

%install
%make_install

# Remove the static libraries and the temporary libtool artifacts
rm -f %{buildroot}%{_libdir}/lib%{name_alias}.{a,la}

# Move the header files into /usr/include
mv -f %{buildroot}%{_includedir}/%{name_alias}-%{version_main}/%{name_alias} %{buildroot}%{_includedir}/

%files
%doc COPYING
%license LICENSE
%{_libdir}/*.so.*

%files devel
%doc examples/
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/openpgm-5.3.pc


%changelog
%autochangelog
