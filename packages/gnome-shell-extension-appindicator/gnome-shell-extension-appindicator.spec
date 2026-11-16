%global forgeurl https://github.com/ubuntu/gnome-shell-extension-appindicator
%global uuid appindicatorsupport@rgcjonas.gmail.com

Name: gnome-shell-extension-appindicator
Version: 66
%forgemeta
Release: %autorelease
Summary: AppIndicator/KStatusNotifierItem support for GNOME Shell
BuildArch: noarch

License: GPL-2.0-only
URL: %{forgeurl}
Source0: %{forgesource}

BuildRequires: gettext
BuildRequires: glib2
BuildRequires: jq
BuildRequires: meson

Requires: gnome-shell >= 3.14.0
Requires: libappindicator-gtk3

# gnome-shell-extension-appindicator version >= 40 now also includes
# support for legacy X11 tray icons and the topicons(-plus) extensions
# are no longer maintained upstream
Provides:  gnome-shell-extension-topicons-plus = %{version}-%{release}
Obsoletes: gnome-shell-extension-topicons-plus <= 27-9

%description
This extension integrates Ubuntu AppIndicators and KStatusNotifierItems (KDE's
blessed successor of the systray) into GNOME Shell.

You can use gnome-tweaks (additional package) or run in terminal:

  $ gnome-extensions enable %uuid


%prep
%forgeautosetup -p1


%build
%meson \
    -Dlocal_install=disabled
%meson_build


%install
%meson_install
%find_lang AppIndicatorExtension
rm %{buildroot}%{_datadir}/glib-2.0/schemas/gschemas.compiled


%files -f AppIndicatorExtension.lang
%license LICENSE
%doc README.md AUTHORS.md
%{_datadir}/gnome-shell/extensions/%{uuid}/
%{_datadir}/glib-2.0/schemas/*.gschema.xml


%changelog
%autochangelog
