%if 0%{?fedora}
%bcond_without mingw
%else
%bcond_with mingw
%endif

%global common_description %{expand:
Ogg Vorbis is a fully open, non-proprietary, patent- and royalty-free,
general-purpose compressed audio format for audio and music at fixed
and variable bitrates.

The libvorbis package contains runtime libraries for use in programs
that support Ogg Vorbis.}

%{!?_pkgdocdir: %global _pkgdocdir %{_docdir}/%{name}-%{version}}

Summary:	The Vorbis General Audio Compression Codec
Name:		libvorbis
Version:	1.3.7
Release:	%autorelease
Epoch:		1
License:	BSD-3-Clause
URL:		https://www.xiph.org/vorbis
Source:		https://downloads.xiph.org/releases/vorbis/%{name}-%{version}.tar.xz
Patch:		libvorbis-0001-Export-CMake-targets-to-the-build-tree.patch
Patch:		libvorbis-0002-Fix-pkgconfig-creation-with-cmake.patch
Patch:		libvorbis-0003-Add-tests-to-CMake-project.patch
Patch:		libvorbis-0004-CMake-Link-libm-to-test-binaries-if-available.patch
Patch:		libvorbis-0005-Update-minimum-cmake-version-from-3.0-to-3.6.patch
Patch:		libvorbis-0006-Specify-the-languages-used-by-CMake.patch
Patch:		libvorbis-0007-Windows-fix-syntax-error-in-.def-files.patch
Patch:		libvorbis-0008-Set-both-VERSION-and-SOVERSION-for-cmake-builds.patch
# Add a soversion to the mingw dlls (like the autotools build used to)
Patch:		libvorbis-mingw-sover.patch
BuildRequires:	cmake
BuildRequires:	gcc
BuildRequires:	pkgconfig(ogg) >= 1.0

%if %{with mingw}
BuildRequires:	mingw32-binutils
BuildRequires:	mingw32-filesystem >= 95
BuildRequires:	mingw32-gcc
BuildRequires:	mingw32-libogg

BuildRequires:	mingw64-binutils
BuildRequires:	mingw64-filesystem >= 95
BuildRequires:	mingw64-gcc
BuildRequires:	mingw64-libogg
%endif

%description
%{common_description}

%package devel
Summary: Development tools for Vorbis applications
Requires:	%{name}%{?_isa} = %{epoch}:%{version}-%{release}

%description devel
The libvorbis-devel package contains the header files and documentation
needed to develop applications with Ogg Vorbis.

%package devel-docs
Summary: Documentation for developing Vorbis applications
Requires: %{name}-devel = %{epoch}:%{version}-%{release}
BuildArch: noarch

%description devel-docs
Documentation for developing applications with libvorbis.

%package -n mingw32-%{name}
Summary: %{summary}

%description -n mingw32-%{name}
%{common_description}

This package is MinGW compiled %{name} library for the Win32 target.

%package -n mingw64-%{name}
Summary: %{summary}

%description -n mingw64-%{name}
%{common_description}

This package is MinGW compiled %{name} library for the Win64 target.

%{?mingw_debug_package}

%prep
%autosetup -p1

%build
%cmake -DCMAKE_POLICY_VERSION_MINIMUM=3.5
%cmake_build

%if %{with mingw}
%mingw_cmake -DCMAKE_POLICY_VERSION_MINIMUM=3.5
%mingw_make_build
%endif

%install
%cmake_install

# Not installed by CMake, but needed for building other packages that depend on libvorbis
install -D -p -m 0644 ./vorbis.m4 %{buildroot}%{_datadir}/aclocal/vorbis.m4

%if %{with mingw}
%mingw_make_install
# Not installed by CMake, but needed for building other packages that depend on libvorbis
install -D -p -m 0644 ./vorbis.m4 %{buildroot}%{mingw32_datadir}/aclocal/vorbis.m4
install -D -p -m 0644 ./vorbis.m4 %{buildroot}%{mingw64_datadir}/aclocal/vorbis.m4
%endif

%{?mingw_debug_install_post}

%check
%ctest

%files
%doc AUTHORS
%license COPYING
%{_libdir}/libvorbis.so.*
%{_libdir}/libvorbisenc.so.*
%{_libdir}/libvorbisfile.so.*

%files devel
%{_includedir}/vorbis
%{_libdir}/cmake/Vorbis/
%{_libdir}/libvorbis.so
%{_libdir}/libvorbisenc.so
%{_libdir}/libvorbisfile.so
%{_libdir}/pkgconfig/*.pc
%{_datadir}/aclocal/vorbis.m4

%files devel-docs
%{_pkgdocdir}/*

%if %{with mingw}
%files -n mingw32-%{name}
%license COPYING
%{mingw32_bindir}/libvorbis-0.dll
%{mingw32_bindir}/libvorbisenc-2.dll
%{mingw32_bindir}/libvorbisfile-3.dll
%{mingw32_includedir}/vorbis/
%{mingw32_libdir}/cmake/Vorbis/
%{mingw32_libdir}/libvorbis.dll.a
%{mingw32_libdir}/libvorbisenc.dll.a
%{mingw32_libdir}/libvorbisfile.dll.a
%{mingw32_libdir}/pkgconfig/vorbis.pc
%{mingw32_libdir}/pkgconfig/vorbisenc.pc
%{mingw32_libdir}/pkgconfig/vorbisfile.pc
%{mingw32_datadir}/aclocal/vorbis.m4

%files -n mingw64-%{name}
%license COPYING
%{mingw64_bindir}/libvorbis-0.dll
%{mingw64_bindir}/libvorbisenc-2.dll
%{mingw64_bindir}/libvorbisfile-3.dll
%{mingw64_includedir}/vorbis/
%{mingw64_libdir}/cmake/Vorbis/
%{mingw64_libdir}/libvorbis.dll.a
%{mingw64_libdir}/libvorbisenc.dll.a
%{mingw64_libdir}/libvorbisfile.dll.a
%{mingw64_libdir}/pkgconfig/vorbis.pc
%{mingw64_libdir}/pkgconfig/vorbisenc.pc
%{mingw64_libdir}/pkgconfig/vorbisfile.pc
%{mingw64_datadir}/aclocal/vorbis.m4
%endif

%autochangelog
