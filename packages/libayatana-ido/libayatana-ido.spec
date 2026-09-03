%bcond_without check

%global         src_name ayatana-ido
%global         nsversion 0.4

Name:           lib%{src_name}
Version:        0.10.4
Release:        %autorelease
Summary:        Ayatana Indicator Display Objects library

# For a breakdown of the licensing, see PACKAGE-LICENSING
License:        LGPL-2.0-or-later AND GPL-3.0-only AND (LGPL-3.0-only OR LGPL-2.1-only)
URL:            https://github.com/AyatanaIndicators/%{src_name}
Source0:        %{url}/archive/%{version}/%{src_name}-%{version}.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  cmake
BuildRequires:  pkgconfig(gtk+-3.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  vala

%if %{with check}
BuildRequires:  pkgconfig(gtest)
BuildRequires:  xwayland-run
%endif

%global _description %{expand:
Ayatana IDO provides custom GTK menu widgets for Ayatana System Indicators.}

%description %_description


%package        gtk3
Summary:        %{summary} for GTK3

%description    gtk3 %_description

This version is built against GTK3.


%package        gtk3-devel
Summary:        Development files for %{name}-gtk3
Requires:       %{name}-gtk3%{?_isa} = %{version}-%{release}

%description gtk3-devel
The %{name}-gtk3-devel package contains libraries and header files for
developing applications that use %{name}-gtk3.


%prep
%autosetup -p1 -n %{src_name}-%{version}


%build
%cmake \
%if %{with check}
    -DENABLE_TESTS=ON
%endif

%cmake_build


%install
%cmake_install


%if %{with check}
%check
cd %_vpath_builddir
xwfb-run -- %__ctest --output-on-failure --force-new-ctest-process %{?_smp_mflags}
%endif


%files gtk3
%license AUTHORS COPYING.LGPL-2 COPYING.GPL-3 COPYING.LGPL-3 COPYING.LGPL-2.1
%doc README.md
%{_libdir}/%{name}3-%{nsversion}.so.0
%{_libdir}/%{name}3-%{nsversion}.so.0.0.0
%{_libdir}/girepository-1.0/AyatanaIdo3-%{nsversion}.typelib


%files gtk3-devel
%dir %{_datadir}/gir-1.0/
%{_datadir}/gir-1.0/AyatanaIdo3-%{nsversion}.gir
%{_datadir}/vala/vapi/%{name}3-%{nsversion}.vapi
%dir %{_includedir}/%{name}3-%{nsversion}/
%dir %{_includedir}/%{name}3-%{nsversion}/%{name}/
%{_includedir}/%{name}3-%{nsversion}/%{name}/*.h
%{_libdir}/%{name}3-%{nsversion}.so
%{_libdir}/pkgconfig/%{name}3-%{nsversion}.pc


%changelog
%autochangelog
