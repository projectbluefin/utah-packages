%global appstream_version 0.16.3
%global debugedit_version 5.0
%global glib2_version 2.66
%global ostree_version 2017.14
%global flatpak_version 0.99.1

%global __requires_exclude ^/usr/bin/python2$

Name:           flatpak-builder
Version:        1.4.12
Release:        %autorelease
Summary:        Tool to build flatpaks from source

# src/builder-utils.c has portions derived from GPLv2+ code,
# the rest is LGPLv2+
License:        LGPL-2.1-or-later AND GPL-2.0-or-later
URL:            https://flatpak.org/
Source0:        https://github.com/flatpak/flatpak-builder/releases/download/%{version}/%{name}-%{version}.tar.xz

# ostree not on i686 for RHEL 10
# https://github.com/containers/composefs/pull/229#issuecomment-1838735764
%if 0%{?rhel} >= 10
ExcludeArch:    %{ix86}
%endif

BuildRequires:  appstream-compose >= %{appstream_version}
BuildRequires:  gettext
BuildRequires:  debugedit >= %{debugedit_version}
BuildRequires:  docbook-dtds
BuildRequires:  docbook-style-xsl
BuildRequires:  flatpak >= %{flatpak_version}
BuildRequires:  libcap-devel
BuildRequires:  meson
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(json-glib-1.0)
BuildRequires:  pkgconfig(libcurl)
BuildRequires:  pkgconfig(libelf)
BuildRequires:  pkgconfig(libxml-2.0)
BuildRequires:  pkgconfig(ostree-1) >= %{ostree_version}
BuildRequires:  pkgconfig(yaml-0.1)
BuildRequires:  /usr/bin/xmlto
BuildRequires:  /usr/bin/xsltproc

Requires:       appstream-compose >= %{appstream_version}
Requires:       debugedit >= %{debugedit_version}
Requires:       flatpak%{?_isa} >= %{flatpak_version}
Requires:       glib2%{?_isa} >= %{glib2_version}
Requires:       ostree-libs%{?_isa} >= %{ostree_version}
Requires:       /usr/bin/rofiles-fuse

# Recommend various things that may or may not be needed depending on the code being built
Recommends:     /usr/bin/bsdunzip
Recommends:     /usr/bin/bzip2
Recommends:     /usr/bin/eu-strip
Recommends:     /usr/bin/git
Recommends:     /usr/bin/git-lfs
Recommends:     /usr/bin/patch
Recommends:     /usr/bin/strip
Recommends:     /usr/bin/tar
Recommends:     /usr/bin/zstd
Recommends:     ccache

# Uncommon enough that we don't want to pull them in by default
#Recommends:     /usr/bin/brz
#Recommends:     /usr/bin/lzip
#Recommends:     /usr/bin/svn

%description
Flatpak-builder is a tool for building flatpaks from sources.

See https://flatpak.org/ for more information.

%package tests
Summary:        Tests for %{name}
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description tests
This package contains installed tests for %{name}.


%prep
%autosetup -p1


%build
%meson -Ddocs=enabled -Dfuse=3 -Dinstalled_tests=true -Dyaml=enabled
%meson_build


%install
%meson_install
install -pm 644 NEWS README.md %{buildroot}/%{_pkgdocdir}


%check
%meson_test


%files
%license COPYING
%doc %{_pkgdocdir}
%{_bindir}/flatpak-builder
%{_mandir}/man1/flatpak-builder.1*
%{_mandir}/man5/flatpak-manifest.5*

%files tests
%{_datadir}/installed-tests
%{_libexecdir}/installed-tests


%changelog
%autochangelog
