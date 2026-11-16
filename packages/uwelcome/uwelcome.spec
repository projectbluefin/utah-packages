# uwelcome, the login welcome banner, as Project Bluefin Dakota ships it.
#
# Dakota's bluefin/uwelcome.bst (projectbluefin/dakota bf271777) installs the
# upstream release binary, not a source build, so this recipe repackages the
# same SHA-256-identical release binary, as the tailscale recipe does for its
# Go release binaries. projectbluefin/common ships the hooks that run it
# (/etc/profile.d/uwelcome.sh, the fish greeting, /etc/uwelcome); this package
# is the binary alone, like the element. The element installs no license, so
# LICENSE is the project's file at the v0.4.1 tag (commit 13f8161f).
#
# The factory builds x86_64 only, so the recipe takes the element's amd64 asset.
%global debug_package %{nil}
%global __strip /bin/true

Name:           uwelcome
Version:        0.4.1
Release:        1%{?dist}
Summary:        Configurable terminal welcome banner for Universal Blue systems

License:        Apache-2.0
URL:            https://github.com/projectbluefin/uwelcome
Source0:        %{url}/releases/download/v%{version}/uwelcome_%{version}_linux_amd64#/uwelcome-%{version}-x86_64
Source1:        LICENSE

ExclusiveArch:  x86_64

%description
uwelcome renders the terminal welcome banner on Universal Blue and Project
Bluefin systems; users enable, disable, edit or reset it with its
subcommands. This is the upstream release binary Project Bluefin Dakota
ships.

%prep
%setup -q -c -T
cp -p %{SOURCE1} LICENSE

%build
# The release payload is a prebuilt Go binary.

%install
install -Dpm 0755 %{SOURCE0} %{buildroot}%{_bindir}/uwelcome

%check
test "$(%{buildroot}%{_bindir}/uwelcome version)" = "%{version}"

%files
%license LICENSE
%{_bindir}/uwelcome

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.4.1-1
- Initial recipe: Dakota's uwelcome release binary (bluefin/uwelcome.bst)
