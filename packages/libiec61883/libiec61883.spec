Summary:        Streaming library for IEEE1394
Name:           libiec61883
Version:        1.2.0
Release:        %autorelease
License:        LGPL-2.1-or-later AND GPL-2.0-or-later
Source:         http://www.kernel.org/pub/linux/libs/ieee1394/%{name}-%{version}.tar.gz
URL:            https://ieee1394.docs.kernel.org/en/latest/#libiec61883
ExcludeArch:    s390 s390x

# Fedora specific patches.
Patch0:         libiec61883-1.2.0-installtests.patch
Patch1:         libiec61883-channel-allocation-without-local-node-rw.patch

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  gcc
# Works only with newer libraw1394 versions
BuildRequires:  libraw1394-devel
BuildRequires:  libtool
BuildRequires:  make

%description
The libiec61883 library provides an higher level API for streaming DV,
MPEG-2 and audio over IEEE1394.  Based on the libraw1394 isochronous
functionality, this library acts as a filter that accepts DV-frames,
MPEG-2 frames or audio samples from the application and breaks these
down to isochronous packets, which are transmitted using libraw1394.

%package devel
Summary:        Development files for libiec61883
Requires:       %{name} = %{version}-%{release}

%description devel
Development files needed to build applications against libiec61883

%package utils
Summary:        Utilities for use with libiec61883
Requires:       %{name} = %{version}-%{release}

%description utils
Utilities that make use of iec61883

%prep
%autosetup -p1

%build
autoreconf -vif
%configure --disable-static
%make_build

%install
%make_install

find %{buildroot} -name '*.la' -delete

%files
%doc AUTHORS COPYING NEWS README
%{_libdir}/libiec61883.so.*

%files devel
%{_libdir}/libiec61883.so
%dir %{_includedir}/libiec61883
%{_includedir}/libiec61883/*.h
%{_libdir}/pkgconfig/libiec61883.pc

%files utils
%{_bindir}/*
%{_mandir}/man1/*.1*

%changelog
%autochangelog
