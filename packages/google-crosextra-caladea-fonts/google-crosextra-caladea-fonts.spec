%global archivename crosextrafonts-20130214

Version:        1.002
Release:        0.23.20130214%{?dist}
Epoch:          1
URL:            http://code.google.com/p/chromium/issues/detail?id=168879

%global foundry           Google Crosextra
# License added in font as "otfinfo -i Caladea-Regular.ttf | grep License"
# also from http://code.google.com/p/chromium/issues/detail?id=280557
%global fontlicense       Apache-2.0
%global fontlicenses      LICENSE-2.0.txt

%global fontfamily        Caladea
%global fontsummary       Serif font metric-compatible with Cambria font

%global fonts             *.ttf
%global fontconfs         %{SOURCE1} %{SOURCE2}
%global fontdescription   %{expand:
Caladea is metric-compatible with Cambria font. This font is a serif
typeface family based on Lato.
}

Source0:        http://gsdview.appspot.com/chromeos-localmirror/distfiles/%{archivename}.tar.gz
Source1:        30-0-%{fontpkgname}.conf
Source2:        62-%{fontpkgname}.conf
Source3:        https://www.apache.org/licenses/LICENSE-2.0.txt

%global fontpkgheader     %{expand:
Obsoletes: ht-caladea-fonts < 1:1.001-10.20200428git336a529
}

%fontpkg

%prep
%autosetup -n %{archivename}
cp -p %{SOURCE3} .

%build
%fontbuild

%install
%fontinstall

%check
%fontcheck

%fontfiles

%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.23.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.22.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.21.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.20.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.19.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.18.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.17.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1:1.002-0.16.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Mon Feb 06 2023 Parag Nemade <pnemade AT redhat DOT com> - 1:1.002-0.15.20130214
- Un-retire this package in F38+ (#2162532)
- Update as per suggestions given in rename package review (#2166813)

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.14.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.13.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.12.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.11.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.10.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.9.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.8.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.002-0.7.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.002-0.6.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Oct 16 2014 Parag Nemade <pnemade AT redhat DOT com> - 1.002-0.5.20130214
- Add metainfo file to show this font in gnome-software

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.002-0.4.20130214
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed Jan 22 2014 Parag Nemade <pnemade AT redhat DOT com> - 1.002-0.3.20130214
- Resolves:rh#1056029 - Fontconfig and summary required fixes

* Tue Oct 15 2013 Parag Nemade <pnemade AT redhat DOT com> - 1.002-0.2.20130214
- Added license information in comments

* Thu Oct 10 2013 Parag Nemade <pnemade AT redhat DOT com> - 1.002-0.1.20130214
- Initial Fedora release.

