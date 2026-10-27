Name:           ykpers
Version:        1.20.0
Release:        19%{?dist}
Summary:        Yubikey personalization program

# Automatically converted from old format: BSD - review is highly recommended.
License:        LicenseRef-Callaway-BSD
URL:            http://opensource.yubico.com/yubikey-personalization/
Source0:        http://opensource.yubico.com/yubikey-personalization/releases/%{name}-%{version}.tar.gz
Patch0:         ykpers-args-extern.patch

%ifnarch s390 s390x
BuildRequires: libusb1-devel
%else
BuildRequires: libusb-compat-0.1-devel
%endif
BuildRequires: libyubikey-devel
BuildRequires: systemd
BuildRequires: gcc
BuildRequires: make

%description
Yubico's YubiKey can be re-programmed with a new AES key. This is a library
that makes this an easy task.

%package devel
Summary:        Development files for ykpers
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
This package contains the header file needed to develop applications that
use ykpers.

%prep
%setup -q
%patch -P0 -p0

%build
%configure --enable-static=no --disable-rpath \
    --with-udevrulesdir=/usr/lib/udev/rules.d \
%ifnarch s390 s390x
    --with-backend=libusb-1.0
%else
    --with-backend=libusb
%endif
# --disable-rpath doesn't work for the configure script
sed -i 's|^hardcode_libdir_flag_spec=.*|hardcode_libdir_flag_spec=""|g' libtool
sed -i 's|^runpath_var=LD_RUN_PATH|runpath_var=DIE_RPATH_DIE|g' libtool
%make_build

%check
export LD_LIBRARY_PATH=$RPM_BUILD_DIR/%{name}-%{version}/.libs
make check

%install
%make_install INSTALL="%{__install} -p"

%files
%license COPYING
%doc AUTHORS README ChangeLog NEWS
%doc doc/Compatibility.asciidoc
%{_bindir}/ykinfo
%{_bindir}/ykpersonalize
%{_bindir}/ykchalresp
%{_libdir}/libykpers-1.so.1
%{_libdir}/libykpers-1.so.%{version}
%{_mandir}/man1/ykpersonalize.1*
%{_mandir}/man1/ykchalresp.1*
%{_mandir}/man1/ykinfo.1*
%{_udevrulesdir}/69-yubikey.rules

%files devel
%doc doc/USB-Hid-Issue.asciidoc
%{_libdir}/pkgconfig/ykpers-1.pc
%{_libdir}/libykpers-1.so
%{_includedir}/ykpers-1/
%exclude %{_libdir}/libykpers-1.la

%changelog
* Fri Jul 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-18
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Sun Jan 19 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-16
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Sep 04 2024 Miroslav Suchý <msuchy@redhat.com> - 1.20.0-15
- convert license to SPDX

* Sat Jul 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sat Jan 27 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jul 22 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat Jan 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Sat Jul 23 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sat Jan 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Thu Jan 28 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Fri Feb 14 2020 Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.20.0-5
- Fix build error for Fedora 32 / gcc10

* Fri Jan 31 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Aug 1 2019 Orion Poplawski <orion@nwra.com> - 1.20.0-3
- Modernize spec

* Sat Jul 27 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.20.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jul 04 2019 Kevin Fenzi <kevin@scrye.com> - 1.20.0-1
- Update to 1.20.0. Fixes bug #1726859

* Sat Feb 23 2019 Kevin Fenzi <kevin@scrye.com> - 1.19.3-1
- Update to 1.19.3. Fixes bug #1678647

* Sun Feb 03 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.19.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Sun Jul 22 2018 Kevin Fenzi <kevin@scrye.com> - 1.19.0-3
- Fix FTBFS bug #1606768

* Sat Jul 14 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.19.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Jul 09 2018 Nick Bebout <nb@fedoraproject.org> - 1.19.0-1
- Update to 1.19.0

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.18.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Tue Jan 16 2018 Kevin Fenzi <kevin@scrye.com> - 1.18.1-1
- Update to 1.18.1. Fixes bug #1534995

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.18.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.18.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.18.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Jan 28 2017 Kevin Fenzi <kevin@scrye.com> - 1.18.0-1
- Update to 1.18.0. Fixes bug #1417179

* Fri Feb 05 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.17.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Fri Jan 08 2016 Kevin Fenzi <kevin@scrye.com> - 1.17.3-1
- Update to 1.17.3

* Sun Oct 18 2015 Kevin Fenzi <kevin@scrye.com> 1.17.2-3
- Switch to systemd BuildRequires as systemd-devel doesn't provide udev.pc
- Fixes permissions issue #1272637

* Wed Sep 23 2015 Kevin Fenzi <kevin@scrye.com> 1.17.2-2
- Properly conditionalize udev rules file.

* Wed Sep 23 2015 Kevin Fenzi <kevin@scrye.com> 1.17.2-1
- Update to 1.17.2. Fixes bug #1265449

* Sun Jul 05 2015 Kevin Fenzi <kevin@scrye.com> 1.17.1-3
- Fix name of udev rules file. Fixes bug #1240090

* Fri Jun 19 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.17.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Wed Apr 01 2015 Kevin Fenzi <kevin@scrye.com> 1.17.1-1
- Update to 1.17.1. Fixes bug #1208140

* Sat Feb 07 2015 Kevin Fenzi <kevin@scrye.com> 1.16.2-1
- Update to 1.16.2

* Sun Nov 23 2014 Kevin Fenzi <kevin@scrye.com> 1.16.1-1
- Update to 1.16.1. Fixes bugs #1167113 and #1157894

* Mon Aug 18 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.15.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.15.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed Mar 12 2014 Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.15.1-1
- New upstream release 1.15.1, should fix ARM build failure on make check

* Mon Jan 13 2014 Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.15.0-1
- New upstream release 1.15.0, which includes (amongst others):
- Fixes for race conditions on new machines
- Support for NEO 3.2 keys

* Thu Nov 28 2013 Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.14.1-1
- Update to 1.14.1
- With dry-run option (-d) and new ykinfo options to view individual slots

* Sun Aug 04 2013 Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.13.0.3
- BR systemd-devel for Fedora 20 / Rawhide

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.13.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Mon May 13 2013 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.13.0-1
- Update to 1.13.0: ycfg-json functions, recognize newer firmware

* Fri Feb 15 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.9.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Nov 8 2012 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.9.0-1
- Update to new upstream version 1.9.0

* Wed Oct 17 2012 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.8.2-1
- Update to 1.8.2 that adds ykinfo
- Drop local patch for udev rules as it is now upstreamed

* Mon Oct 1 2012 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.8.0-1
- Update to 1.8.0:
- Support for yk_challenge_response, Yubikey 2.3, bugfixes and more
- Drop bigendian patch, is now in upstream source

* Sun Jul 22 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.6.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Wed Feb 15 2012 - Nick Bebout <nb@fedoraproject.org> - 1.6.3-1
- Update to 1.6.3

* Sun Jan 8 2012 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.6.2-2
- Rebuild for gcc 4.7

* Tue Nov 29 2011 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.6.2-1
- New upstream version with some minor bugfixes

* Thu Jul 21 2011 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.6.0-2
- Rebuild for rpm-4.9.1 trailing slash bug

* Thu Jul 21 2011 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.6.0-1
- Update to upstream version 1.6.0 (support for firmware 2.3.x, oath changes)
- First implementation of udev rules for ykpers

* Fri Apr 29 2011 - Dan Horák <dan[at]danny.cz> - 1.4.1-2
- fix build on big endians and with default unsigned char (like s390(x))

* Sun Feb 6 2011 - Maxim Burgerhout <wzzrd@fedoraproject.org> - 1.4.1-1
- Add support for new features in YubiKey 2.2.
- Stricter argument parsing, to help user avoid configuration surprises.
- Ask kernel to detach USB HID driver with libusb 0.1 too.
- Properly reject keys (-a) with upper case hex, instead of just ignoring
  those bits.
- Really check Yubikey compatibility when setting options.
- Pretty-printer did not handle bit overloaded cfgflags.
  It is better now, but not perfect.
- Fixes to make it work under Windows.

* Mon Oct 18 2010 - Dan Horák <dan[at]danny.cz> - 1.3.4-2
- build with libusb on s390(x)

* Wed Oct 13 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.3.4-1
- Version bump

* Thu May 27 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.3.3-1
- Version bump

* Wed Mar 17 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.3.2-1
- Version bump

* Mon Jan 25 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.3.1-1
- Version bump

* Mon Jan 25 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.2-4
- RPM_OPT_FLAGS removed again

* Mon Jan 25 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.2-3
- Removed pkgconfig dependency for devel
- Fixed ownership of ykpers-1 in /usr/include
- Fixed install with original timestamp

* Sat Jan 23 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.2-2
- Used macros for sed, make, rm and Source0
- Removed INSTALL and MakeRelease.wiki from the docs
- Inserted INSTALLFLAGS
- Inserted RPM_OPT_FLAGS
- Made sure the URL no longer points to a redirect

* Sat Jan 23 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.2-1
- New upstream release (support for newer firmware)

* Wed Jan 20 2010 - Maxim Burgerhout <maxim@wzzrd.com> - 1.1-1
- First packaged release
