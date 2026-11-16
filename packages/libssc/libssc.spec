# libssc, the Qualcomm Sensor Core client library iio-sensor-proxy uses on
# Qualcomm SoCs, as GNOME OS and Project Bluefin Dakota ship it.
#
# Fedora has no recipe. Written from gnome-build-meta's gnomeos-deps/libssc.bst
# (8a89846d, which Dakota bf271777 tracks): tag v0.4.4 (commit 0cf77b93), meson
# with its defaults, against libqmi, GLib and protobuf-c. The element has no
# GObject introspection or Vala in its build root, so neither is generated
# here.
#
# The build always installs the DSP mocking server the unit tests run under;
# it goes to the -tests subpackage. The tests themselves are not run: the
# mocking server serves over a QRTR socket (AF_QIPCRTR), which the kernel of a
# build root does not provide.

Name:           libssc
Version:        0.4.4
Release:        1%{?dist}
Summary:        Library to expose Qualcomm Sensor Core sensors

License:        GPL-3.0-or-later
URL:            https://codeberg.org/DylanVanAssche/libssc
Source0:        %{url}/archive/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  meson >= 1.4.0
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  pkgconfig(glib-2.0) >= 2.56
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(libprotobuf-c)
BuildRequires:  pkgconfig(qmi-glib) >= 1.33.4
BuildRequires:  protobuf-c-compiler
BuildRequires:  protobuf-compiler
BuildRequires:  python3-devel

%description
libssc exposes the sensors managed by the Qualcomm Sensor Core (the Sensor
Low Power Island DSP found in Qualcomm SoCs from 2018 on) as a GLib library:
proximity, light, accelerometer, magnetometer, compass and gyroscope. The
ssccli tool reads them from the command line.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, generated protobuf-c message headers and the pkg-config file for
developing against %{name}.

%package tests
Summary:        DSP mocking server for testing %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       python3-protobuf

%description tests
A Python mocking server that answers Qualcomm Sensor Core QMI requests over
QRTR, used by the %{name} unit tests.

%prep
%autosetup -n %{name}

%build
%meson
%meson_build

%install
%meson_install

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/ssccli
%{_libdir}/libssc.so.2

%files devel
%{_includedir}/libssc/
%{_libdir}/libssc.so
%{_libdir}/pkgconfig/libssc.pc

%files tests
%{_libexecdir}/installed-tests/libssc/
%{python3_sitelib}/ssc_server/

%changelog
* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 0.4.4-1
- Initial recipe from gnome-build-meta gnomeos-deps/libssc.bst
