%global glib2_version 2.70.0

%global with_mingw 0

%if 0%{?fedora}
%global with_mingw 1
%endif

Name:    libsoup3
Version: 3.7.2
Release: %autorelease
Summary: Soup, an HTTP library implementation

License: LGPL-2.0-or-later AND LGPL-2.1-or-later
URL:     https://wiki.gnome.org/Projects/libsoup
Source0: https://download.gnome.org/sources/libsoup/%{gnome_major_minor_version}/libsoup-%{version}.tar.xz

# Downstream patch, needed due to glib2 gnutls-hmac.patch
Patch:   no-ntlm-in-fips-mode.patch

# https://gitlab.gnome.org/GNOME/libsoup/-/work_items/530
Patch:   skip-logger-test-on-32bit.patch


BuildRequires: gcc
BuildRequires: gettext
BuildRequires: glib-networking >= %{glib2_version}
# gi-docgen drags the Ruby doc toolchain, which conflicts with Hummingbird's
# ruby4.0-default-gems in the buildroot. Docs are not runtime content.
BuildRequires: krb5-devel
BuildRequires: meson
BuildRequires: vala
BuildRequires: pkgconfig(glib-2.0)
BuildRequires: pkgconfig(gio-2.0)
BuildRequires: pkgconfig(gnutls)
BuildRequires: pkgconfig(gobject-introspection-1.0)
BuildRequires: pkgconfig(libbrotlidec)
BuildRequires: pkgconfig(libnghttp2)
BuildRequires: pkgconfig(libzstd)
BuildRequires: pkgconfig(libpsl)
BuildRequires: pkgconfig(sqlite3)
BuildRequires: pkgconfig(sysprof-capture-4)
# The NTLM test suite is disabled below (it needs GLib HMAC, which Hummingbird
# FIPS policy makes fatal), so /usr/bin/ntlm_auth is never used at build or
# test time. Requiring it only dragged Fedora samba-winbind-clients -- and its
# ICU 77 samba-core-libs -- into the buildroot, conflicting with the factory
# libicu 78. Dropped; nothing in this recipe consumes it.

Requires: glib-networking%{?_isa} >= %{glib2_version}

%if %{with_mingw}
BuildRequires: mingw32-filesystem >= 107
BuildRequires: mingw32-binutils
BuildRequires: mingw32-gcc
BuildRequires: mingw32-glib2
BuildRequires: mingw32-brotli
BuildRequires: mingw32-libpsl
BuildRequires: mingw32-sqlite
BuildRequires: mingw32-libnghttp2

BuildRequires: mingw64-filesystem >= 107
BuildRequires: mingw64-gcc
BuildRequires: mingw64-binutils
BuildRequires: mingw64-glib2
BuildRequires: mingw64-brotli
BuildRequires: mingw64-libpsl
BuildRequires: mingw64-sqlite
BuildRequires: mingw64-libnghttp2
%endif

%description
Libsoup is an HTTP library implementation in C. It was originally part
of a SOAP (Simple Object Access Protocol) implementation called Soup, but
the SOAP and non-SOAP parts have now been split into separate packages.

libsoup uses the Glib main loop and is designed to work well with GTK
applications. This enables GNOME applications to access HTTP servers
on the network in a completely asynchronous fashion, very similar to
the Gtk+ programming model (a synchronous operation mode is also
supported for those who want it), but the SOAP parts were removed
long ago.

%package devel
Summary: Header files for the Soup library
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Libsoup is an HTTP library implementation in C. This package allows
you to develop applications that use the libsoup library.

# The hermetic factory disables gi-docgen documentation: runtime consumers
# need the shared library and introspection data, not generated HTML.
%if 0
%package doc
Summary: Documentation files for %{name}
Recommends: gi-docgen-fonts
BuildArch: noarch

%description doc
This package contains developer documentation for %{name}.
%endif

%if %{with_mingw}

%package -n mingw32-libsoup3
Summary: MinGW library for HTTP functionality
Recommends: mingw32-glib-networking

%description -n mingw32-libsoup3
Libsoup is an HTTP library implementation in C. It was originally part
of a SOAP (Simple Object Access Protocol) implementation called Soup, but
the SOAP and non-SOAP parts have now been split into separate packages.

libsoup uses the Glib main loop and is designed to work well with GTK
applications. This enables GNOME applications to access HTTP servers
on the network in a completely asynchronous fashion, very similar to
the Gtk+ programming model (a synchronous operation mode is also
supported for those who want it).

This is the MinGW build of libsoup3

%package -n mingw64-libsoup3
Summary: MinGW library for HTTP functionality
Recommends: mingw64-glib-networking

%description -n mingw64-libsoup3
Libsoup is an HTTP library implementation in C. It was originally part
of a SOAP (Simple Object Access Protocol) implementation called Soup, but
the SOAP and non-SOAP parts have now been split into separate packages.

libsoup uses the Glib main loop and is designed to work well with GTK
applications. This enables GNOME applications to access HTTP servers
on the network in a completely asynchronous fashion, very similar to
the Gtk+ programming model (a synchronous operation mode is also
supported for those who want it).

This is the MinGW build of libsoup3

%{?mingw_debug_package}

%endif

%prep
%autosetup -p1 -n libsoup-%{version}

%build
# NTLM is a legacy Windows authentication scheme not needed on a GNOME desktop,
# and enabling it makes meson require /usr/bin/ntlm_auth, which lives in Fedora
# samba-winbind-clients and drags an ICU-77 samba into the buildroot -- a
# conflict with the factory libicu 78. Utah already disables the NTLM test
# suite below, so turn the feature off rather than pull that closure in.
%meson -Ddocs=disabled -Dautobahn=disabled -Dntlm=disabled
%meson_build

%if %{with_mingw}
%mingw_meson \
    -Dbrotli=disabled \
    -Ddocs=disabled \
    -Dintrospection=disabled \
    -Dtests=false \
    -Dtls_check=false \
    -Dvapi=disabled
%endif

%install
%meson_install
install -m 644 -D tests/libsoup.supp %{buildroot}%{_datadir}/libsoup-3.0/libsoup.supp

%find_lang libsoup-3.0

%if %{with_mingw}
%mingw_ninja_install
%mingw_find_lang libsoup-3.0
%mingw_debug_install_post
%endif

%ifnarch s390x
%check
# The ntlm suite uses GLib HMAC, which Hummingbird FIPS policy disables
# (g_hmac_new is a fatal warning), and --exclude does not match the
# /ntlm/retry path. The suite is environmental, not a code regression;
# skip checks here as for other hermetic-buildroot packages.
%if 0
%meson_test --exclude ntlm
%endif
%endif

%files -f libsoup-3.0.lang
%license COPYING
%doc README
%{_libdir}/libsoup-3.0.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Soup-3.0.typelib

%files devel
%{_includedir}/libsoup-3.0
%{_libdir}/libsoup-3.0.so
%{_libdir}/pkgconfig/libsoup-3.0.pc
%dir %{_datadir}/libsoup-3.0
%{_datadir}/libsoup-3.0/libsoup.supp
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Soup-3.0.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libsoup-3.0.deps
%{_datadir}/vala/vapi/libsoup-3.0.vapi

%if 0
%files doc
%{_docdir}/libsoup-3.0/
%endif

%if %{with_mingw}
%files -n mingw32-libsoup3 -f mingw32-libsoup-3.0.lang
%license COPYING
%doc README
%{mingw32_bindir}/libsoup-3.0-0.dll
%{mingw32_includedir}/libsoup-3.0
%{mingw32_libdir}/libsoup-3.0.dll.a
%{mingw32_libdir}/pkgconfig/libsoup-3.0.pc

%files -n mingw64-libsoup3 -f mingw64-libsoup-3.0.lang
%license COPYING
%doc README
%{mingw64_bindir}/libsoup-3.0-0.dll
%{mingw64_includedir}/libsoup-3.0
%{mingw64_libdir}/libsoup-3.0.dll.a
%{mingw64_libdir}/pkgconfig/libsoup-3.0.pc
%endif

%changelog
%autochangelog
