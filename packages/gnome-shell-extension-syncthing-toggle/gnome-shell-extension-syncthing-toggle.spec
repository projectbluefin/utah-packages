# Sync Folder Toggle (bluefin-bling's syncthing-toggle), as Project Bluefin
# Dakota builds it: elements/bluefin/shell-extensions/syncthing-toggle.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref. Fedora has no
# recipe. Layout shared by every extension recipe written from a Dakota
# element: docs/skills/gnome-shell-extension-recipes.md.
#
# Requires are the element's runtime-depends: the toggle runs Syncthing as a
# Podman Quadlet through service.js (gjs), reading the XDG user directories,
# and talks to it with libsoup 3. The element also depends on Dakota's native
# syncthing, kept there only to migrate existing Dakota installs; Utah ships
# no native syncthing, so this does not require it.
%global uuid syncthing-toggle@projectbluefin.io
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global commit baa802a45d7aaa514ad02e3b91076546bfa034d9
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261102

Name:           gnome-shell-extension-syncthing-toggle
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        GNOME Shell Quick Settings toggle for a Syncthing sync folder

# SPDX headers; bluefin-bling carries no repository license file.
License:        GPL-3.0-or-later
URL:            https://github.com/projectbluefin/bluefin-bling
Source0:        %{url}/archive/%{commit}/bluefin-bling-%{shortcommit}.tar.gz

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
Requires:       coreutils
Requires:       gjs
Requires:       gnome-shell
Requires:       libsoup3
Requires:       podman
Requires:       systemd
Requires:       xdg-user-dirs

%description
Sync Folder Toggle adds a Quick Settings toggle that runs Syncthing in a
rootless Podman container and shares the user's folders with paired devices.

%prep
%autosetup -n bluefin-bling-%{commit}

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR extensions/syncthing-toggle/. %{buildroot}%{extdir}/
rm -rf %{buildroot}%{extdir}/schemas
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  extensions/syncthing-toggle/schemas/org.gnome.shell.extensions.syncthing-toggle.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%doc README.md
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.syncthing-toggle.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20261102gitbaa802a-1
- Initial recipe from Dakota's bluefin/shell-extensions/syncthing-toggle.bst
