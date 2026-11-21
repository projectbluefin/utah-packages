# uupd, Universal Blue's unattended updater, as Project Bluefin Dakota ships it.
#
# Dakota's bluefin/uupd.bst (projectbluefin/dakota bf271777) installs the
# upstream release binary, not a source build, so this recipe repackages the
# same SHA-256-identical release payload, as the tailscale recipe does for its
# Go release binaries. The element's units, /etc/uupd/config.json and polkit
# rule are already packaged, cut from the same element, as dakota-config-uupd;
# this package carries the binary and requires that subpackage, so installing
# uupd installs the whole element.
#
# Dakota pins the x86_64 asset at 1.5.5 and the aarch64 asset at 1.4.0; the
# factory builds x86_64 only, so the recipe follows the x86_64 pin.
%global debug_package %{nil}
%global __strip /bin/true

Name:           uupd
Version:        1.5.7
Release:        1%{?dist}
Summary:        Universal Blue unattended system, Flatpak, Homebrew and distrobox updater

License:        Apache-2.0
URL:            https://github.com/ublue-os/uupd
Source0:        %{url}/releases/download/v%{version}/uupd_Linux_x86_64.tar.gz#/uupd-%{version}-x86_64.tar.gz

ExclusiveArch:  x86_64

Requires:       dakota-config-uupd

%description
uupd updates a bootc system image, Flatpaks, Homebrew and distrobox
containers in one unattended run, after checking battery, CPU, memory and
network load. This is the upstream release binary Project Bluefin Dakota
ships; its systemd units, configuration and polkit rule come from
dakota-config-uupd.

%prep
%setup -q -c -n %{name}-%{version}

%build
# The release payload is a prebuilt Go binary.

%install
install -Dpm 0755 uupd %{buildroot}%{_bindir}/uupd

%check
test "$(./uupd --version)" = "uupd version %{version}"

%files
%license LICENSE
%doc README.md
%{_bindir}/uupd

%changelog
* Fri Nov 20 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 1.5.7-1
- Update to 1.5.7

* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 1.5.5-1
- Initial recipe: Dakota's uupd release binary (bluefin/uupd.bst)
