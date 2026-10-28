# snapshot version
%global snapver .20240616git
# use hardened build
%global _hardened_build 1
# udev rules prefix
%global udev_prefix 70

Name:     hyperv-daemons
Version:  6.10
Release:  %autorelease
Summary:  Hyper-V daemons suite

License:  GPL-2.0-only
URL:      http://www.kernel.org

# Source files obtained from kernel upstream 6.10-rc4 (6ba59ff4227927d3a8530fc2973b80e94b54d58f)
# git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
Source0:  tools-hv-6ba59ff42279.tar.gz
Source1:  COPYING

# HYPERV KVP DAEMON
Source5:  hypervkvpd.service
Source6:  hypervkvp.rules

# HYPERV VSS DAEMON
Source101:  hypervvssd.service
Source102:  hypervvss.rules

# HYPERV FCOPY DAEMON
Source201:  hypervfcopyd.service
Source202:  hypervfcopy.rules

# Hyper-V is available only on x86 and aarch64 architectures
# The base empty (a.k.a. virtual) package can not be noarch
# due to http://www.rpm.org/ticket/78
ExclusiveArch:  i686 x86_64 aarch64

Requires:       hypervkvpd = %{version}-%{release}
Requires:       hypervvssd = %{version}-%{release}
# Fcopy UIO driver is x86 only
%ifarch i686 x86_64
Requires:       hypervfcopyd = %{version}-%{release}
%else
Obsoletes:      hypervfcopyd <= %{version}-%{release}
%endif
BuildRequires:  gcc

%description
Suite of daemons that are needed when Linux guest
is running on Windows Host with Hyper-V.


%package -n hypervkvpd
Summary: Hyper-V key value pair (KVP) daemon
Requires: %{name}-license = %{version}-%{release}
BuildRequires: systemd, kernel-headers
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description -n hypervkvpd
Hypervkvpd is an implementation of Hyper-V key value pair (KVP)
functionality for Linux. The daemon first registers with the
kernel driver. After this is done it collects information
requested by Windows Host about the Linux Guest. It also supports
IP injection functionality on the Guest.


%package -n hypervvssd
Summary: Hyper-V VSS daemon
Requires: %{name}-license = %{version}-%{release}
BuildRequires: systemd, kernel-headers
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description -n hypervvssd
Hypervvssd is an implementation of Hyper-V VSS functionality
for Linux. The daemon is used for host initiated guest snapshot
on Hyper-V hypervisor. The daemon first registers with the
kernel driver. After this is done it waits for instructions
from Windows Host if to "freeze" or "thaw" the filesystem
on the Linux Guest.

# Fcopy UIO driver is x86 only
%ifarch i686 x86_64
%package -n hypervfcopyd
Summary: Hyper-V FCOPY daemon
Requires: %{name}-license = %{version}-%{release}
BuildRequires: systemd, kernel-headers
Requires(post):   systemd
Requires(preun):  systemd
Requires(postun): systemd

%description -n hypervfcopyd
Hypervfcopyd is an implementation of file copy service functionality
for Linux Guest running on Hyper-V. The daemon enables host to copy
a file (over VMBUS) into the Linux Guest. The daemon first registers
with the kernel driver. After this is done it waits for instructions
from Windows Host.
%endif

%package license
Summary:    License of the Hyper-V daemons suite
BuildArch:  noarch

%description license
Contains license of the Hyper-V daemons suite.

%package -n hyperv-tools
Summary:    Tools for Hyper-V guests
BuildArch:  noarch

%description -n hyperv-tools
Contains tools and scripts useful for Hyper-V guests.

%prep
%setup -q -n tools/hv
cp -pvL %{SOURCE1} COPYING

%build
%make_build

%install
%make_install sbindir=%{_sbindir}

# Systemd unit file
mkdir -p %{buildroot}%{_unitdir}
install -p -m 0644 %{SOURCE5} %{buildroot}%{_unitdir}
install -p -m 0644 %{SOURCE101} %{buildroot}%{_unitdir}
%ifarch i686 x86_64
install -p -m 0644 %{SOURCE201} %{buildroot}%{_unitdir}
%endif
# Udev rules
mkdir -p %{buildroot}%{_udevrulesdir}
install -p -m 0644 %{SOURCE6} %{buildroot}%{_udevrulesdir}/%{udev_prefix}-hypervkvp.rules
install -p -m 0644 %{SOURCE102} %{buildroot}%{_udevrulesdir}/%{udev_prefix}-hypervvss.rules
%ifarch i686 x86_64
install -p -m 0644 %{SOURCE202} %{buildroot}%{_udevrulesdir}/%{udev_prefix}-hypervfcopy.rules
%endif
# Shell scripts for the KVP daemon
mkdir -p %{buildroot}%{_libexecdir}/hypervkvpd
install -p -m 0755 hv_get_dhcp_info.sh %{buildroot}%{_libexecdir}/hypervkvpd/hv_get_dhcp_info
install -p -m 0755 hv_get_dns_info.sh %{buildroot}%{_libexecdir}/hypervkvpd/hv_get_dns_info
install -p -m 0755 hv_set_ifconfig.sh %{buildroot}%{_libexecdir}/hypervkvpd/hv_set_ifconfig
# Directory for pool files
mkdir -p %{buildroot}%{_sharedstatedir}/hyperv

sed -i 's,#!/usr/bin/env python,#!/usr/bin/python3,' %{buildroot}%{_sbindir}/lsvmbus

%post -n hypervkvpd
if [ $1 -gt 1 ] ; then
	# Upgrade
	systemctl --no-reload disable hypervkvpd.service >/dev/null 2>&1 || :
fi

%preun -n hypervkvpd
%systemd_preun hypervkvpd.service

%postun -n hypervkvpd
# hypervkvpd daemon does NOT support restarting (driver, neither)
%systemd_postun hypervkvpd.service
# If removing the package, delete %%{_sharedstatedir}/hyperv directory
if [ "$1" -eq "0" ] ; then
    rm -rf %{_sharedstatedir}/hyperv || :
fi


%post -n hypervvssd
if [ $1 -gt 1 ] ; then
	# Upgrade
	systemctl --no-reload disable hypervvssd.service >/dev/null 2>&1 || :
fi

%postun -n hypervvssd
%systemd_postun hypervvssd.service

%preun -n hypervvssd
%systemd_preun hypervvssd.service

%ifarch i686 x86_64
%post -n hypervfcopyd
%systemd_postun hypervfcopyd.service

%postun -n hypervfcopyd
%systemd_postun hypervfcopyd.service

%preun -n hypervfcopyd
%systemd_preun hypervfcopyd.service
%endif

%files
# the base package does not contain any files.

%files -n hypervkvpd
%{_sbindir}/hv_kvp_daemon
%{_unitdir}/hypervkvpd.service
%{_udevrulesdir}/%{udev_prefix}-hypervkvp.rules
%dir %{_libexecdir}/hypervkvpd
%{_libexecdir}/hypervkvpd/*
%dir %{_sharedstatedir}/hyperv

%files -n hypervvssd
%{_sbindir}/hv_vss_daemon
%{_unitdir}/hypervvssd.service
%{_udevrulesdir}/%{udev_prefix}-hypervvss.rules

%ifarch i686 x86_64
%files -n hypervfcopyd
%{_sbindir}/hv_fcopy_uio_daemon
%{_unitdir}/hypervfcopyd.service
%{_udevrulesdir}/%{udev_prefix}-hypervfcopy.rules
%endif

%files license
%doc COPYING

%files -n hyperv-tools
%{_sbindir}/lsvmbus

%changelog
%autochangelog
