Name:           openpace
Version:        1.1.4
Release:        4%{?dist}
Summary:        Cryptographic library for EAC version 2

License:        GPL-3.0-only
URL:            https://frankmorgner.github.io/openpace/
Source:         https://github.com/frankmorgner/openpace/releases/download/%{version}/openpace-%{version}.tar.gz
Patch1:         openpace-1.1.3-unsupported-tests.patch
Patch2:         openpace-openssl4.patch

BuildRequires:  autoconf automake libtool gcc
BuildRequires:  openssl openssl-devel

%description
OpenPACE implements Extended Access Control (EAC) version 2 as specified in
BSI TR-03110. OpenPACE comprises support for Password Authenticated Connection
Establishment (PACE), Terminal Authentication (TA), and Chip Authentication (CA)
protocols. Its also supports Card Verifiable Certificates (CV Certificates)
and signing requests as well as easy to use wrappers for using the established
secure channels.

%package devel
Summary:        Files for development of applications which will use OpenPACE
Requires:       %{name}%{?_isa} = %{version}-%{release}
 
%description devel
Development files with header files to develop applications
which support EAC protocol.

%package doc
Summary:        HTML documentation for %{name}
BuildArch:      noarch
Requires:       %{name} = %{version}-%{release}
Suggests:       font(glyphicons-halflings-fonts)
 
%description doc
HTML documentation for OpenPACE.

%prep
%setup -q
%patch 1 -p1 -b .unsupported-tests
%patch 2 -p1 -b .openssl4

%build	
autoreconf -fvi
%set_build_flags
CFLAGS="$CFLAGS -Wno-deprecated-declarations"
%configure --disable-static
%make_build

%check
# https://fedoraproject.org/wiki/Changes/OpenSSLDistrustSHA1SigVer
export OPENSSL_ENABLE_SHA1_SIGNATURES=1
make check

%install
%make_install

find %{buildroot}%{_libdir} -type f -name "*.la" | xargs rm

# Remove unnecessary files from the documentation directory
find %{buildroot}%{_docdir}/openpace -type f -name 'Makefile*' | xargs rm
find %{buildroot}%{_docdir}/openpace -type f -name '.nojekyll' | xargs rm

# Remove the example and test files
rm -rf %{buildroot}%{_bindir}/example
rm -rf %{buildroot}%{_bindir}/eactest

# Remove fonts
rm -rf %{buildroot}%{_docdir}/openpace/_static/bootstrap-3.3.7/fonts
rm -rf %{buildroot}%{_docdir}/openpace/_static/bootswatch-3.3.7/fonts

%files
%license COPYING
%dir %{_sysconfdir}/eac/
%dir %{_sysconfdir}/eac/cvc
%dir %{_sysconfdir}/eac/x509
%{_bindir}/cvc-create
%{_bindir}/cvc-print
%{_libdir}/libeac.so.*
%config(noreplace) %{_sysconfdir}/eac/cvc/DECVCAEPASS00102
%config(noreplace) %{_sysconfdir}/eac/cvc/DECVCAeID00102
%config(noreplace) %{_sysconfdir}/eac/cvc/DECVCAeSign00102
%config(noreplace) %{_sysconfdir}/eac/x509/ff3d20d2
%{_mandir}/man1/cvc-create.1.gz
%{_mandir}/man1/cvc-print.1.gz

%files devel
%dir %{_includedir}/eac/
%{_libdir}/libeac.so
%{_includedir}/eac/*
%{_libdir}/pkgconfig/libeac.pc

%files doc
%doc %{_docdir}/openpace

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jun 12 2026 Yaakov Selkowitz <yselkowi@redhat.com> - 1.1.4-3
- Rebuilt for openssl 4.0

* Wed Apr 29 2026 Dmitry Belyavskiy <beldmit@gmail.com> - 1.1.4-2
- Fix build with OpenSSL 4.0 (opaque ASN1_STRING)

* Fri Feb 27 2026 Jakub Jelen <jjelen@redhat.com> - 1.1.4-1
- New upstream release

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.3-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Jul 31 2024 Veronika Hanulikova <vhanulik@redhat.com> - 1.1.3-2
- Avoid SHA-1 test failures (#2301013)

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.3-1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Mon Jun 17 2024 Veronika Hanulikova <vhanulik@redhat.com> - 1.1.3-0
- First build.
