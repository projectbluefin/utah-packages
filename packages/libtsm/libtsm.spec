Name:           libtsm
Version:        4.8.0
Release:        %autorelease
Summary:        DEC-VT terminal emulator state machine
License:        MIT AND LGPL-2.1-or-later
URL:            https://github.com/kmscon/libtsm
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig
BuildRequires:  xz
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(check)

%description
TSM is a state machine for DEC VT100-VT520 compatible terminal
emulators. It can be used to implement terminal emulators, or other
applications that need to interpret terminal escape sequences. The
library does no rendering or window management of its own, and does
not depend on a graphics stack, unlike the similar GNOME libvte.

%package devel
Summary:        Development files for the DEC-VT terminal state machine library
License:        LGPL-2.1-or-later
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
TSM is a state machine for DEC VT100-VT520 compatible terminal
emulators. It can be used to implement terminal emulators, or other
applications that need to interpret terminal escape sequences. The
library does no rendering or window management of its own, and does
not depend on a graphics stack, unlike the similar GNOME libvte.

This package contains the development headers for the library found
in %{name}.

%prep
%autosetup -p1

%conf
%meson

%build
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING LICENSE_htable
%{_libdir}/libtsm.so.4{,.*}

%files devel
%doc README.md
%{_includedir}/libtsm.h
%{_libdir}/libtsm.so
%{_libdir}/pkgconfig/*.pc

%changelog
%autochangelog
