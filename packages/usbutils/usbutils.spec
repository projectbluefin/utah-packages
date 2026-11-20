Name:    usbutils
Version: 020
Release: %autorelease
Summary: Linux USB utilities
URL:     http://www.linux-usb.org/
License: GPL-2.0-or-later

Source0: https://www.kernel.org/pub/linux/utils/usb/usbutils/%{name}-%{version}.tar.xz

# This adds usbreset binary to the package, but since upstream does not consider it stable, 
# let's not include it in the ELN. https://github.com/gregkh/usbutils/issues/222#issuecomment-2715192013
%if 0%{?fedora}
Patch0: usbreset.patch
%endif

BuildRequires: meson
BuildRequires: gcc
BuildRequires: libusb1-devel
BuildRequires: systemd-devel
Requires: hwdata

%description
This package contains utilities for inspecting devices connected to a
USB bus.

%prep
%autosetup -p1

%build
%meson --sbindir=%{_sbindir} --datadir=%{_datadir}/hwdata
%meson_build

%install
%meson_install
rm -rf %{buildroot}/%{_libdir}/pkgconfig/usbutils.pc

%files
%license LICENSES/GPL*
%doc NEWS
%{_mandir}/*/*
%{_bindir}/*

%changelog
%autochangelog
