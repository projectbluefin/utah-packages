# Tailscale QS, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/tailscale-qs.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref (tag v9) with the
# element's patch. Fedora has no recipe. Layout shared by every extension
# recipe written from a Dakota element:
# docs/skills/gnome-shell-extension-recipes.md.
#
# The patch sends an unauthorized or signed-out user to Dakota's Tailscale
# setup app, which is why this requires dakota-config-tailscale-setup, as the
# element depends on bluefin/tailscale-setup.bst.
%global uuid tailscale-gnome-qs@tailscale-qs.github.io
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}

Name:           gnome-shell-extension-tailscale-qs
Version:        9
Release:        1%{?dist}
Summary:        GNOME Shell Quick Settings toggle for Tailscale

License:        GPL-2.0-or-later AND GPL-3.0-only
URL:            https://github.com/tailscale-qs/tailscale-gnome-qs
Source0:        %{url}/archive/v%{version}/tailscale-gnome-qs-%{version}.tar.gz
# From Dakota (patches/shell-extensions/tailscale-setup.patch): open Dakota's
# Tailscale setup app, poll the daemon without blocking the shell, and
# recover after authorization or a daemon restart.
Patch0:         tailscale-setup.patch

BuildArch:      noarch
BuildRequires:  jq
Requires:       dakota-config-tailscale-setup
Requires:       gnome-shell
Requires:       libsoup3

%description
Tailscale QS adds a Quick Settings toggle for Tailscale with menus for nodes,
exit nodes, Mullvad exit nodes, preferences and profiles.

%prep
%autosetup -n tailscale-gnome-qs-%{version} -p1

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR %{uuid}/. %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas

%files
%license LICENSE
%doc README.md
%{extdir}/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 9-1
- Initial recipe from Dakota's bluefin/shell-extensions/tailscale-qs.bst
