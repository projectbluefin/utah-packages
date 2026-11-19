%global nautilus_version 43~beta

Name:           nautilus-python
Version:        4.2.0
Release:        %autorelease
Summary:        Python bindings for Nautilus

License:        GPL-2.0-or-later
URL:            https://wiki.gnome.org/Projects/NautilusPython
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildRequires:  gcc
BuildRequires:  gtk-doc
BuildRequires:  meson
BuildRequires:  pkgconfig(libnautilus-extension-4) >= %{nautilus_version}
BuildRequires:  pkgconfig(pygobject-3.0)
BuildRequires:  python3-devel

Requires:       nautilus-extensions%{?_isa} >= %{nautilus_version}
Requires:       python3-gobject-base%{?_isa}

%description
Python bindings for Nautilus


%package devel
Summary:        Python bindings for Nautilus
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Python bindings for Nautilus


%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}


%build
%meson
%meson_build


%install
%meson_install
mkdir -p $RPM_BUILD_ROOT%{_datadir}/nautilus-python/extensions
rm -rfv $RPM_BUILD_ROOT%{_docdir}


%files
%license COPYING
%doc AUTHORS NEWS.md README.md
%{_libdir}/nautilus/extensions-4/libnautilus-python.so
%dir %{_datadir}/nautilus-python/extensions

%files devel
%doc examples/
%{_datadir}/pkgconfig/nautilus-python.pc
%dir %{_datadir}/gtk-doc
%dir %{_datadir}/gtk-doc/html
%{_datadir}/gtk-doc/html/nautilus-python/


%changelog
%autochangelog
