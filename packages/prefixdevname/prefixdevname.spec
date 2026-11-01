Name:           prefixdevname
Version:        0.2.0
Release:        1%{?dist}
Summary:        Udev helper utility that provides network interface naming using user defined prefix
# MIT
# MIT OR Apache-2.0
# Unlicense OR MIT
License:        MIT AND (MIT OR Apache-2.0) AND (Unlicense OR MIT)
# LICENSE.dependencies contains a full license breakdown
URL:            https://github.com/msekletar/prefixdevname
Source:         prefixdevname-%{version}-vendored.tar.xz

ExclusiveArch:  %{rust_arches}

BuildRequires:  cargo-rpm-macros
BuildRequires:  systemd-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  pkg-config

%description
This package provides a udev helper utility that tries to consistently name all
ethernet NICs using a user defined prefix (e.g. net.ifnames.prefix=net produces
NIC names net0, net1, ...). It is invoked from a udev rule and writes out a
configuration file for udev's net_setup_link built-in
(/etc/systemd/network/71-net-ifnames-prefix-<iface>.link).

%prep
%autosetup -n %{name}-%{version}
%cargo_prep -v vendor

%build
%cargo_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest

%install
install -D -m 0755 target/release/prefixdevname %{buildroot}%{_udevdir}/prefixdevname
install -D -m 0644 rules/71-prefixdevname.rules %{buildroot}%{_udevrulesdir}/71-prefixdevname.rules
install -D -m 0755 dracut/71prefixdevname/module-setup.sh %{buildroot}%{_prefix}/lib/dracut/modules.d/71%{name}/module-setup.sh
install -D -m 0755 dracut/71prefixdevname-tools/module-setup.sh %{buildroot}%{_prefix}/lib/dracut/modules.d/71%{name}-tools/module-setup.sh

%files
%license LICENSE
%license LICENSE.dependencies
%license cargo-vendor.txt
%doc README.md
%{_udevdir}/prefixdevname
%{_udevrulesdir}/71-prefixdevname.rules
%dir %{_prefix}/lib/dracut/modules.d/71%{name}
%{_prefix}/lib/dracut/modules.d/71%{name}/module-setup.sh
%dir %{_prefix}/lib/dracut/modules.d/71%{name}-tools
%{_prefix}/lib/dracut/modules.d/71%{name}-tools/module-setup.sh

%changelog
* Fri Jan 16 2026 kylerankin <kylerankin@users.noreply.github.com> - 0.2.0-1
- Import recipe from msekletar/prefixdevname v0.2.0 for #505
