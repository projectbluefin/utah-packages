Name:       setxkbmap
Version:    1.3.5
Release:    %autorelease
Summary:    X11 keymap client

License:    HPND
URL:        https://www.x.org
Source0:    https://www.x.org/pub/individual/app/%{name}-%{version}.tar.xz
Source1:    https://www.x.org/pub/individual/app/%{name}-%{version}.tar.xz.sig
Source2:    3AB285232C46AE43D8E192F4DAB0F78EA6E7E2D2.asc

BuildRequires:  gcc
BuildRequires:  gpgverify
BuildRequires:  make
BuildRequires:  pkgconfig(x11)
BuildRequires:  pkgconfig(xkbfile)
BuildRequires:  pkgconfig(xorg-macros) >= 1.8
BuildRequires:  pkgconfig(xrandr)

Obsoletes:  xorg-x11-xkb-utils < 7.8
Provides:   xorg-x11-xkb-utils >= 7.8

%description
setxkbmap is an X11 client to change the keymaps in the X server for a
specified keyboard to use the layout determined by the options listed
on the command line.

%prep
%{gpgverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup

%build
%configure --disable-silent-rules
%make_build

%install
%make_install

%check
make check

%files
%license COPYING
%{_bindir}/setxkbmap
%{_mandir}/man1/setxkbmap.1*

%changelog
%autochangelog
