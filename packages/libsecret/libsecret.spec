%ifarch %{valgrind_arches}
%global has_valgrind 1
%endif

%bcond_without gnutls

Name:           libsecret
Version:        0.21.8.2
Release:        %autorelease
Summary:        Library for storing and retrieving passwords and other secrets

# docs/reference is GCR-docs
# libsecret/mock/aes.py is Apache-2.0
# libsecret/mock/hkdf.py is GPL-2.0-or-later OR TGPPL-1.0
# part of libsecret/mock/dh.py is LicenseRef-Fedora-Public-Domain
License:        LGPL-2.1-or-later AND Apache-2.0 AND (GPL-2.0-or-later OR TGPPL-1.0) AND LicenseRef-Fedora-Public-Domain AND GCR-docs
URL:            https://wiki.gnome.org/Projects/Libsecret
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  docbook-style-xsl
BuildRequires:  gettext
BuildRequires:  gi-docgen
BuildRequires:  meson
BuildRequires:  vala
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(bash-completion)

%if %{with gnutls}
BuildRequires:  pkgconfig(gnutls) >= 3.8.2
%else
BuildRequires:  pkgconfig(libgcrypt) >= 1.2.2
%endif
BuildRequires:  python3-devel
BuildRequires:  /usr/bin/xsltproc
%if 0%{?has_valgrind}
BuildRequires:  valgrind-devel
%endif

Provides:       bundled(egglib)

%description
libsecret is a library for storing and retrieving passwords and other secrets.
It communicates with the "Secret Service" using DBus. gnome-keyring and
KSecretService are both implementations of a Secret Service.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends:     gi-docgen-fonts

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%package        mock-service
Summary:        Python mock-service files from %{name}
# This subpackage does not need libsecret installed,
# but this ensure that if it is installed, the version matches (for good measure):
Requires:       (%{name} = %{version}-%{release} if %{name})
BuildArch:      noarch

%description    mock-service
The %{name}-mock-service package contains testing Python files from %{name},
for testing of other similar tools, such as the Python SecretStorage package.


%prep
%autosetup -p1

# Use system valgrind headers instead
%if 0%{?has_valgrind}
rm -rf build/valgrind/
%endif


%build
%meson \
%if %{with gnutls}
-Dcrypto=gnutls \
%else
-Dcrypto=libgcrypt \
%endif
%{nil}

%meson_build


%install
%meson_install

%find_lang libsecret

# For the mock-service subpackage
mkdir -p %{buildroot}%{_datadir}/libsecret/mock
cp -a libsecret/mock/*.py %{buildroot}%{_datadir}/libsecret/mock/
cp -a libsecret/mock-service*.py %{buildroot}%{_datadir}/libsecret/
%py_byte_compile %{python3} %{buildroot}%{_datadir}/libsecret/mock/


%files -f libsecret.lang
%license COPYING
%doc NEWS README.md
%{_bindir}/secret-tool
%{_libdir}/libsecret-1.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Secret-1.typelib
%{_mandir}/man1/secret-tool.1*
%{_datadir}/bash-completion/completions/secret-tool

%files devel
%license docs/reference/COPYING
%{_includedir}/libsecret-1/
%{_libdir}/libsecret-1.so
%{_libdir}/pkgconfig/libsecret-1.pc
%{_libdir}/pkgconfig/libsecret-unstable.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Secret-1.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libsecret-1.deps
%{_datadir}/vala/vapi/libsecret-1.vapi
%doc %{_docdir}/libsecret-1/

%files mock-service
%license COPYING
%license COPYING.TESTS
%dir %{_datadir}/libsecret
%{_datadir}/libsecret/mock/
%{_datadir}/libsecret/mock-service*.py


%changelog
%autochangelog
