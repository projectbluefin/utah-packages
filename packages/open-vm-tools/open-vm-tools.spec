%global toolsbuild      25218885
%global toolsdaemon     vmtoolsd
%global vgauthdaemon    vgauthd

Name:             open-vm-tools
Version:          13.1.0
Release:          %autorelease
Summary:          Open Virtual Machine Tools for virtual machines hosted on VMware
License:          GPL-2.0-only AND W3C AND LGPL-2.1-only AND ICU AND ISC AND MIT
URL:              https://github.com/vmware/%{name}

Source0:          https://github.com/vmware/%{name}/releases/download/stable-%{version}/%{name}-%{version}-%{toolsbuild}.tar.gz
Source1:          %{toolsdaemon}.service
Source2:          %{vgauthdaemon}.service
Source3:          run-vmblock\x2dfuse.mount
Source4:          open-vm-tools.conf
Source5:          vmtoolsd.pam

Patch0:           open-vm-tools-gcc16.patch
Patch1:           open-vm-tools-sigc++3.patch
Patch2:           open-vm-tools-openssl4.patch

ExclusiveArch:    %{ix86} x86_64 aarch64

BuildRequires:    autoconf
BuildRequires:    automake
BuildRequires:    libtool
BuildRequires:    make
BuildRequires:    gcc-c++
BuildRequires:    doxygen
BuildRequires:    fuse3-devel >= 3.10.0
BuildRequires:    libtool-ltdl-devel
BuildRequires:    libX11-devel
BuildRequires:    libXext-devel
BuildRequires:    libXi-devel
BuildRequires:    libXinerama-devel
BuildRequires:    libXrandr-devel
BuildRequires:    libXrender-devel
BuildRequires:    libXtst-devel
BuildRequires:    pam-devel
BuildRequires:    pkgconfig(glib-2.0) >= 2.34.0
BuildRequires:    pkgconfig(gmodule-2.0) >= 2.34.0
BuildRequires:    pkgconfig(gobject-2.0) >= 2.34.0
BuildRequires:    pkgconfig(gthread-2.0) >= 2.34.0
BuildRequires:    pkgconfig(gtk4) >= 4.0.0
BuildRequires:    pkgconfig(gtkmm-4.0) >= 4.0.0
BuildRequires:    pkgconfig(icu-i18n)
BuildRequires:    pkgconfig(libdrm)
BuildRequires:    pkgconfig(libmspack) >= 0.0.20040308alpha
BuildRequires:    pkgconfig(libudev)
BuildRequires:    pkgconfig(libtirpc)
BuildRequires:    pkgconfig(openssl)
BuildRequires:    pkgconfig(protobuf) >= 3.0.0
BuildRequires:    procps-devel
BuildRequires:    rpcgen
# Required otherwise udev rules are not built:
BuildRequires:    systemd-udev
BuildRequires:    xmlsec1-openssl-devel

Requires:         coreutils
Requires:         fuse3
Requires:         grep
Requires:         iproute
Requires:         pciutils
Requires:         sed
Requires:         tar
Requires:         util-linux
Requires:         which
# xmlsec1-openssl needs to be added explicitly
Requires:         xmlsec1-openssl

# open-vm-tools >= 10.0.0 do not require open-vm-tools-deploypkg provided by
# VMware. That functionality is now available as part of open-vm-tools package
# itself.
Obsoletes:        open-vm-tools-deploypkg <= 10.0.5

%description
The %{name} project is an open source implementation of VMware Tools. It
is a suite of open source virtualization utilities and drivers to improve the
functionality, user experience and administration of VMware virtual machines.
This package contains only the core user-space programs and libraries of
%{name}.

%package          desktop
Summary:          User experience components for Open Virtual Machine Tools
Requires:         %{name}%{?_isa} = %{version}-%{release}

%description      desktop
This package contains only the user-space programs and libraries of
%{name} that are essential for improved user experience of VMware virtual
machines.

%package          sdmp
Summary:          Service Discovery components for Open Virtual Machine Tools
Requires:         %{name}%{?_isa} = %{version}-%{release}
Requires:         coreutils
Requires:         gawk
Requires:         glibc-common
Requires:         grep
Requires:         iproute
Requires:         procps

%description      sdmp
This package contains only the user-space programs and utility scripts of
%{name} that are essential for performing service discovery in VMware
virtual machines by vRealize Operations Service Discovery Management Pack.

%package          salt-minion
Summary:          Script file to install/uninstall salt-minion
Requires:         %{name}%{?_isa} = %{version}-%{release}, systemd, curl, coreutils, gawk, grep
ExclusiveArch:    x86_64

%description      salt-minion
This package contains a script to setup Salt Minion on VMware virtual machines.

%package          devel
Summary:          Development libraries for Open Virtual Machine Tools
Requires:         %{name}%{?_isa} = %{version}-%{release}

%description      devel
This package contains only the user-space programs and libraries of
%{name} that are essential for developing customized applications for
VMware virtual machines.

%package          test
Summary:          Test utilities for Open Virtual Machine Tools
Requires:         %{name}%{?_isa} = %{version}-%{release}

%description      test
This package contains only the test utilities for %{name} that are
useful for verifying the functioning of %{name} in VMware virtual
machines.

%prep
%autosetup -p1 -n %{name}-%{version}-%{toolsbuild}

%build
autoreconf -vif

%configure \
    --disable-static \
    --enable-resolutionkms \
%ifarch x86_64
    --enable-salt-minion \
%endif
    --enable-servicediscovery \
    --enable-vmwgfxctrl \
    --with-fuse \
    --with-gtk4 \
    --with-tirpc \
    --with-xmlsec1 \
    --without-kernel-modules

sed -i -e 's! -shared ! -Wl,--as-needed\0!g' libtool
%make_build

%install
%make_install

# Remove exec bit from config files
chmod a-x %{buildroot}%{_sysconfdir}/pam.d/*
chmod a-x %{buildroot}%{_sysconfdir}/vmware-tools/*.conf
chmod a-x %{buildroot}%{_sysconfdir}/vmware-tools/vgauth/schemas/*

# Remove exec bit on udev rules.
chmod a-x %{buildroot}%{_udevrulesdir}/99-vmware-scsi-udev.rules

# Remove the DOS line endings
sed -i "s|\r||g" README

# Remove "Encoding" key from the "Desktop Entry"
sed -i "s|^Encoding.*$||g" %{buildroot}%{_sysconfdir}/xdg/autostart/vmware-user.desktop

# Remove unnecessary files from packaging
find %{buildroot}%{_libdir} -name '*.la' -delete
rm -fr %{buildroot}%{_defaultdocdir}
rm -f docs/api/build/html/FreeSans.ttf

# Systemd unit files
install -p -m 644 -D %{SOURCE1} %{buildroot}%{_unitdir}/%{toolsdaemon}.service
install -p -m 644 -D %{SOURCE2} %{buildroot}%{_unitdir}/%{vgauthdaemon}.service
install -p -m 644 -D '%{SOURCE3}' %{buildroot}%{_unitdir}/run-vmblock\\x2dfuse.mount
install -p -m 644 -D %{SOURCE4} %{buildroot}%{_modulesloaddir}/open-vm-tools.conf
install -p -m 644 -D %{SOURCE5} %{buildroot}%{_sysconfdir}/pam.d/vmtoolsd

# 'make check' in open-vm-tools rebuilds docs and ends up regenerating the font
# file. We can add %%check secion once 'make check' is fixed upstream.

%post
# Setup mount point for Shared Folders
# NOTE: Use systemd-detect-virt to detect VMware platform because
#       vmware-checkvm might misbehave on non-VMware platforms.
if [ -f %{_bindir}/vmware-checkvm -a                     \
     -f %{_bindir}/vmhgfs-fuse ] &&                      \
   %{_bindir}/systemd-detect-virt | grep -iq VMware &&   \
   %{_bindir}/vmware-checkvm &> /dev/null &&             \
   %{_bindir}/vmware-checkvm -p | grep -q Workstation && \
   %{_bindir}/vmhgfs-fuse -e &> /dev/null; then
   mkdir -p /mnt/hgfs
fi

if [ "$1" = "2" ]; then
   # Cleanup GuestProxy certs, relevant for upgrades only
   if [ -f %{_bindir}/vmware-guestproxycerttool ]; then
      %{_bindir}/vmware-guestproxycerttool -e &> /dev/null || /bin/true
   fi
   if [ -d /etc/vmware-tools/GuestProxyData ]; then
      rm -rf /etc/vmware-tools/GuestProxyData &> /dev/null || /bin/true
   fi

   # Cleanup vmtoolsd-init.service in case of upgrades
   %{_bindir}/systemctl disable %{toolsdaemon}-init.service &> /dev/null || /bin/true
fi
%systemd_post %{vgauthdaemon}.service %{toolsdaemon}.service

%post desktop
%systemd_post run-vmblock\\x2dfuse.mount
# Need to enable the service as it is not enabled by default.
# Enabling an already-enabled service is not an error. So, we can perform this
# step everytime during the post-install.
if [ -f %{_bindir}/vmware-checkvm ] &&                   \
   %{_bindir}/systemd-detect-virt | grep -iq VMware &&   \
   %{_bindir}/vmware-checkvm &> /dev/null &&             \
   %{_bindir}/vmware-checkvm -p | grep -q Workstation; then
   %{_bindir}/systemctl enable run-vmblock\\x2dfuse.mount &> /dev/null || /bin/true
fi

%post sdmp
# Load the newly installed or upgraded SDMP plugin
if %{_bindir}/systemctl is-active %{toolsdaemon}.service &> /dev/null; then
   %{_bindir}/systemctl restart %{toolsdaemon}.service &> /dev/null || /bin/true
fi

%preun
%systemd_preun %{toolsdaemon}.service %{vgauthdaemon}.service

if [ "$1" = "0" -a                                       \
     -f %{_bindir}/vmware-checkvm ] &&                   \
   %{_bindir}/systemd-detect-virt | grep -iq VMware &&   \
   %{_bindir}/vmware-checkvm &> /dev/null; then

   # Tell VMware that open-vm-tools is being uninstalled
   if [ -f %{_bindir}/vmware-rpctool ]; then
      %{_bindir}/vmware-rpctool 'tools.set.version 0' &> /dev/null || /bin/true
   fi

   # Teardown mount point for Shared Folders
   if [ -d /mnt/hgfs ] &&                               \
      %{_bindir}/vmware-checkvm -p | grep -q Workstation; then
      umount /mnt/hgfs &> /dev/null || /bin/true
      rmdir /mnt/hgfs &> /dev/null || /bin/true
   fi
fi

%preun desktop
%systemd_preun run-vmblock\\x2dfuse.mount

%postun
%systemd_postun_with_restart %{toolsdaemon}.service %{vgauthdaemon}.service

%postun desktop
%systemd_postun run-vmblock\\x2dfuse.mount

%postun sdmp
# In case of uninstall, unload the uninstalled SDMP plugin
if [ "$1" = "0" ] &&                                       \
   %{_bindir}/systemctl is-active %{toolsdaemon}.service &> /dev/null; then
   %{_bindir}/systemctl restart %{toolsdaemon}.service &> /dev/null || /bin/true
fi

%files
%license COPYING
%doc AUTHORS ChangeLog NEWS README
%config(noreplace) %{_sysconfdir}/pam.d/*
%dir %{_sysconfdir}/vmware-tools/
%dir %{_sysconfdir}/vmware-tools/vgauth
%dir %{_sysconfdir}/vmware-tools/vgauth/schemas
%config(noreplace) %{_sysconfdir}/vmware-tools/*.conf
# Don't expect users to modify example tools.conf file
%config %{_sysconfdir}/vmware-tools/tools.conf.example
# Don't expect users to modify VGAuth schema files
%config %{_sysconfdir}/vmware-tools/vgauth/schemas/*
%{_sysconfdir}/vmware-tools/*-vm-default
%{_sysconfdir}/vmware-tools/scripts
%{_sysconfdir}/vmware-tools/statechange.subr
%{_bindir}/VGAuthService
%{_bindir}/vm-support
%{_bindir}/vmhgfs-fuse
%{_bindir}/vmtoolsd
%{_bindir}/vmware-alias-import
%{_bindir}/vmware-checkvm
%{_bindir}/vmware-hgfsclient
%{_bindir}/vmware-namespace-cmd
%{_bindir}/vmware-rpctool
%{_bindir}/vmware-toolbox-cmd
%{_bindir}/vmware-vgauth-cmd
%{_bindir}/vmware-xferlogs
%{_libdir}/libDeployPkg.so.*
%{_libdir}/libguestlib.so.*
%{_libdir}/libguestStoreClient.so.*
%{_libdir}/libhgfs.so.*
%{_libdir}/libvgauth.so.*
%{_libdir}/libvmtools.so.*
%dir %{_libdir}/%{name}/
%dir %{_libdir}/%{name}/plugins
%dir %{_libdir}/%{name}/plugins/common
%{_libdir}/%{name}/plugins/common/*.so
%dir %{_libdir}/%{name}/plugins/vmsvc
%{_libdir}/%{name}/plugins/vmsvc/libappInfo.so
%{_libdir}/%{name}/plugins/vmsvc/libcomponentMgr.so
%{_libdir}/%{name}/plugins/vmsvc/libdeployPkgPlugin.so
%{_libdir}/%{name}/plugins/vmsvc/libgdp.so
%{_libdir}/%{name}/plugins/vmsvc/libguestInfo.so
%{_libdir}/%{name}/plugins/vmsvc/libguestStore.so
%{_libdir}/%{name}/plugins/vmsvc/libpowerOps.so
%{_libdir}/%{name}/plugins/vmsvc/libresolutionKMS.so
%{_libdir}/%{name}/plugins/vmsvc/libtimeSync.so
%{_libdir}/%{name}/plugins/vmsvc/libvmbackup.so

%{_datadir}/%{name}/
%{_udevrulesdir}/99-vmware-scsi-udev.rules
%{_unitdir}/%{toolsdaemon}.service
%{_unitdir}/%{vgauthdaemon}.service
%{_modulesloaddir}/open-vm-tools.conf

%files desktop
%{_sysconfdir}/xdg/autostart/*.desktop
%{_bindir}/vmware-user
%{_bindir}/vmwgfxctrl
%attr(4755,-,-) %{_bindir}/vmware-user-suid-wrapper
%{_bindir}/vmware-vmblock-fuse
%{_libdir}/%{name}/plugins/vmusr/
%{_unitdir}/run-vmblock\x2dfuse.mount

%files sdmp
%{_libdir}/%{name}/plugins/vmsvc/libserviceDiscovery.so
%{_libdir}/%{name}/serviceDiscovery

%ifarch x86_64
%files salt-minion
%dir %{_libdir}/%{name}/componentMgr/
%dir %{_libdir}/%{name}/componentMgr/saltMinion/
%{_libdir}/%{name}/componentMgr/saltMinion/svtminion.sh
%endif

%files devel
%doc docs/api/build/*
%exclude %{_includedir}/libDeployPkg/
%{_includedir}/vmGuestLib/
%{_libdir}/pkgconfig/*.pc
%{_libdir}/libDeployPkg.so
%{_libdir}/libguestlib.so
%{_libdir}/libguestStoreClient.so
%{_libdir}/libhgfs.so
%{_libdir}/libvgauth.so
%{_libdir}/libvmtools.so

%files test
%{_bindir}/vmware-vgauth-smoketest

%changelog
%autochangelog
