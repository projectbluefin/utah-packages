%global fontname gnu-free
%global fontconf 69-%{fontname}

Name:      %{fontname}-fonts
Version:   20120503
Release:   39%{?dist}
Summary:   Free UCS Outline Fonts

License:   GPL-3.0-or-later WITH Font-exception-2.0
URL:       http://www.gnu.org/software/freefont/ 
Source0:   http://ftp.gnu.org/gnu/freefont/freefont-src-%{version}.tar.gz
Source2:   %{fontconf}-mono.conf
Source3:   %{fontconf}-sans.conf
Source4:   %{fontconf}-serif.conf
Source5:   %{fontname}.metainfo.xml
Source6:   %{fontname}-mono.metainfo.xml
Source7:   %{fontname}-sans.metainfo.xml
Source8:   %{fontname}-serif.metainfo.xml

Patch0:    gnu-free-fonts-devanagari-rendering.patch
Patch1:    gnu-free-sans-square-dot-glyph-fix.patch
Patch2:    python3.patch
Patch3:    hints.patch

BuildArch: noarch
BuildRequires: make
BuildRequires: fontpackages-devel fontforge

%global common_desc \
Gnu FreeFont is a free family of scalable outline fonts, suitable for general \
use on computers and for desktop publishing. It is Unicode-encoded for \
compatibility with all modern operating systems. \
 \
Besides a full set of characters for writing systems based on the Latin \
alphabet, FreeFont contains large selection of characters from other writing \
systems some of which are hard to find elsewhere. \
 \
FreeFont also contains a large set of symbol characters, both technical and \
decorative. We are especially pleased with the Mathematical Operators range, \
with which most of the glyphs used in LaTeX can be displayed.

%description
%common_desc


%package common
Summary:  Common files for freefont (documentation…)
Requires: fontpackages-filesystem
Obsoletes: gnu-free-fonts-compat < 20120503

%description common
%common_desc

This package consists of files used by other %{name} packages.


%package -n %{fontname}-mono-fonts
Summary:  GNU FreeFont Monospaced Font
Requires: %{name}-common = %{version}-%{release}

%description -n %{fontname}-mono-fonts
%common_desc

This package contains the GNU FreeFont monospaced font.


%package -n %{fontname}-sans-fonts
Summary:  GNU FreeFont Sans-Serif Font
Requires: %{name}-common = %{version}-%{release}

%description -n %{fontname}-sans-fonts
%common_desc

This package contains the GNU FreeFont sans-serif font.


%package -n %{fontname}-serif-fonts
Summary:  GNU FreeFont Serif Font
Requires: %{name}-common = %{version}-%{release}

%description -n %{fontname}-serif-fonts
%common_desc

This package contains the GNU FreeFont serif font.


%prep
%autosetup -n freefont-%{version} -p1

# Following for loop should not be used on pyc files
# better remove pre-compiled buildutils.pyc file
rm tools/generate/*.pyc

%build
make

%install
pushd sfd
install -m 0755 -d %{buildroot}%{_fontdir}
install -p -m 644 *.ttf  %{buildroot}%{_fontdir}

install -m 0755 -d %{buildroot}%{_fontconfig_templatedir} \
                   %{buildroot}%{_fontconfig_confdir}

install -m 0644 -p %{SOURCE2} \
        %{buildroot}%{_fontconfig_templatedir}/%{fontconf}-mono.conf

install -m 0644 -p %{SOURCE3} \
        %{buildroot}%{_fontconfig_templatedir}/%{fontconf}-sans.conf

install -m 0644 -p %{SOURCE4} \
        %{buildroot}%{_fontconfig_templatedir}/%{fontconf}-serif.conf


for fconf in %{fontconf}-mono.conf \
                %{fontconf}-sans.conf \
                %{fontconf}-serif.conf ; do
  ln -s %{_fontconfig_templatedir}/$fconf \
        %{buildroot}%{_fontconfig_confdir}/$fconf
done

# Add AppStream metadata
install -Dm 0644 -p %{SOURCE5} \
        %{buildroot}%{_datadir}/appdata/%{fontname}.metainfo.xml
install -Dm 0644 -p %{SOURCE6} \
        %{buildroot}%{_datadir}/appdata/%{fontname}-mono.metainfo.xml
install -Dm 0644 -p %{SOURCE7} \
        %{buildroot}%{_datadir}/appdata/%{fontname}-sans.metainfo.xml
install -Dm 0644 -p %{SOURCE8} \
        %{buildroot}%{_datadir}/appdata/%{fontname}-serif.metainfo.xml

%_font_pkg -n mono -f %{fontconf}-mono.conf FreeMono*.ttf
%{_datadir}/appdata/%{fontname}-mono.metainfo.xml
%_font_pkg -n sans -f %{fontconf}-sans.conf FreeSans*.ttf
%{_datadir}/appdata/%{fontname}-sans.metainfo.xml
%_font_pkg -n serif -f %{fontconf}-serif.conf FreeSerif*.ttf
%{_datadir}/appdata/%{fontname}-serif.metainfo.xml

%files common
%doc AUTHORS ChangeLog CREDITS README
%license COPYING
%{_datadir}/appdata/%{fontname}.metainfo.xml

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-39
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Feb 06 2026 Gwyn Ciesla <gwync@protonmail.com> - 20120503-38
- no-hints patch, BZ 2435265

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-37
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-36
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-35
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-34
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-33
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-32
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-31
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat May 27 2023 Parag Nemade <pnemade AT redhat DOT com> - 20120503-30
- Resolves:rh#1813728 - Square four dot Unicode character has incorrect glyph 

* Wed Mar 01 2023 Gwyn Ciesla <gwync@protonmail.com> - 20120503-29
- migrated to SPDX license

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-28
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-27
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-26
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-25
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-24
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-23
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-22
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-21
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-20
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed May 02 2018 Gwyn Ciesla <limburgher@gmail.com> - 20120503-18
- BR fix.

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Fri Nov 03 2017 Karsten Hopp <karsten@redhat.com> - 20120503-16
- 2to3 moved to python3-tools

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Thu Mar 09 2017 Parag Nemade <pnemade AT redhat DOT com> - 20120503-14
- Use 2to3 tool to make build scripts compatible with python3

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 20120503-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20120503-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Nov 06 2014 Parag Nemade <pnemade AT redhat DOT com> - 20120503-10
- Add metainfo file to show this font in gnome-software
- Remove %%clean section which is optional now
- Remove buildroot which is optional now
- Remove removal of buildroot in %%install
- Remove %%defattr
- Remove group tag

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20120503-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20120503-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Mon Jun 24 2013 Jon Ciesla <limburgher@gmail.com> 20120503-7
- Patch for devanagari rendering, BZ 961298.

* Wed May 15 2013 Jon Ciesla <limburgher@gmail.com> 20120503-6
- Additional Indic rendering fix, BZ 871252.

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20120503-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Jan 11 2013 Jon Ciesla <limburgher@gmail.com> 20120503-4
- Fix Indic rendering, BZ 871252.

* Tue Nov 06 2012 Jens Petersen <petersen@redhat.com> - 20120503-3
- Update source url and license tag, BZ 873508.

* Tue Oct 23 2012 Jon Ciesla <limburgher@gmail.com> 20120503-2
- Drop fontconfig priority to 69, BZ 869224.

* Fri Sep 28 2012 Jon Ciesla <limburgher@gmail.com> 20120503-1
- New upstream.
- Dropped compat package.

* Thu Jul 19 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20100919-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20100919-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20100919-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Thu Dec 30 2010 Jon Ciesla <limb@jcomserv.net> 20100919-3
- Fixed URL.

* Sun Dec 12 2010 Jon Ciesla <limb@jcomserv.net> 20100919-2
- Fixed license tag, URL, BZ 644992.

* Tue Oct 05 2010 Jon Ciesla <limb@jcomserv.net> 20100919-1
- New upstream.

* Tue Aug 10 2010 Jon Ciesla <limb@jcomserv.net> 20090104-12
- Moved priority from 60 to 67, BZ 621498.

* Fri Jul 24 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 20090104-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Mon Mar 23 2009 Jon Ciesla <limb@jcomserv.net> 20090104-10
- Moved closer to template in effort to correct symlinks.

* Fri Mar 20 2009 Jon Ciesla <limb@jcomserv.net> 20090104-9
- Fixed compat requires.
- Fixed symlinks.

* Wed Mar 18 2009 Jon Ciesla <limb@jcomserv.net> 20090104-8
- Changed fontname, fixed symlinks, typos.

* Mon Mar 09 2009 Jon Ciesla <limb@jcomserv.net> 20090104-7
- Tidied Requires and Obsoletes.

* Thu Mar 05 2009 Jon Ciesla <limb@jcomserv.net> 20090104-6
- Converted last define to global.
- Dropped -common group declaration.
- Dropped free from package names.
- Dropped unneccessary requires and obsoletes.
- Dropped fontdir from -common.
- Fixed conf install and names.

* Thu Mar 05 2009 Jon Ciesla <limb@jcomserv.net> 20090104-5
- Added -lang=ff to build script.

* Thu Mar 05 2009 Jon Ciesla <limb@jcomserv.net> 20090104-4
- Changed define to global.
- Dropped main package, created compat package.
- Dropped freefont-ttf Obsoletes.
- Fixed subpackage requires.
- Dropped subpackage Groups.
- Fixed font_pkg syntax.
- Buildrequire fontforge.
- Added fontconfig rules.
- Minor spec order corrections.

* Tue Feb 17 2009 Jon Ciesla <limb@jcomserv.net> 20090104-3
- For BZ 477336:
- Renamed from freefont to gnu-free-fonts.
- Build from sfd now.
- Removed Requires for fontconfig.
- Drop old Provides.

* Mon Feb 09 2009 Jon Ciesla <limb@jcomserv.net> 20090104-2
- Implemented font_pkg.
- Corrected subpackage names.

* Mon Jan 12 2009 Orion Poplawski <orion@cora.nwra.com> 20090104-1
- update to 20090104
- conform to font package guidelines

* Fri Jul 18 2008 Tom "spot" Callaway <tcallawa@redhat.com> 20080323-1
- fix license tag
- update to 20080323

* Fri Jan  5 2007 Orion Poplawski <orion@cora.nwra.com> 20060126-4
- Require fontconfig, not /usr/share/fonts

* Tue Oct 31 2006 Orion Poplawski <orion@cora.nwra.com> 20060126-3
- BOO!
- Make Provides/Osoletes versioned
- Make setup quiet

* Wed Oct 25 2006 Orion Poplawski <orion@cora.nwra.com> 20060126-2
- Remove fonts.cache refs
- fc-cache /usr/share/fonts/freefont

* Thu Oct 12 2006 Orion Poplawski <orion@cora.nwra.com> 20060126-1
- freefont-ttf-20060126

* Tue Dec 06 2005 Rex Dieter 20051206-1
- freefont-ttf-20051206
