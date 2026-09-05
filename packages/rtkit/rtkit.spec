Name:             rtkit
Version:          0.14
Release:          %autorelease
Summary:          Realtime Policy and Watchdog Daemon
# The daemon itself is GPLv3+, the reference implementation for the client MIT
# The LICENSE file incorrectly states that the client is under BSD.
License:          GPL-3.0-or-later AND MIT
%define forgeurl https://gitlab.freedesktop.org/pipewire/rtkit
%define tag v%{version}
%forgemeta
URL:              %{forgeurl}
Requires:         dbus
Requires:         polkit
BuildRequires:    ninja-build
BuildRequires:    meson
BuildRequires:    gcc
BuildRequires:    xxd
BuildRequires:    systemd-rpm-macros
BuildRequires:    pkgconfig(libsystemd)
BuildRequires:    pkgconfig(systemd)
BuildRequires:    dbus-devel >= 1.2
BuildRequires:    libcap-devel
BuildRequires:    polkit-devel
Source0:          %{forgesource}

Patch:            remove-debug-messages.patch

%description
RealtimeKit is a D-Bus system service that changes the
scheduling policy of user processes/threads to SCHED_RR (i.e. realtime
scheduling mode) on request. It is intended to be used as a secure
mechanism to allow real-time scheduling to be used by normal user
processes.

%prep
%autosetup -p1 -C

%build
%meson \
  -D systemd_systemunitdir=%{_unitdir}			\
  -D installed_tests=false				\
  %{nil}
%meson_build
%{_vpath_builddir}/rtkit-daemon --introspect >org.freedesktop.RealtimeKit1.xml

%install
install -Dm0644 org.freedesktop.RealtimeKit1.xml -t %{buildroot}%{_datadir}/dbus-1/interfaces/
%meson_install

# Relocate dbus policy to /usr
mkdir -p %{buildroot}%{_datadir}/dbus-1/system.d


%post
%systemd_post rtkit-daemon.service
dbus-send --system --type=method_call --dest=org.freedesktop.DBus / org.freedesktop.DBus.ReloadConfig >/dev/null 2>&1 || :

%preun
%systemd_preun rtkit-daemon.service

%postun
%systemd_postun_with_restart rtkit-daemon.service

%files
%doc README GPL LICENSE rtkit.c rtkit.h
%attr(0755,root,root) %{_sbindir}/rtkitctl
%attr(0755,root,root) %{_libexecdir}/rtkit-daemon
%{_datadir}/dbus-1/system-services/org.freedesktop.RealtimeKit1.service
%{_datadir}/dbus-1/system.d/org.freedesktop.RealtimeKit1.conf
%{_datadir}/dbus-1/interfaces/org.freedesktop.RealtimeKit1.xml
%{_datadir}/polkit-1/actions/org.freedesktop.RealtimeKit1.policy
%{_prefix}/lib/systemd/system/rtkit-daemon.service
%{_mandir}/man8/*
%{_sysusersdir}/rtkit.conf

%changelog
%autochangelog
