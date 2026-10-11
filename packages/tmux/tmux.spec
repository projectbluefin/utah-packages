Name:           tmux
Version:        3.7c
Release:        %autorelease
Summary:        A terminal multiplexer

License:        ISC AND BSD-2-Clause AND BSD-3-Clause AND SSH-short AND LicenseRef-Fedora-Public-Domain
URL:            https://tmux.github.io/
Source0:        https://github.com/tmux/%{name}/releases/download/%{version}/%{name}-%{version}.tar.gz
Source2:        tmux@.service
Source3:        README.polkit

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  byacc
BuildRequires:  gcc
BuildRequires:  libutempter-devel
BuildRequires:  make
BuildRequires:  pkgconfig(libevent_core) >= 2
BuildRequires:  pkgconfig(ncurses)
BuildRequires:  pkgconfig(ncursesw)
BuildRequires:  pkgconfig(tinfo)
BuildRequires:  systemd-devel
BuildRequires:  systemd-rpm-macros

Requires(post):   coreutils
Requires(post):   grep
Requires(postun): sed

%description
tmux is a "terminal multiplexer."  It enables a number of terminals (or
windows) to be accessed and controlled from a single terminal.  tmux is
intended to be a simple, modern, BSD-licensed alternative to programs such
as GNU Screen.


%prep
%autosetup
cp %{SOURCE3} .
./autogen.sh


%build
%configure --enable-sixel --enable-systemd --enable-utempter
%make_build


%install
%make_install
# Install the systemd file
install -Dpm 644 %{SOURCE2} %{buildroot}%{_unitdir}/tmux@.service


%check
%{buildroot}%{_bindir}/tmux -V


%post
# Add login shell entries to /etc/shells only when installing the package
# for the first time:
if [ "$1" = 1 ]; then
  if [ ! -f %{_sysconfdir}/shells ]; then
    echo "%{_bindir}/tmux" > %{_sysconfdir}/shells
    echo "/bin/tmux" >> %{_sysconfdir}/shells
  else
    grep -q "^%{_bindir}/tmux$" %{_sysconfdir}/shells || echo "%{_bindir}/tmux" >> %{_sysconfdir}/shells
    grep -q "^/bin/tmux$" %{_sysconfdir}/shells || echo "/bin/tmux" >> %{_sysconfdir}/shells
  fi
fi

%postun
# Remove the login shell lines from /etc/shells only when uninstalling:
if [ "$1" = 0 ] && [ -f %{_sysconfdir}/shells ]; then
  sed -i -e '\!^%{_bindir}/tmux$!d' -e '\!^/bin/tmux$!d' %{_sysconfdir}/shells
fi

%files
%license COPYING
%doc CHANGES README* example_tmux.conf
%{_bindir}/tmux
%{_mandir}/man1/tmux.1.*
%{_unitdir}/tmux@.service

%changelog
%autochangelog
