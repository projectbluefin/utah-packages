%global _hardened_build 1

# This controls support for launching X11 desktops.
# gdm itself will always use Wayland.
%if 0%{?rhel}
%bcond x11 0
%else
%bcond x11 1
%endif

Name:           gdm
Epoch:          1
Version:        51.0
Release:        %autorelease
Summary:        The GNOME Display Manager

License:        GPL-2.0-or-later
URL:            https://wiki.gnome.org/Projects/GDM
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz
Source1:        org.gnome.login-screen.gschema.override
Source2:        gdm.sysusers

%gnome_check_version

# Upstream patches

# Downstream patches
Patch:          0001-Honor-initial-setup-being-disabled-by-distro-install.patch
Patch:          0001-data-add-system-dconf-databases-to-gdm-profile.patch
Patch:          0001-Add-headless-session-files.patch

BuildRequires:  dconf
BuildRequires:  desktop-file-utils
BuildRequires:  gettext-devel
BuildRequires:  git-core
BuildRequires:  meson
BuildRequires:  pam-devel
BuildRequires:  pkgconfig(accountsservice) >= 0.6.3
BuildRequires:  pkgconfig(audit)
BuildRequires:  pkgconfig(check)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(iso-codes)
BuildRequires:  pkgconfig(json-glib-1.0)
BuildRequires:  pkgconfig(libkeyutils)
BuildRequires:  pkgconfig(libselinux)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(ply-boot-client)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(xau)
BuildRequires:  systemd-rpm-macros
BuildRequires:  which
BuildRequires:  yelp-tools

%if %{with x11}
BuildRequires:  pkgconfig(x11)
%endif

Provides: service(graphical-login) = %{name}

Requires: accountsservice
Requires: dbus-common
Requires: dconf
# since we use it, and pam spams the log if the module is missing
Requires: gnome-keyring-pam
Requires: gnome-session >= 50~alpha
Requires: gnome-session-wayland-session >= 50~alpha
Requires: gnome-settings-daemon >= 3.27.90
Requires: gnome-shell
Requires: iso-codes
# We need 1.0.4-5 since it lets us use "localhost" in auth cookies
Requires: libXau >= 1.0.4-4
Requires: pam
Requires: /sbin/nologin
Requires: systemd >= 186
Requires: system-logos
Requires: python3-pam

%if %{with x11}
Requires: xorg-x11-xinit
%endif

Provides: gdm-libs%{?_isa} = %{epoch}:%{version}-%{release}

%description
GDM, the GNOME Display Manager, handles authentication-related backend
functionality for logging in a user and unlocking the user's session after
it's been locked. GDM also provides functionality for initiating user-switching,
so more than one user can be logged in at the same time. It handles
graphical session registration with the system for both local and remote
sessions (in the latter case, via GNOME Remote Desktop and the RDP protocol).

%package devel
Summary: Development files for gdm
Requires: %{name}%{?_isa} = %{epoch}:%{version}-%{release}
Requires: gdm-pam-extensions-devel = %{epoch}:%{version}-%{release}

%description devel
The gdm-devel package contains headers and other
files needed to build custom greeters.

%package pam-extensions-devel
Summary: Macros for developing GDM extensions to PAM
Requires: pam-devel

%description pam-extensions-devel
The gdm-pam-extensions-devel package contains headers and other
files that are helpful to PAM modules wishing to support
GDM specific authentication features.

%prep
%autosetup -S git -p1 -n %{name}-%{gnome_tarball_version}

%build
%meson -Ddbus-sys=%{_datadir}/dbus-1/system.d \
       -Ddefault-path=/usr/local/bin:/usr/bin \
       -Ddefault-pam-config=redhat \
       -Ddistro=redhat \
%if %{with x11}
       -Dx11-support=true \
%else
       -Dx11-support=false \
%endif

%meson_build

%install
%meson_install

cp -a %{SOURCE1} %{buildroot}%{_datadir}/glib-2.0/schemas

install -p -m644 -D %{SOURCE2} %{buildroot}%{_sysusersdir}/%{name}.conf

mkdir -p %{buildroot}%{_sysconfdir}/dconf/db/gdm.d/locks

%if %{with x11}
ln -sf ../X11/xinit/Xsession %{buildroot}%{_sysconfdir}/gdm/
%endif

%find_lang gdm --with-gnome

%post
%systemd_post gdm.service

%preun
%systemd_preun gdm.service

%postun
%systemd_postun gdm.service

%files -f gdm.lang
%doc AUTHORS NEWS README.md
%license COPYING
%dir %{_sysconfdir}/gdm
%config(noreplace) %{_sysconfdir}/gdm/custom.conf
%{_prefix}/lib/pam.d/gdm-autologin
%{_prefix}/lib/pam.d/gdm-password
%{_prefix}/lib/pam.d/gdm-password-auth-substack
# not config files
%if %{with x11}
%{_sysconfdir}/gdm/Xsession
%endif
%{_datadir}/gdm/gdm.schemas
%{_datadir}/dbus-1/system.d/gdm.conf
%dir %{_sysconfdir}/dconf/db/gdm.d
%dir %{_sysconfdir}/dconf/db/gdm.d/locks
%{_datadir}/glib-2.0/schemas/org.gnome.login-screen.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.login-screen.gschema.override
%{_libexecdir}/gdm-runtime-config
%{_libexecdir}/gdm-session-worker
%{_libexecdir}/gdm-new-session
%{_libexecdir}/gdm-wayland-session
%if %{with x11}
%{_libexecdir}/gdm-x-session
%endif
%{_libexecdir}/gdm-headless-login-session
%{_sbindir}/gdm
%{_bindir}/gdm-config
%dir %{_datadir}/dconf
%dir %{_datadir}/dconf/profile
%{_datadir}/dconf/profile/gdm
%dir %{_datadir}/gdm/greeter
%dir %{_datadir}/gdm/greeter/applications
%dir %{_datadir}/gdm/greeter/wayland-sessions
%{_datadir}/gdm/greeter/applications/*
%{_datadir}/gdm/greeter/wayland-sessions/*
%{_datadir}/gdm/greeter-dconf-defaults
%{_datadir}/gdm/locale.alias
%{_datadir}/gdm/gdb-cmd
%{_datadir}/gnome-session/sessions/gnome-login.session
%{_datadir}/polkit-1/rules.d/20-gdm.rules
%{_datadir}/polkit-1/actions/org.gnome.displaymanager.policy
%{_libdir}/girepository-1.0/Gdm-1.0.typelib
%{_libdir}/security/pam_gdm.so
%{_libdir}/libgdm.so.1{,.*}
%{_libexecdir}/gdm-auth-config-redhat
%ghost %dir %{_localstatedir}/log/gdm
%ghost %dir %{_localstatedir}/lib/gdm
%ghost %dir %{_rundir}/gdm
%{_prefix}/lib/pam.d/gdm-smartcard
%{_prefix}/lib/pam.d/gdm-smartcard-auth-substack
%{_prefix}/lib/pam.d/gdm-fingerprint
%{_prefix}/lib/pam.d/gdm-fingerprint-auth-substack
%{_prefix}/lib/pam.d/gdm-switchable-auth
%{_prefix}/lib/pam.d/gdm-switchable-auth-substack
%{_prefix}/lib/pam.d/gdm-launch-environment
%{_unitdir}/gdm.service
%{_unitdir}/gnome-headless-session@.service
%dir %{_userunitdir}/gnome-session@gnome-login.target.d/
%{_userunitdir}/gnome-session@gnome-login.target.d/gnome-login.session.conf
%{_sysusersdir}/%{name}.conf

%files devel
%dir %{_includedir}/gdm
%{_includedir}/gdm/*.h
%exclude %{_includedir}/gdm/gdm-pam-extensions.h
%exclude %{_includedir}/gdm/gdm-choice-list-pam-extension.h
%exclude %{_includedir}/gdm/gdm-custom-json-pam-extension.h
%exclude %{_includedir}/gdm/gdm-pam-extensions-common.h
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Gdm-1.0.gir
%{_libdir}/libgdm.so
%{_libdir}/pkgconfig/gdm.pc

%files pam-extensions-devel
%{_includedir}/gdm/gdm-pam-extensions.h
%{_includedir}/gdm/gdm-choice-list-pam-extension.h
%{_includedir}/gdm/gdm-custom-json-pam-extension.h
%{_includedir}/gdm/gdm-pam-extensions-common.h
%{_libdir}/pkgconfig/gdm-pam-extensions.pc

%changelog
%autochangelog
