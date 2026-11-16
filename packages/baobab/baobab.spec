%global gtk4_version 4.15.1
%global libadwaita_version 1.6~alpha

Name:           baobab
Version:        50.0
Release:        %autorelease
Summary:        A graphical directory tree analyzer

# Sources are under GPL-2.0-or-later, help is under CC-BY-SA-3.0, Appdata is
# under CC0-1.0.
License:        GPL-2.0-or-later AND CC-BY-SA-3.0 AND CC0-1.0
URL:            https://wiki.gnome.org/Apps/Baobab
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildRequires:  pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:  pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:  /usr/bin/appstream-util
BuildRequires:  desktop-file-utils
BuildRequires:  gettext
BuildRequires:  itstool
BuildRequires:  meson
BuildRequires:  vala

Requires:       gtk4%{?_isa} >= %{libadwaita_version}
Requires:       libadwaita%{?_isa} >= %{libadwaita_version}

%description
Baobab is able to scan either specific directories or the whole filesystem, in
order to give the user a graphical tree representation including each
directory size or percentage in the branch.  It also auto-detects in real-time
any change made to your home folder as far as any mounted/unmounted device.

%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}


%build
%meson
%meson_build


%install
%meson_install

%find_lang %{name} --with-gnome


%check
appstream-util validate-relax --nonet %{buildroot}/%{_metainfodir}/org.gnome.baobab.metainfo.xml
desktop-file-validate %{buildroot}/%{_datadir}/applications/org.gnome.baobab.desktop


%files -f %{name}.lang
%doc AUTHORS NEWS README.md
%license COPYING
%{_bindir}/baobab
%{_datadir}/applications/org.gnome.baobab.desktop
%{_datadir}/dbus-1/services/org.gnome.baobab.service
%{_datadir}/icons/hicolor/scalable/apps/org.gnome.baobab*.svg
%{_datadir}/icons/hicolor/symbolic/apps/org.gnome.baobab-symbolic.svg
%{_datadir}/glib-2.0/schemas/org.gnome.baobab.gschema.xml
%{_metainfodir}/org.gnome.baobab.metainfo.xml
%{_mandir}/man1/baobab.1*


%changelog
%autochangelog
