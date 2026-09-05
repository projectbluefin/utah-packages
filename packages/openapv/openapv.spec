Name:          openapv
Release:       %autorelease
Version:       0.3.0.0
Summary:       Open Advanced Professional Video Codec
License:       BSD-3-Clause
URL:           https://github.com/AcademySoftwareFoundation/openapv
Source:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
# https://github.com/AcademySoftwareFoundation/openapv/pull/177
Patch0:        %{name}-fix-md5-hash-mismatch-on-big-endian.patch
BuildRequires: cmake
BuildRequires: ninja-build
BuildRequires: gcc
Requires:      %{name}-libs%{?_isa} = %{version}-%{release}

%global somaj %{lua:t={} for f in string.gmatch(macros['version'], "([^.]*)(.?)") do table.insert(t,f) end print(t[2])}
%global sover %{lua:t={} for f in string.gmatch(macros['version'], "([^.]*)(.?)") do table.insert(t,f) end print(string.format("%s.%s.%s",t[2],t[3],t[4]))}

%description
OpenAPV provides the reference implementation of the APV codec which can
be used to record professional-grade video and associated metadata
without quality degradation.

%package  devel
Summary:  Development files for %{name}
Requires: %{name}-libs%{?_isa} = %{version}-%{release}

%description devel
The openapv-devel package contains the header files needed
to develop programs that use openapv.

%package libs
Summary: Shared libraries for openapv

%description libs
The openapv-libs package contains the shared library files

%prep
%autosetup -p1

%build
%cmake \
        -G Ninja \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DCMAKE_SKIP_INSTALL_RPATH=ON \
        -DOAPV_APP_STATIC_BUILD=OFF

%cmake_build

%install
%cmake_install
rm -v %{buildroot}%{_libdir}/oapv/liboapv.a

%check
%ctest

%files
%{_bindir}/oapv_app_dec
%{_bindir}/oapv_app_enc

%files devel
%{_libdir}/liboapv.so
%{_libdir}/pkgconfig/oapv.pc
%{_includedir}/oapv/

%files libs
%license LICENSE
%doc README.md
%{_libdir}/liboapv.so.{%{somaj},%{sover}}

%changelog
%autochangelog
