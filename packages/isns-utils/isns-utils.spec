Name:           isns-utils
Version:        0.103
Release:        %autorelease
Summary:        The iSNS daemon and utility programs

License:        LGPL-2.1-or-later
URL:            https://github.com/open-iscsi/open-isns
Source0:        https://github.com/open-iscsi/open-isns/archive/v%{version}.tar.gz#/open-isns-%{version}.tar.gz
Source1:        isnsd.service
Patch1:         test_as_installed.patch
Patch2:         0001-Fix-issue-in-error-path-causing-double-free.patch

BuildRequires:  gcc
BuildRequires:  pkgconfig systemd-devel systemd
BuildRequires:  meson ninja-build
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units
Requires: %{name}-libs%{?_isa} = %{version}-%{release}

%description
The iSNS package contains the daemon and tools to setup a iSNS server,
and iSNS client tools. The Internet Storage Name Service (iSNS) protocol
allows automated discovery, management and configuration of iSCSI and
Fibre Channel devices (using iFCP gateways) on a TCP/IP network.

%package libs
Summary: Shared library files for iSNS

%description libs
Shared library files for iSNS

%package devel
Summary: Development files for iSNS
Requires: %{name}-libs%{?_isa} = %{version}-%{release}

%description devel
Development files for iSNS


%prep
%autosetup -p1 -n open-isns-%{version}


%build
%meson -Dsecurity=disabled -Dslp=disabled
%meson_build

%install
%meson_install
chmod 755 %{buildroot}%{_sbindir}/isns*
chmod 755 %{buildroot}%{_libdir}/libisns.so.0
chmod 700 %{buildroot}/var/lib/isns
rm %{buildroot}%{_unitdir}/isnsd.service
rm %{buildroot}%{_unitdir}/isnsd.socket
install -p -m 644 %{SOURCE1} %{buildroot}%{_unitdir}/isnsd.service


%post
%systemd_post isnsd.service


%postun
%systemd_postun isnsd.service


%preun
%systemd_preun isnsd.service


%triggerun -- isns-utils < 0.91-7
# Save the current service runlevel info
# User must manually run systemd-sysv-convert --apply httpd
# to migrate them to systemd targets
/usr/bin/systemd-sysv-convert --save isnsd >/dev/null 2>&1 ||:

# Run these because the SysV package being removed won't do them
/sbin/chkconfig --del isnsd >/dev/null 2>&1 || :
/bin/systemctl try-restart isnsd.service >/dev/null 2>&1 || :


%ldconfig_scriptlets -n %{name}-libs


%files
%license COPYING
%doc README.md
%{_sbindir}/isnsd
%{_sbindir}/isnsadm
%{_sbindir}/isnsdd
%{_mandir}/man5/*
%{_mandir}/man8/*
%{_unitdir}/isnsd.service
%dir %{_sysconfdir}/isns
%dir %{_var}/lib/isns
%config(noreplace) %{_sysconfdir}/isns/*

%files libs
%license COPYING
%{_libdir}/libisns.so.0

%files devel
%dir %{_includedir}/libisns
%{_includedir}/libisns/*.h
%{_libdir}/libisns.so
%{_libdir}/pkgconfig/libisns.pc


%changelog
%autochangelog
