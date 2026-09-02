%global api_version 0.3

Name:           libcloudproviders
Summary:        Library for integration of cloud storage providers
Version:        0.4.1
Release:        %autorelease
License:        LGPL-3.0-or-later

URL:            https://gitlab.gnome.org/GNOME/libcloudproviders
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  gtk-doc
BuildRequires:  meson
BuildRequires:  vala

BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gi-docgen)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)

%description
Cross desktop library for desktop integration of cloud storage providers
and sync tools.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1


%build
%meson -Denable-gtk-doc=true
%meson_build


%install
%meson_install


%files
%license LICENSE
%doc CHANGELOG README.md
%{_libdir}/libcloudproviders.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/CloudProviders-%{api_version}.typelib

%files devel
%{_includedir}/cloudproviders/
%{_libdir}/pkgconfig/cloudproviders.pc
%{_libdir}/libcloudproviders.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/CloudProviders-%{api_version}.gir
%{_datadir}/doc/
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/cloudproviders.*


%changelog
%autochangelog
