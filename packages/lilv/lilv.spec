%{!?_pkgdocdir: %global _pkgdocdir %{_docdir}/%{name}-%{version}}
%global maj 0

Name:       lilv
Version:    0.28.0
Release:    %autorelease
Summary:    An LV2 Resource Description Framework Library

License:    MIT
URL:        https://drobilla.net/software/lilv
Source0:    https://download.drobilla.net/%{name}-%{version}.tar.xz
Source1:    https://download.drobilla.net/%{name}-%{version}.tar.xz.sig
Source2:    https://drobilla.net/drobilla.gpg

# Bindings test seems broken, disable for now
Patch0:     %{name}-bindings-test.patch

BuildRequires:  gnupg2
BuildRequires:  meson
BuildRequires:  doxygen
BuildRequires:  graphviz
BuildRequires:  pkgconfig(sord-0) >= 0.16.16
BuildRequires:  pkgconfig(sratom-0) >= 0.6.10
BuildRequires:  pkgconfig(lv2) >= 1.18.2
BuildRequires:  pkgconfig(python3)
BuildRequires:  pkgconfig(serd-0) >= 0.30.10
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig(sndfile) >= 1.0.0
BuildRequires:  pkgconfig(zix-0) >= 0.6.0
BuildRequires:  python3-sphinx
BuildRequires:  python3-sphinx_lv2_theme
BuildRequires:  python3-sphinxygen

Requires:       lv2 >= 1.18.2

# To try and deal with multilib issues from the -libs split:
# https://bugzilla.redhat.com/show_bug.cgi?id=2052588
Obsoletes:      lilv < 0.24.12-2

%description
%{name} is a library to make the use of LV2 plugins as simple as possible
for applications. Lilv is the successor to SLV2, rewritten to be significantly
faster and have minimal dependencies.

%package libs
Summary:    Libraries for %{name}
Obsoletes:  lilv < 0.24.12-2

%description libs
%{name} is a lightweight C library for Resource Description Syntax which
supports reading and writing Turtle and NTriples.

This package contains the libraries for %{name}.

%package devel
Summary:    Development libraries and headers for %{name}
Requires:   %{name}-libs%{_isa} = %{version}-%{release}

%description devel
%{name} is a lightweight C library for Resource Description Syntax which
supports reading and writing Turtle and NTriples.

This package contains the headers and development libraries for %{name}.

%package -n python3-%{name}
%{?python_provide:%python_provide python3-%{name}}
Summary:    Python bindings for %{name}
Requires:   %{name}-libs%{_isa} = %{version}-%{release}

%description -n python3-%{name}
%{name} is a lightweight C library for Resource Description Syntax which
supports reading and writing Turtle and NTriples.

This package contains the python libraries for %{name}.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

# Move devel docs to the right directory
install -d %{buildroot}%{_docdir}/%{name}
mv %{buildroot}%{_docdir}/%{name}-%{maj} %{buildroot}%{_docdir}/%{name}

%check
%meson_test

%files
%exclude %{_pkgdocdir}/%{name}-%{maj}/
%{_bindir}/lv2info
%{_bindir}/lv2ls
%{_bindir}/lv2bench
%{_bindir}/lv2apply
%{_sysconfdir}/bash_completion.d/lilv
%{_mandir}/man1/*

%files libs
%doc AUTHORS NEWS README.md
%license COPYING
%{_libdir}/lib%{name}-%{maj}.so.*

%files devel
%{_libdir}/lib%{name}-%{maj}.so
%{_libdir}/pkgconfig/%{name}-%{maj}.pc
%{_includedir}/%{name}-%{maj}/
%{_pkgdocdir}/%{name}-%{maj}/

%files -n python3-%{name}
%{python3_sitelib}/%{name}.*
%{python3_sitelib}/__pycache__/*

%changelog
%autochangelog
