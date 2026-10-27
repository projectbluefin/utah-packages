%global systemd_unit gnome-ponytail-daemon.service
%global libname ponytail

Name:           gnome-ponytail-daemon
Version:        0.0.12
Release:        1%{?dist}
Summary:        Sort of a bridge for dogtail for GNOME on Wayland

License:        GPL-2.0-or-later
URL:            https://gitlab.gnome.org/ofourdan/gnome-ponytail-daemon
Source0:        %url/-/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  git-core
BuildRequires:  meson >= 0.40.0
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(glib-2.0) >= 2.32
BuildRequires:  pkgconfig(gio-unix-2.0) >= 2.32
BuildRequires:  python%{python3_pkgversion}-devel
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  systemd-rpm-macros

%if 0%{?fedora} >= 39 || 0%{?rhel} >= 10
BuildRequires:  pkgconfig(libei-1.0) >= 1.0.0
%endif

%{?systemd_requires}
BuildRequires:  systemd

%description
GNOME Ponytail Daemon is a sort of bridge for dogtail for GNOME on Wayland.

%package        -n python3-%{name}
Summary:        Python module for %{name}
Requires:       %{name} = %{version}-%{release}
Requires:       python3-dbus
Requires:       python3-gobject
BuildArch:      noarch

%description -n python3-%{name}
Python module for D-BUS interactions with gnome-ponytail-daemon interfaces.

%prep
%autosetup -n %{name}-%{version} -p1

%build
%meson
%meson_build

%install
%meson_install

%post
%systemd_user_post %{systemd_unit}

%preun
%systemd_user_preun %{systemd_unit}

%postun
%systemd_user_postun_with_restart %{systemd_unit}
%systemd_user_postun_with_reload %{systemd_unit}
%systemd_user_postun %{systemd_unit}

%files
%license LICENSE
%doc README.md
%{_libexecdir}/gnome-ponytail-daemon
%{_userunitdir}/gnome-ponytail-daemon.service
%{_datadir}/dbus-1/services/org.gnome.Ponytail.service

%files -n python3-%{name}
%doc examples/*.py
%{python3_sitelib}/%{libname}/

%changelog
* Thu Oct 22 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 0.0.12-1
- Update to 0.0.12

* Thu Jul 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.0.11-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Wed Jun 03 2026 Python Maint <python-maint@redhat.com> - 0.0.11-10
- Rebuilt for Python 3.15

* Fri Jan 16 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.0.11-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Sep 19 2025 Python Maint <python-maint@redhat.com> - 0.0.11-8
- Rebuilt for Python 3.14.0rc3 bytecode

* Fri Aug 15 2025 Python Maint <python-maint@redhat.com> - 0.0.11-7
- Rebuilt for Python 3.14.0rc2 bytecode

* Wed Jul 23 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.0.11-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Mon Jun 02 2025 Python Maint <python-maint@redhat.com> - 0.0.11-5
- Rebuilt for Python 3.14

* Thu Jan 16 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.0.11-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.0.11-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Jun 07 2024 Python Maint <python-maint@redhat.com> - 0.0.11-2
- Rebuilt for Python 3.13

* Mon May 20 2024 José Expósito <jexposit@redhat.com> - 0.0.11-1
- Version 0.0.11

* Fri Feb 02 2024 José Expósito <jexposit@redhat.com> - 0.0.10-2
- Fix requires in Python package

* Mon Jan 08 2024 José Expósito <jexposit@redhat.com> - 0.0.10-1
- Add libei support
- Bug fixing

* Tue Dec 10 2019 Olivier Fourdan <ofourdan@redhat.com> - 0.0.9-1
- Version 0.0.9

* Tue Jan 29 2019 Olivier Fourdan <ofourdan@redhat.com> - 0.0.8-1
- Version 0.0.8

* Wed Dec 19 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.7-1
- Version 0.0.7

* Thu Dec 13 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.6-1
- Version 0.0.6

* Wed Dec 5 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.5-1
- Version 0.0.5

* Wed Nov 28 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.4-1
- Version 0.0.4

* Thu Nov 22 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.3-1
- Version 0.0.3

* Mon Nov 19 2018 Olivier Fourdan <ofourdan@redhat.com> - 0.0.2-1
- Initial version
