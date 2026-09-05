Name:           gupnp-igd
Version:        1.6.0
Release:        %autorelease
Summary:        Library to handle UPnP IGD port mapping

License:        LGPL-2.1-or-later
URL:            https://wiki.gnome.org/Projects/GUPnP
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gupnp-1.6)
BuildRequires:  gobject-introspection-devel
BuildRequires:  gtk-doc
BuildRequires:  meson

%description
%{name} is a library to handle UPnP IGD port mapping.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1


%build
%meson -Dgtk_doc=true
%meson_build


%install
%meson_install


%files
%license COPYING
%doc NEWS README
%{_libdir}/libgupnp-igd-1.6.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GUPnPIgd-1.6.typelib


%files devel
%{_includedir}/*
%{_libdir}/libgupnp-igd-1.6.so
%{_libdir}/pkgconfig/%{name}-1.6*.pc
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/%{name}/
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GUPnPIgd-1.6.gir


%changelog
%autochangelog
