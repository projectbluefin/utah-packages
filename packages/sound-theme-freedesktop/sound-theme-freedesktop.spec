Name: sound-theme-freedesktop
Version: 0.8
Release: %autorelease
Summary: freedesktop.org sound theme
Source0: http://people.freedesktop.org/~mccann/dist/sound-theme-freedesktop-%{version}.tar.bz2
# For details on the licenses used, see CREDITS
License: GPL-2.0-only AND GPL-2.0-or-later AND LGPL-2.0-or-later AND CC-BY-SA-3.0 AND CC-BY-3.0 AND CC-BY-4.0
Url: http://www.freedesktop.org/wiki/Specifications/sound-theme-spec
BuildArch: noarch
BuildRequires: make
BuildRequires:  gcc
BuildRequires: gettext
BuildRequires: intltool >= 0.40
Requires(post): coreutils
Requires(postun): coreutils

%description
The default freedesktop.org sound theme following the XDG theming
specification.  (http://0pointer.de/public/sound-theme-spec.html).

%prep
%setup -q

%build
%configure

%install
%make_install

%post
touch --no-create %{_datadir}/sounds/freedesktop %{_datadir}/sounds

%postun
touch --no-create %{_datadir}/sounds/freedesktop %{_datadir}/sounds

%files
%doc README
%dir %{_datadir}/sounds/freedesktop
%dir %{_datadir}/sounds/freedesktop/stereo
%{_datadir}/sounds/freedesktop/index.theme
%{_datadir}/sounds/freedesktop/stereo/*.oga

%changelog
%autochangelog
