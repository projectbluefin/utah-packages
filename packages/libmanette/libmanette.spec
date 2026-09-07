Name:           libmanette
Version:        0.2.13
Release:        %autorelease
Summary:        Game controller library

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/libmanette
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(hidapi-hidraw)
BuildRequires:  pkgconfig(libevdev)
BuildRequires:  vala

%description
libmanette is a small GObject library giving you simple access to game
controllers.

This library is intended for software needing a painless access to game
controllers from any programming language and with little dependencies.

It supports the de-facto standard gamepads as defined by the W3C standard
Gamepad specification or as implemented by the SDL GameController. More game
controller kinds could be supported in the future if needed. Mapping of the
devices is handled transparently and internally by the library using the
popular SDL mapping string format.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%doc NEWS README.md
%{_libdir}/girepository-1.0/
%{_libdir}/libmanette-0.2.so.0*

%files devel
%{_bindir}/manette-test
%{_includedir}/libmanette/
%{_libdir}/libmanette-0.2.so
%{_libdir}/pkgconfig/manette-0.2.pc
%{_datadir}/gir-1.0/
%{_datadir}/vala/

%changelog
%autochangelog
