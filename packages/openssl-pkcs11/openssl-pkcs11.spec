Version: 0.4.21
Release: %autorelease

Name:           openssl-pkcs11
Summary:        A PKCS#11 engine for use with OpenSSL
# The source code is LGPLv2+ except eng_back.c and eng_parse.c which are BSD
# There are parts licensed with OpenSSL license too
License:        LGPL-2.1-or-later AND BSD-2-Clause AND OpenSSL
URL:            https://github.com/OpenSC/libp11
Source0:        https://github.com/OpenSC/libp11/releases/download/libp11-%{version}/libp11-%{version}.tar.gz
Source1:        https://github.com/OpenSC/libp11/releases/download/libp11-%{version}/libp11-%{version}.tar.gz.asc
# sq network search 2BC7E4E67E3CC0C1BEA72F8C2EFC7FF0D416E014
# sq cert export --cert=AC915EA30645D9D3D4DAE4FEB1048932DD3AAAA3 --output libp11.keyring
Source2:        libp11.keyring

BuildRequires: make
BuildRequires:  autoconf automake libtool
BuildRequires:  openssl-devel
BuildRequires:  openssl >= 3.0.0
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(p11-kit-1)
# Needed for testsuite
BuildRequires:  softhsm opensc procps-ng
BuildRequires:  doxygen
BuildRequires:  gpgverify

Requires:       p11-kit-trust
Requires:       openssl-libs >= 3.0.0

# Package renamed from libp11 to openssl-pkcs11 in release 0.4.7-4
Provides:       libp11%{?_isa} = %{version}-%{release}
Obsoletes:      libp11 < 0.4.7-4
# The engine_pkcs11 subpackage is also provided 
Provides:       engine_pkcs11%{?_isa} = %{version}-%{release}
Obsoletes:      engine_pkcs11 < 0.4.7-4

# The libp11-devel subpackage was removed in libp11-0.4.7-1, but not obsoleted
# This Obsoletes prevents the conflict in updates by removing old libp11-devel
Obsoletes:      libp11-devel < 0.4.7-4

%description -n openssl-pkcs11
openssl-pkcs11 enables hardware security module (HSM), and smart card support in
OpenSSL applications. More precisely, it is an OpenSSL engine which makes
registered PKCS#11 modules available for OpenSSL applications. The engine is
optional and can be loaded by configuration file, command line or through the
OpenSSL ENGINE API.

# The libp11-devel subpackage was reintroduced in libp11-0.4.7-7 for Fedora
%package -n libp11-devel
Summary:        Files for developing with libp11
Requires:       %{name} = %{version}-%{release}

%description -n libp11-devel
The libp11-devel package contains libraries and header files for
developing applications that use libp11.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p 1 -n libp11-%{version}

%build
autoreconf -fvi
export CFLAGS="%{optflags}"
%configure --disable-static --enable-api-doc --with-modulesdir=%{_libdir}/ossl-modules
make V=1 %{?_smp_mflags}

%install
make install DESTDIR=%{buildroot}

# Remove libtool .la files
rm -f %{buildroot}%{_libdir}/*.la


# Remove documentation automatically installed by make install
rm -rf %{buildroot}%{_docdir}/libp11/

%check
# to run tests use "--with check". They crash now in softhsm
%if %{?_with_check:1}%{!?_with_check:0}
make check %{?_smp_mflags} || if [ $? -ne 0 ]; then cat tests/*.log; exit 1; fi;
%endif

%ldconfig_scriptlets

%files
%license COPYING
%doc NEWS
%{_libdir}/libp11.so.*
%{_libdir}/ossl-modules/libpkcs11.so
%{_libdir}/ossl-modules/pkcs11prov.so

%files -n libp11-devel
%doc examples/ doc/api.out/html/
%{_libdir}/libp11.so
%{_libdir}/pkgconfig/libp11.pc
%{_includedir}/*.h

%changelog
%autochangelog
