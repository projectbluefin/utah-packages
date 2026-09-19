Name:           iw
Version:        6.17
Release:        %autorelease
Summary:        A nl80211 based wireless configuration tool

# part of sha256.c is public domain
License:        ISC AND LicenseRef-Fedora-Public-Domain
URL:            https://wireless.docs.kernel.org/en/latest/en/users/documentation/iw.html
Source0:        http://www.kernel.org/pub/software/network/iw/iw-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  kernel-headers
BuildRequires:  libnl3-devel
BuildRequires:  make
BuildRequires:  pkgconfig      

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch: %{ix86}

%description
iw is a new nl80211 based CLI configuration utility for wireless devices.
Currently you can only use this utility to configure devices which
use a mac80211 driver as these are the new drivers being written - 
only because most new wireless devices being sold are now SoftMAC.


%prep
%autosetup


%build
%{make_build}


%install
%{make_install} SBINDIR=%{_sbindir}


%files
%license COPYING
%{_sbindir}/%{name}
%{_datadir}/man/man8/iw.*


%changelog
%autochangelog
