Name:           gnome-autoar
Version:        0.5.2
Release:        %autorelease
Summary:        Archive library

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/gnome-autoar
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz


BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  gi-docgen
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(libarchive)
BuildRequires:  vala

%description
gnome-autoar is a GObject based library for handling archives.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1


%build
%meson -Dvapi=true \
       -Ddocs=true \
       -Dintrospection=enabled \
       -Dtests=true \
        %{nil}
%meson_build


%install
%meson_install


%check
%meson_test


%files
%license COPYING
%doc NEWS
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GnomeAutoar-0.1.typelib
%{_libdir}/libgnome-autoar-0.so.0*

%files devel
%{_includedir}/gnome-autoar-0/
%{_libdir}/pkgconfig/gnome-autoar-0.pc
%{_libdir}/*.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GnomeAutoar-0.1.gir
%{_datadir}/doc/%{name}
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gnome-autoar-0.vapi
%{_datadir}/vala/vapi/gnome-autoar-0.deps


%changelog
%autochangelog
