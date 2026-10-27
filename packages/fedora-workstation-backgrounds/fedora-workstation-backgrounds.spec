Name: fedora-workstation-backgrounds
Version: 1.6
Release: 10%{?dist}
Summary: Desktop backgrounds for Fedora Workstation

License: CC-BY-4.0
URL: https://pagure.io/fedora-design/fedora-workstation-backgrounds
Source0: https://pagure.io/fedora-design/%{name}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch: noarch

BuildRequires: autoconf
BuildRequires: automake
BuildRequires: make

# See RHBZ 2112390 - this allows package to be installable without the GNOME stack
Requires: (webp-pixbuf-loader if gdk-pixbuf2)

%description
The fedora-workstation-backgrounds packages contains the additional standard
wallpapers for Fedora Workstation.

%prep
%autosetup -p1 -n %{name}-%{version}

%build
%configure
%make_build

%install
%make_install


%files
%license COPYING
%doc NEWS README AUTHORS
%dir %{_datadir}/gnome-background-properties
%{_datadir}/gnome-background-properties/flight.xml
%{_datadir}/gnome-background-properties/futurecity.xml
%{_datadir}/gnome-background-properties/glasscurtains.xml
%{_datadir}/gnome-background-properties/mermaid.xml
%{_datadir}/gnome-background-properties/montclair.xml
%{_datadir}/gnome-background-properties/petals.xml
%{_datadir}/backgrounds/fedora-workstation/flight_light.webp
%{_datadir}/backgrounds/fedora-workstation/flight_dark.webp
%{_datadir}/backgrounds/fedora-workstation/futurecity_light.webp
%{_datadir}/backgrounds/fedora-workstation/futurecity_dark.webp
%{_datadir}/backgrounds/fedora-workstation/glasscurtains_light.webp
%{_datadir}/backgrounds/fedora-workstation/glasscurtains_dark.webp
%{_datadir}/backgrounds/fedora-workstation/mermaid_light.webp
%{_datadir}/backgrounds/fedora-workstation/mermaid_dark.webp
%{_datadir}/backgrounds/fedora-workstation/montclair_light.webp
%{_datadir}/backgrounds/fedora-workstation/montclair_dark.webp
%{_datadir}/backgrounds/fedora-workstation/petals_light.webp
%{_datadir}/backgrounds/fedora-workstation/petals_dark.webp

%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Tue Sep 20 2022 Máirín Duffy <duffy@redhat.com> - 1.6-1 
- Correcting package mistake, replacing petals_light with correct file

* Mon Sep 19 2022 Máirín Duffy <duffy@redhat.com> - 1.5-1
- Reworking Future City to more detailed render with more appealing palette
- Minor tweaks to Montclair and Petals 

* Thu Aug 04 2022 Máirín Duffy <duffy@redhat.com> - 1.4-1
- Removing all pre-existing backgrounds
- Adding new set of 6 light and dark mode abstract backgrounds
- See https://gitlab.com/fedora/design/team/extra-default-wallpapers

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Tue Apr 5 2022 Luya Tshimbalanga <luya@fedoraproject.org> - 1.3-1
- New upstream release with enhanced dark mode variants

* Mon Mar 21 2022 Máirín Duffy <duffy@redhat.com> - 1.2
- Dark mode variants added for Fedora 36: calm, cherryblossom, corn, dandelion, winter-in-bohemia, zen
- Split XML for backgrounds so each has its own xml
- Modified spec so only the 6 dark mode capable backgrounds are shipped for F36
- See https://pagure.io/design/issue/809

* Wed Jul 21 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Wed May 24 2017 Ryan Lerch <rlerch@redhat.com> - 1.1-1
- Initial Release
