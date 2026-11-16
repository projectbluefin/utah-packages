# Fuzzy Application Search, as Project Bluefin Dakota builds it:
# elements/bluefin/shell-extensions/fuzzy-application-search.bst at
# projectbluefin/dakota@bf27177, pinned to the element's ref (tag v2). Fedora
# has no recipe. Layout shared by every extension recipe written from a
# Dakota element: docs/skills/gnome-shell-extension-recipes.md.
%global uuid fuzzy-application-search@mkhl.codeberg.page
%global extdir %{_datadir}/gnome-shell/extensions/%{uuid}

Name:           gnome-shell-extension-fuzzy-application-search
Version:        2
Release:        1%{?dist}
Summary:        Fuzzy matching for GNOME Shell application search

License:        0BSD
URL:            https://codeberg.org/mkhl/gnome-shell-extension-fuzzy-application-search
Source0:        %{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  jq
Requires:       gnome-shell

%description
Fuzzy Application Search replaces the overview's application search with
fuzzy matching, so abbreviations and typos still find the application.

%prep
%autosetup -n %{name}

%build
# Nothing to build: the extension is plain JavaScript.

%install
install -d %{buildroot}%{extdir}
install -pm 0644 -t %{buildroot}%{extdir} extension.js scoring.js metadata.json
find %{buildroot}%{extdir} -type d -exec chmod 0755 '{}' +
find %{buildroot}%{extdir} -type f -exec chmod 0644 '{}' +

%check
jq -e --arg uuid '%{uuid}' '.uuid == $uuid' %{buildroot}%{extdir}/metadata.json
test ! -e %{buildroot}%{extdir}/schemas

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{extdir}/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 2-1
- Initial recipe from Dakota's bluefin/shell-extensions/fuzzy-application-search.bst
