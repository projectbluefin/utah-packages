Name:           adwaita-icon-theme-legacy
Version:        46.2
Release:        %autorelease
Summary:        Full-color icons for the Adwaita icon theme

License:        LGPL-3.0-only OR CC-BY-SA-3.0
URL:            https://gitlab.gnome.org/GNOME/adwaita-icon-theme-legacy
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildArch:      noarch

BuildRequires:  meson
BuildRequires:  /usr/bin/gtk4-update-icon-cache

# Offer alternative name
Provides:       adwaita-legacy-icon-theme = %{version}-%{release}

%description
This package contains the full color Adwaita icons for the Adwaita icon theme
used by the GNOME desktop.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name} = %{version}-%{release}

# Offer alternative name
Provides:       adwaita-legacy-icon-theme-devel = %{version}-%{release}

%description    devel
The %{name}-devel package contains the pkgconfig file for
developing applications that use %{name}.

%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}

%build
%meson
%meson_build

%install
%meson_install

# Delete license files being installed in the adwaita-icon-theme dir
rm -rf %{buildroot}%{_licensedir}/adwaita-icon-theme

# Delete useless hidden files
find %{buildroot} -name ".placeholder" -delete
find %{buildroot} -name ".empty" -delete

touch %{buildroot}%{_datadir}/icons/AdwaitaLegacy/.icon-theme.cache

%transfiletriggerin -- %{_datadir}/icons/AdwaitaLegacy
gtk-update-icon-cache --force %{_datadir}/icons/AdwaitaLegacy &>/dev/null || :

%transfiletriggerpostun -- %{_datadir}/icons/AdwaitaLegacy
gtk-update-icon-cache --force %{_datadir}/icons/AdwaitaLegacy &>/dev/null || :

%files
%license COPYING*
%dir %{_datadir}/icons/AdwaitaLegacy/
%{_datadir}/icons/AdwaitaLegacy/8x8/
%{_datadir}/icons/AdwaitaLegacy/16x16/
%{_datadir}/icons/AdwaitaLegacy/22x22/
%{_datadir}/icons/AdwaitaLegacy/24x24/
%{_datadir}/icons/AdwaitaLegacy/32x32/
%{_datadir}/icons/AdwaitaLegacy/48x48/
%{_datadir}/icons/AdwaitaLegacy/index.theme
%ghost %{_datadir}/icons/AdwaitaLegacy/.icon-theme.cache

%files devel
%{_datadir}/pkgconfig/%{name}.pc

%changelog
%autochangelog
