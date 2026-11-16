# umotd, Universal Blue's message-of-the-day tool, as Project Bluefin Dakota
# ships it.
#
# Dakota's bluefin/umotd.bst (projectbluefin/dakota bf271777) installs the
# upstream release binary and the project LICENSE, not a source build, so this
# recipe repackages the same SHA-256-identical release binary, as the tailscale
# recipe does for its Go release binaries. LICENSE is the file the element
# fetches (projectbluefin/umotd 97520c61, SHA-256 c71d239d...).
#
# The factory builds x86_64 only, so the recipe takes the element's amd64 asset.
%global debug_package %{nil}
%global __strip /bin/true

Name:           umotd
Version:        0.3.3
Release:        1%{?dist}
Summary:        Translatable message of the day for Universal Blue systems

License:        Apache-2.0
URL:            https://github.com/projectbluefin/umotd
Source0:        %{url}/releases/download/v%{version}/umotd_%{version}_linux_amd64#/umotd-%{version}-x86_64
Source1:        LICENSE

ExclusiveArch:  x86_64

%description
umotd prints the message of the day on Universal Blue and Project Bluefin
systems, with tags that select which messages a user sees. This is the
upstream release binary Project Bluefin Dakota ships.

%prep
%setup -q -c -T
cp -p %{SOURCE1} LICENSE

%build
# The release payload is a prebuilt Go binary.

%install
install -Dpm 0755 %{SOURCE0} %{buildroot}%{_bindir}/umotd

%check
test "$(%{buildroot}%{_bindir}/umotd version)" = "%{version}"

%files
%license LICENSE
%{_bindir}/umotd

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.3.3-1
- Initial recipe: Dakota's umotd release binary (bluefin/umotd.bst)
