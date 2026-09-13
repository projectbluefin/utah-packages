%global debug_package %{nil}
%global __strip /bin/true

Name:           tailscale
Version:        1.98.8
Release:        3%{?dist}
Summary:        The easiest, most secure way to use WireGuard and 2FA
License:        BSD-3-Clause
URL:            https://tailscale.com/

# Match Dakota's platform-independent packaging approach: Tailscale publishes
# static release binaries, so the package does not depend on Hummingbird's Go
# version merely to reproduce an upstream release artifact.
Source0:        https://pkgs.tailscale.com/stable/tailscale_%{version}_amd64.tgz
Source1:        LICENSE
Source2:        tailscaled.service
Source3:        tailscale-systray-user.service

ExclusiveArch:  x86_64
BuildRequires:  file
BuildRequires:  systemd-rpm-macros
Requires:       iproute
Requires:       (iptables or nftables)

%description
Tailscale is a modern VPN built on top of WireGuard. It works like an overlay
network between the machines of your networks, using NAT traversal.

%prep
%autosetup -n tailscale_%{version}_amd64
cp -p %{SOURCE1} LICENSE

%build
# The official release payload contains statically linked binaries.

%install
install -Dpm 0755 tailscale tailscaled -t %{buildroot}%{_bindir}
install -Dpm 0644 %{SOURCE2} %{buildroot}%{_unitdir}/tailscaled.service
install -Dpm 0644 %{SOURCE3} %{buildroot}%{_userunitdir}/tailscale-systray.service
install -dpm 0700 %{buildroot}%{_sharedstatedir}/tailscale
install -dpm 0700 %{buildroot}%{_localstatedir}/cache/tailscale

%check
test "$(./tailscale version | head -n1)" = "%{version}"
test "$(./tailscaled --version | head -n1)" = "%{version}"
file tailscale tailscaled | grep -c 'statically linked' | grep -qx 2

%post
%systemd_post tailscaled.service
%systemd_user_post tailscale-systray.service

%preun
%systemd_preun tailscaled.service
%systemd_user_preun tailscale-systray.service

%postun
%systemd_postun_with_restart tailscaled.service
%systemd_user_postun_with_restart tailscale-systray.service

%files
%license LICENSE
%{_bindir}/tailscale
%{_bindir}/tailscaled
%{_unitdir}/tailscaled.service
%{_userunitdir}/tailscale-systray.service
%dir %{_sharedstatedir}/tailscale
%dir %{_localstatedir}/cache/tailscale

%changelog
* Sat Sep 05 2026 Project Bluefin <bot@projectbluefin.io> - 1.98.8-3
- Package the official static release payload, matching Dakota
