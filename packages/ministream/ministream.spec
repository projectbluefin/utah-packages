# ministream, the small AppStream parser libadwaita's About dialog uses, as
# GNOME OS and Project Bluefin Dakota ship it.
#
# Fedora has no recipe. Written from gnome-build-meta's sdk/ministream.bst
# (8a89846d, which Dakota bf271777 tracks): the 0.99.1 release (tag commit
# baf2b7dc), meson with -Das-compare=disabled, GObject introspection on (the
# element build-depends on it), and the unit tests built, as the defaults are.

Name:           ministream
Version:        0.99.1
Release:        1%{?dist}
Summary:        Minimal AppStream metadata parser

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/ministream
Source0:        https://download.gnome.org/sources/%{name}/0.99/%{name}-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)

%description
Ministream is a small subset of libappstream. libadwaita uses it to fill in
its About dialog from the application's AppStream metainfo. Unlike
libappstream, it depends only on GLib.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, pkg-config file and GObject introspection data for developing
against %{name}.

%prep
%autosetup

%build
%meson -Das-compare=disabled -Dintrospection=enabled -Dtests=true
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING
%doc NEWS README
%{_libdir}/libministream.so.1
%{_libdir}/libministream.so.%{version}
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Ministream-1.typelib

%files devel
%{_includedir}/ministream/
%{_libdir}/libministream.so
%{_libdir}/pkgconfig/ministream.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Ministream-1.gir

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.99.1-1
- Initial recipe from gnome-build-meta sdk/ministream.bst
