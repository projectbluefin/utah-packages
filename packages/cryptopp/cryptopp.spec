# Per upstream recommendations.
# https://www.cryptopp.com/wiki/Link_Time_Optimization
%define _lto_cflags %{nil}

%global upstream_url https://github.com/cryptopp-modern/cryptopp-modern

Name:           cryptopp
Version:        2026.10.0
Release:        %autorelease
Summary:        C++ class library of cryptographic schemes
License:        BSL-1.0
URL:            https://cryptopp-modern.com/

Source0:       %{upstream_url}/releases/download/%{version}/cryptopp-modern-%{version}.tar.gz
Source1:       %{upstream_url}/releases/download/%{version}/cryptopp-modern-%{version}.tar.gz.sig
#https://github.com/cryptopp-modern/cryptopp-modern/blob/main/KEYS
# gpg --import KEYS
# gpg2 --export --export-options export-minimal "844DCFC44A5DE9C14C3A2F62497A4CFBB700543E" > gpgkey-CoraleSoft-844DCFC44A5DE9C14C3A2F62497A4CFBB700543E.gpg
Source2: gpgkey-CoraleSoft-844DCFC44A5DE9C14C3A2F62497A4CFBB700543E.gpg

# This recipe builds with CMake/Ninja; the upstream GNUmakefile conversion
# target that uses dos2unix is not part of the build.
BuildRequires:  cmake
BuildRequires:  coreutils
BuildRequires:  doxygen
BuildRequires:  findutils
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  gnupg2
BuildRequires:  ninja-build

Obsoletes:  %{name}-progs < 8.8.0-3


%description
Crypto++ Library is a free C++ class library of cryptographic schemes.
See http://www.cryptopp.com/ for a list of supported algorithms.

One purpose of Crypto++ is to act as a repository of public domain
(not copyrighted) source code. Although the library is copyrighted as a
compilation, the individual files in it are in the public domain.

%package devel
Summary:        Header files and development documentation for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Obsoletes:      %{name}-doc < 8.8.0-3
Provides:       %{name}-doc < 8.8.0-3

%description devel
Crypto++ Library is a free C++ class library of cryptographic schemes.

This package contains the header files and development documentation
for %{name}.

%package static
Summary:        Static libraries for %{name}
Requires:       %{name}-devel%{?_isa} = %{version}-%{release}

%description static
Crypto++ Library is a free C++ class library of cryptographic schemes.

This package contains static libraries for %{name}.

%package tests
Summary:        Tests for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description tests
Tests for %{name}.


%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p1 -n cryptopp-modern-%{version}


%build
# build shared
%cmake \
  -DCRYPTOPP_BUILD_SHARED=ON \
  -DCRYPTOPP_BUILD_STATIC=ON \
  -DCRYPTOPP_BUILD_TESTING=ON

%cmake_build


%install
%cmake_install


%check
%ctest


%files
%doc FORK.md GETTING_STARTED.md README.md Readme.txt RELEASE-*.md ROADMAP.md Security.md
%license LICENSE
%{_libdir}/libcryptopp.so.9
%{_libdir}/libcryptopp.so.%{version}

%files devel
%{_includedir}/cryptopp
%{_libdir}/libcryptopp.so
%{_libdir}/pkgconfig/libcryptopp.pc
%{_libdir}/pkgconfig/cryptopp*.pc
%{_libdir}/cmake/cryptopp-modern/*.cmake

%files static
%{_libdir}/libcryptopp.a

%files tests
%{_bindir}/cryptest*
%{_datadir}/cryptopp

%changelog
%autochangelog
