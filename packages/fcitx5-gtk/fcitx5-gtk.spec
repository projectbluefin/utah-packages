Name:           fcitx5-gtk
Version:        5.1.7
Release:        %autorelease
Summary:        Gtk im module and glib based dbus client library
# Automatically converted from old format: LGPLv2+ - review is highly recommended.
License:        LicenseRef-Callaway-LGPLv2+
URL:            https://github.com/fcitx/fcitx5-gtk
Source:         https://download.fcitx-im.org/fcitx5/%{name}/%{name}-%{version}.tar.zst
Source1:        https://download.fcitx-im.org/fcitx5/%{name}/%{name}-%{version}.tar.zst.sig
# Refreshed from keyservers (same keys, newer signatures):
#   sq --home=none network keyserver search 2CC8A0609AD2A479C65B6D5C8E8B898CBF2412F9 --output 0x8E8B898CBF2412F9 --overwrite
Source2:        https://pgp.key-server.io/download/0x8E8B898CBF2412F9

BuildRequires:  openpgpverify
BuildRequires:  cmake
BuildRequires:  extra-cmake-modules
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0) >= 2.38
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gtk+-2.0)
BuildRequires:  pkgconfig(gtk+-3.0)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  cmake(fmt)

Requires:       (%{name}2 if gtk2)
Requires:       (%{name}3 if gtk3)
Requires:       (%{name}4 if gtk4)

# not requiring fcitx5 due to that I want to make 
# im_modules be able to install seperately
# this will be helpful to those who are looking 
# forward to use upstream flatpak version.

%description
Gtk im module and glib based dbus client library.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       fcitx5-devel%{?_isa}

%description devel
Development files for fcitx5-gtk.

%package -n %{name}2
Summary:        fcitx5 gtk module for gtk2
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n %{name}2
fcitx5 gtk module for gtk2.

%package -n %{name}3
Summary:        fcitx5 gtk module for gtk3
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n %{name}3
fcitx5 gtk module for gtk3.

%package -n %{name}4
Summary:        fcitx5 gtk module for gtk4
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description -n %{name}4
fcitx5 gtk module for gtk4.

%prep
%{openpgpverify} --keyring='%{SOURCE2}' --signature='%{SOURCE1}' --data='%{SOURCE0}'
%autosetup -p1

%build
%cmake -GNinja
%cmake_build 

%install
%cmake_install

%files
%license LICENSES/LGPL-2.1-or-later.txt
%doc README.md 
%{_libdir}/libFcitx5GClient.so.5.*
%{_libdir}/libFcitx5GClient.so.2
%{_libdir}/girepository-1.0/FcitxG-1.0.typelib

%files devel
%{_includedir}/Fcitx5/GClient/
%{_libdir}/cmake/Fcitx5GClient
%{_libdir}/libFcitx5GClient.so
%{_libdir}/pkgconfig/Fcitx5GClient.pc
%{_datadir}/gir-1.0/

%files -n %{name}2
%{_libdir}/gtk-2.0/*/immodules/im-fcitx5.so
%{_bindir}/fcitx5-gtk2-immodule-probing

%files -n %{name}3
%{_libdir}/gtk-3.0/*/immodules/im-fcitx5.so
%{_bindir}/fcitx5-gtk3-immodule-probing

%files -n %{name}4
%{_libdir}/gtk-4.0/*/immodules/libim-fcitx5.so
%{_bindir}/fcitx5-gtk4-immodule-probing

%changelog
%autochangelog
