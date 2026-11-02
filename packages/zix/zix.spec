%global         maj 0
# Doxygen 1.18 in the build root writes function-pointer typedefs in a form
# sphinxygen 1.0.12 cannot read (AssertionError in read_typedef), so the
# Sphinx API reference fails to build. Off until sphinxygen handles it.
%bcond docs 0

Name:           zix
Version:        0.8.0
Release:        %autorelease
Summary:        A lightweight C library of portability wrappers and data structures

License:        ISC
URL:            https://gitlab.com/drobilla/%{name}
Source0:        https://download.drobilla.net/%{name}-%{version}.tar.xz
Source1:        https://download.drobilla.net/%{name}-%{version}.tar.xz.sig
Source2:        https://drobilla.net/drobilla.gpg

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  meson
%if %{with docs}
BuildRequires:  doxygen
BuildRequires:  python3-sphinx
BuildRequires:  python3-sphinxygen
%endif
BuildRequires:  gnupg2

%description
%{name} is a lightweight C library of portability wrappers and data structures.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%if %{with docs}
%package        doc
Summary:        Documentation files for %{name}
Provides:       bundled(js-jquery) = 3.6.0
Buildarch:      noarch

%description    doc
The %{name}-doc package contains documentation files for
developing applications that use %{name}.
%endif

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup

%build
# Do not build benchmarks
%meson -Dbenchmarks=disabled -Ddocs=%{?with_docs:enabled}%{!?with_docs:disabled}
%meson_build

%install
%meson_install
%if %{with docs}
# Delete duplicated sphinx docs
rm -rf %{buildroot}%{_docdir}/%{name}-%{maj}/singlehtml
# Delete sphinx buildinfo
rm -f %{buildroot}%{_docdir}/%{name}-%{maj}/html/.buildinfo
# Move devel docs to the right directory
install -d %{buildroot}%{_docdir}/%{name}
mv %{buildroot}%{_docdir}/%{name}-%{maj} %{buildroot}%{_docdir}/%{name}
%endif

%check
%meson_test

%files
%license COPYING
%doc README.md
%{_libdir}/lib%{name}-%{maj}.so.%{maj}*

%files devel
%{_includedir}/%{name}-%{maj}
%{_libdir}/lib%{name}-%{maj}.so
%{_libdir}/pkgconfig/%{name}-%{maj}.pc

%if %{with docs}
%files doc
%license COPYING
%doc %{_docdir}/%{name}/%{name}-%{maj}
%endif

%changelog
%autochangelog
