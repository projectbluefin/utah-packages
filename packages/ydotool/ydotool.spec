# -*-Mode: rpm-spec-mode; -*-

%undefine __cmake_in_source_build

%global debug_package %{nil}

Name:     ydotool
Version:  1.0.4
Release:  9%{?dist}
Summary:  Generic command-line automation tool (no X!)
# Automatically converted from old format: AGPLv3
License:  AGPL-3.0-only
URL:      https://github.com/ReimuNotMoe/%{name}

Source0:  %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: make
BuildRequires: scdoc
BuildRequires: systemd-rpm-macros

%description

Performs some of the functions of xdotool(1) without requiring X11 -
however, it generally requires root permission (to open /dev/uinput)

N.B. it is strongly recommended to start the ydotoold daemon with:

- systemctl enable ydotool
- systemctl start ydotool

%prep
%setup -q

%build
%cmake -DBUILD_SHARED_LIBS:BOOL=OFF

make -C %{_vpath_builddir} -j `nproc`

%install
mkdir -p %{buildroot}/%{_bindir}
strip */%{name}
strip */%{name}d
install -p -m 0755 */%{name} %{buildroot}/%{_bindir}
install -p -m 0755 */%{name}d %{buildroot}/%{_bindir}
mkdir -p %{buildroot}/%{_unitdir}
install -p -m 0644 */%{name}.service %{buildroot}/%{_unitdir}
mkdir -p %{buildroot}/%{_mandir}/man1
mkdir -p %{buildroot}/%{_mandir}/man8
scdoc < manpage/%{name}.1.scd > %{buildroot}/%{_mandir}/man1/%{name}.1
scdoc < manpage/%{name}d.8.scd > %{buildroot}/%{_mandir}/man8/%{name}d.8

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service

%files
%{_unitdir}/%{name}.service
%{_bindir}/%{name}*
%license LICENSE
%doc README.md
%{_mandir}/man1/%{name}.1.*
%{_mandir}/man8/%{name}d.8.*

%changelog
* Fri Jul 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Sun Jan 19 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Sat Jul 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Jul 17 2024 Miroslav Suchý <msuchy@redhat.com> - 1.0.4-4
- convert license to SPDX

* Sat Jan 27 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jul 22 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Tue Jan 31 2023 Bob Hepple <bob.hepple@gmail.com> - 1.0.4-1
- new version

* Sat Jan 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jan 12 2023 Bob Hepple <bob.hepple@gmail.com> - 1.0.3-1
- new version

* Sat Jul 23 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.0.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Mon Mar 21 2022 Bob Hepple <bob.hepple@gmail.com> - 1.0.1-2
- added new manual (also pushed upstream)

* Thu Feb 17 2022 Bob Hepple <bob.hepple@gmail.com> - 1.0.1-1
- new version

* Sun Feb 06 2022 Bob Hepple <bob.hepple@gmail.com> - 1.0.0-2
- now builds on all architectures without patches

* Sun Feb 06 2022 Bob Hepple <bob.hepple@gmail.com> - 1.0.0-1
- new version

* Sun Jan 30 2022 Bob Hepple <bob.hepple@gmail.com> - 0.2.0-8
- add -Wno-error= flags for FTBFS #2047136 in f36
- exclude armv7hl as it fails to compile

* Sat Jan 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Mar 02 2021 Zbigniew Jędrzejewski-Szmek <zbyszek@in.waw.pl> - 0.2.0-5
- Rebuilt for updated systemd-rpm-macros
  See https://pagure.io/fesco/issue/2583.

* Thu Jan 28 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Fri Jan 22 2021 Jonathan Wakely <jwakely@redhat.com> - 0.2.0-3
- Rebuilt for Boost 1.75

* Wed Jan 20 2021 Bob Hepple <bob.hepple@gmail.com> - 0.2.0-2
- rebuilt excluding s390x and ppc64le

* Mon Jan 11 2021 Bob Hepple <bob.hepple@gmail.com> - 0.2.0-1
- new version
- upstream has dropped the idea of -devel libraries so we are only
  distributing the regular package now; also libevdevPlus-devel and
  libuInputPlus-devel are no longer needed as they are now compiled
  in.

* Sat Aug 15 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.4.20200815.git.787fd25
- most recent version

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.9-0.3.20200405.git.9c3a4e7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sat May 30 2020 Jonathan Wakely <jwakely@redhat.com> - 0.1.9-0.2.20200405.git.9c3a4e7
- Rebuilt for Boost 1.73

* Sun Apr 05 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200405.git.9c3a4e7
- Changes per RHBZ#1807753 - %{?systemd_requires} and ldconfig are no longer required

* Fri Apr 03 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200403.git.9c3a4e7
- Changes per RHBZ#1807753

* Wed Apr 01 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200401.git.9c3a4e7
- Changes per RHBZ#1807753

* Mon Mar 30 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200330.git.9c3a4e7
- Changes per RHBZ#1807753

* Sun Mar 22 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200322.git.9c3a4e7
- fix Source to get git tag directly

* Sat Feb 29 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200229.git.9c3a4e7
- Add a note on how to get source from upstream
- use lib*-devel packages in BuildRequires

* Tue Feb 18 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.9-0.1.20200218.git.9c3a4e7
- rebuild from head to pick up manuals & service file
- remove static build
- strip binaries (rpmlint complained about them)

* Mon Feb 17 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.8.20200211.3
- add BuildRequires: systemd-rpm-macros; add dist to release

* Sun Feb 16 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.8.20200211.2
- use %%_unitdir

* Sun Feb 16 2020 Bob Hepple <bob.hepple@gmail.com> - 0.1.8.20200211.1
- Initial version of the package
