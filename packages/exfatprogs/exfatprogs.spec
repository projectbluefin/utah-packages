Name:           exfatprogs
Version:        1.4.4
Release:        %autorelease
Summary:        Userspace utilities for exFAT filesystems
License:        GPL-2.0-only
URL:            https://github.com/%{name}/%{name}

Source0:        %{url}/releases/download/%{version}/%{name}-%{version}.tar.xz

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  gcc
BuildRequires:  libtool
BuildRequires:  make
BuildRequires:  pkgconfig(blkid) >= 2.20

%description
Utilities for formatting and repairing exFAT filesystems.

%prep
%autosetup

%build
autoreconf -vif
%configure \
    --enable-shared=yes \
    --enable-static=no
%make_build

%install
%make_install

%files
%license COPYING
%doc README.md
%{_bindir}/chdosattr
%{_bindir}/lsdosattr
%{_docdir}/%{name}/*
%{_sbindir}/dump.exfat
%{_sbindir}/exfat2img
%{_sbindir}/exfatlabel
%{_sbindir}/fsck.exfat
%{_sbindir}/mkfs.exfat
%{_sbindir}/tune.exfat
%{_mandir}/man1/chdosattr.*
%{_mandir}/man1/lsdosattr.*
%{_mandir}/man8/dump.exfat.*
%{_mandir}/man8/exfat2img.*
%{_mandir}/man8/exfatlabel.*
%{_mandir}/man8/fsck.exfat.*
%{_mandir}/man8/mkfs.exfat.*
%{_mandir}/man8/tune.exfat.*
%{_libexecdir}/exfat-uctbl2bin.sh

%changelog
%autochangelog
