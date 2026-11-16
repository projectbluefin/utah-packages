# Custom Command Menu, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/custom-command-menu.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref (tag v16). Fedora
# has no recipe. Layout shared by every extension recipe written from a
# Dakota element: docs/skills/gnome-shell-extension-recipes.md.
#
# The element also installs two Dakota dconf keyfiles; those are
# dakota-config-custom-command-menu-dconf, not part of this package. It copies
# the whole checkout into the extension directory; this installs the files
# the extension loads (no screenshots, po/ or changelog).
%global uuid custom-command-list@storageb.github.com
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}

Name:           gnome-shell-extension-custom-command-menu
Version:        16
Release:        1%{?dist}
Summary:        GNOME Shell top-bar menu of user-defined commands

# Sources are GPL-2.0-or-later (SPDX headers); the repository license is GPL-3.0.
License:        GPL-2.0-or-later AND GPL-3.0-only
URL:            https://github.com/StorageB/custom-command-menu
Source0:        %{url}/archive/v%{version}/custom-command-menu-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
Requires:       gnome-shell

%description
Custom Command Menu adds a top-bar menu whose entries run commands the user
defines in the extension's preferences.

%prep
%autosetup -n custom-command-menu-%{version}

%build
# Nothing to build: the extension is plain JavaScript with compiled catalogs.

%install
install -d %{buildroot}%{extdir}
cp -pR about.js commandsUI.js extension.js prefs.js metadata.json locale \
  %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  schemas/org.gnome.shell.extensions.custom-command-list.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%license LICENSE
%doc README.md changelog.md
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.custom-command-list.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 16-1
- Initial recipe from Dakota's bluefin/shell-extensions/custom-command-menu.bst
