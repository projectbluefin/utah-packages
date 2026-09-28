%define glib2_version 2.44.0

Name:           dconf
Version:        51.0
Release:        %autorelease
Summary:        A configuration system

License:        LGPL-2.0-or-later AND LGPL-2.1-or-later AND GPL-2.0-or-later AND GPL-3.0-or-later
URL:            https://wiki.gnome.org/Projects/dconf
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

Patch1:         dconf-override.patch

BuildRequires:  gcc
BuildRequires:  gtk-doc
BuildRequires:  meson
BuildRequires:  pkgconfig(bash-completion)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(systemd)
BuildRequires:  systemd-rpm-macros
BuildRequires:  vala

Requires:       dbus
Requires:       glib2%{?_isa} >= %{glib2_version}

%description
dconf is a low-level configuration system. Its main purpose is to provide a
backend to the GSettings API in GLib.

%package devel
Summary: Header files and libraries for dconf development
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
dconf development package. Contains files needed for doing software
development using dconf.

%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}

%build
%meson -Dgtk_doc=true -Dsystemduserunitdir=%{_userunitdir}
%meson_build

%install
%meson_install

mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/dconf/profile

cat << EOF > $RPM_BUILD_ROOT%{_sysconfdir}/dconf/profile/user
user-db:user
system-db:local
system-db:site
system-db:distro
EOF

mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/dconf/db/local.d/locks
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/dconf/db/site.d/locks
mkdir -p $RPM_BUILD_ROOT%{_sysconfdir}/dconf/db/distro.d/locks

%posttrans
%{_bindir}/dconf update

%post
%systemd_user_post dconf.service

%preun
%systemd_user_preun dconf.service

%postun
%systemd_user_postun_with_restart dconf.service

%files
%license COPYING
%dir %{_sysconfdir}/dconf
%dir %{_sysconfdir}/dconf/db
%dir %{_sysconfdir}/dconf/db/local.d
%dir %{_sysconfdir}/dconf/db/local.d/locks
%dir %{_sysconfdir}/dconf/db/site.d
%dir %{_sysconfdir}/dconf/db/site.d/locks
%dir %{_sysconfdir}/dconf/db/distro.d
%dir %{_sysconfdir}/dconf/db/distro.d/locks
%dir %{_sysconfdir}/dconf/profile
%config(noreplace) %{_sysconfdir}/dconf/profile/user
%{_libdir}/gio/modules/libdconfsettings.so
%{_libexecdir}/dconf-service
%{_datadir}/dbus-1/services/ca.desrt.dconf.service
%{_bindir}/dconf
%{_libdir}/libdconf.so.1*
%{_datadir}/bash-completion/completions/dconf
%{_mandir}/man1/dconf-service.1*
%{_mandir}/man1/dconf.1*
%{_mandir}/man7/dconf.7*
%{_userunitdir}/dconf.service

%files devel
%{_includedir}/dconf
%{_libdir}/libdconf.so
%{_libdir}/pkgconfig/dconf.pc
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/dconf
%{_datadir}/vala

%changelog
%autochangelog
