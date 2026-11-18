# Bazaar Companion, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/bazaar-companion.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref. Fedora has no
# recipe. Layout shared by every extension recipe written from a Dakota
# element: docs/skills/gnome-shell-extension-recipes.md.
#
# Upstream publishes no release; the extension is src/.
%global uuid bazaar-integration@kolunmi.github.io
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global commit 3bb9134985343ffd1993520eb37c90e113bfb09b
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20260403

Name:           gnome-shell-extension-bazaar-companion
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        GNOME Shell integration for the Bazaar app store

# SPDX headers in src/; the repository carries no license file.
License:        GPL-3.0-or-later
URL:            https://github.com/bazaar-org/bazaar-companion
Source0:        %{url}/archive/%{commit}/bazaar-companion-%{shortcommit}.tar.gz

BuildArch:      noarch
BuildRequires:  jq
Requires:       gnome-shell

%description
Bazaar Companion makes the app grid's "App Details" item open Flatpak apps in
Bazaar instead of GNOME Software, and adds an Uninstall item for Flatpak
apps.

%prep
%autosetup -n bazaar-companion-%{commit}

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR src/. %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas

%files
%doc README.md
%{extdir}/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20260403git3bb9134-1
- Initial recipe from Dakota's bluefin/shell-extensions/bazaar-companion.bst
