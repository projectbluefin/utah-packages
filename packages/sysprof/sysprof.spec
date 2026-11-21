%global glib2_version 2.80.0
%global polkit_version 0.105

Name:           sysprof
Version:        51.0
# Sort above Hummingbird's 51.0-1.1.hum1 so consumers select this fix.
Release:        1.2%{?dist}
Summary:        A system-wide Linux profiler

License:        GPL-2.0-or-later AND GPL-3.0-or-later AND CC-BY-SA-4.0 AND CC0-1.0 AND BSD-2-Clause-Patent
URL:            http://www.sysprof.com
Source0:        https://download.gnome.org/sources/%{name}/%{gnome_major_version}/%{name}-%{gnome_tarball_version}.tar.xz

%gnome_check_version

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gio-unix-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(json-glib-1.0)
BuildRequires:  pkgconfig(libdebuginfod)
BuildRequires:  pkgconfig(libdex-1)
BuildRequires:  pkgconfig(libdw)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(libunwind-generic)
BuildRequires:  pkgconfig(polkit-gobject-1) >= %{polkit_version}
BuildRequires:  pkgconfig(systemd)

%description
Sysprof is a sampling CPU profiler for Linux that collects accurate,
high-precision data and provides efficient access to the sampled
calltrees.


%package        agent
Summary:        Sysprof agent utility

%description    agent
The %{name}-agent package contains the sysprof-agent program. It provides a P2P
D-Bus API to the process which can control subprocesses. It's used by IDE
tooling to have more control across container boundaries.


%package        cli
Summary:        Sysprof command line utility
# Only optional RAPL energy measurements use turbostat (kernel-tools).
# sysprofd reports a missing helper when that collector is requested; CPU
# profiling and daemon startup do not need it. Keep host installs resolvable.
Recommends:     kernel-tools
Requires:       libsysprof%{?_isa} = %{version}-%{release}

%description    cli
The %{name}-cli package contains the sysprof-cli command line utility.


%package     -n libsysprof
Summary:        Sysprof libraries
# Subpackage removed/obsoleted in F39
Obsoletes:      libsysprof-ui < 45.0

%description -n libsysprof
The libsysprof package contains the Sysprof libraries.


%package        capture-devel
Summary:        Development files for sysprof-capture static library
License:        BSD-2-Clause-Patent
Provides:       sysprof-capture-static = %{version}-%{release}

%description    capture-devel
The %{name}-capture-devel package contains the sysprof-capture static library and header files.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}-capture-devel%{?_isa} = %{version}-%{release}
Requires:       libsysprof%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1 -n %{name}-%{gnome_tarball_version}


%build
# Utah uses the Flatpak GUI; build only the native host tools and libraries.
%meson -Dgtk=false -Dhelp=false -Dsysprofd=bundled -Dlibsysprof=true -Dtools=true -Dtests=true
%meson_build


%install
%meson_install
%find_lang %{name} --with-gnome


%check
%meson_test

%files agent
%license COPYING
%{_bindir}/sysprof-agent

%files cli -f %{name}.lang
%license COPYING
%{_bindir}/sysprof-cli
%{_bindir}/sysprof-cat
%{_libexecdir}/sysprofd
%{_libexecdir}/sysprof-live-unwinder
%{_datadir}/dbus-1/system.d/org.gnome.Sysprof3.conf
%{_datadir}/dbus-1/system-services/org.gnome.Sysprof3.service
%{_datadir}/polkit-1/actions/org.gnome.sysprof3.policy
%{_unitdir}/sysprof3.service

%files -n libsysprof
%license COPYING COPYING.gpl-2
%{_libdir}/libsysprof-6.so.6*
%{_libdir}/libsysprof-memory-6.so
%{_libdir}/libsysprof-speedtrack-6.so
%{_libdir}/libsysprof-tracer-6.so

%files capture-devel
%license src/libsysprof-capture/COPYING
%dir %{_includedir}/sysprof-6
%{_includedir}/sysprof-6/sysprof-address.h
%{_includedir}/sysprof-6/sysprof-capture-condition.h
%{_includedir}/sysprof-6/sysprof-capture-cursor.h
%{_includedir}/sysprof-6/sysprof-capture.h
%{_includedir}/sysprof-6/sysprof-capture-reader.h
%{_includedir}/sysprof-6/sysprof-capture-types.h
%{_includedir}/sysprof-6/sysprof-capture-writer.h
%{_includedir}/sysprof-6/sysprof-clock.h
%{_includedir}/sysprof-6/sysprof-collector.h
%{_includedir}/sysprof-6/sysprof-macros.h
%{_includedir}/sysprof-6/sysprof-platform.h
%{_includedir}/sysprof-6/sysprof-version.h
%{_includedir}/sysprof-6/sysprof-version-macros.h
%{_libdir}/libsysprof-capture-4.a
%{_libdir}/pkgconfig/sysprof-capture-4.pc

%files devel
%{_includedir}/sysprof-6/
%{_libdir}/libsysprof-6.so
%{_libdir}/pkgconfig/sysprof-6.pc
%{_datadir}/dbus-1/interfaces/org.gnome.Sysprof.Agent.xml
%{_datadir}/dbus-1/interfaces/org.gnome.Sysprof3.Profiler.xml
%{_datadir}/dbus-1/interfaces/org.gnome.Sysprof3.Service.xml


%changelog
%autochangelog
