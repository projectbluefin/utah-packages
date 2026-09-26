%global with_mingw 0

%if 0%{?fedora} && !0%{?flatpak}
%global with_mingw 1
%endif

Name: libgsf
Version: 1.14.59
Release: %autorelease
Summary: GNOME Structured File library

License: LGPL-2.1-only
URL:     https://gitlab.gnome.org/GNOME/libgsf/
Source:  https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: bzip2-devel
BuildRequires: chrpath
BuildRequires: gettext
BuildRequires: intltool
BuildRequires: make
BuildRequires: pkgconfig(gdk-pixbuf-2.0)
BuildRequires: pkgconfig(gio-2.0)
BuildRequires: pkgconfig(gobject-introspection-1.0)
BuildRequires: pkgconfig(libxml-2.0)

Obsoletes: libgsf-gnome < 1.14.22
Obsoletes: libgsf-python < 1.14.26

%if %{with_mingw}
BuildRequires: mingw32-filesystem >= 95
BuildRequires: mingw32-gcc-c++
BuildRequires: mingw64-filesystem >= 95
BuildRequires: mingw64-gcc-c++

BuildRequires: mingw64-bzip2
BuildRequires: mingw32-bzip2
BuildRequires: mingw64-glib2
BuildRequires: mingw32-glib2
BuildRequires: mingw64-libxml2
BuildRequires: mingw32-libxml2
%endif

%description
A library for reading and writing structured files (e.g. MS OLE and Zip)

%package devel
Summary: Support files necessary to compile applications with libgsf
Requires: libgsf = %{version}-%{release}, glib2-devel, libxml2-devel
Requires: pkgconfig
Obsoletes: libgsf-gnome-devel < 1.14.22

%description devel
Libraries, headers, and support files necessary to compile applications using
libgsf.

%if %{with_mingw}
%package -n mingw32-libgsf
Summary: MinGW GNOME Structured File library
BuildArch: noarch

%description -n mingw32-libgsf
A library for reading and writing structured files (e.g. MS OLE and Zip)

%package -n mingw64-libgsf
Summary: MinGW GNOME Structured File library
BuildArch: noarch

%description -n mingw64-libgsf
A library for reading and writing structured files (e.g. MS OLE and Zip)

%{?mingw_debug_package}
%endif

%prep
%autosetup -p1

%build
%global _configure ../configure

mkdir -p build/doc && pushd build
ln -s ../../doc/html doc # some day meson... libgsf!4
%configure --disable-gtk-doc --disable-static --enable-introspection=yes \
%if 0%{?flatpak}
--with-typelib_dir=%{_libdir}/girepository-1.0 --with-gir-dir=%{_datadir}/gir-1.0
%endif

%make_build
popd

%if %{with_mingw}
%mingw_configure --disable-static
%mingw_make_build
%endif

%install
export GCONF_DISABLE_MAKEFILE_SCHEMA_INSTALL=1
pushd build
%make_install
popd

%find_lang %{name}

%if %{with_mingw}
%mingw_make_install
%mingw_debug_install_post
%mingw_find_lang %{name} --all-name
%endif

# Remove lib rpaths
chrpath --delete %{buildroot}%{_bindir}/gsf*

# Remove .la files
find %{buildroot} -name '*.la' -delete -print

%ldconfig_scriptlets

%files -f libgsf.lang
%doc AUTHORS README
%license COPYING
%{_libdir}/libgsf-1.so.*
%{_libdir}/girepository-1.0/Gsf-1.typelib
%{_bindir}/gsf-office-thumbnailer
%{_mandir}/man1/gsf-office-thumbnailer.1*
%dir %{_datadir}/thumbnailers
%{_datadir}/thumbnailers/gsf-office.thumbnailer

%files devel
%{_bindir}/gsf
%{_bindir}/gsf-vba-dump
%{_libdir}/libgsf-1.so
%{_libdir}/pkgconfig/libgsf-1.pc
%dir %{_includedir}/libgsf-1
%{_includedir}/libgsf-1/gsf
%{_datadir}/gtk-doc/html/gsf
%{_datadir}/gir-1.0/Gsf-1.gir
%{_mandir}/man1/gsf.1*
%{_mandir}/man1/gsf-vba-dump.1*

%if %{with_mingw}
%files -n mingw32-libgsf -f mingw32-libgsf.lang
%license COPYING
%{mingw32_bindir}/gsf.exe
%{mingw32_bindir}/gsf-vba-dump.exe
%{mingw32_bindir}/gsf-office-thumbnailer.exe
%{mingw32_bindir}/libgsf-1-114.dll
%{mingw32_bindir}/libgsf-win32-1-114.dll
%{mingw32_libdir}/libgsf-1.dll.a
%{mingw32_libdir}/libgsf-win32-1.dll.a
%{mingw32_libdir}/pkgconfig/libgsf-1.pc
%{mingw32_libdir}/pkgconfig/libgsf-win32-1.pc
%{mingw32_includedir}/libgsf-1/
%{mingw32_mandir}/man1/gsf.1*
%{mingw32_mandir}/man1/gsf-vba-dump.1*
%{mingw32_mandir}/man1/gsf-office-thumbnailer.1*
%{mingw32_datadir}/thumbnailers/gsf-office.thumbnailer

%files -n mingw64-libgsf -f mingw64-libgsf.lang
%license COPYING
%{mingw64_bindir}/gsf.exe
%{mingw64_bindir}/gsf-vba-dump.exe
%{mingw64_bindir}/gsf-office-thumbnailer.exe
%{mingw64_bindir}/libgsf-1-114.dll
%{mingw64_bindir}/libgsf-win32-1-114.dll
%{mingw64_libdir}/libgsf-1.dll.a
%{mingw64_libdir}/libgsf-win32-1.dll.a
%{mingw64_libdir}/pkgconfig/libgsf-1.pc
%{mingw64_libdir}/pkgconfig/libgsf-win32-1.pc
%{mingw64_includedir}/libgsf-1/
%{mingw64_mandir}/man1/gsf.1*
%{mingw64_mandir}/man1/gsf-vba-dump.1*
%{mingw64_mandir}/man1/gsf-office-thumbnailer.1*
%{mingw64_datadir}/thumbnailers/gsf-office.thumbnailer
%endif

%changelog
%autochangelog
