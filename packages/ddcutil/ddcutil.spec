%bcond_without build_lib

Name:       ddcutil
Version:    2.2.7
Release:    %autorelease
Summary:    Query and update monitor settings
# Automatically converted from old format: GPLv2+ - review is highly recommended.
License:    GPL-2.0-or-later
URL:        http://www.ddcutil.com
Source0:    https://github.com/rockowitz/ddcutil/archive/v%{version}/%{name}-%{version}.tar.gz

# Excluding arch s390/s390x due to i2c-tools does so
ExcludeArch:    s390 s390x

BuildRequires:      automake
BuildRequires:      autoconf
BuildRequires:      libtool
BuildRequires:      gcc
BuildRequires:      make
BuildRequires:      pkgconfig(glib-2.0)   >= 2.40
BuildRequires:      pkgconfig(libusb-1.0) >= 1.0.15
BuildRequires:      pkgconfig(systemd)
BuildRequires:      pkgconfig(libudev)
BuildRequires:      pkgconfig(xrandr)
BuildRequires:      pkgconfig(libdrm) >= 2.4.67
BuildRequires:      pkgconfig(libkmod)
BuildRequires:      pkgconfig(libacl)
BuildRequires:      pkgconfig(jansson) >= 2.0

Requires:   hwdata
Requires:   i2c-tools

# file that may be used at runtime
Recommends: /usr/bin/lsusb
Recommends: /usr/bin/modprobe
Recommends: pkg-config
Recommends: /usr/bin/lscpu
Recommends: /usr/bin/lsb_release
Recommends: xrandr

%description
Query and change monitor settings

ddcutil communicates with monitors implementing MCCS (Monitor Control Command
Set), using either the DDC/CI protocol on the I2C bus or as a Human Interface
Device on USB.  In general, anything that can be controlled using a monitor's
on-screen display can be controlled by this program.  Examples include
changing a monitor's input source and adjusting its brightness.

# libddcutil can be installed separately
%if %{with build_lib}
%package -n libddcutil
Summary:        Shared library to query and update monitor settings

%description -n libddcutil
Shared library version of ddcutil, exposing a C API.

%package -n libddcutil-devel
Summary:        Development files for libddcutil
# FindDDCUtils.cmake has BSD-3-Clause license header
License:        GPL-2.0-or-later AND BSD-3-Clause
Requires:       libddcutil%{?_isa} = %{version}-%{release}
Requires:       cmake-filesystem%{?_isa}

%description -n libddcutil-devel
Development files for libddcutil
%endif

%prep
%setup -q

%build
NOCONFIGURE=1 ./autogen.sh
%configure \
%if %{with build_lib}
    --enable-lib=yes
%else
    --enable-lib=no
%endif
%make_build

%install
%make_install

%files
%doc AUTHORS NEWS.md README.md CHANGELOG.md
%license COPYING
%{_bindir}/%{name}
%{_datadir}/%{name}
%{_mandir}/man1/%{name}.1.*
%{_udevrulesdir}/60-ddcutil-i2c.rules
%{_modulesloaddir}/ddcutil.conf

%if %{with build_lib}
%files -n libddcutil
%doc AUTHORS NEWS.md README.md CHANGELOG.md
%license COPYING
%{_libdir}/lib%{name}.so.5*

%files -n libddcutil-devel
%{_libdir}/lib%{name}.so
%{_includedir}/%{name}*.h
%{_libdir}/cmake/%{name}
%{_libdir}/pkgconfig/%{name}.pc
%endif

%changelog
%autochangelog
