%global gdk_pixbuf2_version               2.36.5
%global gtk3_version                      3.3.6
%global gtk4_version                      4.12.0
%global glib2_version                     2.53.0
%global gsettings_desktop_schemas_version 3.27.0
%global po_package                        gnome-desktop-3.0

Name:    gnome-desktop3
Version: 51.0
Release: %autorelease
Summary: Library with common API for various GNOME modules

License: GPL-2.0-or-later AND LGPL-2.0-or-later AND GFDL-1.1-or-later
URL:     https://gitlab.gnome.org/GNOME/gnome-desktop
Source:  https://download.gnome.org/sources/gnome-desktop/%{gnome_major_version}/gnome-desktop-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildRequires: gcc
BuildRequires: gettext
BuildRequires: gtk-doc
BuildRequires: itstool
BuildRequires: meson
BuildRequires: pkgconfig(gdk-pixbuf-2.0) >= %{gdk_pixbuf2_version}
BuildRequires: pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(gobject-introspection-1.0)
BuildRequires: pkgconfig(gsettings-desktop-schemas) >= %{gsettings_desktop_schemas_version}
BuildRequires: pkgconfig(gtk+-3.0) >= %{gtk3_version}
BuildRequires: pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires: pkgconfig(iso-codes)
BuildRequires: pkgconfig(libseccomp)
BuildRequires: pkgconfig(libudev)
BuildRequires: pkgconfig(xkeyboard-config)
BuildRequires: python3
BuildRequires: python3dist(langtable)

%if !0%{?flatpak}
Requires: bubblewrap
%endif
Requires: gdk-pixbuf2%{?_isa} >= %{gdk_pixbuf2_version}
Requires: glib2%{?_isa} >= %{glib2_version}
# needed for GnomeWallClock
Requires: gsettings-desktop-schemas >= %{gsettings_desktop_schemas_version}

# GnomeBGSlideShow API change breaks older gnome-shell versions
Conflicts: gnome-shell < 3.33.4

%description
gnome-desktop3 contains the libgnome-desktop library as well as a data
file that exports the "GNOME" version to the Settings Details panel.

The libgnome-desktop library provides API shared by several applications
on the desktop, but that cannot live in the platform for various
reasons. There is no API or ABI guarantee, although we are doing our
best to provide stability. Documentation for the API is available with
gtk-doc.

%package devel
Summary: Libraries and headers for %{name}
License: LGPL-2.0-or-later
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package -n gnome-desktop4
Summary: Library with common API for various GNOME modules
License: GPL-2.0-or-later AND LGPL-2.0-or-later
# Depend on base package for translations, help, and version.
Requires: %{name}%{?_isa} = %{version}-%{release}

%description -n gnome-desktop4
gnome-desktop4 contains the libgnome-desktop library.

The libgnome-desktop library provides API shared by several applications
on the desktop, but that cannot live in the platform for various
reasons. There is no API or ABI guarantee, although we are doing our
best to provide stability.

%package -n gnome-desktop4-devel
Summary: Libraries and headers for gnome-desktop4
License: LGPL-2.0-or-later
Requires: gnome-desktop4%{?_isa} = %{version}-%{release}

%description -n gnome-desktop4-devel
The gnome-desktop4-devel package contains libraries and header files for
developing applications that use gnome-desktop4.

%package  tests
Summary:  Tests for the %{name} package
Requires: %{name}%{?_isa} = %{version}-%{release}

%description tests
The %{name}-tests package contains tests that can be used to verify
the functionality of the installed %{name} package.

%prep
%autosetup -p1 -n gnome-desktop-%{gnome_tarball_version}

%build
%meson -Dgtk_doc=true -Dinstalled_tests=true
%meson_build

%install
%meson_install

%find_lang %{po_package} --all-name --with-gnome

%files -f %{po_package}.lang
%doc AUTHORS NEWS README.md
%license COPYING COPYING.LIB
# LGPL
%{_libdir}/libgnome-desktop-3.so.21{,.*}
%{_libdir}/girepository-1.0/GnomeDesktop-3.0.typelib
%{_libexecdir}/gnome-desktop-debug/

%files devel
%{_libdir}/libgnome-desktop-3.so
%{_libdir}/pkgconfig/gnome-desktop-3.0.pc
%{_includedir}/gnome-desktop-3.0
%{_datadir}/gir-1.0/GnomeDesktop-3.0.gir
%dir %{_datadir}/gtk-doc/
%dir %{_datadir}/gtk-doc/html/
%doc %{_datadir}/gtk-doc/html/gnome-desktop3/

%files -n gnome-desktop4
%doc AUTHORS NEWS README.md
%license COPYING COPYING.LIB
# LGPL
%{_libdir}/libgnome-bg-4.so.2{,.*}
%{_libdir}/libgnome-desktop-4.so.2{,.*}
%{_libdir}/libgnome-qr-4.so.0{,.*}
%{_libdir}/libgnome-qr-gtk-4.so.0{,.*}
%{_libdir}/girepository-1.0/Gnome*-4.0.typelib

%files -n gnome-desktop4-devel
%{_libdir}/libgnome-*-4.so
%{_libdir}/pkgconfig/gnome-*-4.pc
%{_includedir}/gnome-desktop-4.0
%{_datadir}/gir-1.0/Gnome*-4.0.gir

%files tests
%{_libexecdir}/installed-tests/gnome-desktop
%{_datadir}/installed-tests

%changelog
%autochangelog
