# Quick Settings Audio Devices Renamer, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/quicksettings-audio-devices-renamer.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref: the
# extensions.gnome.org build version_tag 69925 (SHA-256 a4f33897...). Fedora
# has no recipe. Layout shared by every extension recipe written from a
# Dakota element: docs/skills/gnome-shell-extension-recipes.md.
%global uuid quicksettings-audio-devices-renamer@marcinjahn.com
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global version_tag 69925

Name:           gnome-shell-extension-quicksettings-audio-devices-renamer
Version:        8
Release:        1%{?dist}
Summary:        Rename audio devices in the GNOME Shell Quick Settings menu

License:        MIT
URL:            https://github.com/marcinjahn/gnome-quicksettings-audio-devices-renamer-extension
Source0:        https://extensions.gnome.org/download-extension/%{uuid}.shell-extension.zip?version_tag=%{version_tag}#/%{name}-%{version}.zip

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
BuildRequires:  unzip
Requires:       gnome-shell

%description
Quick Settings Audio Devices Renamer lets the user give the audio output and
input devices in the Quick Settings volume menus names of their choosing.

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
  schemas/org.gnome.shell.extensions.quicksettings-audio-devices-renamer.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.quicksettings-audio-devices-renamer.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 8-1
- Initial recipe from Dakota's bluefin/shell-extensions/quicksettings-audio-devices-renamer.bst
