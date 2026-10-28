# Utah targets Linux; do not build the optional Windows cross-compiled outputs.
%bcond mingw 0
# Work around linker failures on MinGW32 with MinGW C libraries version 14,
# https://bugzilla.redhat.com/show_bug.cgi?id=2481005, by omitting the
# mingw{32,64}-libdeflate-utils subpackages.
%bcond mingw_utils %[ 0%{?fedora} < 45 && 0%{?rhel} < 11 ]

Name:          libdeflate
Version:       1.26
Release:       %autorelease
Summary:       Fast implementation of DEFLATE, gzip, and zlib

# SPDX
License:       MIT
URL:           https://github.com/ebiggers/libdeflate
Source:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

# Add a library version to the mingw dll
Patch:         libdeflate-mingw-libver.patch

BuildRequires: gcc
BuildRequires: cmake

# For tests
BuildRequires: zlib-devel

%if %{with mingw}
BuildRequires: mingw32-filesystem
BuildRequires: mingw32-gcc

BuildRequires: mingw64-filesystem
BuildRequires: mingw64-gcc
%endif

%description
libdeflate is a library for fast, whole-buffer DEFLATE-based compression and
decompression, supporting DEFLATE, gzip, and zlib.

%package devel
Summary:       Development files for libdeflate
Requires:      %{name}%{?_isa} = %{version}-%{release}

%description devel
Development files for libdeflate.

%package utils
Summary:       Binaries from libdeflate
Requires:      %{name}%{?_isa} = %{version}-%{release}

%description utils
Binaries from libdeflate.

%if %{with mingw}
%package -n mingw32-%{name}
Summary:       MinGW Windows %{name} library
BuildArch:     noarch

%if %{without mingw_utils}
Obsoletes:     mingw32-%{name}-utils < 1.25-4
%endif

%description -n mingw32-%{name}
MinGW Windows %{name} library.

%if %{with mingw_utils}
%package -n mingw32-%{name}-utils
Summary:       MinGW Windows %{name} binaries
BuildArch:     noarch

%description -n mingw32-%{name}-utils
MinGW Windows %{name} binaries.
%endif

%package -n mingw64-%{name}
Summary:       MinGW Windows %{name} library
BuildArch:     noarch

%if %{without mingw_utils}
Obsoletes:     mingw64-%{name}-utils < 1.25-4
%endif

%description -n mingw64-%{name}
MinGW Windows %{name} library.

%if %{with mingw_utils}
%package -n mingw64-%{name}-utils
Summary:       MinGW Windows %{name} binaries
BuildArch:     noarch

%description -n mingw64-%{name}-utils
MinGW Windows %{name} binaries.
%endif

%{?mingw_debug_package}
%endif


%prep
%autosetup -p1

%build
cmake_opts="\
    -DLIBDEFLATE_BUILD_STATIC_LIB:BOOL=OFF \
    -DLIBDEFLATE_BUILD_SHARED_LIB:BOOL=ON \
    -DLIBDEFLATE_COMPRESSION_SUPPORT:BOOL=ON \
    -DLIBDEFLATE_DECOMPRESSION_SUPPORT:BOOL=ON \
    -DLIBDEFLATE_ZLIB_SUPPORT:BOOL=ON \
    -DLIBDEFLATE_GZIP_SUPPORT:BOOL=ON \
    -DLIBDEFLATE_FREESTANDING:BOOL=OFF \
    -DLIBDEFLATE_BUILD_GZIP:BOOL=ON \
    -DLIBDEFLATE_USE_SHARED_LIBS:BOOL=ON"

# Native build
%cmake $cmake_opts -DLIBDEFLATE_BUILD_TESTS:BOOL=ON
%cmake_build

%if %{with mingw}
# MinGW build
%mingw_cmake $cmake_opts \
%if %{without mingw_utils}
    -DLIBDEFLATE_BUILD_GZIP:BOOL=OFF \
%endif
    -DLIBDEFLATE_BUILD_TESTS:BOOL=OFF
%mingw_make
%endif

%install
# Native build
%cmake_install

%if %{with mingw}
# MinGW Build
%mingw_make_install
%mingw_debug_install_post
%endif

%check
%ctest

%files
%doc NEWS.md README.md
%license COPYING
%{_libdir}/libdeflate.so.0

%files devel
%{_includedir}/libdeflate.h
%{_libdir}/libdeflate.so
%{_libdir}/pkgconfig/libdeflate.pc
%{_libdir}/cmake/libdeflate/

%files utils
%{_bindir}/libdeflate-gzip
%{_bindir}/libdeflate-gunzip

%if %{with mingw}
%files -n mingw32-%{name}
%{mingw32_bindir}/libdeflate-0.dll
%{mingw32_libdir}/libdeflate.dll.a
%{mingw32_libdir}/pkgconfig/libdeflate.pc
%{mingw32_libdir}/cmake/libdeflate/
%{mingw32_includedir}/libdeflate.h

%if %{with mingw_utils}
%files -n mingw32-%{name}-utils
%{mingw32_bindir}/libdeflate-gzip.exe
%{mingw32_bindir}/libdeflate-gunzip.exe
%endif

%files -n mingw64-%{name}
%{mingw64_bindir}/libdeflate-0.dll
%{mingw64_libdir}/libdeflate.dll.a
%{mingw64_libdir}/pkgconfig/libdeflate.pc
%{mingw64_libdir}/cmake/libdeflate/
%{mingw64_includedir}/libdeflate.h

%if %{with mingw_utils}
%files -n mingw64-%{name}-utils
%{mingw64_bindir}/libdeflate-gzip.exe
%{mingw64_bindir}/libdeflate-gunzip.exe
%endif
%endif

%changelog
%autochangelog
