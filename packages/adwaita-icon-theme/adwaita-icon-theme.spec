%global adwlegacy_ver 46.2

Name:           adwaita-icon-theme
Version:        51.0
Release:        %autorelease
Summary:        Adwaita icon theme

License:        LGPL-3.0-only OR CC-BY-SA-3.0
URL:            https://gitlab.gnome.org/GNOME/adwaita-icon-theme
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildArch:      noarch

BuildRequires:  meson
BuildRequires:  /usr/bin/gtk4-update-icon-cache

# Only require the legacy icon package on Fedora
%if 0%{?fedora}
Requires:       %{name}-legacy >= %{adwlegacy_ver}
%endif
Requires:       adwaita-cursor-theme = %{version}-%{release}

%description
This package contains the Adwaita icon theme used by the GNOME desktop.

%package -n     adwaita-cursor-theme
Summary:        Adwaita cursor theme

%description -n adwaita-cursor-theme
The adwaita-cursor-theme package contains a modern set of cursors originally
designed for the GNOME desktop.

%package        devel
Summary:        Development files for %{name}
%if 0%{?fedora}
Requires:       %{name}-legacy-devel >= %{adwlegacy_ver}
%endif
Requires:       %{name} = %{version}-%{release}

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

touch $RPM_BUILD_ROOT%{_datadir}/icons/Adwaita/.icon-theme.cache

%transfiletriggerin -- %{_datadir}/icons/Adwaita
gtk-update-icon-cache --force %{_datadir}/icons/Adwaita &>/dev/null || :

%transfiletriggerpostun -- %{_datadir}/icons/Adwaita
gtk-update-icon-cache --force %{_datadir}/icons/Adwaita &>/dev/null || :

%files
%license COPYING*
%dir %{_datadir}/icons/Adwaita/
%{_datadir}/icons/Adwaita/16x16/
%{_datadir}/icons/Adwaita/scalable/
%{_datadir}/icons/Adwaita/symbolic/
%{_datadir}/icons/Adwaita/index.theme
%ghost %{_datadir}/icons/Adwaita/.icon-theme.cache

%files -n adwaita-cursor-theme
%license COPYING*
%dir %{_datadir}/icons/Adwaita/
%{_datadir}/icons/Adwaita/cursors/

%files devel
%{_datadir}/pkgconfig/adwaita-icon-theme.pc

%changelog
%autochangelog
