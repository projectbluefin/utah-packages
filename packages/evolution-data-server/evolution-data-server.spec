%undefine __cmake_in_source_build

%define ldap_support 1
%define static_ldap 0
%define krb5_support 1
%define largefile_support 1

# disable for i686, because libphonenumber 8.12.57 is not built for it
%ifarch i686
%global phonenum_support 0
%else
# enabled only for Fedora
%global phonenum_support 0%{?fedora}
%endif

# Coverity scan can override this to 0, to skip checking in gtk-doc generated code
%{!?with_docs: %global with_docs 1}

%if 0%{?flatpak}
%global with_docs 0
%endif

%{!?with_webkitgtk: %global with_webkitgtk (%{undefined rhel} || 0%{?rhel} < 10)}

%define glib2_version 2.68
%define gtk3_version 3.20
%define gtk4_version 4.4
%define gtk_doc_version 1.9
%define goa_version 3.8
%define libsecret_version 0.5
%define libgweather_version 4.0
%define libical_version 3.0.16
%define libsoup_version 3.1.1
%define nss_version 3.14
%define sqlite_version 3.7.17
%define webkit2gtk_version 2.34.0
%define webkit2gtk4_version 2.36.0
%define json_glib_version 1.0.4
%define uuid_version 2.0

%define credential_modules_dir %{_libdir}/evolution-data-server/credential-modules
%define camel_provider_dir %{_libdir}/evolution-data-server/camel-providers
%define ebook_backends_dir %{_libdir}/evolution-data-server/addressbook-backends
%define ecal_backends_dir %{_libdir}/evolution-data-server/calendar-backends
%define modules_dir %{_libdir}/evolution-data-server/registry-modules
%define uimodules_dir %{_libdir}/evolution-data-server/ui-modules

%global dbus_service_name_address_book	org.gnome.evolution.dataserver.AddressBook10
%global dbus_service_name_calendar	org.gnome.evolution.dataserver.Calendar8
%global dbus_service_name_sources	org.gnome.evolution.dataserver.Sources5
%global dbus_service_name_user_prompter	org.gnome.evolution.dataserver.UserPrompter0

### Abstract ###

Name: evolution-data-server
Version: 3.62.1
Release: %autorelease
Summary: Backend data server for Evolution
License: LGPL-2.0-or-later
URL: https://gitlab.gnome.org/GNOME/evolution/-/wikis/home
Source: http://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

# 0-99: General patches
# enable corresponding autopatch below to make them applied

# 100-199: Flatpak-specific patches
# https://gitlab.gnome.org/GNOME/evolution-data-server/-/merge_requests/144
Patch100: Make-DBUS_SERVICES_PREFIX-runtime-configurable.patch

Provides: evolution-webcal = %{version}
Obsoletes: evolution-webcal < 2.24.0

# RH-bug #1362477
Recommends: pinentry-gui

%if 0%{?fedora}
# From rhughes-f20-gnome-3-12 copr
Obsoletes: compat-evolution-data-server310-libcamel < 3.12
%endif

### Dependencies ###

Requires: %{name}-langpacks = %{version}-%{release}

### Build Dependencies ###

BuildRequires: cmake
BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: gettext
BuildRequires: gperf
%if %{with_docs}
BuildRequires: gtk-doc >= %{gtk_doc_version}
%endif
BuildRequires: vala
BuildRequires: systemd

BuildRequires: pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(gio-unix-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(gmodule-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(icu-i18n)
BuildRequires: pkgconfig(gtk+-3.0) >= %{gtk3_version}
BuildRequires: pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires: pkgconfig(goa-1.0) >= %{goa_version}
BuildRequires: pkgconfig(gweather4) >= %{libgweather_version}
BuildRequires: pkgconfig(libical-glib) >= %{libical_version}
BuildRequires: pkgconfig(libsecret-unstable) >= %{libsecret_version}
BuildRequires: pkgconfig(libsoup-3.0) >= %{libsoup_version}
BuildRequires: pkgconfig(libxml-2.0)
BuildRequires: pkgconfig(nspr)
BuildRequires: pkgconfig(nss) >= %{nss_version}
BuildRequires: pkgconfig(sqlite3) >= %{sqlite_version}
BuildRequires: pkgconfig(uuid) >= %{uuid_version}
%if %{with_webkitgtk}
BuildRequires: pkgconfig(webkit2gtk-4.1) >= %{webkit2gtk_version}
BuildRequires: pkgconfig(webkitgtk-6.0) >= %{webkit2gtk4_version}
%endif
BuildRequires: pkgconfig(json-glib-1.0) >= %{json_glib_version}
BuildRequires: pkgconfig(libcanberra-gtk3)

%if %{ldap_support}
BuildRequires: openldap-devel >= 2.0.11
%if %{static_ldap}
BuildRequires: pkgconfig(openssl)
%endif
%endif

%if %{krb5_support}
BuildRequires: krb5-devel >= 1.11
%endif

%if %{phonenum_support}
BuildRequires: libphonenumber-devel
BuildRequires: protobuf-devel
BuildRequires: boost-devel
BuildRequires: abseil-cpp-devel
%endif

# libical 3.0.16 added new API, this ensures to bring it in
Requires: libical-glib >= %{libical_version}

%description
The %{name} package provides a unified backend for programs that work
with contacts, tasks, and calendar information.

It was originally developed for Evolution (hence the name), but is now used
by other packages.

%package devel
Summary: Development files for building against %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

Requires: pkgconfig(goa-1.0) >= %{goa_version}
Requires: pkgconfig(gweather4) >= %{libgweather_version}
Requires: pkgconfig(libical-glib) >= %{libical_version}
Requires: pkgconfig(libsecret-unstable) >= %{libsecret_version}
Requires: pkgconfig(libsoup-3.0) >= %{libsoup_version}
Requires: pkgconfig(sqlite3) >= %{sqlite_version}
%if %{with_webkitgtk}
Requires: pkgconfig(webkit2gtk-4.1) >= %{webkit2gtk_version}
Requires: pkgconfig(webkitgtk-6.0) >= %{webkit2gtk4_version}
%endif
Requires: pkgconfig(json-glib-1.0) >= %{json_glib_version}

%description devel
Development files needed for building things which link against %{name}.

%package langpacks
Summary: Translations for %{name}
BuildArch: noarch
Requires: %{name} = %{version}-%{release}

%description langpacks
This package contains translations for %{name}.

%if %{with_docs}

%package doc
Summary: Documentation files for %{name}
BuildArch: noarch

%description doc
This package contains developer documentation for %{name}.

# %%{with_docs}
%endif

%package perl
Summary: Supplemental utilities that require Perl
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: perl-interpreter

%description perl
This package contains supplemental utilities for %{name} that require Perl.

%package tests
Summary: Tests for the %{name} package
Requires: %{name}%{?_isa} = %{version}-%{release}

%description tests
The %{name}-tests package contains tests that can be used to verify
the functionality of the installed %{name} package.

%prep
%autosetup -p1 -S gendiff -N

# General patches
# %%autopatch -p1 -m 0 -M 99

# Flatpak-specific patches
%if 0%{?flatpak}
%autopatch -p1 -m 100 -M 199
%endif

%build

%if %{ldap_support}

%if %{static_ldap}
%define ldap_flags -DWITH_OPENLDAP=ON -DWITH_STATIC_LDAP=ON
# Set LIBS so that configure will be able to link with static LDAP libraries,
# which depend on Cyrus SASL and OpenSSL.  XXX Is the "else" clause necessary?
if pkg-config openssl ; then
	export LIBS="-lsasl2 `pkg-config --libs openssl`"
else
	export LIBS="-lsasl2 -lssl -lcrypto"
fi
# newer versions of openldap are built with Mozilla NSS crypto, so also need
# those libs to link with the static ldap libs
if pkg-config nss ; then
    export LIBS="$LIBS `pkg-config --libs nss`"
else
    export LIBS="$LIBS -lssl3 -lsmime3 -lnss3 -lnssutil3 -lplds4 -lplc4 -lnspr4"
fi
%else
%define ldap_flags -DWITH_OPENLDAP=ON
%endif

%else
%define ldap_flags -DWITH_OPENLDAP=OFF
%endif

%if %{krb5_support}
%define krb5_flags -DWITH_KRB5=ON
%else
%define krb5_flags -DWITH_KRB5=OFF
%endif

%if %{largefile_support}
%define largefile_flags -DENABLE_LARGEFILE=ON
%else
%define largefile_flags -DENABLE_LARGEFILE=OFF
%endif

%if %{phonenum_support}
%define phonenum_flags -DWITH_PHONENUMBER=ON
%else
%define phonenum_flags -DWITH_PHONENUMBER=OFF
%endif

%define ssl_flags -DENABLE_SMIME=ON

%if %{with_docs}
%define gtkdoc_flags -DENABLE_GTK_DOC=ON
%else
%define gtkdoc_flags -DENABLE_GTK_DOC=OFF
%endif

%if %{with_webkitgtk}
%define webkitgtk_flags -DENABLE_OAUTH2_WEBKITGTK=ON -DENABLE_OAUTH2_WEBKITGTK4=ON
%else
%define webkitgtk_flags -DENABLE_OAUTH2_WEBKITGTK=OFF -DENABLE_OAUTH2_WEBKITGTK4=OFF
%endif

if ! pkg-config --exists nss; then
  echo "Unable to find suitable version of nss to use!"
  exit 1
fi

export CPPFLAGS="-I%{_includedir}/et"
export CFLAGS="$RPM_OPT_FLAGS -DLDAP_DEPRECATED -fPIC -I%{_includedir}/et -Wno-deprecated-declarations"

%cmake -DENABLE_MAINTAINER_MODE=OFF \
	-DENABLE_FILE_LOCKING=fcntl \
	-DENABLE_DOT_LOCKING=OFF \
	-DENABLE_INTROSPECTION=ON \
	-DENABLE_VALA_BINDINGS=ON \
	-DENABLE_INSTALLED_TESTS=ON \
	-DWITH_LIBDB=OFF \
        -DWITH_SYSTEMDUSERUNITDIR=%{_userunitdir} \
	%ldap_flags %krb5_flags %ssl_flags %webkitgtk_flags \
	%largefile_flags %gtkdoc_flags %phonenum_flags \
	-DINCLUDE_INSTALL_DIR:PATH=%{_includedir} \
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

# make sure the directory exists, because it's owned by eds
mkdir $RPM_BUILD_ROOT/%{uimodules_dir} || :
mkdir $RPM_BUILD_ROOT/%{credential_modules_dir} || :

# give the libraries some executable bits
find $RPM_BUILD_ROOT -name '*.so.*' -exec chmod +x {} \;

%find_lang %{name}

%files
%license COPYING
%doc README ChangeLog NEWS
%{_libdir}/libcamel-1.2.so.68
%{_libdir}/libcamel-1.2.so.68.0.0
%{_libdir}/libebackend-1.2.so.11
%{_libdir}/libebackend-1.2.so.11.0.0
%{_libdir}/libebook-1.2.so.21
%{_libdir}/libebook-1.2.so.21.1.3
%{_libdir}/libebook-contacts-1.2.so.5
%{_libdir}/libebook-contacts-1.2.so.5.0.0
%{_libdir}/libecal-2.0.so.3
%{_libdir}/libecal-2.0.so.3.0.0
%{_libdir}/libedata-book-1.2.so.27
%{_libdir}/libedata-book-1.2.so.27.0.0
%{_libdir}/libedata-cal-2.0.so.2
%{_libdir}/libedata-cal-2.0.so.2.0.0
%{_libdir}/libedataserver-1.2.so.28
%{_libdir}/libedataserver-1.2.so.28.0.0
%{_libdir}/libedataserverui-1.2.so.4
%{_libdir}/libedataserverui-1.2.so.4.0.0
%{_libdir}/libedataserverui4-1.0.so.0
%{_libdir}/libedataserverui4-1.0.so.0.0.0

%{_libdir}/girepository-1.0/Camel-1.2.typelib
%{_libdir}/girepository-1.0/EBackend-1.2.typelib
%{_libdir}/girepository-1.0/EBook-1.2.typelib
%{_libdir}/girepository-1.0/EBookContacts-1.2.typelib
%{_libdir}/girepository-1.0/ECal-2.0.typelib
%{_libdir}/girepository-1.0/EDataBook-1.2.typelib
%{_libdir}/girepository-1.0/EDataCal-2.0.typelib
%{_libdir}/girepository-1.0/EDataServer-1.2.typelib
%{_libdir}/girepository-1.0/EDataServerUI-1.2.typelib
%{_libdir}/girepository-1.0/EDataServerUI4-1.0.typelib

%{_libexecdir}/camel-gpg-photo-saver
%{_libexecdir}/camel-index-control-1.2
%{_libexecdir}/camel-lock-helper-1.2
%{_libexecdir}/evolution-addressbook-factory
%{_libexecdir}/evolution-addressbook-factory-subprocess
%{_libexecdir}/evolution-calendar-factory
%{_libexecdir}/evolution-calendar-factory-subprocess
%{_libexecdir}/evolution-source-registry
%{_libexecdir}/evolution-user-prompter

%dir %{_libexecdir}/evolution-data-server
%{_libexecdir}/evolution-data-server/addressbook-export
%{_libexecdir}/evolution-data-server/evolution-alarm-notify
%{_libexecdir}/evolution-data-server/evolution-oauth2-handler
%{_libexecdir}/evolution-data-server/list-sources
%if 0%{?flatpak}
%{_libexecdir}/evolution-data-server/set-dbus-prefix
%endif

%{_sysconfdir}/xdg/autostart/org.gnome.Evolution-alarm-notify.desktop
%{_datadir}/applications/org.gnome.Evolution-alarm-notify.desktop
%{_datadir}/applications/org.gnome.evolution-data-server.OAuth2-handler.desktop

# GSettings schemas:
%{_datadir}/GConf/gsettings/evolution-data-server.convert
%{_datadir}/glib-2.0/schemas/org.gnome.Evolution.DefaultSources.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.evolution-data-server.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.evolution-data-server.addressbook.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.evolution-data-server.calendar.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.evolution.eds-shell.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.evolution.shell.network-config.gschema.xml

%{_datadir}/evolution-data-server
%{_datadir}/dbus-1/services/%{dbus_service_name_address_book}.service
%{_datadir}/dbus-1/services/%{dbus_service_name_calendar}.service
%{_datadir}/dbus-1/services/%{dbus_service_name_sources}.service
%{_datadir}/dbus-1/services/%{dbus_service_name_user_prompter}.service
%{_datadir}/pixmaps/evolution-data-server
%{_datadir}/icons/hicolor/scalable/apps/org.gnome.Evolution-alarm-notify.svg

%{_userunitdir}/evolution-addressbook-factory.service
%{_userunitdir}/evolution-calendar-factory.service
%{_userunitdir}/evolution-source-registry.service
%{_userunitdir}/evolution-user-prompter.service
%{_userunitdir}/evolution-alarm-notify.service

%dir %{_libdir}/evolution-data-server
%dir %{credential_modules_dir}
%dir %{camel_provider_dir}
%dir %{ebook_backends_dir}
%dir %{ecal_backends_dir}
%dir %{modules_dir}
%dir %{uimodules_dir}

%{_libdir}/evolution-data-server/libedbus-private.so

# Camel providers:
%{camel_provider_dir}/libcamelimapx.so
%{camel_provider_dir}/libcamelimapx.urls

%{camel_provider_dir}/libcamellocal.so
%{camel_provider_dir}/libcamellocal.urls

%{camel_provider_dir}/libcamelnntp.so
%{camel_provider_dir}/libcamelnntp.urls

%{camel_provider_dir}/libcamelpop3.so
%{camel_provider_dir}/libcamelpop3.urls

%{camel_provider_dir}/libcamelsendmail.so
%{camel_provider_dir}/libcamelsendmail.urls

%{camel_provider_dir}/libcamelsmtp.so
%{camel_provider_dir}/libcamelsmtp.urls

# e-d-s extensions:
%{credential_modules_dir}/module-credentials-goa.so
%{ebook_backends_dir}/libebookbackendcarddav.so
%{ebook_backends_dir}/libebookbackendfile.so
%{ebook_backends_dir}/libebookbackendldap.so
%{ecal_backends_dir}/libecalbackendcaldav.so
%{ecal_backends_dir}/libecalbackendcontacts.so
%{ecal_backends_dir}/libecalbackendfile.so
%{ecal_backends_dir}/libecalbackendgtasks.so
%{ecal_backends_dir}/libecalbackendhttp.so
%{ecal_backends_dir}/libecalbackendweather.so
%{ecal_backends_dir}/libecalbackendwebdavnotes.so
%{modules_dir}/module-cache-reaper.so
%{modules_dir}/module-google-backend.so
%{modules_dir}/module-gnome-online-accounts.so
%{modules_dir}/module-oauth2-services.so
%{modules_dir}/module-outlook-backend.so
%{modules_dir}/module-secret-monitor.so
%{modules_dir}/module-trust-prompt.so
%{modules_dir}/module-webdav-backend.so
%{modules_dir}/module-yahoo-backend.so

%files devel
%{_includedir}/evolution-data-server
%{_libdir}/libcamel-1.2.so
%{_libdir}/libebackend-1.2.so
%{_libdir}/libebook-1.2.so
%{_libdir}/libebook-contacts-1.2.so
%{_libdir}/libecal-2.0.so
%{_libdir}/libedata-book-1.2.so
%{_libdir}/libedata-cal-2.0.so
%{_libdir}/libedataserver-1.2.so
%{_libdir}/libedataserverui-1.2.so
%{_libdir}/libedataserverui4-1.0.so
%{_libdir}/pkgconfig/camel-1.2.pc
%{_libdir}/pkgconfig/evolution-data-server-1.2.pc
%{_libdir}/pkgconfig/libebackend-1.2.pc
%{_libdir}/pkgconfig/libebook-1.2.pc
%{_libdir}/pkgconfig/libebook-contacts-1.2.pc
%{_libdir}/pkgconfig/libecal-2.0.pc
%{_libdir}/pkgconfig/libedata-book-1.2.pc
%{_libdir}/pkgconfig/libedata-cal-2.0.pc
%{_libdir}/pkgconfig/libedataserver-1.2.pc
%{_libdir}/pkgconfig/libedataserverui-1.2.pc
%{_libdir}/pkgconfig/libedataserverui4-1.0.pc
%{_datadir}/gir-1.0/Camel-1.2.gir
%{_datadir}/gir-1.0/EBackend-1.2.gir
%{_datadir}/gir-1.0/EBook-1.2.gir
%{_datadir}/gir-1.0/EBookContacts-1.2.gir
%{_datadir}/gir-1.0/ECal-2.0.gir
%{_datadir}/gir-1.0/EDataBook-1.2.gir
%{_datadir}/gir-1.0/EDataCal-2.0.gir
%{_datadir}/gir-1.0/EDataServer-1.2.gir
%{_datadir}/gir-1.0/EDataServerUI-1.2.gir
%{_datadir}/gir-1.0/EDataServerUI4-1.0.gir
%{_datadir}/vala/vapi/camel-1.2.deps
%{_datadir}/vala/vapi/camel-1.2.vapi
%{_datadir}/vala/vapi/libebackend-1.2.deps
%{_datadir}/vala/vapi/libebackend-1.2.vapi
%{_datadir}/vala/vapi/libebook-1.2.deps
%{_datadir}/vala/vapi/libebook-1.2.vapi
%{_datadir}/vala/vapi/libebook-contacts-1.2.deps
%{_datadir}/vala/vapi/libebook-contacts-1.2.vapi
%{_datadir}/vala/vapi/libecal-2.0.deps
%{_datadir}/vala/vapi/libecal-2.0.vapi
%{_datadir}/vala/vapi/libedata-book-1.2.deps
%{_datadir}/vala/vapi/libedata-book-1.2.vapi
%{_datadir}/vala/vapi/libedata-cal-2.0.deps
%{_datadir}/vala/vapi/libedata-cal-2.0.vapi
%{_datadir}/vala/vapi/libedataserver-1.2.deps
%{_datadir}/vala/vapi/libedataserver-1.2.vapi
%{_datadir}/vala/vapi/libedataserverui-1.2.deps
%{_datadir}/vala/vapi/libedataserverui-1.2.vapi
%{_datadir}/vala/vapi/libedataserverui4-1.0.deps
%{_datadir}/vala/vapi/libedataserverui4-1.0.vapi

%files langpacks -f %{name}.lang

%if %{with_docs}

%files doc
%{_datadir}/gtk-doc/html/*

%endif

%files perl
%{_libexecdir}/evolution-data-server/csv2vcard

%files tests
%{_libdir}/libetestserverutils.so
%{_libdir}/libetestserverutils.so.0
%{_libdir}/libetestserverutils.so.0.0.0
%{_libexecdir}/%{name}/installed-tests
%{_datadir}/installed-tests

%changelog
%autochangelog
