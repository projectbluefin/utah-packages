%global glib2_minver 2.28

%global apimajor 1
%global apiver %{apimajor}
%global somajor 1

Name:           msgraph
Version:        0.3.5
Release:        %autorelease
Summary:        Library to access MS Graph API for Microsoft 365

License:        LGPL-3.0-or-later
URL:            https://gitlab.gnome.org/GNOME/msgraph
Source:         https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_minver}
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_minver}
BuildRequires:  pkgconfig(json-glib-1.0)
BuildRequires:  pkgconfig(rest-1.0)
BuildRequires:  pkgconfig(libsoup-3.0)
BuildRequires:  pkgconfig(goa-1.0)
BuildRequires:  pkgconfig(libuhttpmock-1.0) >= 0.11.0
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gtk-doc)
BuildRequires:  /usr/bin/gi-docgen
BuildRequires:  glib-networking

%description
libmsgraph is a GLib-based library for accessing online service APIs
using the MS Graph protocol.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package        doc
Summary:        Documentation files for %{name}
Enhances:       %{name}-devel = %{version}-%{release}
BuildArch:      noarch

%description    doc
The %{name}-doc package contains documentation for
developing applications that use %{name}.


%prep
%autosetup


%build
%meson
%meson_build


%install
%meson_install


%check
%meson_test


%files
%license COPYING
%doc README.md NEWS
%{_libdir}/lib%{name}-%{apimajor}.so.%{version}
%{_libdir}/lib%{name}-%{apimajor}.so.%{somajor}
%{_libdir}/girepository-1.0/Msg-%{apimajor}.typelib

%files devel
%{_includedir}/msg/
%{_libdir}/lib%{name}-%{apimajor}.so
%{_libdir}/pkgconfig/%{name}-%{apiver}.pc
%{_datadir}/gir-1.0/Msg-%{apimajor}.gir

%files doc
%{_docdir}/msgraph-%{apimajor}/


%changelog
%autochangelog
