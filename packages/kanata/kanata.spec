# kanata, the keyboard remapper Project Bluefin Dakota ships in place of
# input-remapper (projectbluefin/utah#1222).
#
# Written from Dakota's bluefin/kanata.bst (projectbluefin/dakota bf271777):
# the v1.12.0 tag, built with cargo offline from the crates its Cargo.lock pins
# (vendored by tools/generated_sources.py; Hummingbird ships no Rust crate
# RPMs), and the element's files at the element's paths: the binary, its docs
# and minimal example, kanata.service, and 80-kanata.preset.
#
# kanata.service is opt-in, as in Dakota: the preset disables it, and
# ConditionPathExists keeps an enabled unit a silent no-op until
# /etc/kanata/kanata.kbd exists. It runs as a DynamicUser with only the input
# group, so it needs /dev/uinput writable by that group; Dakota gets the udev
# rule and the uinput module load from its ydotool element, which the element
# depends on, so this package requires ydotool too.
Name:           kanata
Version:        1.12.0
Release:        1%{?dist}
Summary:        Software keyboard remapper with multiple layers and advanced actions

# kanata: LGPL-3.0-only
# Statically linked crates (cargo2rpm license-summary; its deprecated
# "LGPL-3.0" lines are workspace tools and macOS-only karabiner-driverkit,
# none of which link into the kanata binary):
# 0BSD OR MIT OR Apache-2.0
# Apache-2.0
# Apache-2.0 OR BSL-1.0
# Apache-2.0 OR MIT
# Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT
# BSL-1.0
# ISC
# LGPL-3.0-only
# MIT
# MIT OR Apache-2.0
# MIT OR Zlib OR Apache-2.0
# MPL-2.0
# Unlicense OR MIT
# Zlib OR Apache-2.0 OR MIT
# LICENSE.dependencies contains a full license breakdown
License:        LGPL-3.0-only AND (0BSD OR MIT OR Apache-2.0) AND Apache-2.0 AND (Apache-2.0 OR BSL-1.0) AND (Apache-2.0 OR MIT) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND BSL-1.0 AND ISC AND MIT AND (MIT OR Zlib OR Apache-2.0) AND MPL-2.0 AND (Unlicense OR MIT) AND (Zlib OR Apache-2.0 OR MIT)
URL:            https://github.com/jtroo/kanata
Source0:        kanata-%{version}-vendored.tar.xz
Source1:        kanata.service
Source2:        80-kanata.preset

ExclusiveArch:  %{rust_arches}

BuildRequires:  cargo-rpm-macros
BuildRequires:  gcc
BuildRequires:  systemd-rpm-macros

Requires:       ydotool

%description
kanata remaps keyboard input on Linux, Windows and macOS: multiple layers,
tap-hold keys, chords, macros and more, configured in a single text file.
Write /etc/kanata/kanata.kbd and enable it with
`sudo systemctl enable --now kanata`.

%prep
%autosetup -n %{name}-%{version}
%cargo_prep -v vendor

%build
%cargo_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%cargo_vendor_manifest

%install
install -Dpm 0755 target/release/kanata %{buildroot}%{_bindir}/kanata
install -Dpm 0644 README.md %{buildroot}%{_docdir}/%{name}/README.md
install -Dpm 0644 docs/config.adoc %{buildroot}%{_docdir}/%{name}/config.adoc
install -Dpm 0644 cfg_samples/minimal.kbd %{buildroot}%{_docdir}/%{name}/examples/minimal.kbd
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_unitdir}/kanata.service
install -Dpm 0644 %{SOURCE2} %{buildroot}%{_presetdir}/80-kanata.preset

%check
# tcp_layer_change_tests build a full Kanata, which opens /dev/uinput for its
# virtual keyboard; the build has no such device.
%cargo_test -- -- --skip kanata::tcp_layer_change_tests

%post
%systemd_post kanata.service

%preun
%systemd_preun kanata.service

%postun
%systemd_postun_with_restart kanata.service

%files
%license LICENSE
%license LICENSE.dependencies
%license cargo-vendor.txt
%{_bindir}/kanata
%{_docdir}/%{name}/
%{_unitdir}/kanata.service
%{_presetdir}/80-kanata.preset

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 1.12.0-1
- Initial recipe: Dakota's kanata (bluefin/kanata.bst), built from source
