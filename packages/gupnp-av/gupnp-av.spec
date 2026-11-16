Name:          gupnp-av
Version:       0.14.5
Release:       %autorelease
Summary:       A collection of helpers for building UPnP AV applications
License:       LGPL-2.1-or-later AND CC0-1.0
URL:           http://www.gupnp.org/
Source0:       https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: gi-docgen
BuildRequires: gobject-introspection-devel
BuildRequires: gtk-doc
BuildRequires: meson
BuildRequires: vala
BuildRequires: pkgconfig(glib-2.0)
BuildRequires: pkgconfig(libxml-2.0)

%description
GUPnP is an object-oriented open source framework for creating UPnP
devices and control points, written in C using GObject and libsoup.
The GUPnP API is intended to be easy to use, efficient and flexible.

GUPnP-AV is a collection of helpers for building AV (audio/video)
applications using GUPnP.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with %{name}.

%package docs
Summary: Documentation files for %{name}
Requires: %{name} = %{version}-%{release}
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
%{_libdir}/libgupnp-av-1.0.so.3*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GUPnPAV-1.0.typelib
%{_datadir}/gupnp-av/

%files devel
%{_includedir}/gupnp-av-1.0/
%{_libdir}/pkgconfig/gupnp-av-1.0.pc
%{_libdir}/libgupnp-av-1.0.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GUPnPAV-1.0.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gupnp-av*

%files docs
%dir %{_datadir}/doc
%{_datadir}/doc/gupnp-av-1.0/

%changelog
%autochangelog
