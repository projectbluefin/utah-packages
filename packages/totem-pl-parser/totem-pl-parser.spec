Name:		totem-pl-parser
Version:	3.26.7
Release:	%autorelease
Summary:	Totem Playlist Parser library
License:	LGPL-2.0-or-later AND (LGPL-2.1-or-later WITH GStreamer-exception-2005)
Url:		https://wiki.gnome.org/Apps/Videos
Source0:	https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:	glib2-devel
BuildRequires:	libxml2-devel
BuildRequires:	gobject-introspection-devel
BuildRequires:	gettext
BuildRequires:	gtk-doc
BuildRequires:	libarchive-devel
BuildRequires:	libgcrypt-devel
BuildRequires:	uchardet-devel
BuildRequires:	meson

%description
A library to parse and save playlists, as used in music and movie players.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%meson -Denable-gtk-doc=true \
	-Denable-libarchive=yes \
	-Denable-libgcrypt=yes \
	-Dintrospection=true
%meson_build

%install
%meson_install

%find_lang %{name} --with-gnome

%ldconfig_scriptlets

%files -f %{name}.lang
%license COPYING.LIB
%doc AUTHORS NEWS README.md
%{_libdir}/*.so.*
%{_libdir}/girepository-1.0/*.typelib
%{_libexecdir}/totem-pl-parser/

%files devel
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/*.pc
%{_datadir}/gtk-doc/html/totem-pl-parser
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/*.gir

%changelog
%autochangelog
