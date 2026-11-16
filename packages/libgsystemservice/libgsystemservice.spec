# libgsystemservice, the D-Bus system service helper library, as GNOME OS and
# Project Bluefin Dakota ship it.
#
# Fedora has no recipe. Written from gnome-build-meta's
# core-deps/libgsystemservice.bst (8a89846d, which Dakota bf271777 tracks):
# the 0.3.0 tag (commit f4c57646), meson with its defaults, which render the
# gtk-doc reference (the element build-depends on gtk-doc) and leave
# installed tests off.

Name:           libgsystemservice
Version:        0.3.0
Release:        1%{?dist}
Summary:        Common components for building D-Bus system services

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/pwithnall/libgsystemservice
Source0:        %{url}/-/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  gtk-doc
BuildRequires:  pkgconfig(gio-2.0) >= 2.71
BuildRequires:  pkgconfig(glib-2.0) >= 2.44
BuildRequires:  pkgconfig(gobject-2.0) >= 2.44
BuildRequires:  pkgconfig(libsystemd)
# The peer-manager test runs a private bus with GTestDBus.
BuildRequires:  dbus-daemon
BuildRequires:  pkgconfig(polkit-gobject-1)

%description
libgsystemservice provides common components for building D-Bus system
services: a service main loop with inactivity timeout and signal handling,
a peer manager that resolves D-Bus callers to processes, and a typed
configuration file loader.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, pkg-config file and API reference for developing against %{name}.

%prep
%autosetup

%build
%meson -Dgtk_doc=true -Dinstalled_tests=false
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING LICENSES/LGPL-2.1-or-later.txt
%doc NEWS README
%{_libdir}/libgsystemservice-0.so.0
%{_libdir}/libgsystemservice-0.so.%{version}

%files devel
%{_includedir}/gsystemservice-0/
%{_libdir}/libgsystemservice-0.so
%{_libdir}/pkgconfig/gsystemservice-0.pc
%{_datadir}/gtk-doc/html/libgsystemservice/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.3.0-1
- Initial recipe from gnome-build-meta core-deps/libgsystemservice.bst
