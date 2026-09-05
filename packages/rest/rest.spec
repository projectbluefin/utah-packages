Name:          rest
Version:       0.10.2
Release:       %autorelease
Summary:       A library for access to RESTful web services

License:       LGPL-2.1-only
URL:           https://gitlab.gnome.org/GNOME/librest
Source0:       https://download.gnome.org/sources/librest/%{gnome_major_minor_version}/librest-%{version}.tar.xz

Patch0: CVE-2026-16615.patch

BuildRequires: meson
BuildRequires: pkgconfig(glib-2.0)
BuildRequires: pkgconfig(gio-2.0)
BuildRequires: pkgconfig(gobject-introspection-1.0)
BuildRequires: pkgconfig(libsoup-3.0)
BuildRequires: pkgconfig(libxml-2.0)
BuildRequires: pkgconfig(json-glib-1.0)
BuildRequires: pkgconfig(libadwaita-1)
BuildRequires: pkgconfig(gtksourceview-5)
BuildRequires: pkgconfig(gi-docgen)

%description
This library was designed to make it easier to access web services that
claim to be "RESTful". A RESTful service should have urls that represent
remote objects, which methods can then be called on. The majority of services
don't actually adhere to this strict definition. Instead, their RESTful end
point usually has an API that is just simpler to use compared to other types
of APIs they may support (XML-RPC, for instance). It is this kind of API that
this library is attempting to support.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends: gi-docgen-fonts

%description devel
Files for development with %{name}.

%package demo
Summary: Demo application for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description demo
Demo application for %{name}.

%prep
%autosetup -p1 -n librest-%{version} -S gendiff

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%doc AUTHORS README.md
%{_libdir}/librest-1.0.so.0*
%{_libdir}/librest-extras-1.0.so.0*
%{_libdir}/girepository-1.0/Rest-1.0.typelib
%{_libdir}/girepository-1.0/RestExtras-1.0.typelib

%files devel
%{_includedir}/rest-1.0/
%{_libdir}/pkgconfig/rest-1.0.pc
%{_libdir}/pkgconfig/rest-extras-1.0.pc
%{_libdir}/librest-1.0.so
%{_libdir}/librest-extras-1.0.so
%{_datadir}/doc/librest-1.0/
%{_datadir}/gir-1.0/Rest-1.0.gir
%{_datadir}/gir-1.0/RestExtras-1.0.gir

%files demo
%{_bindir}/librest-demo
%{_datadir}/applications/org.gnome.RestDemo.desktop

%changelog
%autochangelog
