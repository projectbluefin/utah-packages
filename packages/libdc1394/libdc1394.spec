%global sover 26
Name:       libdc1394
Summary:    1394-based digital camera control library
Version:    2.2.7
Release:    %autorelease
License:    LGPL-2.0-or-later
URL:        http://sourceforge.net/projects/%{name}/

ExcludeArch:    s390 s390x

Source:     http://downloads.sourceforge.net/project/%{name}/%{name}-2/%{version}/%{name}-%{version}.tar.gz
Patch0:     %{name}-sdl.patch

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  doxygen
BuildRequires:  gcc
BuildRequires:  kernel-headers
BuildRequires:  make
BuildRequires:  libraw1394-devel
BuildRequires:  libtool
BuildRequires:  libusb1-devel
BuildRequires:  libX11-devel
BuildRequires:  libXv-devel
BuildRequires:  perl-interpreter

%description
Libdc1394 is a library that is intended to provide a high level programming
interface for application developers who wish to control IEEE 1394 based cameras
that conform to the 1394-based Digital Camera Specification.

%package devel
Summary:    Header files and libraries for %{name}
Requires:   %{name}%{?_isa} = %{version}-%{release}
Requires:   libraw1394-devel

%description devel
This package contains the header files and libraries for %{name}. If you like
to develop programs using %{name}, you will need to install %{name}-devel.

%package docs
Summary:    Development documentation for %{name}

%description docs
This package contains the development documentation for %{name}.

%package tools
Summary:    Tools for use with %{name}

%description tools
This package contains tools that are useful when working and developing with
%{name}.

%prep
%autosetup -p1

%build
autoreconf -vif
%configure --disable-static --enable-doxygen-html --enable-doxygen-dot
%make_build
%make_build doc

%install
%make_install

for p in grab_color_image grab_gray_image grab_partial_image ladybug grab_partial_pvn; do
    install -p -m 0755 -s examples/.libs/$p %{buildroot}%{_bindir}/dc1394_$p
done
install -p -m 0755 examples/dc1394_multiview %{buildroot}%{_bindir}/dc1394_multiview

for f in grab_color_image grab_gray_image grab_partial_image; do
    mv %{buildroot}%{_mandir}/man1/$f.1 %{buildroot}%{_mandir}/man1/dc1394_$f.1
done

find %{buildroot} -name "*.la" -delete

%{?ldconfig_scriptlets}

%files
%license COPYING
%doc AUTHORS ChangeLog NEWS README
%{_libdir}/%{name}.so.%{sover}*

%files devel
%doc examples/*.h examples/*.c
%{_includedir}/dc1394/
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}-2.pc

%files docs
%doc doc/html/*

%files tools
%{_bindir}/dc1394_grab_color_image
%{_bindir}/dc1394_grab_gray_image
%{_bindir}/dc1394_grab_partial_image
%{_bindir}/dc1394_grab_partial_pvn
%{_bindir}/dc1394_ladybug
%{_bindir}/dc1394_multiview
%{_bindir}/dc1394_reset_bus
%{_mandir}/man1/dc1394_grab_color_image.*
%{_mandir}/man1/dc1394_grab_gray_image.*
%{_mandir}/man1/dc1394_grab_partial_image.*
%{_mandir}/man1/dc1394_multiview.*
%{_mandir}/man1/dc1394_reset_bus.*
%{_mandir}/man1/dc1394_vloopback.*

%changelog
%autochangelog
