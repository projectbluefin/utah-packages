# Tiling Shell, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/tilingshell.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref: the
# extensions.gnome.org 17.3 build, version_tag 70233 (SHA-256 0a9f2b26...),
# with Dakota's GNOME 51 patch. Fedora has no recipe. Layout shared by every
# extension recipe written from a Dakota element:
# docs/skills/gnome-shell-extension-recipes.md.
%global uuid tilingshell@ferrarodomenico.com
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global version_tag 70233

Name:           gnome-shell-extension-tilingshell
Version:        17.3
Release:        1%{?dist}
Summary:        Tiling window management for GNOME Shell

License:        GPL-3.0-or-later
URL:            https://github.com/domferr/tilingshell
Source0:        https://extensions.gnome.org/download-extension/%{uuid}.shell-extension.zip?version_tag=%{version_tag}#/%{name}-%{version}.zip
# From Dakota (patches/tilingshell/0001-gnome-51-support.patch): port of
# domferr/tilingshell#605 to the compiled build, for mutter 51 dropping the
# org.gnome.mutter experimental-features key; adds "51" to shell-version.
# Drop once a release lists GNOME 51.
Patch0:         0001-gnome-51-support.patch

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
BuildRequires:  unzip
Requires:       gnome-shell

%description
Tiling Shell adds tiling window management to GNOME Shell: layouts with an
editor, snap assistant, tile previews and keyboard tiling.

%prep
%autosetup -c -p1

%build
# Nothing to build: the extensions.gnome.org build is compiled JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR ./* %{buildroot}%{extdir}/
rm -rf %{buildroot}%{extdir}/schemas
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  schemas/org.gnome.shell.extensions.tilingshell.gschema.xml

%check
# As the element does: fail the build, not the session, when the patched
# metadata stops declaring GNOME 51.
jq -e --arg uuid '%{uuid}' '.uuid == $uuid and (."shell-version" | index("51") != null)' \
  %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.tilingshell.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 17.3-1
- Initial recipe from Dakota's bluefin/shell-extensions/tilingshell.bst
