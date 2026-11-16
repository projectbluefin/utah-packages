# BudsLink Companion, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/budslink-companion.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref (a commit on the
# Gnome-Extension branch) with the element's patch. Fedora has no recipe.
# Layout shared by every extension recipe written from a Dakota element:
# docs/skills/gnome-shell-extension-recipes.md.
#
# The element also compiles po/*.po into the extension's locale/; this commit
# has only the template (po/BudsLink-Companion.pot), so there is nothing to
# compile. Add the step back when a .po lands.
%global uuid BudsLink-Companion@maniacx.github.com
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global commit c11b6cf5626ee5417efc0af91148736e0697c354
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20260823

Name:           gnome-shell-extension-budslink-companion
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        GNOME Shell Bluetooth earbuds controls for BudsLink

License:        GPL-3.0-only
URL:            https://github.com/maniacx/BudsLink-Companion
Source0:        %{url}/archive/%{commit}/BudsLink-Companion-%{shortcommit}.tar.gz
# From Dakota (patches/shell-extensions/budslink-companion-startup.patch):
# wait for Bluetooth to come up and for the BudsLink app to be installed.
Patch0:         budslink-companion-startup.patch

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
Requires:       gnome-shell

%description
BudsLink Companion shows battery levels and controls for supported Bluetooth
earbuds in the Quick Settings Bluetooth menu, talking to the BudsLink app over
D-Bus.

%prep
%autosetup -n BudsLink-Companion-%{commit} -p1

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR extension.js prefs.js metadata.json stylesheet.css icons lib preferences ui \
  %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  schemas/org.gnome.shell.extensions.BudsLink-Companion.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%license LICENSE
%doc README.md
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.BudsLink-Companion.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20260823gitc11b6cf-1
- Initial recipe from Dakota's bluefin/shell-extensions/budslink-companion.bst
