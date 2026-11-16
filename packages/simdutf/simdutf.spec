%global lib_ver 34.0.0
%global so_ver 34
Name:		simdutf
Version:	9.0.0
Release:	%autorelease
Summary:	Unicode validation and transcoding at billions of characters per second

License:	Apache-2.0 AND BSD-3-Clause
URL:		https://github.com/simdutf/simdutf
Source0:	%{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildRequires:	cmake
BuildRequires:	gcc-c++
BuildRequires:	make
%ifnarch %{arm}
BuildRequires:	libasan
%endif

%description
Unicode (UTF8, UTF16, UTF32) validation and transcoding at billions of 
characters per second using SSE2, AVX2, NEON, AVX-512.

%package devel
Summary: Development files for %{name}
Requires:	%{name} = %{version}-%{release}

%description devel
The package contains libraries and header files for developing applications
that use %{name}.

%prep
%autosetup -p1

%build
%cmake \
	-DCMAKE_BUILD_TYPE=Release \
	-DSIMDUTF_BENCHMARKS=OFF \
	-DSIMDUTF_TOOLS=OFF
%cmake_build

%install
%cmake_install

%check
%ctest

%files
%license LICENSE-APACHE
%doc AUTHORS README.md
%{_libdir}/lib%{name}.so.%{lib_ver}
%{_libdir}/lib%{name}.so.%{so_ver}

%files devel
%{_includedir}/%{name}.h
%{_includedir}/%{name}_c.h
%{_includedir}/%{name}
%{_libdir}/cmake/%{name}
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
%autochangelog
