Name:           pam_yubico
Version:        2.27
Release:        11%{?dist}
Summary:        A Pluggable Authentication Module for yubikeys

# Automatically converted from old format: BSD - review is highly recommended.
License:        LicenseRef-Callaway-BSD
URL:            https://developers.yubico.com/yubico-pam/
Source0:        https://developers.yubico.com/yubico-pam/Releases/pam_yubico-%{version}.tar.gz

BuildRequires: make
BuildRequires:  gcc
BuildRequires:  ykclient-devel >= 2.15
BuildRequires:  libyubikey-devel >= 1.5
BuildRequires:  pam-devel ykpers-devel openldap-devel automake
Requires:       pam

%description
This is pam_yubico, a pluggable authentication module that can be used with
Linux-PAM and yubikeys. This module supports yubikey OTP checking.

%prep
%autosetup

%build
autoconf
%configure --libdir=/%{_lib} \
           --with-pam-dir=/%{_lib}/security/ \
           --disable-rpath
%make_build

%install
%make_install
rm $RPM_BUILD_ROOT/%{_lib}/security/pam_yubico.la

%files
%license COPYING
%doc NEWS README ChangeLog
/%{_lib}/security/pam_yubico.so
%{_bindir}/ykpamcfg
%{_mandir}/man1/ykpamcfg.1.gz
%{_mandir}/man8/pam_yubico.8.gz

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Tue Jan 07 2025 Stephen Gallagher <sgallagh@redhat.com> - 2.27-7
- Drop upstreamed patch to fix FTBFS

* Mon Sep  2 2024 Miroslav Suchý <msuchy@redhat.com> - 2.27-6
- convert license to SPDX

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.27-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Fri Jun 23 2023 Nick Bebout <nb@fedoraproject.org> - 2.27-1
- Update to 2.27

* Wed Mar  8 2023 DJ Delorie <dj@redhat.com> - 2.26-13
- Fix C99 compatibility issue

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Aug 04 2021 Maxim Burgerhout <wzzrd@fedoraproject.org> - 2.26-9
- Disable rpath because of new policy

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.26-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Nov 16 2018 Orion Poplawski <orion@nwra.com> - 2.26-2
- Update URLs
- Require pam
- Modernize specfile

* Mon Jul 23 2018 Nick Bebout <nb@fedoraproject.org> - 2.26-1
- Update to 2.26

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.24-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.24-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.24-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.24-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.24-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Mon Nov 28 2016 Oliver Haessler <oliver@redhat.com> - 2.24-1
- Update to 2.24

* Wed Jun 15 2016 Oliver Haessler <oliver@redhat.com> - 2.23-1
- Update to 2.23

* Tue Jun 07 2016 Oliver Haessler <oliver@redhat.com> - 2.22-2
- changed BR to automake to include aclocal

* Mon May 23 2016 Oliver Haessler <oliver@redhat.com> - 2.22-1
- Update to 2.22
- removed requirement for ykclient >= 2.15 as BuildRequires:  ykclient-devel >= 2.15
takes care of it already

* Tue May 10 2016 Nick Bebout <nb@fedoraproject.org> - 2.21-3
- Fix it to read >= instead of just >

* Tue May 03 2016 Nick Bebout <nb@fedoraproject.org> - 2.21-2
- Fix dep on ykclient

* Tue Feb 23 2016 Oliver Haessler <oliver@redhat.com> - 2.21-1
- Update to 2.21

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.20-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Nov 18 2015 Nick Bebout <nb@fedoraproject.org> - 2.20-1
- Update to 2.20

* Thu Jun 18 2015 Nick Bebout <nb@fedoraproject.org> - 2.19-1
- Update to 2.19

* Thu Jun 18 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.14-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.14-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Fri Jun 06 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.14-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu Mar 13 2014 Nick Bebout <nb@fedoraproject.org> - 2.14-1
- Update to 2.14

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.13-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Mon Mar  4 2013 Peter Robinson <pbrobinson@fedoraproject.org> 2.13-1
- Update to 2.13

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.12-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Jan 11 2013 Nick Bebout <nb@fedoraproject.org> - 2.12-1
- Update to 2.12

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.11-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Wed Feb 15 2012 Nick Bebout <nb@fedoraproject.org> - 2.11-1
- Upgrade to 2.11

* Wed Feb 8 2012 Nick Bebout <nb@fedoraproject.org> - 2.10-1
- Upgrade to 2.10

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.8-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Mon Nov 07 2011 Dennis Gilmore <dennis@ausil.us> - 2.8-1
- update to 2,8 fixes bz#733322

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Mon Oct 18 2010 Dennis Gilmore <dennis@ausil.us> - 2.4-1
- update to 2.4
- fixes crashing bug

* Fri Sep 03 2010 Dennis Gilmore <dennis@ausil.us> - 2.3-1
- update to 2.3

* Sat Jul 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Fri May  8 2009 Mike McGrath <mmcgrath@redhat.com> - 2.1-2
- Added patch to prevent segfaults in x86_64

* Wed Apr 29 2009 Dennis Gilmore <dennis@ausil.us> - 2.1-1
- initial packaging
