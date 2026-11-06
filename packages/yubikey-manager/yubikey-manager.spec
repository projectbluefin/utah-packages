%global forgeurl https://github.com/Yubico/yubikey-manager/
%global commit 60ab055dd34b6384bdd4ceb85a38d36bc15ce58a

Name:           yubikey-manager
Version:        5.9.2
Release:        %autorelease
Summary:        Python library and command line tool for configuring a YubiKey
License:        BSD-2-Clause

%forgemeta

URL:            %{forgeurl}
Source0:        %{forgesource}
Source1:        %{name}.rpmlintrc

BuildArch:      noarch
BuildRequires:  swig pcsc-lite-devel ykpers
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  %{py3_dist makefun pytest python-pskc}

Requires:       python3-%{name} = %{?epoch:%{epoch}:}%{version}-%{release}
Requires:       u2f-hidraw-policy

%description
Command line tool for configuring a YubiKey.

%package -n python3-%{name}
Summary:        Python library for configuring a YubiKey
Requires:       ykpers pcsc-lite

%description -n python3-%{name}
Python library for configuring a YubiKey.

%prep
%forgesetup
%autosetup -p1 -n %{archivename}
# Do not upper-bound the version of keyring, since its major version increases
# frequently, usually without significant incompatibilities.
sed -r -i 's/(keyring = ">=[^"]+), <[^"]+"/\1"/' pyproject.toml

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files ykman yubikit

%check
# Tests disabled: upstream provides no tox configuration and tests
# require hardware and external services.

%files -n python3-%{name} -f %{pyproject_files}
%license COPYING
%doc README.adoc NEWS

%files
%{_bindir}/ykman

%changelog
%autochangelog
