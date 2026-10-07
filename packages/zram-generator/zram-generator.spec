%bcond vendor %{defined rhel}

Name:           zram-generator
Version:        1.2.1
Release:        %autorelease -b 5
Summary:        Systemd unit generator for zram devices

SourceLicense:  MIT
# Statically linked Rust dependencies:
# MIT
# MIT OR Apache-2.0
License:        MIT AND (MIT OR Apache-2.0)
# LICENSE.dependencies contains a full license breakdown

URL:            https://github.com/systemd/zram-generator
Source0:        %{url}/archive/v%{version}/zram-generator-%{version}.tar.gz
Source1:        zram-generator.conf
# generated using vendor.sh
Source2:        zram-generator-%{version}-vendor.tar.xz
Source3:        vendor.sh

# bump nix dev-dependency to v0.30
Patch:          https://github.com/systemd/zram-generator/pull/238.patch

%if %{with vendor}
BuildRequires:  rust-toolset
%else
BuildRequires:  cargo-rpm-macros
%endif

BuildRequires:  /usr/bin/make
BuildRequires:  /usr/bin/ronn
BuildRequires:  pkgconfig(systemd)
BuildRequires:  systemd-rpm-macros

Recommends:     %{_sbindir}/zramctl

%description
This is a systemd unit generator that enables swap on zram.
(With zram, there is no physical swap device. Part of the available RAM
is used to store compressed pages, essentially trading CPU cycles for memory.)

To activate, install the zram-generator-defaults subpackage.

%files
%license LICENSE
%license LICENSE.dependencies
%if %{with vendor}
%license cargo-vendor.txt
%endif

%doc README.md
%doc zram-generator.conf.example

%{_systemdgeneratordir}/zram-generator
%{_unitdir}/systemd-zram-setup@.service
%{_mandir}/man8/zram-generator.8*
%{_mandir}/man5/zram-generator.conf.5*

%package        defaults
Summary:        Default configuration for zram-generator

Requires:       zram-generator = %{version}-%{release}
Obsoletes:      zram < 0.4-2
BuildArch:      noarch

%description    defaults
%{summary}.

%files          defaults
%{_prefix}/lib/systemd/zram-generator.conf

%prep
%if %{with vendor}
%autosetup -n zram-generator-%{version} -a2 -p1
%cargo_prep -v vendor
%else
%autosetup -n zram-generator-%{version} -p1
%cargo_prep
%endif
cp -a %{S:1} .

%if %{without vendor}
%generate_buildrequires
%cargo_generate_buildrequires -t
%endif

%build
export SYSTEMD_UTIL_DIR=%{_systemd_util_dir}
export LC_ALL=C.UTF-8

%cargo_build
%{cargo_license_summary}
%{cargo_license} > LICENSE.dependencies
%if %{with vendor}
%cargo_vendor_manifest
%endif

%make_build SYSTEMD_SYSTEM_UNIT_DIR=%{_unitdir} SYSTEMD_SYSTEM_GENERATOR_DIR=%{_systemdgeneratordir} systemd-service man

%install
export SYSTEMD_UTIL_DIR=%{_systemd_util_dir}

%make_install SYSTEMD_SYSTEM_UNIT_DIR=%{_unitdir} SYSTEMD_SYSTEM_GENERATOR_DIR=%{_systemdgeneratordir} NOBUILD=1

install -Dpm0644 -t %{buildroot}%{_prefix}/lib/systemd %{SOURCE1}

%check
export SYSTEMD_UTIL_DIR=%{_systemd_util_dir}
%cargo_test

%{buildroot}%{_systemdgeneratordir}/zram-generator --help
%{buildroot}%{_systemdgeneratordir}/zram-generator --help | grep -q %{_systemd_util_dir}/systemd-makefs

%changelog
%autochangelog
