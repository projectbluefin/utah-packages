%bcond mingw %{defined fedora}
%bcond stemmer %{defined fedora}

%global glib2_version 2.45.8

Summary:   Library for querying compressed XML metadata
Name:      libxmlb
Version:   0.3.29
Release:   %autorelease
License:   LGPL-2.1-or-later
URL:       https://github.com/hughsie/%{name}
Source0:   https://github.com/hughsie/%{name}/releases/download/%{version}/%{name}-%{version}.tar.xz

BuildRequires: glib2-devel >= %{glib2_version}
BuildRequires: gtk-doc
%if %{with stemmer}
BuildRequires: libstemmer-devel
%endif
BuildRequires: meson
BuildRequires: gobject-introspection-devel
BuildRequires: xz-devel
BuildRequires: libzstd-devel
BuildRequires: python3-setuptools

%if %{with mingw}
BuildRequires: mingw32-filesystem >= 95
BuildRequires: mingw32-gcc-c++
BuildRequires: mingw32-glib2
BuildRequires: mingw32-xz
BuildRequires: mingw32-zstd

BuildRequires: mingw64-filesystem >= 95
BuildRequires: mingw64-gcc-c++
BuildRequires: mingw64-glib2
BuildRequires: mingw64-xz
BuildRequires: mingw64-zstd
%endif

# needed for the self tests
BuildRequires: shared-mime-info

Requires: glib2%{?_isa} >= %{glib2_version}
Requires: shared-mime-info

%description
XML is slow to parse and strings inside the document cannot be memory mapped as
they do not have a trailing NUL char. The libxmlb library takes XML source, and
converts it to a structured binary representation with a deduplicated string
table -- where the strings have the NULs included.

This allows an application to mmap the binary XML file, do an XPath query and
return some strings without actually parsing the entire document. This is all
done using (almost) zero allocations and no actual copying of the binary data.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with %{name}.

%package tests
Summary: Files for installed tests

%description tests
Executable and data files for installed tests.

%if %{with mingw}
%package -n mingw32-libxmlb
Summary: MinGW library for querying compressed XML metadata
BuildArch: noarch

%description -n mingw32-libxmlb
MinGW32 libxmlb library.

%package -n mingw64-libxmlb
Summary: MinGW library for querying compressed XML metadata
BuildArch: noarch

%description -n mingw64-libxmlb
MinGW64 libxmlb library.

%{?mingw_debug_package}
%endif

%prep
%autosetup -p1

%build

%meson \
    -Dgtkdoc=true \
    -Dtests=true

%meson_build

%if %{with mingw}
%mingw_meson -Dintrospection=false -Dtests=false -Dgtkdoc=false
%mingw_ninja
%endif

%check
%meson_test

%install
%meson_install

%if %{with mingw}
%mingw_ninja_install
%mingw_debug_install_post
rm -f $RPM_BUILD_ROOT/%{mingw32_mandir}/man1/xb-tool.1*
rm -f $RPM_BUILD_ROOT/%{mingw64_mandir}/man1/xb-tool.1*
%endif

%files
%doc README.md
%license LICENSE
%{_bindir}/xb-tool
%{_mandir}/man1/xb-tool.1*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Xmlb-2.0.typelib
%{_libdir}/libxmlb.so.2*

%files devel
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Xmlb-2.0.gir
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/libxmlb
%{_includedir}/libxmlb-2
%{_libdir}/libxmlb.so
%{_libdir}/pkgconfig/xmlb.pc

%files tests
%dir %{_libexecdir}/installed-tests/libxmlb
%{_libexecdir}/installed-tests/libxmlb/xb-self-test
%{_libexecdir}/installed-tests/libxmlb/test.*
%dir %{_datadir}/installed-tests/libxmlb
%{_datadir}/installed-tests/libxmlb/libxmlb.test

%if %{with mingw}
%files -n mingw32-libxmlb
%license LICENSE
%{mingw32_bindir}/xb-tool.exe
%{mingw32_bindir}/libxmlb-2.dll
%{mingw32_libdir}/libxmlb.dll.a
%{mingw32_includedir}/libxmlb-2
%{mingw32_libdir}/pkgconfig/xmlb.pc

%files -n mingw64-libxmlb
%license LICENSE
%{mingw64_bindir}/xb-tool.exe
%{mingw64_bindir}/libxmlb-2.dll
%{mingw64_libdir}/libxmlb.dll.a
%{mingw64_includedir}/libxmlb-2
%{mingw64_libdir}/pkgconfig/xmlb.pc
%endif

%changelog
%autochangelog
