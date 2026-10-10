Name:           htop
Version:        3.5.3
Release:        %autorelease
Summary:        Interactive process viewer
License:        GPL-2.0-or-later
URL:            https://htop.dev/
Source0:        https://github.com/htop-dev/htop/releases/download/%{version}/%{name}-%{version}.tar.xz

BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  hwloc-devel
BuildRequires:  libcap-devel
BuildRequires:  libnl3-devel
BuildRequires:  libtool
BuildRequires:  lm_sensors-devel
BuildRequires:  make
BuildRequires:  ncurses-devel

%description
htop is an interactive text-mode process viewer for Linux, similar to
top(1).

%prep
%autosetup -p1

%build
autoreconf -vfi

%configure \
    --enable-capabilities \
    --enable-delayacct \
    --enable-hwloc \
    --enable-sensors \
    --enable-unicode

%make_build

%install
%make_install

desktop-file-validate %{buildroot}/%{_datadir}/applications/%{name}.desktop

%check

%files
%doc AUTHORS ChangeLog README.md
%license COPYING
%{_bindir}/htop
%{_datadir}/pixmaps/htop.png
%{_datadir}/icons/hicolor/scalable/apps/%{name}.svg
%{_datadir}/applications/%{name}.desktop
%{_mandir}/man1/htop.1*

%changelog
%autochangelog
