%undefine __cmake_in_source_build

# Utah needs the EDS backends (evolution-ews-core), not the Evolution mail UI.
# Upstream's WITH_EVOLUTION option keeps those backends independently buildable.
%bcond evolution 0

%global json_glib_version 1.0.4
%global libmspack_version 0.4
%global libsoup_version 3.1.1

Name: evolution-ews
Version: 3.61.3
Release: %autorelease
Summary: Evolution extension for Exchange Web Services
License: LGPL-2.1-or-later
URL: https://gitlab.gnome.org/GNOME/evolution/-/wikis/home
Source: http://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

%global eds_evo_version %{version}

Requires: evolution >= %{eds_evo_version}
Requires: evolution-data-server >= %{eds_evo_version}
Requires: %{name}-core = %{version}-%{release}
Requires: %{name}-langpacks = %{version}-%{release}

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: intltool
BuildRequires: pkgconfig(camel-1.2) >= %{eds_evo_version}
BuildRequires: pkgconfig(evolution-data-server-1.2) >= %{eds_evo_version}
%if %{with evolution}
BuildRequires: pkgconfig(evolution-mail-3.0) >= %{eds_evo_version}
BuildRequires: pkgconfig(evolution-shell-3.0) >= %{eds_evo_version}
BuildRequires: pkgconfig(libemail-engine) >= %{eds_evo_version}
%endif
BuildRequires: pkgconfig(glib-2.0)
BuildRequires: pkgconfig(gtk+-3.0)
BuildRequires: pkgconfig(json-glib-1.0) >= %{json_glib_version}
BuildRequires: pkgconfig(libebackend-1.2) >= %{eds_evo_version}
BuildRequires: pkgconfig(libebook-1.2) >= %{eds_evo_version}
BuildRequires: pkgconfig(libecal-2.0) >= %{eds_evo_version}
BuildRequires: pkgconfig(libedata-book-1.2) >= %{eds_evo_version}
BuildRequires: pkgconfig(libedata-cal-2.0) >= %{eds_evo_version}
BuildRequires: pkgconfig(libical)
BuildRequires: pkgconfig(libmspack) >= %{libmspack_version}
BuildRequires: pkgconfig(libsoup-3.0) >= %{libsoup_version}

%description
This package allows Evolution to interact with Microsoft Exchange servers,
versions 2007 and later, through its Exchange Web Services (EWS) interface.

%package core
Summary: Core files for %{name}
Requires: %{name}-langpacks = %{version}-%{release}
Requires: evolution-data-server >= %{eds_evo_version}
Requires: libmspack >= %{libmspack_version}

%description core
This package contains core files for %{name}, which do not depend on the evolution package.
These files add the functionality for the address books, calendars, task lists and memo lists
without bringing in the evolution package.

%package langpacks
Summary: Translations for %{name}
BuildArch: noarch
Requires: %{name}-core = %{version}-%{release}

%description langpacks
This package contains translations for %{name}.

%prep
%autosetup -p1 -S gendiff

%build
export CFLAGS="$RPM_OPT_FLAGS -Wno-deprecated-declarations"
%cmake -DINCLUDE_INSTALL_DIR:PATH=%{_includedir} \
	-DWITH_EVOLUTION:BOOL=%{?with_evolution:ON}%{!?with_evolution:OFF} \
	-DLIB_INSTALL_DIR:PATH=%{_libdir} \
	-DSYSCONF_INSTALL_DIR:PATH=%{_sysconfdir} \
	-DSHARE_INSTALL_PREFIX:PATH=%{_datadir} \
	%if "%{?_lib}" == "lib64"
		-DLIB_SUFFIX=64 \
	%endif
	%{nil}
%cmake_build

%install
%cmake_install

%find_lang %{name}

%ldconfig_scriptlets

%if %{with evolution}
%files
%license COPYING
%doc NEWS README
%{_libdir}/evolution/modules/module-ews-configuration.so
%{_libdir}/evolution/modules/module-microsoft365-configuration.so
%{_datadir}/evolution/errors/module-ews-configuration.error
%{_datadir}/metainfo/org.gnome.Evolution-ews.metainfo.xml
%endif

%files core
%license COPYING
%doc NEWS README
%{_libdir}/evolution-data-server/camel-providers/libcamelews.so
%{_libdir}/evolution-data-server/camel-providers/libcamelews.urls
%{_libdir}/evolution-data-server/camel-providers/libcamelmicrosoft365.so
%{_libdir}/evolution-data-server/camel-providers/libcamelmicrosoft365.urls
%{_libdir}/evolution-data-server/addressbook-backends/libebookbackendews.so
%{_libdir}/evolution-data-server/addressbook-backends/libebookbackendmicrosoft365.so
%{_libdir}/evolution-data-server/calendar-backends/libecalbackendews.so
%{_libdir}/evolution-data-server/calendar-backends/libecalbackendmicrosoft365.so
%{_libdir}/evolution-data-server/registry-modules/module-ews-backend.so
%{_libdir}/evolution-data-server/registry-modules/module-microsoft365-backend.so
%{_libdir}/evolution-ews/libcamelews-priv.so
%{_libdir}/evolution-ews/libcamelmicrosoft365-priv.so
%{_libdir}/evolution-ews/libevolution-ews.so
%{_libdir}/evolution-ews/libevolution-ews-common.so
%{_libdir}/evolution-ews/libevolution-microsoft365.so
%{_datadir}/evolution-data-server/ews/windowsZones.xml

%files langpacks -f %{name}.lang

%changelog
%autochangelog
