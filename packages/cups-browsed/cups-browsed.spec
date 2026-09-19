%global _cups_serverbin %{_prefix}/lib/cups

%if 0%{?fedora}
%bcond_without mdns
%else
%bcond_with mdns
%endif


Name: cups-browsed
Epoch: 1
Version: 2.1.1
Release: 8%{?dist}
Summary: Daemon for local auto-installation of remote printers
# the CUPS exception text is the same as LLVM exception, so using that name with
# agreement from legal team
# https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/message/A7GFSD6M3GYGSI32L2FC5KB22DUAEQI3/
License: Apache-2.0 WITH LLVM-exception
URL: https://github.com/OpenPrinting/cups-browsed
Source0: %{URL}/releases/download/%{version}/%{name}-%{version}.tar.gz


# Patches
# https://github.com/OpenPrinting/cups-browsed/pull/50
Patch01: 0001-Add-BrowseOptionsUpdate-configuration-directive-50.patch


# remove once CentOS Stream 10 is released, cups-browsed
# was shipped in cups-filters before 2.0
Conflicts: cups-filters < 2.0

# for generating configure and Makefile scripts in autogen.h
BuildRequires: autoconf
# for generating configure and Makefile scripts in autogen.h
BuildRequires: automake
# most filter functions written in C
BuildRequires: gcc
# for generating configure and Makefile scripts in autogen.h
BuildRequires: gettext-devel
# for autosetup
BuildRequires: git-core
# for generating configure and Makefile scripts in autogen.h
BuildRequires: libtool
# uses Makefiles
BuildRequires: make
# for pkg-config in configure and in SPEC file
BuildRequires: pkgconf-pkg-config
# for looking for devices on mDNS and their sharing on mDNS
BuildRequires: pkgconfig(avahi-client)
# for polling avahi
BuildRequires: pkgconfig(avahi-glib)
# uses CUPS and IPP API
BuildRequires: pkgconfig(cups) >= 2.2.2
# uses cupsfilters API
BuildRequires: pkgconfig(libcupsfilters) >= 2.0b3
# implicitclass uses libppd
BuildRequires: pkgconfig(libppd) >= 2.0b3
# for dBUS proxy from GLib
BuildRequires: pkgconfig(glib-2.0)
# needed for systemd rpm macros in scriptlets
BuildRequires: systemd-rpm-macros

%if %{with mdns}
# Avahi has to run for mDNS support
Recommends: avahi
# if set to browse or share mDNS, we need a resolver
Recommends: nss-mdns
%endif
# only recommends cups RPM in case someone wants to use CUPS container/SNAP
# - cups-browsed has to have a cupsd daemon to send requests to
# using a weak dep will work for bootstraping as well in case the old cups-filters
# 1.x, which is CUPS dependency, will be in repos when cups-browsed
Recommends: cups

# requires cups directories
Requires: cups-filesystem

Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd


%description
cups-browsed is a helper daemon, which automatically installs printers
locally, provides load balancing and clustering of print queues.
The daemon installs the printers based on found mDNS records and CUPS
broadcast, or by polling a remote print server.


%prep
%autosetup -S git


%build
# generate configuration/compilation files
./autogen.sh

# --enable-auto-setup-driverless-only - enable autoinstalling of driverless IPP
# destinations
# --disable-saving-created-queues - don't save the queues during shutdown
# --disable-frequent-netif-update - don't update network interfaces after
# every found printer, update only on NM dBUS event
# --with-browseremoteprotocols - which protocols to use for looking for printers, default DNSSD and CUPS
# --with-remote-cups-local-queue-naming - use the name from remote server
# if polling the server for printers via BrowsePoll
%configure --enable-auto-setup-driverless-only\
  --disable-rpath\
  --disable-saving-created-queues\
  --disable-frequent-netif-update\
  --with-browseremoteprotocols=none\
  --with-remote-cups-local-queue-naming=RemoteName\
  --without-rcdir

%make_build


%install
%make_install

# systemd unit file
mkdir -p %{buildroot}%{_unitdir}
install -p -m 644 daemon/cups-browsed.service %{buildroot}%{_unitdir}

# remove INSTALL file
rm -f %{buildroot}%{_pkgdocdir}/INSTALL

# provided by cups-browsed dependency
rm -f %{buildroot}%{_pkgdocdir}/CHANGES-1.x.md

# license related files are already under /usr/share/licenses
rm -f %{buildroot}%{_pkgdocdir}/{LICENSE,COPYING,NOTICE}


%post
%systemd_post cups-browsed.service

# put UpdateCUPSQueuesMaxPerCall and PauseBetweenCUPSQueueUpdates into cups-browsed.conf
# for making cups-browsed work more stable for environments with many print queues
# TODO make this configurable during build
for directive in "UpdateCUPSQueuesMaxPerCall" "PauseBetweenCUPSQueueUpdates"
do
    found=`%{_bindir}/grep "^[[:blank:]]*$directive" %{_sysconfdir}/cups/cups-browsed.conf`
    if [ -z "$found" ]
    then
        if [ "x$directive" == "xUpdateCUPSQueuesMaxPerCall" ]
        then
            %{_bindir}/echo "UpdateCUPSQueuesMaxPerCall 20" >> %{_sysconfdir}/cups/cups-browsed.conf
        else
            %{_bindir}/echo "PauseBetweenCUPSQueueUpdates 5" >> %{_sysconfdir}/cups/cups-browsed.conf
        fi
    fi
done

# Set BrowseRemoteProtocols to none in light of CVE-2024-47176 when upgrading
if [ $1 -gt 1 ]
then
  if ! grep -Fxq "# added by post scriptlet" %{_sysconfdir}/cups/cups-browsed.conf && ! grep -iq "^\s*BrowseRemoteProtocols none" %{_sysconfdir}/cups/cups-browsed.conf
  then
    cp %{_sysconfdir}/cups/cups-browsed.conf %{_sysconfdir}/cups/cups-browsed.conf.rpmsave
    sed -i "s/^\s*BrowseRemoteProtocols.*/# added by post scriptlet\nBrowseRemoteProtocols none/" %{_sysconfdir}/cups/cups-browsed.conf
  fi
fi

%preun
%systemd_preun cups-browsed.service

%postun
%systemd_postun_with_restart cups-browsed.service

# remove once F41 is EOL
%posttrans
if ls -lah /var/cache/cups/cups-browsed* &> /dev/null
then
  BROWSED_ACTIVE="0"
  CUPSD_ACTIVE="0"

  if systemctl is-active cups-browsed &> /dev/null
  then
    BROWSED_ACTIVE="1"
    CUPSD_ACTIVE="1"
  elif systemctl is-active cups &> /dev/null
  then
    CUPSD_ACTIVE="1"
  fi

  if test "x$CUPSD_ACTIVE" = "x1"
  then
    systemctl stop cups
  fi
  
  # RHEL-46785 - clean up recorded options to make the fix work
  rm -rf /var/cache/cups/*.data /var/cache/cups/cups-browsed* &> /dev/null
  
  if test "x$BROWSED_ACTIVE" = "x1"
  then
    systemctl start cups-browsed
  elif test "x$CUPSD_ACTIVE" = "x1"
  then
    systemctl start cups
  fi
fi


%files
%license COPYING LICENSE NOTICE
%doc ABOUT-NLS AUTHORS CHANGES.md CONTRIBUTING.md DEVELOPING.md README.md
# implicitclass backend must be run as root
# https://github.com/OpenPrinting/cups-filters/issues/183#issuecomment-570196216
%attr(0744,root,root) %{_cups_serverbin}/backend/implicitclass
# 2123809 - rpm -Va reports changes due %%post scriptlet (remove the verify part once we remove
# cups-browsed.conf update from %%post scriptlet)
%config(noreplace) %verify(not size filedigest mtime) %{_sysconfdir}/cups/cups-browsed.conf
%{_mandir}/man5/cups-browsed.conf.5.gz
%{_mandir}/man8/cups-browsed.8.gz
%{_sbindir}/cups-browsed
%{_unitdir}/cups-browsed.service


%changelog
* Wed Jul 15 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.1.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.1.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.1.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.1.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Mon May 05 2025 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.1.1-4
- cups-browsed.conf is not clean for rpmconf (fedora#2363223)

* Mon Apr 14 2025 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.1.1-3
- Add BrowseOptionsUpdate directive

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Fri Jan 10 2025 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.1.1-1
- 2.1.1 (fedora#2336480)

* Thu Dec 19 2024 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.1.0-1
- 2.1.0 (fedora#2319904)

* Tue Oct 15 2024 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0.1-4
- do not create PPDs for remote raw queues
- remove the whole CUPS Browsing and LDAP support

* Thu Sep 26 2024 Justin M. Forbes <jforbes@fedoraproject.org> - 1:2.0.1-2
- Fix for CVE-2024-47176

* Thu Aug 15 2024 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0.1-1
- 2305072 - cups-browsed-2.0.1 is available

* Tue Aug 06 2024 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0.0-6
- Cups browsing with 'Autoclustering on' cannot find printer clusters for HA due incorrect orientation-requested-default

* Wed Jul 17 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0.0-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Wed Feb 07 2024 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0.0-4
- 2253985 - cups-browsed crashes when remote CUPS queue found by DNS-SD is not able to response on IPP Get-Printer-Attributes
- fix several issues reported by openscanhub

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Oct 04 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0.0-1
- 2240317 - cups-browsed-2.0.0 is available

* Tue Aug 29 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~rc2-3
- 2150035 - [abrt] cups-filters: __strlen_avx2(): cups-browsed killed by SIGSEGV

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1:2.0~rc2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Wed Jun 28 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~rc2-1
- 2.0rc2

* Thu Apr 27 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~rc1-1
- 2.0rc1

* Mon Apr 03 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~b4-1
- 2179346 - cups-browsed-2.0b4 is available

* Wed Mar 01 2023 Zdenek Dohnal <zdohnal@redhat.com> - 1:2.0~b3-2
- use Epoch to ensure upgrade path because I didn't read FPG carefully

* Thu Feb 02 2023 Zdenek Dohnal <zdohnal@redhat.com> - 2.0b3-1
- Initial import (fedora#2170547)
