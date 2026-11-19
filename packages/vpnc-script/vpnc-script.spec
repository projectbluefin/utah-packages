%global git_date 20250727
%global git_commit_hash ce9e961b

Name:		vpnc-script
Version:	%{git_date}
Release:	%autorelease -e git%{git_commit_hash}

Summary:	Routing setup script for vpnc and openconnect
BuildArch:	noarch
Requires:	iproute
Requires:	which

# Automatically converted from old format: GPLv2+ - review is highly recommended.
License:	GPL-2.0-or-later
URL:		https://gitlab.com/openconnect/vpnc-scripts/
Source0:	vpnc-script

%description
This script sets up routing for VPN connectivity, when invoked by vpnc
or openconnect.


%prep
cp -p %SOURCE0 .

%build

%install
mkdir -p -m 755 %{buildroot}%{_sysconfdir}/vpnc
install -m 0755 vpnc-script \
    %{buildroot}%{_sysconfdir}/vpnc/vpnc-script

%files
%dir %{_sysconfdir}/vpnc
%{_sysconfdir}/vpnc/vpnc-script

%changelog
%autochangelog
