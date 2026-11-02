%global maj 0
# Doxygen 1.18 in the build root writes function-pointer typedefs in a form
# sphinxygen 1.0.12 cannot read (AssertionError in read_typedef), so the
# Sphinx API reference fails to build. Off until sphinxygen handles it.
%bcond docs 0

Name:       sratom
Version:    0.6.22
Release:    %autorelease
Summary:    A C library for serializing LV2 plugins

License:    MIT
URL:        https://drobilla.net/software/%{name}
Source0:    https://download.drobilla.net/%{name}-%{version}.tar.xz
Source1:    https://download.drobilla.net/%{name}-%{version}.tar.xz.sig
Source2:    https://drobilla.net/drobilla.gpg

BuildRequires:  gcc
BuildRequires:  gnupg2
BuildRequires:  meson
BuildRequires:  pkgconfig(sord-0) >= 0.16.16
BuildRequires:  pkgconfig(serd-0) >= 0.30.10
BuildRequires:  pkgconfig(lv2) >= 1.18.4
%if %{with docs}
BuildRequires:  doxygen
BuildRequires:  graphviz
BuildRequires:  python3-sphinx
BuildRequires:  python3-sphinx_lv2_theme
BuildRequires:  python3-sphinxygen
%endif

%description
%{name} is a C library for serializing LV2 atoms to/from Turtle. It is
intended to be a full serialization solution for LV2 atoms, allowing
implementations to serialize binary atoms to strings and read them back again.
This is particularly useful for saving plugin state, or implementing plugin
control with network transparency.

%package devel
Summary:    Development libraries and headers for %{name}
Requires:   %{name}%{_isa} = %{version}-%{release}

%description devel
%{name} is a C library for serializing LV2 atoms to/from Turtle. It is
intended to be a full serialization solution for LV2 atoms, allowing
implementations to serialize binary atoms to strings and read them back again.
This is particularly useful for saving plugin state, or implementing plugin
control with network transparency.

This package contains the headers and development libraries for %{name}.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p1

%build
%meson -Ddocs=%{?with_docs:enabled}%{!?with_docs:disabled}
%meson_build

%install
%meson_install

%if %{with docs}
# Move devel docs to the right directory
install -d %{buildroot}%{_docdir}/%{name}
mv %{buildroot}%{_docdir}/%{name}-%{maj} %{buildroot}%{_docdir}/%{name}
%endif

%check
%meson_test

%files
%doc README.md
%license COPYING
%{_libdir}/lib%{name}-%{maj}.so.*

%files devel
%if %{with docs}
%doc %{_docdir}/%{name}/%{name}-%{maj}/
%endif
%{_libdir}/lib%{name}-%{maj}.so
%{_libdir}/pkgconfig/%{name}-%{maj}.pc
%{_includedir}/%{name}-%{maj}/

%changelog
%autochangelog
