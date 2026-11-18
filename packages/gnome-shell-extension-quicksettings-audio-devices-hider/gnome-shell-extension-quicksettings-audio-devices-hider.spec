# Quick Settings Audio Devices Hider, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/quicksettings-audio-devices-hider.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref: the
# extensions.gnome.org build version_tag 69924 (SHA-256 217082e0...). Fedora
# has no recipe. Layout shared by every extension recipe written from a
# Dakota element: docs/skills/gnome-shell-extension-recipes.md.
%global uuid quicksettings-audio-devices-hider@marcinjahn.com
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global version_tag 69924

Name:           gnome-shell-extension-quicksettings-audio-devices-hider
Version:        18
Release:        1%{?dist}
Summary:        Hide audio devices from the GNOME Shell Quick Settings menu

License:        MIT
URL:            https://github.com/marcinjahn/gnome-quicksettings-audio-devices-hider-extension
Source0:        https://extensions.gnome.org/download-extension/%{uuid}.shell-extension.zip?version_tag=%{version_tag}#/%{name}-%{version}.zip

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
BuildRequires:  unzip
Requires:       gnome-shell

%description
Quick Settings Audio Devices Hider lets the user pick which audio output and
input devices the Quick Settings volume menus list.

%prep
%autosetup -c

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR extension.js prefs.js metadata.json %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  schemas/org.gnome.shell.extensions.quicksettings-audio-devices-hider.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.quicksettings-audio-devices-hider.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 18-1
- Initial recipe from Dakota's bluefin/shell-extensions/quicksettings-audio-devices-hider.bst
