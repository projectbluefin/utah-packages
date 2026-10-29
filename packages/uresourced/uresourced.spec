Name:           uresourced
Version:        0.5.5
Release:        %autorelease
Summary:        Dynamically allocate resources to the active user

License:        LGPL-2.1-or-later
URL:            https://gitlab.freedesktop.org/benzea/uresourced
Source0:        %{url}/-/archive/v%{version}/%{name}-v%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(libpipewire-0.3)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  systemd-rpm-macros

%description
This daemon dynamically assigns a resource allocation to the active
graphical user. If the user has an active graphical session managed
using systemd (e.g. GNOME), then the memory allocation will be used
to protect the sessions core processes (session.slice).

%prep
%autosetup -n %{name}-v%{version} -p1

%build
%meson -Dappmanagement=true
%meson_build

%install
%meson_install

%post
# before version 0.5.5 uresourced accidentally persisted the configuration,
# remove the generated configuration files and directories.
shopt -s nullglob

for f in /etc/systemd/system.control/user{@*.service.d,-*.slice.d}/50-{CPUWeight,IOWeight,MemoryLow,MemoryMin}.conf; do
  /usr/bin/rm -f "$f" || true
done

for d in /etc/systemd/system.control/user{@*.service.d,-*.slice.d}; do
  /usr/bin/rmdir --ignore-fail-on-non-empty "$d"|| true
done

shopt -u nullglob

%systemd_post uresourced.service
%systemd_user_post uresourced.service

%preun
%systemd_preun uresourced.service
%systemd_user_preun uresourced.service

%postun
%systemd_postun uresourced.service
%systemd_user_postun uresourced.service

%files
%license COPYING
%doc README
%doc NEWS.md
%config(noreplace) %{_sysconfdir}/uresourced.conf
%{_datadir}/dbus-1/system.d/org.freedesktop.UResourced.conf
%{_libexecdir}/uresourced
%{_libexecdir}/cgroupify
%{_unitdir}/*
%{_userunitdir}/*

%changelog
%autochangelog
