%global avahi_version 0.6
%global fuse_version 3.0.0
%global glib2_version 2.83.0
%global gsettings_desktop_schemas_version 3.33.0
%global goa_version 3.57.0
%global gudev_version 147
%global libcdio_paranoia_version 0.78.2
%global libgcrypt_version 1.2.2
%global libgphoto2_version 2.5.0
%global libimobiledevice_version 1.2
%global libmtp_version 1.1.21
%global libnfs_version 1.9.8
%global libplist_version 2.2
%global libsmbclient_version 4.12.0
%global libsoup_version 3.0.0
%global libusb_version 1.0.21
%global systemd_version 206
%global talloc_version 1.3.0
%global udisks2_version 1.97

Name:    gvfs
Version: 1.61.91
Release: %autorelease
Summary: Backends for the gio framework in GLib

License: LGPL-2.0-or-later AND GPL-3.0-only AND MPL-2.0 AND BSD-3-Clause-Sun

URL:     https://wiki.gnome.org/Projects/gvfs
Source0: https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires: meson
BuildRequires: gcc
BuildRequires: pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(dbus-1)
BuildRequires: pkgconfig(gcr-4)
BuildRequires: pkgconfig(gsettings-desktop-schemas) >= %{gsettings_desktop_schemas_version}
BuildRequires: /usr/bin/ssh
%if ! (0%{?rhel} >= 10)
BuildRequires: pkgconfig(libcdio_paranoia) >= %{libcdio_paranoia_version}
%endif
BuildRequires: pkgconfig(gudev-1.0) >= %{gudev_version}
BuildRequires: pkgconfig(libsoup-3.0) >= %{libsoup_version}
BuildRequires: pkgconfig(avahi-client) >= %{avahi_version}
BuildRequires: pkgconfig(avahi-glib) >= %{avahi_version}
BuildRequires: pkgconfig(libsecret-1)
BuildRequires: gettext-devel
BuildRequires: pkgconfig(udisks2) >= %{udisks2_version}
%if ! 0%{?rhel}
BuildRequires: pkgconfig(libbluray)
%endif
%if ! (0%{?rhel} >= 9)
BuildRequires: libgcrypt-devel >= %{libgcrypt_version}
%endif
BuildRequires: systemd-devel >= %{systemd_version}
BuildRequires: pkgconfig(libxslt)
BuildRequires: docbook-style-xsl
BuildRequires: pkgconfig(polkit-gobject-1)
BuildRequires: pkgconfig(libcap)

Requires: %{name}-client%{?_isa} = %{version}-%{release}
Requires: glib2%{?_isa} >= %{glib2_version}
Requires: gsettings-desktop-schemas >= %{gsettings_desktop_schemas_version}
Requires: polkit
Requires: udisks2 >= %{udisks2_version}
Requires: /usr/bin/wsdd

Obsoletes: gnome-mount <= 0.8
Obsoletes: gnome-mount-nautilus-properties <= 0.8
Obsoletes: gvfs-afp < 1.61.1-1
Obsoletes: gvfs-archive < 1.61.1-1
Obsoletes: gvfs-obexftp < 1.17.91-2
Obsoletes: gvfs-devel < 1.55.1-1
Obsoletes: gvfs-tests < 1.55.1-3
%ifarch s390 s390x
Obsoletes: gvfs-gphoto2 < 1.55.1-4
Obsoletes: gvfs-mtp < 1.55.1-4
%endif

%description
The gvfs package provides backend implementations for the gio
framework in GLib. It includes ftp, sftp, cifs.


%package client
Summary: Client modules of backends for the gio framework in GLib
Conflicts: %{name} < 1.25.2-2

%description client
The gvfs package provides client modules of backend implementations for the gio
framework in GLib.


%package fuse
Summary: FUSE support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: pkgconfig(fuse3) >= %{fuse_version}
Requires: fuse3 >= %{fuse_version}

%description fuse
This package provides support for applications not using gio
to access the gvfs filesystems.


%package smb
Summary: Windows fileshare support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: libsmbclient-devel >= %{libsmbclient_version}
BuildRequires: pkgconfig(talloc) >= %{talloc_version}

%description smb
This package provides support for reading and writing files on windows
shares (SMB) to applications using gvfs.


%ifnarch s390 s390x
%package gphoto2
Summary: gphoto2 support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: pkgconfig(libgphoto2) >= %{libgphoto2_version}
BuildRequires: libexif-devel

%description gphoto2
This package provides support for reading and writing files on
PTP based cameras (Picture Transfer Protocol) and MTP based
media players (Media Transfer Protocol) to applications using gvfs.


%if ! 0%{?rhel}
%package afc
Summary: AFC support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
Requires: usbmuxd
BuildRequires: pkgconfig(libimobiledevice-1.0) >= %{libimobiledevice_version}
BuildRequires: pkgconfig(libplist-2.0) >= %{libplist_version}

%description afc
This package provides support for reading files on mobile devices
including phones and music players to applications using gvfs.
%endif
%endif


%ifnarch s390 s390x
%package mtp
Summary: MTP support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: pkgconfig(libmtp) >= %{libmtp_version}
BuildRequires: pkgconfig(libusb-1.0) >= %{libusb_version}

%description mtp
This package provides support for reading and writing files on
MTP based devices (Media Transfer Protocol) to applications using gvfs.
%endif


%if ! 0%{?rhel}
%package nfs
Summary: NFS support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: pkgconfig(libnfs) >= %{libnfs_version}

%description nfs
This package provides support for reading and writing files on
NFS network shares (Network File System) to applications using gvfs.
%endif


%package goa
Summary: GOA support for gvfs
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: %{name}-client%{?_isa} = %{version}-%{release}
BuildRequires: pkgconfig(goa-1.0) >= %{goa_version}
%if ! (0%{?rhel} >= 10)
BuildRequires: pkgconfig(msgraph-1)
%endif

%description goa
This package provides seamless integration with gnome-online-accounts
file services.


%prep
%autosetup -p1

%build
# -Dbluray=false is unconditional here, where Fedora sets it only on RHEL:
# libbluray is not in Hummingbird and the factory declines to add it, because
# rawhide dist-git has moved to 1.5.0 (libbluray.so.4) while the composed
# repository the buildroot resolves against still ships 1.4.0
# (libbluray.so.3). Shipping ours would exclude Fedora's and leave Fedora's own
# libavformat-free with no provider. ffmpeg declines the feature likewise.
%meson \
       -Dman=true \
%ifarch s390 s390x
       -Dafc=false \
       -Dgphoto2=false \
       -Dlibusb=false \
       -Dmtp=false \
%endif
       -Dbluray=false \
%if 0%{?rhel}
       -Dnfs=false \
       -Dafc=false \
       -Donedrive=false \
%endif
%if 0%{?rhel} >= 9
       -Dgcrypt=false \
%endif
%if 0%{?rhel} >= 10
       -Dcdda=false \
%endif
        %{nil}
%meson_build

%install
%meson_install

# trashlib is GPLv3, include the license
cp -p daemon/trashlib/COPYING COPYING.GPL3

%find_lang gvfs

%post
# Reload .mount files:
killall -USR1 gvfsd >&/dev/null || :

# Reload .mount files when single subpackage is installed:
%post smb
killall -USR1 gvfsd >&/dev/null || :
%ifnarch s390 s390x
%post gphoto2
killall -USR1 gvfsd >&/dev/null || :
%post mtp
killall -USR1 gvfsd >&/dev/null || :
%endif
%post goa
killall -USR1 gvfsd >&/dev/null || :
%ifnarch s390 s390x
%if ! 0%{?rhel}
%post afc
killall -USR1 gvfsd >&/dev/null || :
%endif
%endif

%if ! 0%{?rhel}
%post nfs
killall -USR1 gvfsd >&/dev/null || :
%endif


%files
%dir %{_datadir}/gvfs
%dir %{_datadir}/gvfs/mounts
%{_datadir}/gvfs/mounts/admin.mount
%{_datadir}/gvfs/mounts/sftp.mount
%{_datadir}/gvfs/mounts/trash.mount
%if ! (0%{?rhel} >= 10)
%{_datadir}/gvfs/mounts/cdda.mount
%endif
%{_datadir}/gvfs/mounts/computer.mount
%{_datadir}/gvfs/mounts/dav.mount
%{_datadir}/gvfs/mounts/dav+sd.mount
%{_datadir}/gvfs/mounts/http.mount
%{_datadir}/gvfs/mounts/localtest.mount
%{_datadir}/gvfs/mounts/dns-sd.mount
%{_datadir}/gvfs/mounts/network.mount
%{_datadir}/gvfs/mounts/ftp.mount
%{_datadir}/gvfs/mounts/ftpis.mount
%{_datadir}/gvfs/mounts/ftps.mount
%{_datadir}/gvfs/mounts/recent.mount
%{_datadir}/gvfs/mounts/wsdd.mount
%{_datadir}/dbus-1/services/org.gtk.vfs.Daemon.service
%{_datadir}/dbus-1/services/org.gtk.vfs.Metadata.service
%{_datadir}/dbus-1/services/org.gtk.vfs.UDisks2VolumeMonitor.service
%dir %{_datadir}/gvfs/remote-volume-monitors
%{_datadir}/gvfs/remote-volume-monitors/udisks2.monitor
%{_datadir}/GConf/gsettings/*.convert
%{_datadir}/glib-2.0/schemas/*.xml
%{_datadir}/polkit-1/actions/org.gtk.vfs.file-operations.policy
%{_datadir}/polkit-1/rules.d/org.gtk.vfs.file-operations.rules
%{_libdir}/gvfs/libgvfsdaemon.so
%{_libexecdir}/gvfsd
%{_libexecdir}/gvfsd-admin
%{_libexecdir}/gvfsd-ftp
%{_libexecdir}/gvfsd-sftp
%{_libexecdir}/gvfsd-trash
%if ! (0%{?rhel} >= 10)
%{_libexecdir}/gvfsd-cdda
%endif
%{_libexecdir}/gvfsd-computer
%{_libexecdir}/gvfsd-dav
%{_libexecdir}/gvfsd-http
%{_libexecdir}/gvfsd-localtest
%{_libexecdir}/gvfsd-dnssd
%{_libexecdir}/gvfsd-network
%{_libexecdir}/gvfsd-metadata
%{_libexecdir}/gvfs-udisks2-volume-monitor
%{_libexecdir}/gvfsd-recent
%{_libexecdir}/gvfsd-wsdd
%{_mandir}/man1/gvfsd.1*
%{_mandir}/man1/gvfsd-metadata.1*
%{_userunitdir}/gvfs-daemon.service
%{_userunitdir}/gvfs-metadata.service
%{_userunitdir}/gvfs-udisks2-volume-monitor.service

%files client -f gvfs.lang
%license COPYING COPYING.GPL3
%doc NEWS README.md
%dir %{_libdir}/gvfs
%{_libdir}/gvfs/libgvfscommon.so
%{_libdir}/gio/modules/libgioremote-volume-monitor.so
%{_libdir}/gio/modules/libgvfsdbus.so
%{_mandir}/man7/gvfs.7*

%files fuse
%{_libexecdir}/gvfsd-fuse
%{_mandir}/man1/gvfsd-fuse.1*
%{_tmpfilesdir}/gvfsd-fuse-tmpfiles.conf

%files smb
%{_libexecdir}/gvfsd-smb
%{_libexecdir}/gvfsd-smb-browse
%{_datadir}/gvfs/mounts/smb-browse.mount
%{_datadir}/gvfs/mounts/smb.mount


%ifnarch s390 s390x
%files gphoto2
%{_libexecdir}/gvfsd-gphoto2
%{_datadir}/gvfs/mounts/gphoto2.mount
%{_libexecdir}/gvfs-gphoto2-volume-monitor
%{_datadir}/dbus-1/services/org.gtk.vfs.GPhoto2VolumeMonitor.service
%{_datadir}/gvfs/remote-volume-monitors/gphoto2.monitor
%{_userunitdir}/gvfs-gphoto2-volume-monitor.service

%if ! 0%{?rhel}
%files afc
%{_libexecdir}/gvfsd-afc
%{_datadir}/gvfs/mounts/afc.mount
%{_libexecdir}/gvfs-afc-volume-monitor
%{_datadir}/dbus-1/services/org.gtk.vfs.AfcVolumeMonitor.service
%{_datadir}/gvfs/remote-volume-monitors/afc.monitor
%{_userunitdir}/gvfs-afc-volume-monitor.service
%endif
%endif

%ifnarch s390 s390x
%files mtp
%{_libexecdir}/gvfsd-mtp
%{_datadir}/gvfs/mounts/mtp.mount
%{_libexecdir}/gvfs-mtp-volume-monitor
%{_datadir}/dbus-1/services/org.gtk.vfs.MTPVolumeMonitor.service
%{_datadir}/gvfs/remote-volume-monitors/mtp.monitor
%{_userunitdir}/gvfs-mtp-volume-monitor.service
%endif

%if ! 0%{?rhel}
%files nfs
# for privileged ports
%caps(cap_net_bind_service=ep) %{_libexecdir}/gvfsd-nfs
%{_datadir}/gvfs/mounts/nfs.mount
%endif

%files goa
%{_libexecdir}/gvfs-goa-volume-monitor
%{_datadir}/dbus-1/services/org.gtk.vfs.GoaVolumeMonitor.service
%{_datadir}/gvfs/remote-volume-monitors/goa.monitor
%if ! 0%{?rhel}
%{_datadir}/gvfs/mounts/onedrive.mount
%{_libexecdir}/gvfsd-onedrive
%endif
%{_userunitdir}/gvfs-goa-volume-monitor.service


%changelog
%autochangelog
