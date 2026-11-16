%global archivename crosextrafonts-carlito-20130920

Version:        1.103
Release:        0.29.20130920%{?dist}
URL:            https://bugs.chromium.org/p/chromium/issues/detail?id=280557

%global foundry           google
# License added in font as "otfinfo -i Carlito-Regular.ttf | grep License"
# also from http://code.google.com/p/chromium/issues/detail?id=280557
%global fontlicense       OFL-1.1

%global fontfamily        Carlito
%global fontsummary       Carlito, a sans-serif font family metric-compatible with Calibri font family
%global fontpkgheader     %{expand:
Obsoletes:      google-crosextra-carlito-fonts < 1.103-0.13.20130920
Provides:       google-crosextra-carlito-fonts = %{version}-%{release}
}
%global fonts             *.ttf
%global fontconfs         %{SOURCE1} %{SOURCE2}
%global fontdescription   %{expand:
Carlito is metric-compatible with Calibri font family. Carlito comes in regular,
bold, italic, and bold italic. The family covers Latin-Greek-Cyrillic (not a
complete set, though) with about 2,000 glyphs. It has the same character
coverage as Calibri. This font is sans-serif typeface family based on Lato.}

Source0:        http://gsdview.appspot.com/chromeos-localmirror/distfiles/%{archivename}.tar.gz
Source1:        30-0-%{fontpkgname}.conf
Source2:        62-%{fontpkgname}.conf

%fontpkg

%prep
%setup -q -n %{archivename}

%build
%fontbuild

%install
%fontinstall

%check
%fontcheck

%fontfiles


%changelog
* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.29.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.28.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.27.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.26.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.25.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.24.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jan 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.23.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.22.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.21.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Dec 01 2022 Parag Nemade <pnemade AT redhat DOT com> - 1.103-0.20.20130920
- Update license tag to SPDX format

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.19.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.18.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.17.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.16.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.15.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sun May 24 2020 Parag Nemade <pnemade AT redhat DOT com> - 1.103-0.14.20130920
- Update fontconfig DTD id in conf file

* Tue Mar 17 2020 Parag Nemade <pnemade AT redhat DOT com> - 1.103-0.13.20130920
- Convert to new fonts packaging guidelines

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.12.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.11.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.10.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.9.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.8.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.7.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.6.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.103-0.5.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.103-0.4.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Thu Oct 16 2014 Parag Nemade <pnemade AT redhat DOT com> - 1.103-0.3.20130920
- Add metainfo file to show this font in gnome-software

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.103-0.2.20130920
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu Oct 10 2013 Parag Nemade <pnemade AT redhat DOT com> - 1.103-0.1.20130920
- Initial Fedora release.

