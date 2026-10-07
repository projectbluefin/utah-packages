%bcond_with check

# Docs are not needed for flatpak builds
%if 0%{?flatpak}
%bcond_with    docs
%else
%bcond_without docs
%endif

# No GTK 2 in RHEL 10
%if 0%{?rhel} > 9
%bcond_with    gtk2
%else
%bcond_without gtk2
%endif

# No gtk-sharp in RHEL
%if 0%{?rhel}
%bcond_with mono
%else
%bcond_without mono
%endif

%ifnarch %{mono_arches}
%undefine with_mono
%endif

%global nsversion   0.1
%global gtknver2    ayatana-appindicator
%global gtknver3    ayatana-appindicator3

%global _summary    Ayatana Application Indicators
%global _description %{expand:
The Ayatana Application Indicator is a library to allow applications
to export a menu into an Application Indicators aware menu bar.
Based on KSNI it also works in KDE and will fallback to generic
Systray support if none of those are available.}

Name:           libayatana-appindicator
Version:        0.6.0
Release:        %autorelease
Summary:        %{_summary}

# For a breakdown of the licensing, see PACKAGE-LICENSING
License:        GPL-3.0-only AND LGPL-3.0-only AND (LGPL-3.0-only OR LGPL-2.1-only)
URL:            https://github.com/AyatanaIndicators/%{name}
Source0:        %{url}/archive/%{version}/%{name}-%{version}.tar.gz
# Fix Mono bindings from installing in %%{_libdir}/cli
Patch0:         0001-fix-mono-dir.patch
# The gapi metadata supplies the C# name/cname for every signal, but the entries
# for new-tooltip and activate (both added in 0.6.0) are missing, so gapi emits
# events with an empty identifier and the C# bindings fail to compile.
Patch1:         0002-mono-add-missing-signal-metadata.patch

BuildRequires:  gcc
BuildRequires:  cmake
%if %{with docs}
BuildRequires:  gtk-doc
%endif
BuildRequires:  pkgconfig(gtk+-3.0)
BuildRequires:  pkgconfig(ayatana-indicator3-0.4)
BuildRequires:  pkgconfig(dbusmenu-gtk3-0.4)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  vala

%if %{with gtk2}
BuildRequires:  pkgconfig(gtk+-2.0)
BuildRequires:  pkgconfig(ayatana-indicator-0.4)
BuildRequires:  pkgconfig(dbusmenu-gtk-0.4)
%endif

%if %{with mono}
BuildRequires:  mono-devel
BuildRequires:  pkgconfig(gapi-3.0)
BuildRequires:  pkgconfig(gtk-sharp-3.0)
%if %{with gtk2}
BuildRequires:  pkgconfig(gapi-2.0)
BuildRequires:  pkgconfig(gtk-sharp-2.0)
%endif
%endif

%if %{with check}
BuildRequires:  dbus-test-runner
BuildRequires:  mutter
BuildRequires:  pkgconfig(gtest)
BuildRequires:  xwayland-run
%endif

%description %{_description}


%if %{with gtk2}
%package gtk2
Summary:        %{_summary} - GTK2
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-appindicator2 = %{version}-%{release}
Obsoletes:      libayatana-appindicator2 < 0.5.93
Provides:       libayatana-appindicator2-gir = %{version}-%{release}
Obsoletes:      libayatana-appindicator2-gir < 0.5.93

%description gtk2 %{_description}

This version is built against GTK2.

%package gtk2-devel
Summary:        Development files for %{name}-gtk2
Requires:       %{name}-gtk2%{?_isa} = %{version}-%{release}
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-appindicator-doc = %{version}-%{release}
Obsoletes:      libayatana-appindicator-doc < 0.5.93
Provides:       libayatana-appindicator2-devel = %{version}-%{release}
Obsoletes:      libayatana-appindicator2-devel < 0.5.93

%description gtk2-devel
The %{name}-gtk2-devel package contains libraries
and header files for developing applications that use
%{name}-gtk2.
%endif


%package gtk3
Summary:        %_summary - GTK3
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-appindicator3 = %{version}-%{release}
Obsoletes:      libayatana-appindicator3 < 0.5.93
Provides:       libayatana-appindicator3-gir = %{version}-%{release}
Obsoletes:      libayatana-appindicator3-gir < 0.5.93

%description gtk3 %{_description}

This version is built against GTK3.

%package gtk3-devel
Summary:        Development files for %{name}-gtk3
Requires:       %{name}-gtk3%{?_isa} = %{version}-%{release}
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-appindicator3-doc = %{version}-%{release}
Obsoletes:      libayatana-appindicator3-doc < 0.5.93
Provides:       libayatana-appindicator3-devel = %{version}-%{release}
Obsoletes:      libayatana-appindicator3-devel < 0.5.93

%description gtk3-devel
The %{name}-gtk3-devel package contains libraries
and header files for developing applications that use
%{name}-gtk3.


%if %{with mono}
%if %{with gtk2}
%package gtk2-sharp
Summary:        Mono C# bindings for %{name}-gtk2
Requires:       mono-core
Requires:       gtk-sharp2
Requires:       %{name}-gtk2%{?_isa} = %{version}-%{release}

%description gtk2-sharp %{_description}

This package contains the Mono C# bindings for %{name}-gtk2.

%package gtk2-sharp-devel
Summary:        Development files for %{name}-gtk2-sharp
Requires:       %{name}-gtk2-sharp%{?_isa} = %{version}-%{release}

%description gtk2-sharp-devel
The %{name}-gtk2-sharp-devel package contains libraries
and header files for developing applications that use
%{name}-gtk2-sharp.
%endif


%package gtk3-sharp
Summary:        Mono C# bindings for %{name}-gtk2
Requires:       mono-core
Requires:       gtk-sharp3
Requires:       %{name}-gtk3%{?_isa} = %{version}-%{release}

%description gtk3-sharp %{_description}

This package contains the Mono C# bindings for %{name}-gtk3.

%package gtk3-sharp-devel
Summary:        Development files for %{name}-sharp
Requires:       %{name}-gtk3-sharp%{?_isa} = %{version}-%{release}

%description gtk3-sharp-devel
The %{name}-gtk3-sharp-devel package contains libraries
and headerfiles for developing applications that use
%{name}-gtk3-sharp.
%endif


%prep
%autosetup -p1


%build
%define _vpath_builddir build-gtk3
%cmake \
%if %{with docs}
    -DENABLE_GTKDOC=ON \
%else
    -DENABLE_GTKDOC=OFF \
%endif
%if %{with check}
    -DENABLE_TESTS=ON \
%endif
    -DENABLE_BINDINGS_MONO=%{?with_mono:ON}%{!?with_mono:OFF} \

%cmake_build

%if %{with gtk2}
%define _vpath_builddir build-gtk2
%cmake -DFLAVOUR_GTK2=ON \
%if %{with docs}
    -DENABLE_GTKDOC=ON \
%else
    -DENABLE_GTKDOC=OFF \
%endif
%if %{with check}
    -DENABLE_TESTS=ON \
%endif
    -DENABLE_BINDINGS_MONO=%{?with_mono:ON}%{!?with_mono:OFF} \

%cmake_build
%endif


%install
%define _vpath_builddir build-gtk3
%cmake_install

%if %{with mono}
mkdir -p %{buildroot}/%{_monogacdir}
gacutil \
    -i %{buildroot}%{_libdir}/ayatana-appindicator3-sharp-%{nsversion}/ayatana-appindicator3-sharp.dll \
    -package ayatana-appindicator3-sharp \
    -root %{buildroot}%{_prefix}/lib
%endif

%if %{with gtk2}
%define _vpath_builddir build-gtk2
%cmake_install

%if %{with mono}
gacutil \
    -i %{buildroot}%{_libdir}/ayatana-appindicator-sharp-%{nsversion}/ayatana-appindicator-sharp.dll \
    -package ayatana-appindicator-sharp \
    -root %{buildroot}%{_prefix}/lib
%endif
%endif


%if %{with check}
%check
# Tests fail randomly when running in parallel!

pushd build-gtk3 >/dev/null
xwfb-run -c mutter -a %__ctest --output-on-failure --force-new-ctest-process
popd >/dev/null

%if %{with gtk2}
pushd build-gtk2 >/dev/null
xwfb-run -c mutter -a %__ctest --output-on-failure --force-new-ctest-process
popd >/dev/null
%endif
%endif


%if %{with gtk2}
%files gtk2
%license AUTHORS COPYING COPYING.GPL.3 COPYING.LGPL.2.1
%doc README.md
%{_libdir}/%{name}.so.1
%{_libdir}/%{name}.so.1.0.0
%{_libdir}/girepository-1.0/AyatanaAppIndicator-%{nsversion}.typelib


%files gtk2-devel
%dir %{_datadir}/gir-1.0/
%{_datadir}/gir-1.0/AyatanaAppIndicator-%{nsversion}.gir
%if %{with docs}
%dir %{_datadir}/gtk-doc/
%dir %{_datadir}/gtk-doc/html/
%{_datadir}/gtk-doc/html/%{name}/
%endif
%dir %{_includedir}/%{name}-%{nsversion}/
%dir %{_includedir}/%{name}-%{nsversion}/%{name}
%{_includedir}/%{name}-%{nsversion}/%{name}/*.h
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/ayatana-appindicator-%{nsversion}.pc
%endif


%files gtk3
%license AUTHORS COPYING COPYING.GPL.3 COPYING.LGPL.2.1
%doc README.md
%{_libdir}/%{name}3.so.1
%{_libdir}/%{name}3.so.1.0.0
%{_libdir}/girepository-1.0/AyatanaAppIndicator3-%{nsversion}.typelib


%files gtk3-devel
%dir %{_datadir}/gir-1.0/
%{_datadir}/gir-1.0/AyatanaAppIndicator3-%{nsversion}.gir
%if %{with docs}
%dir %{_datadir}/gtk-doc/
%dir %{_datadir}/gtk-doc/html/
%{_datadir}/gtk-doc/html/%{name}3/
%endif
%{_datadir}/vala/vapi/ayatana-appindicator3-%{nsversion}.*
%dir %{_includedir}/%{name}3-%{nsversion}/
%dir %{_includedir}/%{name}3-%{nsversion}/%{name}/
%{_includedir}/%{name}3-%{nsversion}/%{name}/*.h
%{_libdir}/%{name}3.so
%{_libdir}/pkgconfig/ayatana-appindicator3-%{nsversion}.pc


%if %{with mono}
%if %{with gtk2}
%files gtk2-sharp
%dir %{_libdir}/ayatana-appindicator-sharp-%{nsversion}/
%{_libdir}/ayatana-appindicator-sharp-%{nsversion}/ayatana-appindicator-sharp.dll{,.config}
%{_libdir}/ayatana-appindicator-sharp-%{nsversion}/policy.0.0.ayatana-appindicator-sharp.{dll,config}
%{_libdir}/ayatana-appindicator-sharp-%{nsversion}/policy.0.1.ayatana-appindicator-sharp.{dll,config}
%dir %{_monodir}/ayatana-appindicator-sharp/
%{_monodir}/ayatana-appindicator-sharp/ayatana-appindicator-sharp.dll
%dir %{_monogacdir}/ayatana-appindicator-sharp/
%dir %{_monogacdir}/ayatana-appindicator-sharp/%{version}*/
%{_monogacdir}/ayatana-appindicator-sharp/%{version}*/ayatana-appindicator-sharp.dll{,.config}


%files gtk2-sharp-devel
%{_libdir}/pkgconfig/ayatana-appindicator-sharp-0.1.pc
%endif


%files gtk3-sharp
%dir %{_libdir}/ayatana-appindicator3-sharp-%{nsversion}/
%{_libdir}/ayatana-appindicator3-sharp-%{nsversion}/ayatana-appindicator3-sharp.dll{,.config}
%{_libdir}/ayatana-appindicator3-sharp-%{nsversion}/policy.0.0.ayatana-appindicator3-sharp.{dll,config}
%{_libdir}/ayatana-appindicator3-sharp-%{nsversion}/policy.0.1.ayatana-appindicator3-sharp.{dll,config}
%dir %{_monodir}/ayatana-appindicator3-sharp/
%{_monodir}/ayatana-appindicator3-sharp/ayatana-appindicator3-sharp.dll
%dir %{_monogacdir}/ayatana-appindicator3-sharp/
%dir %{_monogacdir}/ayatana-appindicator3-sharp/%{version}*/
%{_monogacdir}/ayatana-appindicator3-sharp/%{version}*/ayatana-appindicator3-sharp.dll{,.config}

%files gtk3-sharp-devel
%{_libdir}/pkgconfig/ayatana-appindicator3-sharp-0.1.pc
%endif

%changelog
%autochangelog
