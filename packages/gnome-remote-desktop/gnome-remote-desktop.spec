%global systemd_unit_handover gnome-remote-desktop-handover.service
%global systemd_unit_headless gnome-remote-desktop-headless.service
%global systemd_unit_system gnome-remote-desktop.service
%global systemd_unit_user gnome-remote-desktop.service

%bcond rdp %[0%{?fedora} || 0%{?rhel} >= 10]
%bcond vnc %[0%{?fedora} || 0%{?rhel} < 10]

%global meson_version 1.4.0
%global libei_version 1.3.901
%global pipewire_version 1.2.0
%global glib_version 2.75.0
%global vncserver_version 0.9.11-7

Name:           gnome-remote-desktop
Version:        51.0
Release:        %autorelease
Summary:        GNOME Remote Desktop screen share service

License:        GPL-2.0-or-later
URL:            https://gitlab.gnome.org/GNOME/gnome-remote-desktop
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

Patch0:         CVE-2026-96541.patch

# Adds encryption support (requires patched LibVNCServer)
Patch1:         gnutls-anontls.patch

BuildRequires:  asciidoc
BuildRequires:  gcc
BuildRequires:  meson >= %{meson_version}
BuildRequires:  systemd-rpm-macros
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(epoxy)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(ffnvcodec)
%if %{with rdp}
BuildRequires:  glslc
BuildRequires:  spirv-tools
BuildRequires:  pkgconfig(fdk-aac)
BuildRequires:  pkgconfig(freerdp3)
BuildRequires:  pkgconfig(fuse3)
BuildRequires:  pkgconfig(libva)
BuildRequires:  pkgconfig(opus)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(vulkan)
BuildRequires:  pkgconfig(winpr3)
%endif
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(glib-2.0) >= %{glib_version}
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(gnutls)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(libei-1.0) >= %{libei_version}
BuildRequires:  pkgconfig(libnotify)
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(libsecret-1)
%if %{with vnc}
BuildRequires: pkgconfig(libvncserver) >= %{vncserver_version}
%endif
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(tss2-esys)
BuildRequires:  pkgconfig(tss2-mu)
BuildRequires:  pkgconfig(tss2-rc)
BuildRequires:  pkgconfig(tss2-tctildr)

Requires:       libei%{?_isa} >= %{libei_version}
Requires:       pipewire%{?_isa} >= %{pipewire_version}

Obsoletes:      vino < 3.22.0-21

%description
GNOME Remote Desktop is a remote desktop and screen sharing service for the
GNOME desktop environment.


%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}


%build
%meson \
%if %{with rdp}
    -Drdp=true \
%else
    -Drdp=false \
%endif
%if %{with vnc}
    -Dvnc=true \
%else
    -Dvnc=false \
%endif
    -Dsystemd=true \
    -Dtests=false
%meson_build


%install
%meson_install

%find_lang %{name}


%post
%systemd_post %{systemd_unit_system}
%systemd_user_post %{systemd_unit_handover}
%systemd_user_post %{systemd_unit_headless}
%systemd_user_post %{systemd_unit_user}


%preun
%systemd_preun %{systemd_unit_system}
%systemd_user_preun %{systemd_unit_handover}
%systemd_user_preun %{systemd_unit_headless}
%systemd_user_preun %{systemd_unit_user}


%postun
%systemd_postun_with_restart %{systemd_unit_system}
%systemd_user_postun_with_restart %{systemd_unit_handover}
%systemd_user_postun_with_restart %{systemd_unit_headless}
%systemd_user_postun_with_restart %{systemd_unit_user}


%files -f %{name}.lang
%license COPYING
%doc README.md
%{_bindir}/grdctl
%{_libexecdir}/gnome-remote-desktop-daemon
%{_libexecdir}/gnome-remote-desktop-enable-service
%{_libexecdir}/gnome-remote-desktop-configuration-daemon
%{_libexecdir}/grd-pcscd
%{_libdir}/libgrdpcsc.so
%{_libdir}/libgrdpcsc.so.0
%{_libdir}/libgrdpcsc.so.0.0.0
%{_userunitdir}/%{systemd_unit_user}
%{_userunitdir}/%{systemd_unit_headless}
%{_userunitdir}/%{systemd_unit_handover}
%{_unitdir}/%{systemd_unit_system}
%{_unitdir}/gnome-remote-desktop-configuration.service
%{_unitdir}/gnome-remote-desktop-pcscd.service
%{_datadir}/dbus-1/system-services/org.gnome.RemoteDesktop.Configuration.service
%{_datadir}/dbus-1/system-services/org.gnome.RemoteDesktop.Pcscd.service
%{_datadir}/dbus-1/system.d/org.gnome.RemoteDesktop.conf
%{_datadir}/dbus-1/system.d/org.gnome.RemoteDesktop.Pcscd.conf
%{_datadir}/glib-2.0/schemas/org.gnome.desktop.remote-desktop.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.desktop.remote-desktop.enums.xml
%{_datadir}/polkit-1/actions/org.gnome.remotedesktop.configure-system-daemon.policy
%{_datadir}/polkit-1/actions/org.gnome.remotedesktop.enable-system-daemon.policy
%{_datadir}/polkit-1/actions/org.gnome.remotedesktop.use-grd-pcscd.policy
%{_datadir}/polkit-1/rules.d/20-gnome-remote-desktop.rules
%{_sysusersdir}/gnome-remote-desktop-sysusers.conf
%{_tmpfilesdir}/gnome-remote-desktop-tmpfiles.conf

%if %{with rdp}
%{_datadir}/gnome-remote-desktop/
%endif
%{_mandir}/man1/grdctl.1*


%changelog
%autochangelog
