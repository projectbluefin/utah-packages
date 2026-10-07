%global nm_version            1:1.8.0
%global mbp_version           0.20090602
%global old_libnma_version    1.10.4

Name:           libnma
Summary:        NetworkManager GUI library
Version:        1.10.6
Release:        %autorelease
# The entire source code is GPLv2+ except some files in shared/ which are LGPLv2+
License:        GPL-2.0-or-later AND LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/libnma/
Source0:        https://download.gnome.org/sources/libnma/1.10/%{name}-%{version}.tar.xz

Patch0:         0001-nm-applet-no-notifications.patch
# Fix some build warnings
# https://gitlab.gnome.org/GNOME/libnma/-/commit/9b6165f00ddbcde0d327399945030c2663998f64
# https://gitlab.gnome.org/GNOME/libnma/-/commit/68cc85767b2aad7356f1a733b0f98ca53c74d95c
Patch1:         %{url}/-/commit/9b6165f00ddbcde0d327399945030c2663998f64.patch#/Fix_header_includes.patch
Patch2:         %{url}/-/commit/68cc85767b2aad7356f1a733b0f98ca53c74d95c.patch#/Fix_more_header_includes.patch

BuildSystem:    meson
BuildOption(conf): -Dgcr=true
BuildOption(conf): -Dvapi=false
BuildOption(conf): -Dlibnma_gtk4=true

BuildRequires:  gcc
BuildRequires:  NetworkManager-libnm-devel >= %{nm_version}
BuildRequires:  ModemManager-glib-devel >= 1.0
BuildRequires:  glib2-devel >= 2.38
BuildRequires:  gtk3-devel >= 3.12
BuildRequires:  gtk4-devel >= 4.0
BuildRequires:  gobject-introspection-devel >= 0.10.3
BuildRequires:  gettext-devel
BuildRequires:  pkgconfig
BuildRequires:  gtk-doc
BuildRequires:  iso-codes-devel
BuildRequires:  gcr-devel
BuildRequires:  mobile-broadband-provider-info-devel >= %{mbp_version}

Requires:       %{name}-common = %{version}-%{release}
Requires:       mobile-broadband-provider-info >= %{mbp_version}

Conflicts:      libnma < %{old_libnma_version}
Conflicts:      nm-connection-editor < 1.30.0

%description
This package contains the library used for integrating GUI tools with
NetworkManager.

%package common
Summary:        Common files for NetworkManager GUI library
Conflicts:      libnma < %{version}-%{release}
BuildArch:      noarch

%description common
This package contains common files for the NetworkManager GUI library.

%package devel
Summary:        Header files for NetworkManager GUI library
Requires:       NetworkManager-libnm-devel >= %{nm_version}
Obsoletes:      NetworkManager-gtk-devel < 1:0.9.7
Requires:       libnma%{?_isa} = %{version}-%{release}
Requires:       gtk3-devel%{?_isa}
Conflicts:      libnma < %{old_libnma_version}

%description devel
This package contains header and pkg-config files to be used for integrating
GUI tools with NetworkManager.

%package gtk4
Summary:        Experimental GTK 4 version of NetworkManager GUI library
Requires:       mobile-broadband-provider-info >= %{mbp_version}
Requires:       %{name}-common = %{version}-%{release}
Conflicts:      libnma < %{old_libnma_version}

%description gtk4
This package contains the experimental GTK4 version of library used for
integrating GUI tools with NetworkManager.

%package gtk4-devel
Summary:        Header files for experimental GTK4 version of NetworkManager GUI library
Requires:       NetworkManager-libnm-devel >= %{nm_version}
Requires:       libnma-gtk4%{?_isa} = %{version}-%{release}
Requires:       gtk4-devel%{?_isa}
Conflicts:      libnma < %{old_libnma_version}

%description gtk4-devel
This package contains the experimental GTK4 version of header and pkg-config
files to be used for integrating GUI tools with NetworkManager.

%prep
%autosetup -p1

%install -a
%find_lang %{name}

%check
%meson_test

%files
%{_libdir}/libnma.so.*
%{_libdir}/girepository-1.0/NMA-1.0.typelib

%files common -f %{name}.lang
%exclude %{_datadir}/glib-2.0/schemas/org.gnome.nm-applet.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.nm-applet.eap.gschema.xml
%doc NEWS CONTRIBUTING
%license COPYING

%files devel
%{_includedir}/libnma
%{_libdir}/pkgconfig/libnma.pc
%{_libdir}/libnma.so
%{_datadir}/gir-1.0/NMA-1.0.gir
%{_datadir}/gtk-doc

%files gtk4
%{_libdir}/libnma-gtk4.so.*
%{_libdir}/girepository-1.0/NMA4-1.0.typelib

%files gtk4-devel
%{_includedir}/libnma
%{_libdir}/pkgconfig/libnma-gtk4.pc
%{_libdir}/libnma-gtk4.so
%{_datadir}/gir-1.0/NMA4-1.0.gir

%changelog
%autochangelog