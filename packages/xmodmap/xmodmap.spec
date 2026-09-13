Name:       xmodmap
Version:    1.0.12
Release:    %autorelease
Summary:    Edit and display the X11 core keyboard map

License:    MIT AND MIT-open-group
URL:        https://www.x.org
Source0:    https://xorg.freedesktop.org/archive/individual/app/%{name}-%{version}.tar.xz
Source1:    https://xorg.freedesktop.org/archive/individual/app/%{name}-%{version}.tar.xz.sig
Source2:    gpgkey-3AB285232C46AE43D8E192F4DAB0F78EA6E7E2D2.gpg

BuildRequires:  gcc
BuildRequires:  gnupg2
BuildRequires:  meson
BuildRequires:  pkgconfig(x11)

%description
The xmodmap program is used to edit and display the keyboard modifier
map and keymap table that are used by client applications to convert
event keycodes into keysyms.

%prep
%{gpgverify} --keyring=%{SOURCE2} --signature=%{SOURCE1} --data=%{SOURCE0}
%autosetup

%build
%meson
%meson_build

%install
%meson_install

%check
%meson_test

%files
%license COPYING
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*

%changelog
%autochangelog

