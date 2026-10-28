%bcond tests 1
%bcond pkcs11 %[0%{?fedora} < 43 && %{undefined rhel}]
%bcond libproxy %{undefined rhel}

# Disable automatic .la file removal
%global __brp_remove_la_files %nil

Summary: An HTTP and WebDAV client library
Name: neon
Version: 0.37.1
Release: %autorelease
License: LGPL-2.0-or-later
URL: https://notroj.github.io/neon/
Source0: https://notroj.github.io/neon/neon-%{version}.tar.gz
Patch0: neon-0.34.0-multilib.patch
BuildRequires: expat-devel, openssl-devel, zlib-devel, krb5-devel
BuildRequires: pkgconfig, make, gcc, libntlm-devel
%if %{with pkcs11}
BuildRequires: pakchois-devel
%endif
%if %{with libproxy}
BuildRequires: libproxy-devel
%endif
%if %{with tests}
# SSL tests require openssl binary, PKCS#11 testing need certutil
BuildRequires: /usr/bin/perl, /usr/bin/openssl, /usr/bin/certutil
%endif

%description
neon is an HTTP and WebDAV client library, with a C interface;
providing a high-level interface to HTTP and WebDAV methods along
with a low-level interface for HTTP request handling.  neon
supports persistent connections, proxy servers, Basic, Digest and
Kerberos authentication, and has complete SSL/TLS support.

%package devel
Summary: Development libraries and C header files for the neon library
Requires: neon = %{version}-%{release}, openssl-devel, zlib-devel, expat-devel
Requires: pkgconfig
# Documentation is GPLv2+
License: LGPL-2.0-or-later AND GPL-2.0-or-later

%description devel
The development library for the C language HTTP and WebDAV client library.

%prep
%autosetup -p1 -S gendiff

# prevent installation of HTML docs
sed -i '/^install-docs/s/install-html//' Makefile.in

%build
%configure --with-expat --enable-shared --disable-static \
        --enable-warnings \
        --with-ssl=openssl --enable-threadsafe-ssl=posix \
%ifarch s390x
        --without-libntlm \
%endif
%if %{with libproxy}
        --with-libproxy \
%else
        --without-libproxy \
%endif
%if %{with pkcs11}
        --with-pakchois
%else
        --without-pakchois
%endif
%make_build

%install
rm -rf $RPM_BUILD_ROOT
%make_install

sed -ri "/^dependency_libs/{s,-l[^ ']*,,g}" \
      $RPM_BUILD_ROOT%{_libdir}/libneon.la

%find_lang %{name}

%if %{with tests}
%check
export TEST_QUIET=0
if make %{?_smp_mflags} check; then
    : PASS
else
    : FAIL
    cat test/child.log || true
    cat test/debug.log || true
    exit 1
fi
%endif

%ldconfig_scriptlets

%files -f %{name}.lang
%doc AUTHORS src/COPYING.LIB NEWS README* THANKS
%{_libdir}/*.so.*

%files devel
%{_bindir}/*
%{_includedir}/*
%{_libdir}/pkgconfig/neon.pc
%{_mandir}/man1/*
%{_mandir}/man3/*
%{_libdir}/*.*a
%{_libdir}/*.so

%changelog
%autochangelog
