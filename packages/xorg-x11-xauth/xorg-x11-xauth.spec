%global pkgname xauth

Summary: X.Org X11 X authority utilities
Name: xorg-x11-%{pkgname}
Version: 1.1.5
Release: %autorelease
# NOTE: Remove Epoch line if package gets renamed
Epoch: 1
License: MIT-open-group
URL: https://www.x.org

Source0: https://www.x.org/pub/individual/app/%{pkgname}-%{version}.tar.xz

BuildRequires: automake
BuildRequires: gcc
BuildRequires: libX11-devel
BuildRequires: libXau-devel
BuildRequires: libXext-devel
BuildRequires: libXmu-devel
BuildRequires: make
BuildRequires: pkgconfig

Provides: xauth

%description
xauth is used to edit and display the authorization information
used in connecting to an X server.

%prep
%autosetup -n %{pkgname}-%{version}

%build
%configure
%make_build

%install
%make_install

%check
%make_build check

%files
%doc COPYING README.md
%{_bindir}/xauth
%{_mandir}/man1/xauth.1*

%changelog
%autochangelog
