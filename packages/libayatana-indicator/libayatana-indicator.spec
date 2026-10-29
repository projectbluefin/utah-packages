%bcond_with check

# No GTK 2 in RHEL 10
%if 0%{?rhel} > 9
%bcond_with    gtk2
%else
%bcond_without gtk2
%endif

%global         nsversion 0.4

Name:           libayatana-indicator
Version:        0.9.5
Release:        %autorelease
Summary:        Ayatana Indicators Shared Library

License:        GPL-3.0-only
URL:            https://github.com/AyatanaIndicators/%{name}
Source0:        %{url}/archive/%{version}/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  cmake
BuildRequires:  gtk-doc

%if %{with gtk2}
BuildRequires:  pkgconfig(gtk+-2.0)
%endif

BuildRequires:  pkgconfig(gtk+-3.0)
BuildRequires:  pkgconfig(libayatana-ido3-0.4)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  vala

%if %{with check}
BuildRequires:  dbus-test-runner
BuildRequires:  mutter
BuildRequires:  pkgconfig(gtest)
BuildRequires:  xwayland-run
%endif

%global _description %{expand:
The Ayatana Indicators library contains information to build indicators
to go into modern desktops indicator applets.}

%description %_description


%if %{with gtk2}
%package        gtk2
Summary:        %{summary} for GTK2
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-indicator2 = %{version}-%{release}
Obsoletes:      libayatana-indicator2 < 0.9.4

%description    gtk2 %_description

This version is built against GTK2.
%endif


%package        gtk3
Summary:        %{summary} for GTK3
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-indicator3 = %{version}-%{release}
Obsoletes:      libayatana-indicator3 < 0.9.4

%description    gtk3 %_description

This version is built against GTK3.


%if %{with gtk2}
%package        gtk2-devel
Summary:        Development files for %{name}-gtk2
Requires:       %{name}-gtk2%{?_isa} = %{version}-%{release}
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-indicator2-devel = %{version}-%{release}
Obsoletes:      libayatana-indicator2-devel < 0.9.4

%description    gtk2-devel
The %{name}-gtk2-devel package contains libraries and header files for
developing applications that use %{name}-gtk2.
%endif


%package        gtk3-devel
Summary:        Development files for %{name}-gtk3
Requires:       %{name}-gtk3%{?_isa} = %{version}-%{release}
# Force replacement of packages of copr:copr.fedorainfracloud.org:sergiomb:libayatana-appindicator repo
Provides:       libayatana-indicator3-devel = %{version}-%{release}
Obsoletes:      libayatana-indicator3-devel < 0.9.4

%description gtk3-devel
The %{name}-gtk3-devel package contains libraries and header files for
developing applications that use %{name}-gtk3.


%package tools-gtk3
Summary:    Development tools for %{name}
Requires:   %{name}-gtk3%{?_isa} = %{version}-%{release}

%description tools-gtk3 %_description

This package contains GTK3 developer tools.


%prep
%autosetup -p1


%build
%define _vpath_builddir build-gtk3
%cmake \
%if %{with check}
    -DENABLE_TESTS=ON
%endif
%cmake_build

%if %{with gtk2}
%define _vpath_builddir build-gtk2
%cmake -DFLAVOUR_GTK2=ON \
%if %{with check}
    -DENABLE_TESTS=ON
%endif
%cmake_build
%endif


%install
%define _vpath_builddir build-gtk3
%cmake_install

%if %{with gtk2}
%define _vpath_builddir build-gtk2
%cmake_install
%endif


%if %{with check}
%check
# Tests fail randomly when running in parallel

pushd build-gtk3 >/dev/null
xwfb-run -c mutter -- %__ctest --output-on-failure --force-new-ctest-process
popd >/dev/null

%if %{with gtk2}
pushd build-gtk2 >/dev/null
xwfb-run -c mutter -- %__ctest --output-on-failure --force-new-ctest-process
popd >/dev/null
%endif
%endif


%if %{with gtk2}
%files gtk2
%license AUTHORS COPYING
%doc README.md
%{_libdir}/%{name}.so.7
%{_libdir}/%{name}.so.7.0.0
%endif


%files gtk3
%license AUTHORS COPYING
%doc README.md
%{_libdir}/%{name}3.so.7
%{_libdir}/%{name}3.so.7.0.0


%if %{with gtk2}
%files gtk2-devel
%dir %{_includedir}/%{name}-%{nsversion}/
%dir %{_includedir}/%{name}-%{nsversion}/%{name}/
%{_includedir}/%{name}-%{nsversion}/%{name}/*.h
%{_libdir}/%{name}.so
%{_libdir}/pkgconfig/ayatana-indicator-%{nsversion}.pc
%endif


%files gtk3-devel
%dir %{_includedir}/%{name}3-%{nsversion}/
%dir %{_includedir}/%{name}3-%{nsversion}/%{name}/
%{_includedir}/%{name}3-%{nsversion}/%{name}/*.h
%{_libdir}/%{name}3.so
%{_libdir}/pkgconfig/ayatana-indicator3-%{nsversion}.pc


%files tools-gtk3
%dir %{_datadir}/%{name}/
%{_datadir}/%{name}/80indicator-debugging
%dir %{_libexecdir}/libayatana-indicator
%{_libexecdir}/libayatana-indicator/ayatana-indicator-loader3

%changelog
%autochangelog
