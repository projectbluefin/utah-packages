%global source_name libwnck

Summary: Window Navigator Construction Kit
Name: libwnck3
Version: 43.3
Release: %autorelease
URL: http://download.gnome.org/sources/%{source_name}/
Source0: http://download.gnome.org/sources/%{source_name}/%{gnome_major_version}/%{source_name}-%{version}.tar.xz
License: LGPL-2.0-or-later

# https://gitlab.gnome.org/GNOME/libwnck/-/merge_requests/10
#Patch1:        libwnck_0001-Expose-window-scaling-factor_v43.1.patch
#Patch2:        libwnck_0002-icons-Use-cairo-surfaces-to-render-icons_v43.1.patch
#Patch3:        libwnck_0003-xutils-Change-icons-to-being-cairo-surfaces_v43.1.patch
#Patch4:        libwnck_0004-icons-Mark-GdkPixbuf-icons-as-deprecated_v43.1.patch
#Patch5:        libwnck_0005-tasklist-Add-surface-loader-function_v43.1.patch

BuildRequires: gcc
BuildRequires: meson
BuildRequires: gettext
BuildRequires: glib2-devel
BuildRequires: gobject-introspection-devel
BuildRequires: gtk3-devel
BuildRequires: gtk-doc
BuildRequires: libXres-devel
BuildRequires: pango-devel
BuildRequires: startup-notification-devel

Requires:      startup-notification

%description
libwnck (pronounced "libwink") is used to implement pagers, tasklists,
and other such things. It allows applications to monitor information
about open windows, workspaces, their names/icons, and so forth.

%package devel
Summary: Libraries and headers for libwnck
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -n %{source_name}-%{version} -p1


%build
%meson -Dgtk_doc=true
%meson_build


%install
%meson_install

%find_lang %{source_name}-3.0 --with-gnome --all-name


%ldconfig_scriptlets


%files -f %{source_name}-3.0.lang
%license COPYING
%doc AUTHORS README NEWS
%{_libdir}/%{source_name}-3.so.0*
%{_bindir}/wnck-urgency-monitor
%{_libdir}/girepository-1.0/Wnck-3.0.typelib

%files devel
%{_bindir}/wnckprop
%{_libdir}/%{source_name}-3.so
%{_libdir}/pkgconfig/*
%{_includedir}/%{source_name}-3.0/
%{_datadir}/gir-1.0/Wnck-3.0.gir
%doc %{_datadir}/gtk-doc


%changelog
%autochangelog
