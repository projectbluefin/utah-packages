Name: pycairo
Version: 1.29.2
Release: %autorelease
Summary: Python bindings for the cairo library

License: LGPL-2.1-only OR MPL-1.1
URL: https://www.cairographics.org/pycairo
Source0: https://github.com/pygobject/pycairo/releases/download/v%{version}/pycairo-%{version}.tar.gz

BuildRequires: gcc
BuildRequires: meson
BuildRequires: pkgconfig(cairo)
BuildRequires: python3-devel
BuildRequires: python3-pytest

%description
Python bindings for the cairo library.

%package -n python3-cairo
Summary: Python 3 bindings for the cairo library
%{?python_provide:%python_provide python3-cairo}

%description -n python3-cairo
Python 3 bindings for the cairo library.

%package -n python3-cairo-devel
Summary: Libraries and headers for py3cairo
Requires: python3-cairo%{?_isa} = %{version}-%{release}
Requires: python3-devel

%description -n python3-cairo-devel
This package contains files required to build wrappers for cairo add-on
libraries so that they interoperate with py3cairo.

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

%check
%meson_test

%files -n python3-cairo
%license COPYING*
%doc README.rst
%{python3_sitearch}/cairo/
%{python3_sitearch}/pycairo*.dist-info

%files -n python3-cairo-devel
%dir %{_includedir}/pycairo
%{_includedir}/pycairo/py3cairo.h
%{_libdir}/pkgconfig/py3cairo.pc

%changelog
%autochangelog
