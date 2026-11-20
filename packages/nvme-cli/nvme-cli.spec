# RHEL 8 compatibility
%{!?version_no_tilde: %define version_no_tilde %{shrink:%(echo '%{version}' | tr '~' '-')}}

%global nmlibdir %{_prefix}/lib/NetworkManager

Name:           nvme-cli
Version:        3.1
Release:        1%{?dist}
Summary:        NVMe management command line interface

License:        GPL-2.0-only
URL:            https://github.com/linux-nvme/nvme-cli
Source0:        %{url}/archive/v%{version_no_tilde}/%{name}-%{version_no_tilde}.tar.gz
Source2:        99-nvme-nbft-no-ignore-carrier.conf

BuildRequires:  meson >= 1.0.0
BuildRequires:  gcc gcc-c++
BuildRequires:  systemd-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  zlib-devel
BuildRequires:  openssl-devel
BuildRequires:  keyutils-libs-devel
BuildRequires:  kmod-devel
%if (0%{?rhel} == 0) || (0%{?rhel} > 9)
BuildRequires:  kernel-headers
%endif

BuildRequires:  json-c-devel >= 0.14

BuildRequires:  asciidoc
BuildRequires:  xmlto
# libnvme's kernel-doc generates the libnvme3 API man pages
BuildRequires:  perl-interpreter

Requires:       util-linux
Requires:       libnvme3%{?_isa} = %{version}-%{release}


%description
nvme-cli provides NVM-Express user space tooling for Linux.

%package -n libnvme3
Summary:        Linux-native NVMe device management library, API 3
License:        LGPL-2.1-or-later

%description -n libnvme3
libnvme3 is the NVMe management library nvme-cli 3 carries in its own
tree. Its API and soname (libnvme3.so.1) are separate from libnvme 1.x
(libnvme.so.1), which stays installed for the libraries that link it.

%package -n libnvme3-devel
Summary:        Development files for libnvme3
License:        LGPL-2.1-or-later
Requires:       libnvme3%{?_isa} = %{version}-%{release}

%description -n libnvme3-devel
Headers, pkg-config file, API man pages and the unversioned link for
libnvme3.

%prep
%autosetup -p1 -n %{name}-%{version_no_tilde}


%build
# nvme-cli 3 builds its in-tree libnvme as libnvme3 (headers under
# include/libnvme3, pkg-config libnvme3), side by side with libnvme 1.x.
# Python bindings stay with libnvme 1.x (python3-libnvme). docs=all would
# also build libnvme's HTML reference, which needs Sphinx; man pages only.
%meson -Dudevrulesdir=%{_udevrulesdir} -Dsystemddir=%{_unitdir} -Ddocs=man -Ddocs-build=true -Dpython=disabled -Dtests=false -Djson-c=enabled -Dopenssl=enabled -Dkeyutils=enabled -Dlibkmod=enabled
%meson_build


%install
%meson_install
%{__install} -Dpm 644 README.md %{buildroot}%{_pkgdocdir}/README.md
mkdir -p $RPM_BUILD_ROOT%{nmlibdir}/conf.d
%{__install} -pm 644 %{SOURCE2} $RPM_BUILD_ROOT%{nmlibdir}/conf.d/

# hostid and hostnqn are supposed to be unique per machine.  We obviously
# can't package them.
# nvme-stas ships the stas-config@.service that will take care
# of generating these files if missing. See rhbz 2065886#c19
rm -f %{buildroot}%{_sysconfdir}/nvme/hostid
rm -f %{buildroot}%{_sysconfdir}/nvme/hostnqn

# Do not install the dracut rule yet.  See rhbz 1742764
rm -f %{buildroot}/usr/lib/dracut/dracut.conf.d/70-nvmf-autoconnect.conf


%post
# https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/#_systemd
%systemd_post nvmefc-boot-connections.service
%systemd_post nvmf-autoconnect.service
%systemd_post nvmf-connect@.service
%systemd_post nvmf-connect-nbft.service
if [ -S /run/udev/control ]; then
    udevadm control --reload
    udevadm trigger
fi

%preun
%systemd_preun nvmefc-boot-connections.service
%systemd_preun nvmf-autoconnect.service
%systemd_preun nvmf-connect@.service
%systemd_preun nvmf-connect-nbft.service

%postun
%systemd_postun nvmefc-boot-connections.service
%systemd_postun nvmf-autoconnect.service
%systemd_postun nvmf-connect@.service
%systemd_postun nvmf-connect-nbft.service


%files
%license LICENSE LICENSES/GPL-2.0-only.txt
%doc %{_pkgdocdir}
%{_sbindir}/nvme
%{_mandir}/man1/nvme*.1*
%{_mandir}/man5/nvme*.5*
%{_datadir}/bash-completion/completions/nvme
%{_datadir}/zsh/site-functions/_nvme
%dir %{_sysconfdir}/nvme
%config(noreplace) %{_sysconfdir}/nvme/nvme-fabrics.conf.sample
%{_unitdir}/nvmefc-boot-connections.service
%{_unitdir}/nvmf-autoconnect.service
%{_unitdir}/nvmf-connect.target
%{_unitdir}/nvmf-connect@.service
%{_unitdir}/nvmf-connect-nbft.service
%{_udevrulesdir}/65-persistent-net-nbft.rules
%{_udevrulesdir}/70-nvmf-autoconnect.rules
%{_udevrulesdir}/70-nvmf-keys.rules
%{_udevrulesdir}/70-nvmf-registry.rules
%{_udevrulesdir}/71-nvmf-netapp.rules
%{_udevrulesdir}/71-nvmf-vastdata.rules
%{_udevrulesdir}/71-nvmf-hpe.rules
# Do not install the dracut rule yet.  See rhbz 1742764
# /usr/lib/dracut/dracut.conf.d/70-nvmf-autoconnect.conf
%{nmlibdir}/dispatcher.d/80-nvmf-connect-nbft.sh
%{nmlibdir}/conf.d/99-nvme-nbft-no-ignore-carrier.conf

%files -n libnvme3
%license LICENSES/LGPL-2.1-or-later.txt
%{_libdir}/libnvme3.so.1{,.*}

%files -n libnvme3-devel
%{_includedir}/libnvme3/
%{_libdir}/libnvme3.so
%{_libdir}/pkgconfig/libnvme3.pc
%{_mandir}/man2/*-libnvme3.2*


%changelog
* Mon Nov 16 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 3.1-1
- Update to 3.1 (Dakota: freedesktop-sdk-extra components/nvme-cli.bst)
- Build the in-tree libnvme as the libnvme3 and libnvme3-devel subpackages
- Drop the format SIGINT and resv-report backports, both in 3.1
- Ship upstream's 80-nvmf-connect-nbft.sh NetworkManager hook instead of
  the local 99-nvme-nbft-connect.sh, which it supersedes
- discovery.conf is replaced by nvme-fabrics.conf; ship the sample

* Tue Sep 28 2026 Jesse Taube <jtaubepe@redhat.com> - 2.16-6
- Fix nvme resv report missing registrations

* Tue Aug 18 2026 Tomas Bzatek <tbzatek@redhat.com> - 2.16-5
- Fix ignored interruption in format command (#2501829)

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.16-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jun 12 2026 Yaakov Selkowitz <yselkowi@redhat.com> - 2.16-3
- Rebuilt for openssl 4.0

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 2.16-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Dec 04 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.16-1
- Update to 2.16

* Fri Aug 15 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.15-2
- Fix nvme-list JSON output compatibility
- Rename 71-nvme-hpe.rules to 71-nvmf-hpe.rules

* Fri Jul 25 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.15-1
- Update to 2.15

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.14-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Wed Jul 09 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.14-1
- Update to 2.14
- Disable Persistent Discovery Controllers by default

* Fri Apr 11 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.13-1
- Update to 2.13

* Mon Mar 17 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.12-1
- Update to 2.12

* Tue Feb 04 2025 Tomas Bzatek <tbzatek@redhat.com> - 2.11-3
- Add systemd units scriptlets
- Reload udevd after installing udev rules

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 2.11-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Oct 31 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.11-1
- Update to 2.11

* Mon Aug 26 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.10.2-2
- Install NetworkManager override for nbft interfaces
- Rename reconnect NetworkManager hook to 99-nvme-nbft-connect.sh

* Mon Aug 05 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.10.2-1
- Update to 2.10.2

* Mon Aug 05 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.10-1
- Update to 2.10

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.9.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Mon Jun 03 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.9.1-2
- Install custom nvmf-connect-nbft.sh NetworkManager hook

* Fri May 03 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.9.1-1
- Update to 2.9.1

* Tue Apr 23 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.8-2
- Harden the systemd units

* Wed Feb 14 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.8-1
- Update to 2.8

* Fri Feb 09 2024 Tomas Bzatek <tbzatek@redhat.com> - 2.7.1-4
- Lower the verbosity of TP4126 hostnqn-hostid consistency checks

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.7.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 2.7.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Dec 28 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.7.1-1
- Update to 2.7.1

* Fri Sep 29 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.6-1
- Update to 2.6

* Thu Aug 17 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.5-4
- Mark /etc/nvme/discovery.conf as (noreplace)

* Mon Aug 14 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.5-3
- Backport 'fabrics: Use corresponding hostid when hostnqn is generated'

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Tue Jul 04 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.5-1
- Update to 2.5

* Thu Apr 20 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.4-2
- Backport the NBFT support from git master

* Mon Apr 03 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.4-1
- Update to 2.4

* Wed Feb 01 2023 Tomas Bzatek <tbzatek@redhat.com> - 2.3-1
- Update to 2.3

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 2.2.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Fri Nov 04 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.2.1-1
- Update to 2.2.1

* Tue Nov 01 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.2-1
- Update to 2.2

* Fri Aug 19 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.1.2-1
- Update to 2.1.2

* Fri Aug 05 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.1.1-1
- Update to 2.1.1

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 2.1~rc0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Fri Jul 15 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.1~rc0-1
- Update to 2.1-rc0
- Drop the hostnqn generate scriptlet (#2065886)

* Mon Apr 11 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.0-1
- Update to 2.0

* Mon Apr 04 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.0~rc8-1
- Update to 2.0-rc8
- Added scriptlet to generate /etc/nvme/hostnqn and hostid files (#2065886)

* Tue Mar 15 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.0~rc6-1
- Update to 2.0-rc6

* Fri Mar 04 2022 Tomas Bzatek <tbzatek@redhat.com> - 2.0~rc5-1
- Update to 2.0-rc5

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.11.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sat Apr 25 2020 luto@kernel.org - 1.11.1-1
- Update to 1.11

* Thu Mar 19 2020 luto@kernel.org - 1.10.1-1
- Update to 1.10.1

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.9-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Wed Oct 02 2019 luto@kernel.org - 1.9-1
- Update to 1.9
- Certain fabric functionality may not work yet due to missing dracut
  support and missing hostid and hostnqn configuration.

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.8.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Mon Apr 15 2019 luto@kernel.org - 1.8.1-1
- Update to 1.8.1-1.
- Remove a build hack.

* Sun Feb 24 2019 luto@kernel.org - 1.7-2
- Create /etc/nvme

* Sun Feb 24 2019 luto@kernel.org - 1.7-1
- Bump to 1.7
- Clean up some trivial rpmlint complaints

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Tue Jul 24 2018 luto@kernel.org - 1.6-1
- Update to 1.6

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Nov 22 2017 luto@kernel.org - 1.4-1
- Update to 1.4

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Mon May 22 2017 luto@kernel.org - 1.3-1
- Update to 1.3

* Wed Apr 19 2017 luto@kernel.org - 1.2-2
- Update to 1.2
- 1.2-1 never existed

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Wed Feb 01 2017 luto@kernel.org - 1.1-1
- Update to 1.1

* Sun Nov 20 2016 luto@kernel.org - 1.0-1
- Update to 1.0

* Mon Oct 31 2016 luto@kernel.org - 0.9-1
- Update to 0.9

* Thu Jun 30 2016 luto@kernel.org - 0.8-1
- Update to 0.8

* Tue May 31 2016 luto@kernel.org - 0.7-1
- Update to 0.7

* Fri Mar 18 2016 luto@kernel.org - 0.5-1
- Update to 0.5

* Sun Mar 06 2016 luto@kernel.org - 0.4-1
- Update to 0.4

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.2-3.20160112gitbdbb4da
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jan 20 2016 luto@kernel.org - 0.2-2.20160112gitbdbb4da
- Update to new upstream commit, fixing #49.  "nvme list" now works.

* Wed Jan 13 2016 luto@kernel.org - 0.2-1.20160112gitde3e0f1
- Initial import.
