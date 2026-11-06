%global glib2_version 2.86.0
%global gobject_introspection_version 1.72.0
%global mozjs140_version 140.13.0

Name:           gjs
Version:        1.90.1
Release:        %autorelease
Summary:        Javascript Bindings for GNOME

# The following files contain code from Mozilla which
# is triple licensed under MPL-1.1/GPL-2.0-or-later/LGPL-2.1-or-later:
# The console module (modules/console.c)
# Stack printer (gjs/stack.c)
# modules/esm/_encoding/util.js and few other things are MIT
# modules/script/tweener/equations.js is BSD-3-Clause
License:        MIT AND BSD-3-Clause AND (MIT OR LGPL-2.0-or-later) AND (MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later)
URL:            https://wiki.gnome.org/Projects/Gjs
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  gettext
BuildRequires:  readline-devel
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gobject-introspection-1.0) >= %{gobject_introspection_version}
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(mozjs-140) >= %{mozjs140_version}
BuildRequires:  pkgconfig(sysprof-capture-4)
# For GTK+ 3 tests
BuildRequires:  gtk3
# For dbus tests
BuildRequires:  /usr/bin/dbus-run-session
#dbus-x11, xwfb, mesa-dri-drivers for test suite
BuildRequires:  dbus-x11
BuildRequires:  mesa-dri-drivers
BuildRequires:  mutter
BuildRequires:  xwayland-run

Requires: glib2%{?_isa} >= %{glib2_version}
Requires: gobject-introspection%{?_isa} >= %{gobject_introspection_version}
Requires: mozjs140%{?_isa} >= %{mozjs140_version}

%description
Gjs allows using GNOME libraries from Javascript. It's based on the
Spidermonkey Javascript engine from Mozilla and the GObject introspection
framework.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with %{name}.

%package tests
Summary: Tests for the gjs package
# installed-tests/js/modules/encodings.json is BSD-3-Clause
License: MIT AND (MIT OR LGPL-2.0-or-later) AND BSD-3-Clause
Requires: %{name}%{?_isa} = %{version}-%{release}

%description tests
The gjs-tests package contains tests that can be used to verify
the functionality of the installed gjs package.

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%check
# testGtk4.js requires a running org.freedesktop.portal.Desktop D-Bus service,
# which the hermetic Hummingbird buildroot does not provide. Skip the GTK
# suite; the rest of the meson tests still run.
%meson_test --timeout-multiplier=5 --suite ",!gtk"

%files
%license COPYING
%doc NEWS README.md
%{_bindir}/gjs
%{_bindir}/gjs-console
%{_libdir}/gjs/
%{_libdir}/libgjs.so.0*

%files devel
%doc examples/*
%{_includedir}/gjs-1.0
%{_libdir}/pkgconfig/gjs-1.0.pc
%{_libdir}/libgjs.so
%dir %{_datadir}/gjs-1.0
%{_datadir}/gjs-1.0/lsan/
%{_datadir}/gjs-1.0/valgrind/

%files tests
%{_libexecdir}/installed-tests/
%{_datadir}/glib-2.0/schemas/org.gnome.GjsTest.gschema.xml
%{_datadir}/installed-tests/

%changelog
%autochangelog
