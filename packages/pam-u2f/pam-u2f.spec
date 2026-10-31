
Name:          pam-u2f
Version:       1.4.0
Release:       9%{?dist}

ExcludeArch:   %{ix86}

Summary:       Implements PAM authentication over U2F

License:       BSD-2-Clause
URL:           https://github.com/Yubico/pam-u2f
Source0:       https://developers.yubico.com/pam-u2f/Releases/pam_u2f-%{version}.tar.gz
Source1:       https://developers.yubico.com/pam-u2f/Releases/pam_u2f-%{version}.tar.gz.sig
Source2:       yubico-release-gpgkeys.asc

BuildRequires: asciidoc
BuildRequires: cmake
BuildRequires: openpgpverify
BuildRequires: make
BuildRequires: gcc
BuildRequires: pkgconfig(pam)
BuildRequires: pkgconfig(libfido2)

%description
The PAM U2F module provides an easy way to integrate the Yubikey (or
other U2F-compliant authenticators) into your existing user
authentication infrastructure.

%package -n pamu2fcfg
Summary:       Configures PAM authentication over U2F
Requires:      %{name}%{?_isa} = %{version}-%{release}

%description -n pamu2fcfg
pamu2fcfg provides a command line tool for configuring PAM authentication
over U2F.

%prep
%{openpgpverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -n pam_u2f-%{version}

%build
%cmake
%cmake_build

%install
%cmake_install

%check
%ctest

%files
%doc AUTHORS NEWS README
%license COPYING
%{_mandir}/man8/pam_u2f.8{,.*}
%{_libdir}/security/pam_u2f.so

%files -n pamu2fcfg
%{_bindir}/pamu2fcfg
%{_mandir}/man1/pamu2fcfg.1{,.*}

%changelog
* Tue Oct 13 2026 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.4.0-9
- Remove conditionals as all recent Fedora now support openpgpverify

* Sat Oct 03 2026 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.4.0-8
- Migrate to using sequoia openpgpverify from legacy gpgverify

* Tue Jul 21 2026 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.4.0-7
- Update the signing keys (remove expired, update to current)

* Sat Jul 18 2026 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.4.0-6
- Add ExcludeArch for i686 as this is a leaf package

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jun 12 2026 Yaakov Selkowitz <yselkowi@redhat.com> - 1.4.0-4
- Rebuilt for openssl 4.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Mar 28 2025 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.4.0-1
- Update to 1.4.0 - resolves rhbz#2354803
- Add new yubico release developer gpg key to keyring
- Migrate to cmake builds (upstream change)

* Thu Jan 16 2025 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.3.2-1
- Update to 1.3.2 - resolves rhbz#2338418
  1.3.2 fixes a potentially breaking issue with tightened authfile checking with 1.3.1

* Tue Jan 14 2025 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.3.1-1
- Update to 1.3.1 - resolves rhbz#2337634

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Mon Oct 30 2023 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.3.0-3
- Perform deglobing of files per packaging guidelines

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Mar 15 2023 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.3.0-1
- Update to 1.3.0 - resolves rhbz#2178735
- Move keyring to SCM per packaging guidelines

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Mon Nov 07 2022 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.2.1-3
- Migrate spec file to SPDX license specification (BSD -> BSD-2-Clause)

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu May 12 2022 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.2.1-1
- Update to 1.2.1 upstream release (resolves: rhbz#2084467)

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Sun Dec 05 2021 Gary Buhrmaster <gary.buhrmaster@gmail.com> - 1.2.0-2
- Update changelog to reflect security related issues/tickets
- Fixes CVE-2021-31924
- Fixes rhbz#2028244
- Fixes rhbz#2028245

* Mon Nov 08 2021 Gary Burhmaster <gary.buhrmaster@gmail.com> - 1.2.0-1
- Update to 1.2.0 upstream release (#1993435)
- Support (optional) autoreconf invokation if needed for patches
- Migrate to pkgconfig for BR per packaging guidelines

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.8-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Sat Jul 10 2021 Björn Esser <besser82@fedoraproject.org> - 1.0.8-7
- Rebuild for versioned symbols in json-c

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.8-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.8-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Apr 21 2020 Björn Esser <besser82@fedoraproject.org> - 1.0.8-4
- Rebuild (json-c)

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.8-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Wed Jun 05 2019 Seth Jennings <spartacus06@gmail.com> - 1.0.8-1
- New upstream release
- Fixes Debug file descriptor leak CVE-2019-1221
- Fixes insecure debug file handling CVE-2019-1220
- resolves: #1717326

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Apr 19 2018 Seth Jennings <spartacus06@gmail.com> - 1.0.7-1
- New upstream release

* Thu Apr 19 2018 Seth Jennings <spartacus06@gmail.com> - 1.0.6-1
- New upstream release
- resolves: #1568058

* Mon Apr 16 2018 Seth Jennings <spartacus06@gmail.com> - 1.0.5-2
- fix spec file

* Mon Apr 16 2018 Seth Jennings <spartacus06@gmail.com> - 1.0.5-1
- New upstream release
- resolves: #1568058

* Fri Feb 09 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 1.0.4-8
- Escape macros in %%changelog

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Mon Jan 15 2018 Seth Jennings <spartacus06@gmail.com> - 1.0.4-6
- Resolves: #1528392

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Sep 19 2016 Seth Jennings <spartacus06@gmail.com> - 1.0.4-2
- Remove Fedora-specific README

* Mon Sep 19 2016 Seth Jennings <spartacus06@gmail.com> - 1.0.4-1
- New upstream release
- resolves: #1377459

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.3-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Dec 18 2015 Seth Jennings <spartacus06@gmail.com> - 1.0.3-5
- Fix up descriptions
- Use %%autosetup macro

* Mon Dec 14 2015 Seth Jennings <spartacus06@gmail.com> - 1.0.3-4
- Add upstream patches https://github.com/Yubico/pam-u2f/issues/28

* Mon Nov 30 2015 Seth Jennings <spartacus06@gmail.com> - 1.0.3-3
- Use find -delete option
- Fixup description
- Remove explicit Requires pam

* Wed Nov 18 2015 Seth Jennings <spartacus06@gmail.com> - 1.0.3-2
- Fix typo in pamu2fcfg description

* Wed Nov 18 2015 Seth Jennings <spartacus06@gmail.com> - 1.0.3-1
- Initial package release
