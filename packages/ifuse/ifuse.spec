Name:          ifuse
Version:       1.2.1
Release:       %autorelease
Summary:       Mount Apple iPhone and iPod touch devices
License:       LGPL-2.1-or-later
URL:           https://www.libimobiledevice.org/
Source:        https://github.com/libimobiledevice/%{name}/releases/download/%{version}/%{name}-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  make

BuildRequires:  fuse3-devel
BuildRequires:  libimobiledevice-devel
BuildRequires:  libimobiledevice-glue-devel
BuildRequires:  libplist-devel

Requires:       fuse3
# https://bugzilla.redhat.com/show_bug.cgi?id=2484294
Requires:       libimobiledevice >= 1.4.0

%description
A fuse filesystem for mounting iPhone and iPod touch devices

%prep
%setup -q

%build
%ifarch %{ix86}
export CFLAGS="%{optflags} -D_FILE_OFFSET_BITS=64"
%endif
%configure --disable-static
%make_build

%install
%make_install

%files
%license COPYING
%doc AUTHORS README.md
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*

%changelog
%autochangelog
