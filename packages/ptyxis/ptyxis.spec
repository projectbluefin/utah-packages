%global glib2_version 2.80
%global gtk4_version 4.14
%global vte291_version 0.77
%global json_glib_version 1.6
%global libadwaita_version 1.6
%global libportal_gtk4_version 0.7.1

Name:		ptyxis
Version:	50.1
Release:	%autorelease
Summary:	A container oriented terminal for GNOME

License:	GPL-2.0-or-later AND GPL-3.0-or-later AND LGPL-3.0-or-later AND LGPL-2.0-or-later AND CC0-1.0
URL:		https://gitlab.gnome.org/chergert/ptyxis
Source0:	https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz
Source1:	org.gnome.Ptyxis.fedora.gschema.override

%gnome_check_version

BuildRequires:	pkgconfig(gio-unix-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:	pkgconfig(vte-2.91-gtk4) >= %{vte291_version}
BuildRequires:	pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:  pkgconfig(libportal-gtk4) >= %{libportal_gtk4_version}
BuildRequires:	pkgconfig(json-glib-1.0) >= %{json_glib_version}
BuildRequires:	desktop-file-utils
BuildRequires:	gcc
BuildRequires:	itstool
BuildRequires:	meson
BuildRequires:	/usr/bin/appstream-util

Requires:	hicolor-icon-theme

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:	%{ix86}

%description
Ptyxis is a container oriented terminal that provides transparent support for
container systems like Podman, Distrobox, and Toolbx. It also has robust
support for user profiles.


%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}


%build
%meson -Dgeneric=terminal
%meson_build


%install
%meson_install
install -p %{SOURCE1} %{buildroot}%{_datadir}/glib-2.0/schemas
%find_lang %{name} --with-gnome


%check
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/org.gnome.Ptyxis.metainfo.xml
desktop-file-validate %{buildroot}%{_datadir}/applications/org.gnome.Ptyxis.desktop


%files -f %{name}.lang
%doc README.md NEWS
%license COPYING
%{_bindir}/ptyxis
%{_libexecdir}/ptyxis-agent
%{_metainfodir}/org.gnome.Ptyxis.metainfo.xml
%{_datadir}/applications/org.gnome.Ptyxis.desktop
%dir %{_datadir}/dbus-1
%dir %{_datadir}/dbus-1/services
%{_datadir}/dbus-1/services/org.gnome.Ptyxis.service
%{_datadir}/glib-2.0/schemas/org.gnome.Ptyxis.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.Ptyxis.fedora.gschema.override
%{_datadir}/icons/hicolor/*/*/*.svg
%{_mandir}/man1/ptyxis.1*

%changelog
%autochangelog
