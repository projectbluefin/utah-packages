Name:           libspelling
Version:        0.4.11
Release:        %autorelease
Summary:        Spellcheck library for GTK 4
License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/libspelling
Source:         https://download.gnome.org/sources/libspelling/0.4/libspelling-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(gtksourceview-5)
BuildRequires:  pkgconfig(enchant-2)
BuildRequires:  pkgconfig(icu-uc)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
# for vapigen
BuildRequires:  vala
BuildRequires:  gi-docgen


%description
A spellcheck library for GTK 4.  This library is heavily based upon GNOME Text
Editor and GNOME Builder's spellcheck implementation.


%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}


%description devel
The %{name}-devel package contains libraries and header files for developing
applications that use %{name}.


%prep
%autosetup -n libspelling-%{version}


%build
%meson -Ddocs=false
%meson_build


%install
%meson_install
%find_lang libspelling


%check
%meson_test


%files -f libspelling.lang
%license COPYING
%doc NEWS
%{_libdir}/libspelling-1.so.2*
%{_libdir}/girepository-1.0/Spelling-1.typelib


%files devel
%{_includedir}/libspelling-1
%{_libdir}/libspelling-1.so
%{_libdir}/pkgconfig/libspelling-1.pc
%{_datadir}/gir-1.0/Spelling-1.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libspelling-1.deps
%{_datadir}/vala/vapi/libspelling-1.vapi


%changelog
%autochangelog
