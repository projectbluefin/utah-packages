# SPDX-FileCopyrightText: (C) 2025 Siemens AG

# only needed for sso-mib-tool
%bcond libjwt %{undefined rhel}

%define soversion 0

Name:           sso-mib
Version:        0.10.2
Release:        %autorelease
Summary:        Tools and library for Single-Sign-On with CA for Entra via Himmelblau

License:        LGPL-2.1-only AND GPL-2.0-only AND MIT
URL:            https://github.com/siemens/sso-mib
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz
# Utah-local: Fedora's Source1 is a Debian-hosted bash-completion file fetched
# at build time. The hermetic factory build is offline and locks only
# upstream Source0, so the completion file is dropped (no runtime effect).

# Utah-local: 0.10's client-app test runs a private bus through GTestDBus,
# which spawns dbus-daemon; without it %check aborts (gate run 40032133559).
BuildRequires:  dbus-daemon
BuildRequires:  gcc
BuildRequires:  meson >= 0.53
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(json-glib-1.0)
%if %{with libjwt}
BuildRequires:  pkgconfig(libjwt)
%endif
BuildRequires:  pkgconfig(uuid)

%description
Applications can link with this library to get Entra Conditional Access tokens
for authentication and Single-Sign-On from the Himmelblau stack.

%package libs
Summary:        Shared library for SSO with Entra via Himmelblau
License:        LGPL-2.1-only

%description libs
Applications can link with this library to get Entra Conditional Access tokens
for authentication and Single-Sign-On from the Himmelblau stack.

This package contains the shared library.

%package devel
Summary:        Development files for %{name}-libs
License:        LGPL-2.1-only
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       pkgconfig(gio-2.0)
Requires:       pkgconfig(glib-2.0)
Requires:       pkgconfig(uuid)

%description devel
Applications can link with this library to get Entra Conditional Access tokens
for authentication and Single-Sign-On from the Himmelblau stack.

This package contains the development files for the shared library.

%package tool
Summary:        Command line tool for SSO with Entra via Himmelblau
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
License:        GPL-2.0-only

%description tool
This package contains the command line tool to get Entra Conditional Access tokens
for authentication and Single-Sign-On from the Himmelblau stack.

%package gch-smtp-o365
Summary:        Git credential helper for SMTP on O365 via Himmelblau
License:        MIT
Enhances:       git-core

%description -n sso-mib-gch-smtp-o365
This package contains a git send-email credential helper to authenticate SMTP
on O365.

%prep
%autosetup -p1

%conf
%meson %{!?with_libjwt:-Dlibjwt=disabled}

%build
%meson_build

%install
%meson_install

%check
%meson_test

%files libs
%license LICENSES/LGPL-2.1-only.txt
%doc README.md
%{_libdir}/libsso-mib.so.%{soversion}
%{_libdir}/libsso-mib.so.%{version}

%files devel
%license LICENSES/LGPL-2.1-only.txt
%{_includedir}/sso-mib/
%{_libdir}/libsso-mib.so
%{_libdir}/pkgconfig/sso-mib.pc

%files tool
%license LICENSES/GPL-2.0-only.txt
%{_bindir}/sso-mib-tool
%{_mandir}/man1/sso-mib-tool.1*

%files gch-smtp-o365
%license LICENSES/MIT.txt
%{_bindir}/sso-mib-gch-smtp-o365
%{_mandir}/man1/sso-mib-gch-smtp-o365.1*

%changelog
%autochangelog
