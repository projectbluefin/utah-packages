%global apiver 2.8

Name:          rygel
Version:       46.1
Release:       %autorelease
Summary:       A collection of UPnP/DLNA services

License:       LGPL-2.1-or-later AND CC-BY-SA-3.0
URL:           https://wiki.gnome.org/Projects/Rygel
Source0:       https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildRequires: desktop-file-utils
BuildRequires: docbook-style-xsl
BuildRequires: gettext
BuildRequires: gobject-introspection-devel
BuildRequires: gtk-doc
BuildRequires: libunistring-devel
BuildRequires: meson
BuildRequires: systemd-rpm-macros
BuildRequires: vala
BuildRequires: valadoc
BuildRequires: pkgconfig(gee-0.8)
BuildRequires: pkgconfig(gst-editing-services-1.0)
BuildRequires: pkgconfig(gstreamer-1.0)
BuildRequires: pkgconfig(gstreamer-pbutils-1.0)
BuildRequires: pkgconfig(gtk4)
BuildRequires: pkgconfig(gupnp-1.6)
BuildRequires: pkgconfig(gupnp-av-1.0)
BuildRequires: pkgconfig(gupnp-dlna-2.0)
BuildRequires: pkgconfig(libmediaart-2.0)
BuildRequires: pkgconfig(libsoup-3.0)
BuildRequires: pkgconfig(sqlite3)
BuildRequires: pkgconfig(systemd)
BuildRequires: pkgconfig(tinysparql-3.0)
BuildRequires: python3dist(docutils)
BuildRequires: python3dist(pyyaml)
BuildRequires: /usr/bin/xsltproc

%description
Rygel is a home media solution that allows you to easily share audio, video and
pictures, and control of media player on your home network. In technical terms
it is both a UPnP AV MediaServer and MediaRenderer implemented through a plug-in
mechanism. Interoperability with other devices in the market is achieved by
conformance to very strict requirements of DLNA and on the fly conversion of
media to format that client devices are capable of handling.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with %{name}.

%package localsearch
Summary: Localsearch plugin for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
Obsoletes: %{name}-tracker <= %{version}

%description localsearch
A plugin for rygel to use localsearch to locate media on the local machine.

%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}

%build
%meson \
  -Dapi-docs=true \
  -Dintrospection=enabled \
  -Dexamples=false
%meson_build

%install
%meson_install

%find_lang %{name}

%systemd_user_post %{name}.service

%preun
%systemd_user_preun %{name}.service

%postun
%systemd_user_postun_with_restart %{name}.service

%check
# Verify the desktop files
desktop-file-validate %{buildroot}/%{_datadir}/applications/rygel.desktop
desktop-file-validate %{buildroot}/%{_datadir}/applications/rygel-preferences.desktop

%files -f %{name}.lang
%license COPYING COPYING.logo
%doc AUTHORS NEWS README.md
%config(noreplace) %{_sysconfdir}/rygel.conf
%{_bindir}/rygel
%{_bindir}/rygel-preferences
%{_libdir}/librygel-core-%{apiver}.so.0*
%{_libdir}/librygel-db-%{apiver}.so.0*
%{_libdir}/librygel-renderer-%{apiver}.so.0*
%{_libdir}/librygel-renderer-gst-%{apiver}.so.0*
%{_libdir}/librygel-server-%{apiver}.so.0*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/RygelCore-%{apiver}.typelib
%{_libdir}/girepository-1.0/RygelRenderer-%{apiver}.typelib
%{_libdir}/girepository-1.0/RygelRendererGst-%{apiver}.typelib
%{_libdir}/girepository-1.0/RygelServer-%{apiver}.typelib
%dir %{_libdir}/rygel-%{apiver}
%dir %{_libdir}/rygel-%{apiver}/engines
%dir %{_libdir}/rygel-%{apiver}/plugins
%{_libdir}/rygel-%{apiver}/engines/librygel-media-engine-gst.so
%{_libdir}/rygel-%{apiver}/engines/librygel-media-engine-simple.so
%{_libdir}/rygel-%{apiver}/engines/media-engine-gst.plugin
%{_libdir}/rygel-%{apiver}/engines/media-engine-simple.plugin
%{_libdir}/rygel-%{apiver}/plugins/librygel-external.so
%{_libdir}/rygel-%{apiver}/plugins/external.plugin
%{_libdir}/rygel-%{apiver}/plugins/librygel-gst-launch.so
%{_libdir}/rygel-%{apiver}/plugins/gst-launch.plugin
%{_libdir}/rygel-%{apiver}/plugins/librygel-media-export.so
%{_libdir}/rygel-%{apiver}/plugins/media-export.plugin
%{_libdir}/rygel-%{apiver}/plugins/librygel-mpris.so
%{_libdir}/rygel-%{apiver}/plugins/mpris.plugin
%{_libdir}/rygel-%{apiver}/plugins/librygel-playbin.so
%{_libdir}/rygel-%{apiver}/plugins/playbin.plugin
%{_libexecdir}/rygel/
%{_datadir}/rygel/
%{_datadir}/applications/rygel*
%{_datadir}/dbus-1/services/org.gnome.Rygel1.service
%{_datadir}/icons/hicolor/*/apps/rygel*
%{_mandir}/man1/rygel.1*
%{_mandir}/man5/rygel.conf.5*
%{_userunitdir}/rygel.service

%files localsearch
%{_libdir}/rygel-%{apiver}/plugins/librygel-localsearch.so
%{_libdir}/rygel-%{apiver}/plugins/localsearch.plugin

%files devel
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%doc %{_datadir}/gtk-doc/html/librygel*
%{_libdir}/librygel-*.so
%{_includedir}/rygel-%{apiver}
%{_libdir}/pkgconfig/rygel*.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/RygelCore-%{apiver}.gir
%{_datadir}/gir-1.0/RygelRenderer-%{apiver}.gir
%{_datadir}/gir-1.0/RygelRendererGst-%{apiver}.gir
%{_datadir}/gir-1.0/RygelServer-%{apiver}.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/rygel*.deps
%{_datadir}/vala/vapi/rygel*.vapi

%changelog
%autochangelog
