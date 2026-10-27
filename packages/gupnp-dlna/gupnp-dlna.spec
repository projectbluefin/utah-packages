Name:          gupnp-dlna
Version:       0.12.0
Release:       %autorelease
Summary:       A collection of helpers for building UPnP AV applications
License:       LGPL-2.0-or-later
URL:           http://www.gupnp.org/
Source0:       https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: glib2-devel
BuildRequires: gobject-introspection-devel
BuildRequires: gssdp-devel
BuildRequires: gstreamer1-devel
BuildRequires: gstreamer1-plugins-base-devel
BuildRequires: gtk-doc
BuildRequires: gupnp-av-devel
BuildRequires: gupnp-devel
BuildRequires: libxml2-devel
BuildRequires: meson
BuildRequires: vala

%description
GUPnP is an object-oriented open source framework for creating UPnP
devices and control points, written in C using GObject and libsoup.
The GUPnP API is intended to be easy to use, efficient and flexible.

GUPnP-dlna is a collection of helpers for building DLNA (Digital 
Living Network Alliance) compliant applications using GUPnP.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Contains libraries and header files for developing applications that 
use %{name}.

%package docs
Summary: Development package for %{name}
Requires: %{name} = %{version}-%{release}
BuildArch: noarch

%description docs
Contains developer documentation for %{name}.

%prep
%setup -q

%build
%meson -Dgtk_doc=true
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING
%doc AUTHORS README TODO
%{_bindir}/gupnp-dlna*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GUPnPDLNA-2.0.typelib
%{_libdir}/girepository-1.0/GUPnPDLNAGst-2.0.typelib
%{_libdir}/libgupnp-dlna-2.0.so.4*
%{_libdir}/libgupnp-dlna-gst-2.0.so.4*
%dir %{_libdir}/gupnp-dlna/
%{_libdir}/gupnp-dlna/libgstreamer.so
%{_datadir}/gupnp-dlna-2.0/

%files devel
%{_includedir}/gupnp-dlna-2.0/
%{_libdir}/lib*.so
%{_libdir}/pkgconfig/gupnp-dlna-2.0.pc
%{_libdir}/pkgconfig/gupnp-dlna-gst-2.0.pc
%{_libdir}/pkgconfig/gupnp-dlna-metadata-2.0.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GUPnPDLNA-2.0.gir
%{_datadir}/gir-1.0/GUPnPDLNAGst-2.0.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gupnp-dlna*

%files docs
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/gupnp-dlna
%{_datadir}/gtk-doc/html/gupnp-dlna-gst
%{_datadir}/gtk-doc/html/gupnp-dlna-metadata

%changelog
%autochangelog
