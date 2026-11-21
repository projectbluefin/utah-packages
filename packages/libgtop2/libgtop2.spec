Name:           libgtop2
Version:        2.41.4
Release:        %autorelease
Summary:        LibGTop library (version 2)

License:        GPL-2.0-or-later
URL:            https://download.gnome.org/sources/libgtop
Source0:        https://download.gnome.org/sources/libgtop/%{gnome_major_minor_version}/libgtop-%{version}.tar.xz

BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  gettext
BuildRequires:  make

%description
LibGTop is a library for portably obtaining information about processes,
such as their PID, memory usage, etc.

%package        devel
Summary:        Libraries and include files for developing with libgtop
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
This package provides the necessary development libraries and include
files to allow you to develop with LibGTop.

%prep
%autosetup -p1 -n libgtop-%{version}

%build
%configure --disable-gtk-doc --disable-static
%make_build

%install
%make_install
find %{buildroot} -name '*.la' -print -delete


%find_lang libgtop

%ldconfig_scriptlets

%files -f libgtop.lang
%doc AUTHORS NEWS README
%license COPYING
%{_libexecdir}/libgtop_daemon2
# Strip the suid bit.
%attr(755, -, -)%{_libexecdir}/libgtop_server2
%{_libdir}/libgtop-2.0.so.11*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GTop-2.0.typelib

%files devel
%{_libdir}/libgtop-2.0.so
%{_includedir}/libgtop-2.0
%{_libdir}/pkgconfig/libgtop-2.0.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GTop-2.0.gir
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/libgtop
# not worth fooling with
%exclude %{_datadir}/info

%changelog
%autochangelog
