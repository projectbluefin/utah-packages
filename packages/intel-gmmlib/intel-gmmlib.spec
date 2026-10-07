Name:           intel-gmmlib
Version:        22.10.2
Release:        %autorelease
Summary:        Intel Graphics Memory Management Library

License:        MIT AND BSD-3-Clause
URL:            https://github.com/intel/gmmlib
Source0:        %{url}/archive/%{name}-%{version}.tar.gz

# This package fails on s390x and ppc64le
# g++: error: unrecognized argument in option ‘-march=corei7’
ExcludeArch:  s390x ppc64le

BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  gcc-c++

%description
The Intel Graphics Memory Management Library provides device specific
and buffer management for the Intel Graphics Compute Runtime for OpenCL
and the Intel Media Driver for VAAPI.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1 -n gmmlib-intel-gmmlib-%{version}
# Fix license perm
chmod -x LICENSE.md README.rst
# Fix source code perm
find Source -name "*.cpp" -exec chmod -x {} ';'
find Source -name "*.h" -exec chmod -x {} ';'


%build
%cmake \
  -DRUN_TEST_SUITE:BOOL=False

%cmake_build


%install
%cmake_install


%files
%license LICENSE.md
%doc README.rst
%{_libdir}/libigdgmm.so.12*

%files devel
%{_includedir}/igdgmm
%{_libdir}/libigdgmm.so
%{_libdir}/pkgconfig/igdgmm.pc


%changelog
%autochangelog
