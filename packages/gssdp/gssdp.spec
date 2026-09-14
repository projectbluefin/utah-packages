Name:          gssdp
Version:       1.6.6
Release:       %autorelease
Summary:       Resource discovery and announcement over SSDP
License:       LGPL-2.1-or-later AND CC0-1.0
URL:           http://www.gupnp.org/
Source0:       https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: pkgconfig(gio-2.0)
BuildRequires: pkgconfig(gtk4)
BuildRequires: pkgconfig(libsoup-3.0)
BuildRequires: gi-docgen
BuildRequires: gobject-introspection-devel >= 1.36
BuildRequires: meson
BuildRequires: vala >= 0.20
BuildRequires: /usr/bin/pandoc

%description
GSSDP implements resource discovery and announcement over SSDP and is part
of gUPnP.  GUPnP is an object-oriented open source framework for creating
UPnP devices and control points, written in C using GObject and libsoup. The
GUPnP API is intended to be easy to use, efficient and flexible.

%package devel
Summary: Development package for gssdp
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with gssdp.

%package utils
Summary: Various GUI utuls for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description utils
This package contains GUI utilies for %{name}.

%package docs
Summary: Documentation files for %{name}
Requires: %{name} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends: gi-docgen-fonts
BuildArch: noarch

%description docs
This package contains developer documentation for %{name}.

%prep
%autosetup -p1

%build
%meson -Dgtk_doc=true
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING
%doc AUTHORS NEWS README.md
%{_libdir}/libgssdp-1.6.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GSSDP-1.6.typelib

%files devel
%{_includedir}/gssdp-1.6/
%{_libdir}/libgssdp-1.6.so
%{_libdir}/pkgconfig/gssdp-1.6.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GSSDP-1.6.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gssdp*

%files utils
%{_bindir}/gssdp-device-sniffer
%{_mandir}/man1/gssdp-device-sniffer.1*

%files docs
%{_docdir}/gssdp-1.6/

%changelog
%autochangelog
