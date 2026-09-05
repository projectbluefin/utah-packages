%global real_name OpenJPH
%bcond mingw 1

Name:           openjph
Version:        0.31.0
Release:        %autorelease
Summary:        Open-source implementation of JPEG2000 Part-15 (or JPH or HTJ2K)
License:        BSD-2-Clause
URL:            https://openjph.org/
Source:         https://github.com/aous72/%{real_name}/archive/refs/tags/%{version}/%{real_name}-%{version}.tar.gz

# SSE2 intrinsics used in a file compiled with -msse only, breaks on i686/mingw builds
Patch:          0001-Use-SSE1-intrinsics-in-sse_mem_clear.patch

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(libtiff-4)

%if %{with mingw}
BuildRequires:  mingw32-filesystem
BuildRequires:  mingw32-gcc-c++
BuildRequires:  mingw32-libtiff

BuildRequires:  mingw64-filesystem
BuildRequires:  mingw64-gcc-c++
BuildRequires:  mingw64-libtiff
%endif


%description
Open source implementation of High-throughput JPEG2000 (HTJ2K), also known as
JPH, JPEG2000 Part 15, ISO/IEC 15444-15, and ITU-T T.814. Here, we are
interested in implementing the HTJ2K only, supporting features that are defined
in JPEG2000 Part 1. For example, for wavelet transform, only reversible 5/3 and
irreversible 9/7 are supported.

%package -n lib%{name}
Summary:        JPEG-2000 Part-15 library

%description -n lib%{name}
This package contains libopenjph, a library implementing the JPEG-2000
standard Part 15.

%package -n lib%{name}-devel
Summary:        Development files for libopenjph, a JPEG-2000 library
Requires:       pkgconfig(libjpeg)
Requires:       lib%{name}%{?_isa} = %{version}-%{release}

%description -n lib%{name}-devel
This package contains libopenjph, a library implementing the JPEG-2000
standard Part 15.

%if %{with mingw}
%package -n mingw32-lib%{name}
Summary:       MinGW Windows %{name} library
BuildArch:     noarch

%description -n mingw32-lib%{name}
%{summary}.


%package -n mingw32-%{name}
Summary:       MinGW Windows %{name} tools
Requires:      mingw32-lib%{name} = %{version}-%{release}
BuildArch:     noarch

%description -n mingw32-%{name}
%{summary}.


%package -n mingw64-lib%{name}
Summary:       MinGW Windows %{name} library
BuildArch:     noarch

%description -n mingw64-lib%{name}
%{summary}.


%package -n mingw64-%{name}
Summary:       MinGW Windows %{name} tools
Requires:      mingw64-lib%{name} = %{version}-%{release}
BuildArch:     noarch

%description -n mingw64-%{name}
%{summary}.


%{?mingw_debug_package}
%endif


%prep
%autosetup -n %{real_name}-%{version} -p1


%build
%cmake -DCMAKE_INSTALL_LIBDIR=%{_lib}
%cmake_build

%if %{with mingw}
%mingw_cmake -DCMAKE_DLL_NAME_WITH_SOVERSION=ON
%mingw_make_build
%endif


%install
%cmake_install
%if %{with mingw}
# MinGW build
%mingw_make_install

%mingw_debug_install_post
%endif


%files
%doc README.md
%{_bindir}/ojph_compress
%{_bindir}/ojph_expand

%files -n lib%{name}
%license LICENSE
%{_libdir}/lib%{name}.so.0.31
%{_libdir}/lib%{name}.so.%{version}

%files -n lib%{name}-devel
%{_includedir}/%{name}
%{_libdir}/cmake/%{name}
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%if %{with mingw}
%files -n mingw32-lib%{name}
%license LICENSE
%{mingw32_bindir}/lib%{name}-0.31.dll
%{mingw32_libdir}/lib%{name}.dll.a
%{mingw32_libdir}/cmake/%{name}
%{mingw32_libdir}/pkgconfig/%{name}.pc
%{mingw32_includedir}/%{name}/

%files -n mingw32-%{name}
%{mingw32_bindir}/ojph_compress.exe
%{mingw32_bindir}/ojph_expand.exe

%files -n mingw64-lib%{name}
%license LICENSE
%{mingw64_bindir}/lib%{name}-0.31.dll
%{mingw64_libdir}/lib%{name}.dll.a
%{mingw64_libdir}/cmake/%{name}
%{mingw64_libdir}/pkgconfig/%{name}.pc
%{mingw64_includedir}/%{name}/

%files -n mingw64-%{name}
%{mingw64_bindir}/ojph_compress.exe
%{mingw64_bindir}/ojph_expand.exe
%endif

%changelog
%autochangelog
