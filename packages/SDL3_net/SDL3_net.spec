Name: SDL3_net
Summary: Networking add-on library for SDL3
License: Zlib

%global ver_major 3
%global ver_minor 2
%global ver_micro 0

Version: %{ver_major}.%{ver_minor}.%{ver_micro}
Release: 3%{?dist}

%global so_major 0
%global so_version %{so_major}.%{ver_minor}.%{ver_micro}

URL: https://github.com/libsdl-org/SDL_net
Source0: https://www.libsdl.org/projects/SDL_net/release/%{name}-%{version}.tar.gz
Source1: https://www.libsdl.org/projects/SDL_net/release/%{name}-%{version}.tar.gz.sig
# Taken from: https://www.libsdl.org/signing-keys.php
Source9: SDL3.pgp

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: perl-interpreter

BuildRequires: SDL3-devel

%description
This is a portable network library for use with SDL3. It's goal is to simplify
the use of the usual socket interfaces and use SDL3 to handle common portable
functionality such as threading and reporting errors.


%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for developing
applications that use %{name} along with relevant documentation.


%prep
%{gpgverify} --keyring='%{SOURCE9}' --signature='%{SOURCE1}' --data='%{SOURCE0}'

%autosetup
%cmake \
	-DBUILD_SHARED_LIBS=ON \
	-DSDLNET_SAMPLES=OFF \
	-DSDLNET_INSTALL=ON \
	-DSDLNET_INSTALL_MAN=ON \


%build
%cmake_build


%install
%cmake_install


%files
%license LICENSE.txt
%{_libdir}/lib%{name}.so.%{so_major}
%{_libdir}/lib%{name}.so.%{so_version}


%files devel
%{_includedir}/%{name}/
%{_libdir}/lib%{name}.so
%{_libdir}/cmake/%{name}/
%{_libdir}/pkgconfig/sdl3-net.pc
%{_mandir}/man3/NET_*.3*
%{_mandir}/man3/SDL_NET_*.3*


%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 3.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Tue Jun 30 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.0-2
- Switch from forge-generated tarballs to downloading from upstream homepage
- Verify source signatures
- Fold -doc subpackage into -devel

* Sat Jun 27 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.0-1
- Initial packaging
