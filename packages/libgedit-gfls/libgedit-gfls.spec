Name:           libgedit-gfls
Version:        0.5.1
Release:        %autorelease
Summary:        Gedit Technology File Loading and Saving library

License:        LGPL-3.0-or-later
URL:            https://gedit-text-editor.org/
Source:         https://gitlab.gnome.org/World/gedit/%{name}/-/archive/%{version}/%{name}-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  gtk-doc
BuildRequires:  meson >= 0.64
BuildRequires:  pkgconfig(gio-2.0) >= 2.78
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gtk+-3.0) >= 3.22

%description
libgedit-gfls is part of Gedit Technology. It is a module dedicated to file
loading and saving for the needs of gedit and other similar text editors.

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

%find_lang %{name}-1


%check
%meson_test


%files -f %{name}-1.lang
%license LICENSES/*
%doc NEWS README.md
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Gfls-1.typelib
%{_libdir}/libgedit-gfls-1.so.0{,.*}

%files devel
%{_includedir}/libgedit-gfls-1/
%{_libdir}/libgedit-gfls-1.so
%{_libdir}/pkgconfig/libgedit-gfls-1.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Gfls-1.gir
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/libgedit-gfls-1/


%changelog
%autochangelog
