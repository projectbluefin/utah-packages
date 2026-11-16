# Power Status Color (bluefin-bling's power-status-color), as Project Bluefin
# Dakota builds it: elements/bluefin/shell-extensions/power-status-color.bst
# at projectbluefin/dakota@bf27177, pinned to the element's ref. Fedora has no
# recipe. Layout shared by every extension recipe written from a Dakota
# element: docs/skills/gnome-shell-extension-recipes.md.
#
# bluefin-bling declares no license for this extension: no repository
# license file and no SPDX header (its siblings are GPL-3.0-or-later and
# GPL-2.0-or-later). Replace the LicenseRef once upstream declares one.
%global uuid power-status-color@projectbluefin.io
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global commit f43fc6dccdfebe28e9312756d538208d073f7854
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261111

Name:           gnome-shell-extension-power-status-color
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        Color the GNOME Shell power button by update and uptime status

License:        LicenseRef-Not-Declared
URL:            https://github.com/projectbluefin/bluefin-bling
Source0:        %{url}/archive/%{commit}/bluefin-bling-%{shortcommit}.tar.gz

BuildArch:      noarch
BuildRequires:  jq
Requires:       gnome-shell

%description
Power Status Color tints the Quick Settings power button when a staged
deployment or a pending reboot is waiting, and when the system has been up
for a long time.

%prep
%autosetup -n bluefin-bling-%{commit}

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR extensions/power-status-color/. %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas

%files
%doc README.md
%{extdir}/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20261111gitf43fc6d-1
- Initial recipe from Dakota's bluefin/shell-extensions/power-status-color.bst
