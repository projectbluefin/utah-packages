%global open_iscsi_version	2.1
%global open_iscsi_build	13
%global commit0			40f6b2944f8a8553ad57975d1f2bb512cc23d7d1
%global shortcommit0		%(c=%{commit0}; echo ${c:0:7})
%global commitdate0		20260908
# set this to 1 if commit0 is a snapshot after the tagged version
%global with_snapshot		0

Summary: iSCSI daemon and utility programs
Name: iscsi-initiator-utils
%if %{with_snapshot}
Version: 6.%{open_iscsi_version}.%{open_iscsi_build}^%{commitdate0}git%{shortcommit0}
%else
Version: 6.%{open_iscsi_version}.%{open_iscsi_build}
%endif
Release: %autorelease
License: GPL-2.0-or-later
URL: https://github.com/open-iscsi/open-iscsi
Source0: https://github.com/open-iscsi/open-iscsi/archive/%{commit0}.tar.gz#/open-iscsi-%{shortcommit0}.tar.gz
Source4: 04-iscsi
Source5: iscsi-tmpfiles.conf

Patch01: 0001-meson-don-t-hide-things-with-Wno-all.patch

# https://github.com/open-iscsi/open-iscsi/pull/394/
Patch02: 0002-Currently-when-iscsi.service-is-installed-it-creates.patch
Patch03: 0003-Use-DBROOT-in-iscsi-starter.-Include-iscsi-starter-i.patch
Patch04: 0004-fix-systemctl-path-in-iscsi-starter.service.patch

# Fedora / Red Hat stuff, merge more of this upstream?
Patch05: 0005-improved-onboot-and-shutdown-services.patch
Patch06: 0006-iscsid.conf-Fedora-Red-Hat-defaults.patch
Patch07: 0007-Disable-Data-Digests.patch
Patch08: 0008-Revert-iscsiadm-return-error-when-login-fails.patch
Patch09: 0009-Coverity-scan-fixes.patch
Patch10: 0010-use-Red-Hat-version-string-to-match-RPM-package-vers.patch

# libiscsi, deprecated but still needed until UDisks2 is converted to libopeniscsiusr
Patch101: 0101-libiscsi.patch
Patch102: 0102-libiscsi-introduce-sessions-API.patch
Patch103: 0103-fix-libiscsi-firmware-discovery-issue-with-NULL-drec.patch
Patch104: 0104-libiscsi-build-fixes.patch

BuildRequires: meson git
BuildRequires: flex bison doxygen kmod-devel systemd-units
BuildRequires: autoconf automake libtool libmount-devel openssl-devel
BuildRequires: isns-utils-devel
BuildRequires: systemd-devel
Requires: %{name}-iscsiuio >= %{version}-%{release}
Requires: (fedora-release-common >= 38-0.23 if fedora-release-common)
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

# Old NetworkManager expects the dispatcher scripts in a different place
Conflicts: NetworkManager < 1.20

%global _hardened_build 1
%global __provides_exclude_from ^(%{?python3_sitearch:%{python3_sitearch}/.*\\.so})$

%description
The iscsi package provides the server daemon for the iSCSI protocol,
as well as the utility programs used to manage it. iSCSI is a protocol
for distributed disk access using SCSI commands sent over Internet
Protocol networks.

%package iscsiuio
Summary: Userspace configuration daemon required for some iSCSI hardware
License: BSD-4-Clause
Requires: %{name} = %{version}-%{release}

%description iscsiuio
The iscsiuio configuration daemon provides network configuration help
for some iSCSI offload hardware.

%package devel
Summary: Development files for %{name}
Requires: %{name} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package -n python3-%{name}
Summary: Python %{python3_version} bindings to %{name}
Requires: %{name} = %{version}-%{release}
BuildRequires: python3-devel
BuildRequires: make

%description -n python3-%{name}
The %{name}-python3 package contains Python %{python3_version} bindings to the
libiscsi interface for interacting with %{name}

%prep
%autosetup -p1 -n open-iscsi-%{commit0} -Sgit_am

%generate_buildrequires
pushd libiscsi > /dev/null
%pyproject_buildrequires
popd > /dev/null

%build
# avoid undefined references linking failures
%undefine _ld_as_needed

%meson -Diqn_prefix=iqn.1994-05.com.redhat -Discsi_sbindir=%{_sbindir}
%meson_build

%make_build LDFLAGS="%{build_ldflags}" iqn_prefix=iqn.1994-05.com.redhat DBROOT=/var/lib/iscsi libiscsi
pushd libiscsi
%pyproject_wheel
touch -r libiscsi.doxy html/*
popd

%install
%meson_install
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/nodes
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/send_targets
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/static
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/isns
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/slp
%{__install} -d $RPM_BUILD_ROOT%{_sharedstatedir}/iscsi/ifaces

# for %%ghost
%{__install} -d $RPM_BUILD_ROOT%{_rundir}/lock/iscsi
touch $RPM_BUILD_ROOT%{_rundir}/lock/iscsi/lock

# upstream started installing a bunch of optional stuff from other distros
# maybe we can make use of these, but clean up for now
rm $RPM_BUILD_ROOT/etc/iscsi/initiatorname.iscsi
rm $RPM_BUILD_ROOT/etc/udev/rules.d/50-iscsi-firmware-login.rules
rm $RPM_BUILD_ROOT/usr/lib/systemd/system-generators/ibft-rule-generator
rm $RPM_BUILD_ROOT/%{_sbindir}/brcm_iscsiuio
rm $RPM_BUILD_ROOT/%{_sbindir}/iscsi_discovery
rm $RPM_BUILD_ROOT/%{_sbindir}/iscsi_fw_login
rm $RPM_BUILD_ROOT/%{_sbindir}/iscsi_offload
rm $RPM_BUILD_ROOT/usr/share/man/man8/iscsi_discovery.8
rm $RPM_BUILD_ROOT/usr/share/man/man8/iscsi_fw_login.8

%{__install} -d $RPM_BUILD_ROOT%{_libexecdir}
%{__install} -pm 755 etc/systemd/iscsi-mark-root-nodes $RPM_BUILD_ROOT%{_libexecdir}

%{__install} -d $RPM_BUILD_ROOT%{_prefix}/lib/NetworkManager/dispatcher.d
%{__install} -pm 755 %{SOURCE4} $RPM_BUILD_ROOT%{_prefix}/lib/NetworkManager/dispatcher.d

%{__install} -d $RPM_BUILD_ROOT%{_tmpfilesdir}
%{__install} -pm 644 %{SOURCE5} $RPM_BUILD_ROOT%{_tmpfilesdir}/iscsi.conf

%{__install} -d $RPM_BUILD_ROOT%{_libdir}
%{__install} -pm 755 libiscsi/libiscsi.so.0 $RPM_BUILD_ROOT%{_libdir}
%{__ln_s}    libiscsi.so.0 $RPM_BUILD_ROOT%{_libdir}/libiscsi.so
%{__install} -d $RPM_BUILD_ROOT%{_includedir}
%{__install} -pm 644 libiscsi/libiscsi.h $RPM_BUILD_ROOT%{_includedir}

pushd libiscsi
%{__install} -d $RPM_BUILD_ROOT%{python3_sitearch}
%pyproject_install
%pyproject_save_files '*'
popd

%post
%systemd_post iscsi.service iscsi-starter.service iscsid.service iscsid.socket iscsi-onboot.service iscsi-init.service iscsi-shutdown.service

%preun
%systemd_preun iscsi.service iscsi-starter.service iscsid.service iscsid.socket iscsi-onboot.service iscsi-init.service iscsi-shutdown.service

%postun
%systemd_postun iscsi.service iscsi-starter.service iscsid.service iscsid.socket iscsi-onboot.service iscsi-init.service iscsi-shutdown.service

%post iscsiuio
%systemd_post iscsiuio.service iscsiuio.socket

%preun iscsiuio
%systemd_preun iscsiuio.service iscsiuio.socket

%postun iscsiuio
%systemd_postun iscsiuio.service iscsiuio.socket

%triggerun -- %{name} < 6.2.1.4-8
# This is for upgrades from previous versions before iscsi-starter.service was added.
systemctl --no-reload preset iscsi.service iscsi-starter.service &>/dev/null || :

%files
%doc README
%dir %{_sharedstatedir}/iscsi
%dir %{_sharedstatedir}/iscsi/nodes
%dir %{_sharedstatedir}/iscsi/isns
%dir %{_sharedstatedir}/iscsi/static
%dir %{_sharedstatedir}/iscsi/slp
%dir %{_sharedstatedir}/iscsi/ifaces
%dir %{_sharedstatedir}/iscsi/send_targets
%ghost %dir %attr(0700, root, root) %{_rundir}/lock/iscsi
%ghost %attr(0600, root, root) %{_rundir}/lock/iscsi/lock
%{_unitdir}/iscsi.service
%{_unitdir}/iscsi-starter.service
%{_unitdir}/iscsi-onboot.service
%{_unitdir}/iscsi-init.service
%{_unitdir}/iscsi-shutdown.service
%{_unitdir}/iscsid.service
%{_unitdir}/iscsid.socket
%{_libexecdir}/iscsi-mark-root-nodes
%{_prefix}/lib/NetworkManager
%{_tmpfilesdir}/iscsi.conf
%dir %{_sysconfdir}/iscsi
%attr(0600,root,root) %config(noreplace) %{_sysconfdir}/iscsi/iscsid.conf
%{_sbindir}/iscsi-iname
%{_sbindir}/iscsi-gen-initiatorname
%{_sbindir}/iscsiadm
%{_sbindir}/iscsid
%{_sbindir}/iscsistart
%{_libdir}/libiscsi.so.0
%{_mandir}/man8/iscsi-iname.8.gz
%{_mandir}/man8/iscsi-gen-initiatorname.8.gz
%{_mandir}/man8/iscsiadm.8.gz
%{_mandir}/man8/iscsid.8.gz
%{_mandir}/man8/iscsistart.8.gz
%{_libdir}/libopeniscsiusr.so.*

%files iscsiuio
%{_sbindir}/iscsiuio
%{_unitdir}/iscsiuio.service
%{_unitdir}/iscsiuio.socket
%config(noreplace) %{_sysconfdir}/logrotate.d/iscsiuiolog
%{_mandir}/man8/iscsiuio.8.gz

%files devel
%doc libiscsi/html
%{_libdir}/libiscsi.so
%{_includedir}/libiscsi.h
%{_libdir}/libopeniscsiusr.so
%{_includedir}/libopeniscsiusr.h
%{_includedir}/libopeniscsiusr_common.h
%{_includedir}/libopeniscsiusr_iface.h
%{_includedir}/libopeniscsiusr_node.h
%{_includedir}/libopeniscsiusr_session.h
%{_libdir}/pkgconfig/libopeniscsiusr.pc
%{_mandir}/man3/*

%files -n python3-%{name} -f %{pyproject_files}

%changelog
%autochangelog
