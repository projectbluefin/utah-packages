Name:           gnome-user-docs
Version:        51.2
Release:        %autorelease
Summary:        GNOME User Documentation

License:        CC-BY-SA-3.0
URL:            https://help.gnome.org/
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildArch:      noarch

BuildRequires:  gettext
BuildRequires:  itstool
BuildRequires:  meson
BuildRequires:  pkgconfig
BuildRequires:  yelp-tools

%description
This package contains end-user documentation for the GNOME desktop
environment.

%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}

%build
%meson
%meson_build

%install
%meson_install

%find_lang %{name} --all-name --with-gnome

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md

%changelog
%autochangelog
