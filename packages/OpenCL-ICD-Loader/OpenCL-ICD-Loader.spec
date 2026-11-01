%global commit0 b7bd2803acc779c03d96588e9ca9e9568a18698a
%global date 20260519
%global shortcommit0 %(c=%{commit0}; echo ${c:0:7})

Name:           OpenCL-ICD-Loader
Version:        3.1
Release:        %autorelease -s %{date}git%{shortcommit0}
Summary:        Khronos official OpenCL ICD Loader
License:        Apache-2.0
URL:            https://github.com/KhronosGroup/OpenCL-ICD-Loader
Source0:        %{url}/archive/%{commit0}/%{name}-%{shortcommit0}.tar.gz

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: opencl-headers

Conflicts: ocl-icd

%description
%{summary}.

%package devel
Summary:        Development files for Khronos official OpenCL ICD Loader
Requires:       %{name}%{?_isa} = %{version}-%{release}

Conflicts: ocl-icd-devel

%description devel
%{summary}

%prep
%autosetup -n %{name}-%{commit0}

%build
%cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DOPENCL_ICD_LOADER_HEADERS_DIR="/usr/include/"

%cmake_build

%install
%cmake_install

%files
%license LICENSE
%{_libdir}/libOpenCL.so.1{,.*}

%files devel
%{_bindir}/cllayerinfo
%{_libdir}/libOpenCL.so
%{_libdir}/pkgconfig/OpenCL.pc
%{_datadir}/cmake/OpenCLICDLoader/OpenCLICDLoader*.cmake

%changelog
%autochangelog
