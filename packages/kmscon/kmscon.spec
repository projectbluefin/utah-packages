Name:           kmscon
Version:        10.1.1
Release:        %autorelease
Summary:        Linux KMS/DRM based virtual Console Emulator
# MIT for the source code, and OFL-1.1 for the unifont font.
License:        MIT and OFL-1.1
URL:            https://github.com/kmscon/kmscon/
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
BuildRequires:  check-devel
BuildRequires:  docbook-style-xsl
BuildRequires:  libtsm-devel >= 4.8.0
BuildRequires:  meson
BuildRequires:  ncurses
BuildRequires:  gcc
BuildRequires:  pkg-config
BuildRequires:  xsltproc
BuildRequires:  xz
BuildRequires:  systemd-rpm-macros
BuildRequires:  pkgconfig(egl)
BuildRequires:  pkgconfig(fontconfig) >= 2.16.0
BuildRequires:  pkgconfig(freetype2)
BuildRequires:  google-noto-sans-mono-fonts
BuildRequires:  pkgconfig(gbm)
BuildRequires:  pkgconfig(glesv2)
BuildRequires:  pkgconfig(libdrm)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(libudev) >= 172
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(pangoft2)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(xkbcommon) >= 0.5.0
BuildRequires:  pkgconfig(zlib)
Recommends:     (kmscon-freetype if freetype)

%description
Kmscon is a simple terminal emulator based on linux kernel mode setting (KMS).
It is an attempt to replace the in-kernel VT implementation with a userspace
console.

%package pango
Summary: This adds pango support to kmscon
Requires: %{name}%{?_isa} = %{version}-%{release}

%description pango
This package provide the pango plugin to kmscon
mod-pango.so

%package freetype
Summary: This adds freetype support to kmscon
Requires: %{name}%{?_isa} = %{version}-%{release}

%description freetype
This package provide the freetype plugin to kmscon
mod-freetype.so

%package gl
Summary: This adds opengl support to kmscon
Requires: %{name}%{?_isa} = %{version}-%{release}

%description gl
This package provides 2 plugins for kmscon:
mod-drm3d.so
mod-gltex.so

%prep
%autosetup -p1

%conf
%meson -Dvideo_fbdev=disabled -Dlibseat=disabled

%build
%meson_build

%install
%meson_install

%check
%meson_test

%post
%systemd_post kmscon.service
%systemd_post kmsconvt@.service

%preun
%systemd_preun kmscon.service
%systemd_preun kmsconvt@.service

%postun
%systemd_postun kmscon.service
%systemd_postun kmsconvt@.service

%files
%license COPYING
%{_bindir}/%{name}
%{_bindir}/kmscon-launch-gui
%{_libdir}/kmscon/mod-unifont.so
%{_libdir}/kmscon/mod-psf.so
%{_mandir}/man1/kmscon.1*
%{_mandir}/man5/kmscon.conf.5*
%{_unitdir}/kmscon.service
%{_unitdir}/kmsconvt@.service
%config /etc/kmscon/kmscon.conf.example
%{_datadir}/terminfo/k/kmscon

%files pango
%{_libdir}/kmscon/mod-pango.so

%files freetype
%{_libdir}/kmscon/mod-freetype.so

%files gl
%{_libdir}/kmscon/mod-drm3d.so
%{_libdir}/kmscon/mod-gltex.so

%changelog
%autochangelog

