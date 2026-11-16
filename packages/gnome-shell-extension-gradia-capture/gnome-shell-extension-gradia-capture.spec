# Gradia Capture, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/gradia-capture.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref. Fedora has no
# recipe. Layout shared by every extension recipe written from a Dakota
# element: docs/skills/gnome-shell-extension-recipes.md.
#
# Upstream publishes no release; the extension is src/ plus icons/.
%global uuid gradia-integration@alexandervanhee.github.io
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}
%global commit 0b7e47e1e5c1e68e234e4d2d24b307e1da1d18a9
%global shortcommit %(printf '%s\\n' %{commit} | cut -c1-7)
%global gitdate 20261016

Name:           gnome-shell-extension-gradia-capture
Version:        0^%{gitdate}git%{shortcommit}
Release:        1%{?dist}
Summary:        GNOME Shell screenshot integration for Gradia

License:        GPL-3.0-only
URL:            https://github.com/AlexanderVanhee/gradia-capture
Source0:        %{url}/archive/%{commit}/gradia-capture-%{shortcommit}.tar.gz

BuildArch:      noarch
BuildRequires:  glib2
BuildRequires:  jq
Requires:       gnome-shell

%description
Gradia Capture hands GNOME Shell screenshots to Gradia for annotation and
framing, from the screenshot UI and its toast.

%prep
%autosetup -n gradia-capture-%{commit}

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
cp -pR src/. icons %{buildroot}%{extdir}/
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +
install -Dpm 0644 -t %{buildroot}%{_datadir}/glib-2.0/schemas \
  schemas/org.gnome.shell.extensions.gradia-companion.gschema.xml

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas
glib-compile-schemas --strict --dry-run %{buildroot}%{_datadir}/glib-2.0/schemas

%files
%license LICENSE
%doc README.md
%{extdir}/
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.gradia-companion.gschema.xml

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0^20261016git0b7e47e-1
- Initial recipe from Dakota's bluefin/shell-extensions/gradia-capture.bst
