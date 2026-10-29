%if 0%{?fedora} < 36 && 0%{?rhel} < 9
%bcond_with gtk4
%else
%bcond_without gtk4
%endif

%global selinuxtype targeted
%global selinuxmodulename NetworkManager-ssh
%global selinuxmoduledir selinux

Summary: NetworkManager VPN plugin for SSH
Name: NetworkManager-ssh
Version: 1.4.5
Release: 3%{?dist}
# Automatically converted from old format: GPLv2+ - review is highly recommended.
License: GPL-2.0-or-later
URL: https://github.com/danfruehauf/NetworkManager-ssh
Source0: https://github.com/danfruehauf/NetworkManager-ssh/archive/1.4.5.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires: make
BuildRequires: autoconf
BuildRequires: gtk3-devel
BuildRequires: NetworkManager-libnm-devel >= 1:1.2.6
BuildRequires: glib2-devel
BuildRequires: libtool intltool gettext-devel
BuildRequires: libnma-devel >= 1.1.0
BuildRequires: libsecret-devel
BuildRequires: bzip2
BuildRequires: selinux-policy
BuildRequires: checkpolicy
Requires: gtk3
Requires: dbus
Requires: NetworkManager >= 1:1.2.6
Requires: openssh-clients
Requires: shared-mime-info
Requires: sshpass
Requires: (%{name}-selinux = %{version}-%{release} if selinux-policy-targeted)

%if %with gtk4
BuildRequires: libnma-gtk4-devel
%endif

%global __provides_exclude ^libnm-.*\\.so

%description
This package contains software for integrating VPN capabilities with
the OpenSSH server with NetworkManager.

%package gnome
Summary: NetworkManager VPN plugin for SSH - GNOME files
Requires: %{name}%{?_isa} = %{version}-%{release}

%description gnome
This package contains software for integrating VPN capabilities with
the OpenSSH server with NetworkManager (GNOME files).

%package selinux
Summary: NetworkManager-ssh selinux policy module
License: GPL-2.0-or-later
BuildRequires: selinux-policy

%description selinux
Install NetworkManager-ssh-selinux policy

%prep
%setup -q

%build
autoreconf -fvi
%if 0%{?rhel} == 7
CFLAGS="-DSECRET_API_SUBJECT_TO_CHANGE %{optflags}" \
%endif
%configure \
        --disable-static \
%if %with gtk4
        --with-gtk4 \
%endif
        --enable-more-warnings=yes \
        --with-dist-version=%{version}-%{release}
make %{?_smp_mflags}

pushd .
cd %{selinuxmoduledir}
checkmodule -M -m -o %{selinuxmodulename}.mod %{selinuxmodulename}.te
semodule_package -o %{selinuxmodulename}.pp -m %{selinuxmodulename}.mod
bzip2 %{selinuxmodulename}.pp
popd

%install
make install DESTDIR=%{buildroot} INSTALL="%{__install} -p"
mkdir -p %{buildroot}%{_prefix}/lib/NetworkManager/VPN
%{__cp} -p ./nm-ssh-service.name %{buildroot}%{_prefix}/lib/NetworkManager/VPN/
%{__rm} -f %{buildroot}%{_libdir}/NetworkManager/lib*.la
mkdir -p %{buildroot}/%{_datadir}/selinux/packages
%{__cp} -p %{selinuxmoduledir}/%{selinuxmodulename}.pp.bz2 %{buildroot}/%{_datadir}/selinux/packages/%{selinuxmodulename}.pp.bz2

%find_lang %{name}

%files -f %{name}.lang
%{_datadir}/dbus-1/system.d/nm-ssh-service.conf
%{_prefix}/lib/NetworkManager/VPN/nm-ssh-service.name
%{_libexecdir}/nm-ssh-service
%{_libexecdir}/nm-ssh-auth-dialog
%doc AUTHORS README ChangeLog NEWS
%license COPYING

%files gnome
%{_libdir}/NetworkManager/libnm-vpn-plugin-ssh.so
%{_datadir}/metainfo/network-manager-ssh.metainfo.xml
%{_libdir}/NetworkManager/libnm-gtk3-vpn-plugin-ssh-editor.so

%if %with gtk4
%{_libdir}/NetworkManager/libnm-gtk4-vpn-plugin-ssh-editor.so
%endif
%files selinux
%attr(0644,root,root) %{_datadir}/selinux/packages/%{selinuxmodulename}.pp.bz2
%ghost %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/%{selinuxmodulename}
%license COPYING


%post selinux
%selinux_modules_install -s %{selinuxtype} -p 200 %{_datadir}/selinux/packages/%{selinuxmodulename}.pp.bz2 &> /dev/null

%postun selinux
if [ $1 -eq 0 ]; then
  %selinux_modules_uninstall -s %{selinuxtype} -p 200 %{selinuxmodulename}
fi

%posttrans selinux
%selinux_relabel_post -s %{selinuxtype} &> /dev/null

%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sun Jul 12 2026 Dan Fruehauf <malkodan@gmail.com> - 1.4.5-2
- Pin selinux version to installed NetworkManager-ssh version

* Wed Jul 08 2026 Dan Fruehauf <malkodan@gmail.com> - 1.4.5-1
- Fix selinux policy to allow access to /run/NetworkManager/cert

* Tue Apr 07 2026 Dan Fruehauf <malkodan@gmail.com> - 1.4.4-1
- Add sshpass -P prompt

* Fri Apr 03 2026 Dan Fruehauf <malkodan@gmail.com> - 1.4.3-1
- Always run autoreconf -fvi
- Fix file access for private key and known hosts (rhbz#2428396)
- Fix pkg-config macro
- Move D-Bus policy file to /usr/share/dbus-1/system.d/

* Sat Jan 31 2026 Dan Fruehauf <malkodan@gmail.com> - 1.4.2-4
- Fix compilation error on f44

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Oct 14 2025 Dan Fruehauf <malkodan@gmail.com> - 1.4.2-1
- Revert gettext fix
- Update to upstream 1.4.2 (ipv6 connections)

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Wed May 28 2025 Dan Fruehauf <malkodan@gmail.com> - 1.4.1-2
- Allow connection to any remote port (selinux)

* Sun Apr 13 2025 Dan Fruehauf <malkodan@gmail.com> - 1.4.1-1
- Update to upstream 1.4.1
- Local bind support
- Remote bind support
- Support for no remote device, sudo command, and no remote command

* Thu Mar 27 2025 Dan Fruehauf <malkodan@gmail.com> - 1.3.1-1
- Fix selinux policy to support connection to any port (not just 22)

* Tue Mar 25 2025 Dan Fruehauf <malkodan@gmail.com> - 1.3.0-1
- Update from upstream to version 1.3.0
- Support for no tunnel (dummy interface)
- Support for SOCKS, local and remote binds

* Fri Mar 21 2025 Dan Fruehauf <malkodan@gmail.com> - 1.2.15-1
- Update from upstream, build fixes

* Thu Mar 06 2025 Dan Fruehauf <malkodan@gmail.com> - 1.2.14-2
- Selinux separate package (NetowrkManager-ssh-selinux)

* Thu Mar 06 2025 Dan Fruehauf <malkodan@gmail.com> - 1.2.14-1
- Selinux policy

* Fri Feb 28 2025 Dan Fruehauf <malkodan@gmail.com> - 1.2.13-5
- GTK3/GTK4 adjustments

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.13-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jul 26 2024 Miroslav Suchý <msuchy@redhat.com> - 1.2.13-3
- convert license to SPDX

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.13-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Mar 15 2024 Dan Fruehauf <malkodan@gmail.com> - 1.2.13-1
- Fix build
- Update to gtk4 version

* Mon Jan 22 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Jan 18 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Jul 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Jan 19 2022 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Wed Jul 21 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.12-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Apr 13 2021 Dan Fruehauf <malkodan@gmail.com> - 1.2.12-1
- Initialize variables, compile on f34 (https://bugzilla.redhat.com/show_bug.cgi?id=1943040)

* Mon Jan 25 2021 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.11-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.11-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sun Feb 16 2020 Dan Fruehauf <malkodan@gmail.com> - 1.2.11-1
- Fix privilege escalation (https://bugzilla.redhat.com/show_bug.cgi?id=1803499)

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.10-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu May 09 2019 Dan Fruehauf <malkodan@gmail.com> - 1.2.10-1
- Update from upstream to 1.2.10
- Fix 100% cpu usage bug

* Fri Feb 15 2019 Dan Fruehauf <malkodan@gmail.com> - 1.2.9-1
- Update from upstream to 1.2.9
- Fix deprecated declarations

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.7-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Thu Jul 12 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.7-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Sun Mar 18 2018 Lubomir Rintel <lkundrak@v3.sk> - 1.2.7-4
- Do not drag in the connection editor

* Fri Mar 16 2018 Dan Fruehauf <malkodan@gmail.com> - 1.2.7-3
- Drop libnm-glib for Fedora 28

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Dec 07 2017 Dan Fruehauf <malkodan@gmail.com> - 1.2.7-1
- Support for multiple connections

* Thu Nov 30 2017 Lubomir Rintel <lkundrak@v3.sk> - 1.2.6-4
- Drop libnm-glib for Fedora 28

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue May 02 2017 Dan Fruehauf <malkodan@gmail.com> - 1.2.6-1
- Update to 1.2.6 release

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-1
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Sep 01 2016 Dan Fruehauf <malkodan@gmail.com> - 1.2.1-0
- Update to 1.2.1 release
- Fixed upstream #57 (Fedora #1350244) - Time out waiting for service

* Sat Apr 23 2016 Lubomir Rintel <lkundrak@v3.sk> - 1.2.0-1
- Update to 1.2.0 release

* Wed Feb 03 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.0-0.2.20151023git6a5c776
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Mon Aug 31 2015 Lubomir Rintel <lkundrak@v3.sk> - 1.2.0-0.1.20151023git6a5c776
- Switch back to upstream source
- Fix build with the NetworkManager 1.2 snapshot

* Mon Aug 31 2015 Lubomir Rintel <lkundrak@v3.sk> - 1.2.0-0.1.20150831git2b4fb23
- Update to 1.2 git snapshot with libnm-based properties plugin

* Mon Jul 13 2015 Dan Fruehauf <malkodan@gmail.com> - 0.9.4-0.1.20150713git60f03fe
- Release 0.9.4

* Tue Jun 16 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.3-0.4.20140601git9d834f2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Fri Aug 15 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.3-0.3.20140601git9d834f2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Fri Jun 06 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.3-0.2.20140601git9d834f2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Sun Jun 01 2014 Dan Fruehauf <malkodan@gmail.com> - 0.9.3-0.1.20140601git9d834f2
- Fixed GTK_STOCK deprecation errors
- Czech translation by Jiri Kilmes

* Sun Feb 09 2014 Dan Fruehauf <malkodan@gmail.com> - 0.9.2-0.2.20140209git46247c2
- Fixed upstream #25 (Fedora #1056810) - Bad strcmp usage
- Fixed upstream #27 (Fedora #1061365, #1058028) - sshpass via fd

* Sun Aug 11 2013 Dan Fruehauf <malkodan@gmail.com> - 0.9.1-0.5.20130706git6bf4649
- Added $RPM_OPT_FLAGS to CFLAGS

* Mon Aug 05 2013 Dan Fruehauf <malkodan@gmail.com> - 0.9.1-0.4.20130706git6bf4649
- Remove deprecated warning

* Fri Aug 02 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.1-0.3.20130706git6bf4649
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Sat Jul 06 2013 Dan Fruehauf <malkodan@gmail.com> - 0.9.1-0.2.20130706git6bf4649
- Depends on sshpass

* Sat Jul 06 2013 Dan Fruehauf <malkodan@gmail.com> - 0.9.1-0.1.20130706git6bf4649
- Support for password and plain key authentication 

* Tue Jun 25 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.4-0.1.20130625git241fee0
- Can choose to not set VPN as default route

* Fri Apr 19 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.8.20130419git3d5321b
- DBUS and NetworkManager files in /etc are no longer config files
- Other refactoring to conform with other NetworkManager VPN plugins

* Fri Apr 05 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.7.20130405git6ba59c4
- Added sub package for NetworkManager-ssh-gnome

* Tue Apr 02 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.6.20130402git6ba59c4
- Fixed dependencies (openssh-clients
- Added private libs

* Sat Mar 30 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.5.20130330git9afb20
- Removed macros from changelog

* Thu Mar 28 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.4.20130328gita2add30
- Fixed more issues in spec to conform with Fedora Packaging standards

* Tue Mar 26 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.3.20130326git7549f1d
- More changes to conform with Fedora packaging standards

* Fri Mar 22 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.2.20130322git8767415
- Changes to conform with Fedora packaging standards

* Wed Mar 20 2013 Dan Fruehauf <malkodan@gmail.com> - 0.0.3-0.1.20130320gitcf6c00f
- Initial spec release
