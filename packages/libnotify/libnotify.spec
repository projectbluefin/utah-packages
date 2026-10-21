%define glib2_version 2.38.0

Name:           libnotify
Version:        0.8.9
Release:        %autorelease
Summary:        Desktop notification library

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/libnotify
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  meson
# gi-docgen/docbook-xsl-ns/xmlto drag the Ruby doc toolchain, which conflicts
# with Hummingbird's ruby4.0-default-gems in the buildroot. Docs are not
# runtime content; disable them.

Requires:       glib2%{?_isa} >= %{glib2_version}

%description
libnotify is a library for sending desktop notifications to a notification
daemon, as defined in the freedesktop.org Desktop Notifications spec. These
notifications can be used to inform the user about an event or display some
form of information without getting in the user's way.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
This package contains libraries and header files needed for
development of programs using %{name}.

%prep
%autosetup -p1

%build
%meson -Dtests=false -Dman=false -Dgtk_doc=false -Ddocbook_docs=disabled
%meson_build

%install
%meson_install

%files
%license COPYING
%doc NEWS AUTHORS README.md
%{_bindir}/notify-send
%{_libdir}/libnotify.so.*
%{_libdir}/girepository-1.0/Notify-0.7.typelib

%files devel
%dir %{_includedir}/libnotify
%{_includedir}/libnotify/*
%{_libdir}/libnotify.so
%{_libdir}/pkgconfig/libnotify.pc
%{_datadir}/gir-1.0/Notify-0.7.gir

%changelog
%autochangelog
