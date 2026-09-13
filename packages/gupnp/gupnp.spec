%global apiver 1.6

%global gssdp_version 1.6.2

Name:          gupnp
Version:       1.6.10
Release:       %autorelease
Summary:       A framework for creating UPnP devices & control points

License:       LGPL-2.1-or-later
URL:           https://www.gupnp.org/
Source0:       https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: docbook-style-xsl
BuildRequires: gi-docgen
BuildRequires: gobject-introspection-devel
BuildRequires: meson
BuildRequires: vala
BuildRequires: /usr/bin/xsltproc
BuildRequires: pkgconfig(gssdp-1.6) >= %{gssdp_version}
BuildRequires: pkgconfig(libsoup-3.0)
BuildRequires: pkgconfig(libxml-2.0)
BuildRequires: pkgconfig(uuid)

Requires: dbus
Requires: gssdp%{?_isa} >= %{gssdp_version}

%description
GUPnP is an object-oriented open source framework for creating UPnP 
devices and control points, written in C using GObject and libsoup. 
The GUPnP API is intended to be easy to use, efficient and flexible. 

%package devel
Summary: Development package for gupnp
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
%meson \
  -Dcontext_manager=network-manager \
  -Dgtk_doc=true \
  -Dexamples=false \
  %{nil}
%meson_build

%install
%meson_install

%check
%meson_test --timeout-multiplier 2

%files
%license COPYING
%doc AUTHORS README.md
%{_libdir}/libgupnp-%{apiver}.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GUPnP-%{apiver}.typelib

%files devel
%{_bindir}/gupnp-binding-tool-%{apiver}
%{_includedir}/gupnp-%{apiver}/
%{_libdir}/libgupnp-%{apiver}.so
%{_libdir}/pkgconfig/gupnp-%{apiver}.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GUPnP-%{apiver}.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gupnp*
%{_mandir}/man1/gupnp-binding-tool-%{apiver}.1*

%files docs
%{_docdir}/gupnp-%{apiver}/

%changelog
%autochangelog
