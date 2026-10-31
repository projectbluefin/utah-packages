%global maj 0

Name:       sord
Version:    0.16.22
Release:    %autorelease
Summary:    A lightweight Resource Description Framework (RDF) C library

License:    ISC
URL:        https://drobilla.net/software/%{name}.html
Source0:    https://download.drobilla.net/%{name}-%{version}.tar.xz
Source1:    https://download.drobilla.net/%{name}-%{version}.tar.xz.sig
Source2:    https://drobilla.net/drobilla.gpg

BuildRequires: doxygen
BuildRequires: gcc
BuildRequires: gnupg2
BuildRequires: meson
BuildRequires: pkgconfig(libpcre2-8)
BuildRequires: pkgconfig(serd-0) >= 0.30.10
BuildRequires: pkgconfig(zix-0) >= 0.4.0

%description
%{name} is a lightweight C library for storing Resource Description
Framework (RDF) data in memory. %{name} and parent library serd form 
a lightweight RDF tool-set for resource limited or performance critical 
applications.

%package devel
Summary:    Development libraries and headers for %{name}
Requires:   %{name}%{_isa} = %{version}-%{release}

%description devel
%{name} is a lightweight C library for storing Resource Description
Framework (RDF) data in memory.

This package contains the headers and development libraries for %{name}.

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
%{_pkgdocdir}
%exclude %{_pkgdocdir}/%{name}-%{maj}/
%license COPYING
%{_libdir}/lib%{name}-%{maj}.so.%{maj}*
%{_bindir}/sordi
%{_bindir}/sord_validate
%{_mandir}/man1/%{name}*.1*

%files devel
%{_pkgdocdir}/%{name}-%{maj}/
%{_libdir}/lib%{name}-%{maj}.so
%{_libdir}/pkgconfig/%{name}-%{maj}.pc
%{_includedir}/%{name}-%{maj}/

%changelog
%autochangelog
