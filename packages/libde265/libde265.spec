Name:		  libde265
Summary:	Open H.265 video codec implementation
Version:	1.1.3
Release:	%{autorelease}
License:	LGPLv3+
Source:		https://github.com/strukturag/libde265/releases/download/v%{version}/%{name}-%{version}.tar.gz
URL:		  https://www.libde265.org/

BuildSystem:    cmake
BuildOption(conf): -DENABLE_DECODER=OFF
BuildRequires:	gcc-c++

Obsoletes:      %{name}-examples < %{version}-%{release}

%description
libde265 is an open source implementation of the H.265 video codec.
It is written from scratch for simplicity and efficiency. Its simple
API makes it easy to integrate it into other software.


%package devel
Summary:	Open H.265 video codec implementation - development files
Requires:	%{name}%{?_isa} = %{version}-%{release}

%description devel
libde265 is an open source implementation of the H.265 video codec.
It is written from scratch for simplicity and efficiency. Its simple
API makes it easy to integrate it into other software.

The development headers for compiling programs that use libde265
are provided by this package.

%prep
%autosetup -p1

%files
%doc AUTHORS
%license COPYING
%{_libdir}/libde265.so.*

%files devel
%doc README.md
%{_includedir}/libde265/
%{_libdir}/libde265.so
%{_libdir}/pkgconfig/*.pc
%{_libdir}/cmake/libde265/

%changelog
%autochangelog