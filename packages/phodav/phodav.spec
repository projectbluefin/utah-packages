Name:           phodav
Version:        3.0
Release:        %autorelease
Summary:        A WebDAV server using libsoup3
# Automatically converted from old format: LGPLv2+ - review is highly recommended.
License:        LicenseRef-Callaway-LGPLv2+
URL:            https://wiki.gnome.org/phodav

Source0:        https://download.gnome.org/sources/%{name}/%{version}/%{name}-%{version}.tar.xz

BuildRequires:  gtk-doc
BuildRequires:  gettext-devel
BuildRequires:  meson
BuildRequires:  git-core
BuildRequires:  gcc
BuildRequires:  systemd-devel
BuildRequires:  systemd-units
BuildRequires:  libsoup3-devel
BuildRequires:  avahi-gobject-devel
BuildRequires:  asciidoc
BuildRequires:  xmlto
BuildRequires:  libxml2-devel

%description
phởdav is a WebDAV server implementation using libsoup3 (RFC 4918).

%package -n     libphodav
Summary:        A library to serve files with WebDAV
Obsoletes:      libphodav-2.0 <= 0:2.0-3
Obsoletes:      libphodav2 <= 0:2.0-4
Obsoletes:      libphodav-1.0 <= 0:0.4-6

%description -n libphodav
phởdav is a WebDAV server implementation using libsoup3 (RFC 4918).
This package provides the library.

%package -n     libphodav-devel
Summary:        Development files for libphodav
Requires:       libphodav%{?_isa} = %{version}-%{release}
Obsoletes:      libphodav-2.0-devel <= 0:2.0-3
Obsoletes:      libphodav2-devel <= 0:2.0-4
Obsoletes:      libphodav-1.0-devel <= 0:0.4-6

%description -n libphodav-devel
The libphodav-devel package includes the header files for libphodav.

%package -n     chezdav
Summary:        A simple WebDAV server program

%description -n chezdav
The chezdav package contains a simple tool to share a directory
with WebDAV. The service is announced over mDNS for clients to discover.

%package -n     spice-webdavd
Summary:        Spice daemon for the DAV channel
Requires:       avahi

Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

%description -n spice-webdavd
The spice-webdavd package contains a daemon to proxy WebDAV request to
the Spice virtio channel.

%prep
%autosetup -S git_am


%build
%meson -Dsystemdsystemunitdir=%{_unitdir} -Dudevrulesdir=%{_udevrulesdir}

%meson_build

%check
%meson_test

%install
%meson_install

%find_lang phodav-3.0 --with-gnome

%ldconfig_scriptlets -n libphodav

%post -n spice-webdavd
%systemd_post spice-webdavd.service

%preun -n spice-webdavd
%systemd_preun spice-webdavd.service

%postun -n spice-webdavd
%systemd_postun_with_restart spice-webdavd.service

%files -n libphodav -f phodav-3.0.lang
%license COPYING
%{_libdir}/libphodav-3.0.so.0*

%files -n libphodav-devel
%dir %{_includedir}/libphodav-3.0/
%{_includedir}/libphodav-3.0/*
%{_libdir}/libphodav-3.0.so
%{_libdir}/pkgconfig/libphodav-3.0.pc
%{_datadir}/gtk-doc/html/phodav-3.0/*

%files -n chezdav
%{_bindir}/chezdav
%{_mandir}/man1/chezdav.1*

%files -n spice-webdavd
%license COPYING
%{_sbindir}/spice-webdavd
%{_udevrulesdir}/70-spice-webdavd.rules
%{_unitdir}/spice-webdavd.service

%changelog
%autochangelog
