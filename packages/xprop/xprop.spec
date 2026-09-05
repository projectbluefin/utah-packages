Summary:    X property display utility
Name:       xprop
Version:    1.2.8
Release:    %autorelease
License:    MIT
URL:        https://www.x.org
Source0:    https://www.x.org/pub/individual/app/%{name}-%{version}.tar.xz

BuildRequires:  gcc make
BuildRequires:  gettext-devel
BuildRequires:  libtool

BuildRequires:  pkgconfig(x11)

Obsoletes: xorg-x11-utils < 7.5-39

%description
The xprop utility is for displaying window and font properties in an X server.

%prep
%setup -q

%build
%configure
%make_build

%install
%make_install

%files
%doc README.md
%license COPYING
%{_bindir}/xprop
%{_mandir}/man1/xprop.1*

%changelog
%autochangelog
