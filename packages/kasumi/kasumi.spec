# anthy-unicode migration
# https://github.com/fcitx/fcitx-anthy/issues/12
# https://osdn.net/projects/scim-imengine/ticket/40956
# https://github.com/uim/uim/issues/166

Name:    kasumi
Version: 2.5
Release: 51%{?dist}

License: GPL-2.0-or-later
URL:     http://kasumi.sourceforge.jp/
%if 0%{?fedora}
BuildRequires: anthy-devel
%endif
BuildRequires: autoconf automake libtool
BuildRequires: gcc-c++
BuildRequires: make
BuildRequires: gtk3-devel anthy-unicode-devel
Requires: %{name}-common = %{version}-%{release}
Source0: http://jaist.dl.sourceforge.jp/kasumi/41436/%{name}-%{version}.tar.gz
Patch0: kasumi-853099-manpage.patch
Patch1: kasumi-1928410-gtk3.patch
Patch2: kasumi-check-anthy-pkg.patch
Patch3: kasumi-1938091.patch
Patch4: kasumi-c89.patch
Patch5: kasumi-fix-crash-on-close.patch


Summary: An anthy dictionary management tool
%description
Kasumi is a dictionary management tool for Anthy.


%package common
Provides: %{name} = %{version}-%{release}
Summary: Anthy dictionary management common files between kasumi and kasumi-unicode
BuildArch: noarch

%description common
This package contains common files for kasumi and kasumi-unicode.


%package unicode
Requires: %{name}-common = %{version}-%{release}
Summary: An anthy-unicode dictionary management tool

%description unicode
Kasumi-unicode is a dictionary management tool for Anthy-unicode.


%prep
%autosetup -p1

%build
sed -i -e '/AM_PATH_GTK_2_0(/i\
PKG_CHECK_MODULES([GTK], [gtk+-3.0])\
CFLAGS="$CFLAGS $GTK_CFLAGS"\
CPPFLAGS="$CPPFLAGS $GTK_CFLAGS"\
LIBS="$LIBS $GTK_LIBS"' \
    -e '/AM_PATH_GTK_2_0(/d' \
    configure.in
autoreconf -f -i
export CXXFLAGS="-std=c++14 $RPM_OPT_FLAGS"
echo "# Building kasumi-unicode"
sed -e 's/AC_CHECK_LIB(anthydic,/AC_CHECK_LIB(anthydic-unicode,/' \
    -e 's/AC_CHECK_LIB(anthy,/AC_CHECK_LIB(anthy-unicode,/' \
    -e 's/PKG_CHECK_MODULES(ANTHY, anthy/PKG_CHECK_MODULES(ANTHY, anthy-unicode/' \
    -i.orig configure.in
autoreconf -f -i
%configure
make %{?_smp_mflags}

%if 0%{?fedora}
mv kasumi kasumi-unicode
make clean
cp configure.in.orig configure.in

autoreconf -f -i
echo "# Building kasumi"
%configure
make %{?_smp_mflags}
%endif


%install
make install DESTDIR=$RPM_BUILD_ROOT INSTALL="install -p"
%if 0%{?fedora}
install -pm 755 kasumi-unicode $RPM_BUILD_ROOT%{_bindir}/kasumi-unicode
%else
mv $RPM_BUILD_ROOT%{_bindir}/kasumi $RPM_BUILD_ROOT%{_bindir}/kasumi-unicode
%endif

# remove .desktop file so that kasumi is accessible from scim panel/ibus panel and it's not necessary for other users.
rm -rf $RPM_BUILD_ROOT%{_datadir}/applications/*.desktop

%find_lang %{name}


%if 0%{?fedora}
%files
%{_bindir}/kasumi
%doc AUTHORS ChangeLog NEWS README
%license COPYING
%endif

%files unicode
%{_bindir}/kasumi-unicode
%doc AUTHORS ChangeLog NEWS README
%license COPYING

%files common -f %{name}.lang
%{_mandir}/man1/kasumi.1*
%{_datadir}/pixmaps/kasumi.png


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-51
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-50
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-49
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-48
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Sep  5 2024 Akira TAGOH <tagoh@redhat.com> - 2.5-47
- Fix a crash on closing.
  Resolves: rhbz#1936817

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-46
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-45
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Florian Weimer <fweimer@redhat.com> - 2.5-44
- Fix C89 compatibility issue (#2259428)

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-43
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-42
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jun 15 2023 Stephen Gallagher <sgallagh@redhat.com> - 2.5-41
- Fix typo in RPM macro breaking ELN builds

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-40
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Dec  1 2022 Akira TAGOH <tagoh@redhat.com> - 2.5-39
- Convert License tag to SPDX.

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-38
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Tue Feb 22 2022 Akira TAGOH <tagoh@redhat.com> - 2.5-37
- To prevent confusion, drop some sentence from the error message
  happening when set invalid characters for reading.
  Resolves: rhbz#1938091

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-36
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-35
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Wed Mar 31 2021 Akira TAGOH <tagoh@redhat.com> - 2.5-34
- Drop gtk2 dependency completely.
- Make anthy build conditionally for Fedora release only.
- Fix build fail without anthy-devel.

* Tue Feb 16 2021 Takao Fujiwra <tfujiwar@redhat.com> - 2.5-33
- Migrate kasumi GUI to GTK3

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-32
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Nov 13 2020 Takao Fujiwra <tfujiwar@redhat.com> - 2.5-31
- Add Provides and Obsoletes

* Thu Nov 12 2020 Takao Fujiwra <tfujiwar@redhat.com> - 2.5-30
- Generate kasumi-unicode for anthy-unicode

* Thu Sep 03 2020 Takao Fujiwra <tfujiwar@redhat.com> - 2.5-29
- Replace anthy with anthy-unicode

* Tue Jul 28 2020 Jeff Law <law@redhat.com> - 2.5-28
- Force C++14 as this code is not C++17 ready

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-27
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-26
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-25
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-24
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-23
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Mon Feb 19 2018 Akira TAGOH <tagoh@redhat.com> - 2.5-22
- Add BR: gcc-c++

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-21
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-20
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-18
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-16
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sat May 02 2015 Kalev Lember <kalevlember@gmail.com> - 2.5-15
- Rebuilt for GCC 5 C++11 ABI change

* Sat Aug 16 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Wed Mar 27 2013 Akira TAGOH <tagoh@redhat.com> - 2.5-11
- Rebuilt for aarch64 support (#925621)

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Nov 23 2012 Akira TAGOH <tagoh@redhat.com>
- the spec file cleanup

* Fri Aug 31 2012 Akira TAGOH <tagoh@redhat.com> 2.5-9
- Fix the missing descriptions for some options in --help (#853099)

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Feb 28 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-7
- Rebuilt for c++ ABI breakage

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Mon Nov 07 2011 Adam Jackson <ajax@redhat.com> 2.5-5
- Rebuild for new (ie, no) libpng

* Mon Feb 07 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.5-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Tue Mar  9 2010 Akira TAGOH <tagoh@redhat.com> - 2.5-3
- Get rid of .desktop file again. (#546147)

* Mon Dec 21 2009 Akira TAGOH <tagoh@redhat.com> - 2.5-2
- improve the spec file (#546147)

* Mon Aug  3 2009 Akira TAGOH <tagoh@redhat.com> - 2.5-1
- New upstream release.

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Thu Jan 29 2009 Akira TAGOH <tagoh@redhat.com> - 2.4-1
- New upstream release.

* Tue Apr  8 2008 Akira TAGOH <tagoh@redhat.com> - 2.3-4
- Remove .desktop file since it's accessible from scim-panel and it's not
  necessarily used for every users, particularly on Live. (#439173)

* Tue Feb 19 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 2.3-3
- Autorebuild for GCC 4.3

* Tue Feb 19 2008 Akira TAGOH <tagoh@redhat.com> - 2.3-2
- kasumi-2.3-gcc43.patch: Fix build fails with gcc-4.3.

* Wed Oct 31 2007 Akira TAGOH <tagoh@redhat.com> - 2.3-1
- New upstream release.
- kasumi-2.2-fix-dict-breakage.patch: removed.

* Thu Aug 23 2007 Akira TAGOH <tagoh@redhat.com> - 2.2-6
- Rebuild

* Wed Aug  8 2007 Akira TAGOH <tagoh@redhat.com> - 2.2-4
- Update License tag.

* Thu Jun 14 2007 Akira TAGOH <tagoh@redhat.com> - 2.2-3
- kasumi-2.2-fix-dict-breakage.patch: patch from Debian to fix the dictionary
  breakage when adding words to the personal dictionary against the bugfix
  version of anthy that the version contains non-numeric characters.

* Wed Mar 28 2007 Akira TAGOH <tagoh@redhat.com> - 2.2-2
- Add X-GNOME-PersonalSettings to the category. (#234169)

* Fri Mar  2 2007 Akira TAGOH <tagoh@redhat.com> - 2.2-1
- Updated to 2.2
- Remove kasumi-2.0.1-errorcode.patch. no longer needed.

* Wed Jul 12 2006 Jesse Keating <jkeating@redhat.com> - 2.0.1-1.1
- rebuild

* Fri Jun 30 2006 Akira TAGOH <tagoh@redhat.com> - 2.0.1-1
- New upstream release.
- use dist tag.
- kasumi-2.0.1-errorcode.patch: fixed not working when the private dictionary is empty. (#197313)

* Wed Jun  7 2006 Akira TAGOH <tagoh@redhat.com> - 2.0-2
- added anthy-devel, automake and autoconf to BuildReq. (#194121)

* Tue May 30 2006 Akira TAGOH <tagoh@redhat.com> - 2.0-1
- New upstream release.

* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 1.0-1.fc5.2
- bump again for double-long bug on ppc(64)

* Tue Feb 07 2006 Jesse Keating <jkeating@redhat.com> - 1.0-1.fc5.1
- rebuilt for new gcc4.1 snapshot and glibc changes

* Thu Dec 15 2005 Akira TAGOH <tagoh@redhat.com> - 1.0-1
- New upstream release.
- kasumi-1.0-gcc41.patch: build with -ffriend-injection to temporarily get it
  built with gcc-4.1.

* Fri Dec 09 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt

* Thu Oct 13 2005 Akira TAGOH <tagoh@redhat.com> - 0.10-1
- New upstream release.

* Tue Aug 16 2005 Akira TAGOH <tagoh@redhat.com> - 0.9-3
- Rebuild

* Tue Aug  9 2005 Akira TAGOH <tagoh@redhat.com>
- added dist tag in Release.

* Fri Aug  5 2005 Akira TAGOH <tagoh@redhat.com> - 0.9-2
- Import into Core.
- clean up spec file.

* Wed Jun 29 2005 Ryo Dairiki <ryo-dairiki@users.sourceforge.net> - 0.9-1
- Initial packaging for Fedora Extras

