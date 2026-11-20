Summary: Utilities for manipulating .desktop files
Name: desktop-file-utils
Version: 0.28
Release: %autorelease
URL: https://www.freedesktop.org/software/desktop-file-utils
Source0: https://www.freedesktop.org/software/desktop-file-utils/releases/%{name}-%{version}.tar.xz
Source1: desktop-entry-mode-init.el
# https://gitlab.freedesktop.org/xdg/desktop-file-utils/-/merge_requests/24
Patch0: 0001-validate-Add-Phosh-to-list-of-valid-OnlyShowIn-envir.patch
License: GPL-2.0-or-later

BuildRequires: gcc
BuildRequires: glib2-devel
BuildRequires: emacs
BuildRequires: meson
Requires: emacs-filesystem

%description
.desktop files are used to describe an application for inclusion in
GNOME or KDE menus.  This package contains desktop-file-validate which
checks whether a .desktop file complies with the specification at
http://www.freedesktop.org/standards/, and desktop-file-install
which installs a desktop file to the standard directory, optionally
fixing it up in the process.


%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install

mkdir -p $RPM_BUILD_ROOT%{_emacs_sitelispdir}/desktop-file-utils
mv $RPM_BUILD_ROOT%{_emacs_sitelispdir}/*.el* $RPM_BUILD_ROOT%{_emacs_sitelispdir}/desktop-file-utils
install -Dpm 644 %{SOURCE1} $RPM_BUILD_ROOT%{_emacs_sitestartdir}/desktop-entry-mode-init.el
touch $RPM_BUILD_ROOT%{_emacs_sitestartdir}/desktop-entry-mode-init.elc

%transfiletriggerin -- %{_datadir}/applications
update-desktop-database &> /dev/null || :

%transfiletriggerpostun -- %{_datadir}/applications
update-desktop-database &> /dev/null || :

%files
%doc AUTHORS README NEWS
%license COPYING
%{_bindir}/*
%{_mandir}/man1/desktop-file-install.1*
%{_mandir}/man1/desktop-file-validate.1*
%{_mandir}/man1/update-desktop-database.1*
%{_mandir}/man1/desktop-file-edit.1*
%{_emacs_sitestartdir}/desktop-entry-mode-init.el
%ghost %{_emacs_sitestartdir}/desktop-entry-mode-init.elc
%{_emacs_sitelispdir}/desktop-file-utils/

%changelog
%autochangelog
