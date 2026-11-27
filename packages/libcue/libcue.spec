Name:		libcue
Version:	2.3.0
Release:	%autorelease
Summary:	Cue sheet parser library
# Files libcue/rem.{c,h} contains a BSD-2-Clause header
License:	GPL-2.0-only AND BSD-2-Clause
URL:		https://github.com/lipnitsk/%{name}
VCS:		git:%{url}.git
Source0:	%{url}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch:		libcue-0001-Raise-minimum-CMake-version-up-to-3.5.patch
BuildRequires:	bison
BuildRequires:	cmake
BuildRequires:	flex
BuildRequires:	gcc
BuildRequires:	gcc-c++
BuildRequires:	pkgconfig

%description
Libcue is intended for parsing a so-called cue sheet from a char string or a
file pointer. For handling of the parsed data a convenient API is available.

%package devel
Summary:	Development files
Requires:	%{name}%{?_isa} = %{version}-%{release}

%description	devel
Development files for %{name}.

%prep
%autosetup -p1

%build
%cmake
%cmake_build

%install
%cmake_install

%check
%cmake_build --target test

%files
%license LICENSE
%doc ChangeLog README.md
%{_libdir}/%{name}.so.*

%files devel
%{_includedir}/*
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
%autochangelog
