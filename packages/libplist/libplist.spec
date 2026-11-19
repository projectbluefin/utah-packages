%global forgeurl https://github.com/libimobiledevice/libplist

Name:     libplist
Version:  2.7.0
Release:  %autorelease
Summary:  Library for manipulating Apple Binary and XML Property Lists

License:  LGPL-2.0-or-later
URL:      https://www.libimobiledevice.org/
Source:   %{forgeurl}/releases/download/%{version}/%{name}-%{version}.tar.bz2

BuildRequires: gcc-c++
BuildRequires: python3-Cython
BuildRequires: python3-devel
BuildRequires: python3-setuptools
BuildRequires: make

%description
libplist is a library for manipulating Apple Binary and XML Property Lists

%package  devel
Summary:  Development package for libplist
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: pkgconfig

%description devel
%{name}, development headers and libraries.

%package  -n python3-libplist
Summary:  Python3 bindings for libplist
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: python3

%description -n python3-libplist
%{name}, python3 libraries and bindings.

%prep
%autosetup -p1

%build
export PYTHON_VERSION="%{python3_version}"
%configure --disable-static
%make_build

%install
%make_install

%check
make check

%files
%license COPYING.LESSER
%doc AUTHORS README.md
%{_bindir}/plistutil
%{_libdir}/libplist-2.0.so.4*
%{_libdir}/libplist++-2.0.so.4*
%{_mandir}/man1/plistutil.1*

%files devel
%{_libdir}/pkgconfig/libplist-2.0.pc
%{_libdir}/pkgconfig/libplist++-2.0.pc
%{_libdir}/libplist-2.0.so
%{_libdir}/libplist++-2.0.so
%{_includedir}/plist

%files -n python3-libplist
%{python3_sitearch}/plist.so

%changelog
%autochangelog
