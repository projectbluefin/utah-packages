Name:		xdg-user-dirs
Version:	0.20
Release:	%autorelease
Summary:	Handles user special directories

License:	GPL-2.0-or-later AND MIT
URL:		https://freedesktop.org/wiki/Software/xdg-user-dirs
Source0:	https://user-dirs.freedesktop.org/releases/%{name}-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:	gcc
BuildRequires:	gettext-devel
BuildRequires:	git-core
BuildRequires:	docbook-style-xsl
BuildRequires:	libxslt
BuildRequires:	systemd-rpm-macros

Requires:	%{_sysconfdir}/xdg/autostart

%description
Contains xdg-user-dirs-update that updates folders in a users
homedirectory based on the defaults configured by the administrator.

%prep
%autosetup -p1

%build
%meson
%meson_build

%install
%meson_install
%find_lang %name

%post
%systemd_user_post xdg-user-dirs.service

%preun
%systemd_user_preun xdg-user-dirs.service

%postun
%systemd_user_postun_with_reload xdg-user-dirs.service


%files -f %{name}.lang
%license COPYING
%doc NEWS AUTHORS README.md
%{_bindir}/*
%config(noreplace) %{_sysconfdir}/xdg/user-dirs.conf
%config(noreplace) %{_sysconfdir}/xdg/user-dirs.defaults
%{_sysconfdir}/xdg/autostart/*
%{_mandir}/man1/*
%{_mandir}/man5/*
%{_userunitdir}/xdg-user-dirs.service


%changelog
%autochangelog
