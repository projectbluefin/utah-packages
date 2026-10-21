%ifarch %{valgrind_arches}
%global has_valgrind 1
%endif

Name:           gcr
Version:        4.4.1
Release:        %autorelease
Summary:        A library for bits of crypto UI and parsing

# gck/pkcs11n.h is MPL 1.1/GPL 2.0/LGPL 2.1
# gck/pkcs11x.h is FSFULLRWD
# ui/icons/render-icons.py is LGPL-3.0-or-later OR CC-BY-SA-3.0
# docs/COPYING is GCR-docs
License:        LGPL-2.1-or-later AND FSFULLRWD AND (LGPL-3.0-or-later OR CC-BY-SA-3.0) AND (MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later) AND GCR-docs
URL:            https://gitlab.gnome.org/GNOME/gcr
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  pkgconfig(gi-docgen)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(gnutls)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libsecret-1)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(p11-kit-1)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  systemd-rpm-macros
BuildRequires:  vala
%if 0%{?has_valgrind}
BuildRequires:  valgrind-devel
%endif
BuildRequires:  /usr/bin/gpg2
BuildRequires:  /usr/bin/ssh-add
BuildRequires:  /usr/bin/ssh-agent
BuildRequires:  /usr/bin/xsltproc

Requires: %{name}-libs%{?_isa} = %{version}-%{release}
Requires: /usr/bin/gpg2
Requires: /usr/bin/ssh-add
Requires: /usr/bin/ssh-agent

%description
gcr is a library for displaying certificates, and crypto UI, accessing
key stores. It also provides a viewer for crypto files on the GNOME
desktop.

gck is a library for accessing PKCS#11 modules like smart cards.

%package        libs
Summary:        gcr and gck libraries
# Renamed in F37
Obsoletes:      %{name}-base < 3.92.0-1
Provides:       %{name}-base = %{version}-%{release}
Provides:       %{name}-base%{?_isa} = %{version}-%{release}
# Dropped in F37
Obsoletes:      %{name}-gtk3 < 3.92.0-1
Obsoletes:      %{name}-gtk4 < 3.92.0-1

%description    libs
The %{name}-libs package contains the gcr and gck shared libraries.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends:     gi-docgen-fonts
# Dropped in F37
Obsoletes:      %{name}-gtk3-devel < 3.92.0-1
Obsoletes:      %{name}-gtk4-devel < 3.92.0-1

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%meson -Dcrypto=gnutls
%meson_build

%install
%meson_install
%find_lang gcr-4

%post
%systemd_user_post gcr-ssh-agent.service

%preun
%systemd_user_preun gcr-ssh-agent.service

%postun
%systemd_user_postun_with_restart gcr-ssh-agent.service

%files
%doc NEWS README.md
%{_bindir}/gcr-viewer-gtk4
%{_libexecdir}/gcr-ssh-agent
%{_libexecdir}/gcr4-ssh-askpass
%{_userunitdir}/gcr-ssh-agent.service
%{_userunitdir}/gcr-ssh-agent.socket

%files libs -f gcr-4.lang
%license COPYING
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Gck-2.typelib
%{_libdir}/girepository-1.0/Gcr-4.typelib
%{_libdir}/libgck-2.so.2*
%{_libdir}/libgcr-4.so.4*

%files devel
%{_includedir}/gck-2/
%{_includedir}/gcr-4/
%{_libdir}/libgck-2.so
%{_libdir}/libgcr-4.so
%{_libdir}/pkgconfig/gck-2.pc
%{_libdir}/pkgconfig/gcr-4.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Gck-2.gir
%{_datadir}/gir-1.0/Gcr-4.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gck-2.deps
%{_datadir}/vala/vapi/gck-2.vapi
%{_datadir}/vala/vapi/gcr-4.deps
%{_datadir}/vala/vapi/gcr-4.vapi
%doc %{_datadir}/doc/gck-2/
%doc %{_datadir}/doc/gcr-4/

%changelog
%autochangelog
