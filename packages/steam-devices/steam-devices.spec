%global commit 22ec85e5ff5ea2e15c56d71a41bcbef46356cd60
%if 0%{?rhel} && 0%{?rhel} < 10
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%else
%global shortcommit %{sub %{commit} 1 7}
%endif
%global commitdate 20260625


Name:           steam-devices
Version:        1.0.0.101^git%{commitdate}.%{shortcommit}
Release:        %autorelease
License:        MIT
Summary:        Device support for Steam-related hardware
Url:            https://github.com/ValveSoftware/steam-devices/
Source0:        %{url}/archive/%{commit}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  git-core
BuildRequires:  systemd-rpm-macros

# Temporary workaround to obsolete and replace the equivalent i686 package in RPMFusion
# so we don't break current installs. Can be removed after a while.
Obsoletes:      steam-devices < %{version}-%{release}
Provides:       steam-devices = %{version}-%{release}

%description
This package contains the necessary permissions for gaming devices (such as
gamepads, joysticks and VR headsets) that can be used by Wine, Lutris, Heroic,
and other non-Steam games and game launchers.

%prep
%autosetup -n %{name}-%{commit} -S git_am

%install
install -Dpm0644 60-steam-input.rules %{buildroot}%{_udevrulesdir}/60-steam-input.rules
install -Dpm0644 60-steam-vr.rules %{buildroot}%{_udevrulesdir}/60-steam-vr.rules

%files
%license LICENSE
%{_udevrulesdir}/60-steam-input.rules
%{_udevrulesdir}/60-steam-vr.rules

%changelog
%autochangelog
