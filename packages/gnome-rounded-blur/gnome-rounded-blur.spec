# Native blur provider for blur-my-shell on GNOME 51.
#
# blur-my-shell (built in the image from its submodule) loads the Blur-1.0
# typelib at runtime; without this library its blur effects are inert.
# Bluefin's base image ships gnome-rounded-blur 1.0.1 as an RPM, so this is
# a parity recipe.
#
# Upstream has no mutter-51 support at this commit; the build carries the
# port from Project Bluefin Dakota
# (projectbluefin/dakota, patches/gnome-rounded-blur/0001-mutter-51-support.patch,
# itself a port of upstream commit c0d67c886ac0b54fedaddf75817e85264d16322e,
# submitted upstream as kancko/gnome-rounded-blur#7). Drop the patch when it
# lands upstream; keep the ABI-51 requirement when updating the pin.
%global commit f3bfcc796e1214c1e1d4287ee35cb132ad8133f0
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global gitdate 20260809

Name:           gnome-rounded-blur
Version:        1.0.0
Release:        1.%{gitdate}git%{shortcommit}%{?dist}
Summary:        Rounded corners and blur effect library for GNOME Shell

License:        GPL-3.0-or-later
URL:            https://github.com/kancko/gnome-rounded-blur
Source0:        %{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz
# Port to Mutter 51 (GIR dirs, rpath, CoglContext resolution). From Dakota.
Patch0:         %{name}-1.0.0-mutter-51-support.patch

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  gobject-introspection-devel
BuildRequires:  meson
BuildRequires:  mutter-devel
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
Requires:       mutter%{?_isa}

%description
Library providing the Blur blur effect with corner radius support for
GNOME Shell. blur-my-shell consumes it through GObject introspection;
without it the extension's blur features do nothing.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       mutter-devel%{?_isa}

%description devel
Headers, pkg-config file, and GObject introspection data for building
against %{name}.

%prep
%autosetup -n %{name}-%{commit} -p1

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%{_libdir}/libblur-effect-1.0.so.1*
%{_libdir}/girepository-1.0/Blur-1.0.typelib

%files devel
%{_includedir}/blur-effect-1.0/
%{_libdir}/libblur-effect-1.0.so
%{_libdir}/pkgconfig/blur-effect-1.0.pc
%{_datadir}/gir-1.0/Blur-1.0.gir

%changelog
* Fri Oct 10 2026 Utah Packages <packages@projectbluefin.io> - 1.0.0-1.20260809gitf3bfcc7
- Initial recipe: mutter-51 port from Dakota for the blur-my-shell provider
