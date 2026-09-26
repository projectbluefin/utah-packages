%bcond_without check

%global so_version 3

Name:           rubberband
Version:        4.0.0
Release:        %autorelease
Summary:        Audio time-stretching and pitch-shifting utility

License:        GPL-2.0-or-later
URL:            http://www.breakfastquay.com/rubberband/
Source0:        https://breakfastquay.com/files/releases/%{name}-%{version}.tar.bz2
# Two tests fail on ppc64le: https://todo.sr.ht/~breakfastquay/rubberband/29
Patch:          %{name}-disable-failed-ppc64le-tests.diff

BuildRequires:  meson
BuildRequires:  gcc-c++
BuildRequires:  ladspa-devel
BuildRequires:  pkgconfig(fftw3)
BuildRequires:  pkgconfig(lv2)
BuildRequires:  pkgconfig(samplerate)
BuildRequires:  pkgconfig(sndfile)
BuildRequires:  vamp-plugin-sdk-devel
BuildRequires:  boost-devel

# all runtime components were previously packaged together
Recommends:     (ladspa-%{name}-plugins if ladspa)
Recommends:     (lv2-%{name}-plugins if lv2)
Recommends:     (vamp-%{name}-plugins if vamp-plugin-sdk)

%global _description %{expand:
Rubber Band provides an API that permits you to change the
tempo and pitch of an audio recording independently of one another.}

%description    %{_description}

This package provides standalone command-line utilities.

%package        libs
Summary:        Audio time-stretching and pitch-shifting library
Conflicts:      %{name} < %{version}-%{release}

%description    libs %{_description}

This package provides a shared library for use by applications.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       pkgconfig

%description    devel %{_description}

The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package     -n ladspa-%{name}-plugins
Summary:        LADSPA plugin for audio time-stretching and pitch-shifting
Requires:       ladspa
Conflicts:      %{name} < %{version}-%{release}

%description -n ladspa-%{name}-plugins %{_description}

This package provides a LADSPA plugin.

%package     -n lv2-%{name}-plugins
Summary:        LV2 plugin for audio time-stretching and pitch-shifting
Requires:       lv2
Conflicts:      %{name} < %{version}-%{release}

%description -n lv2-%{name}-plugins %{_description}

This package provides a LV2 plugin.

%package     -n vamp-%{name}-plugins
Summary:        VAMP plugin for audio time-stretching and pitch-shifting
Conflicts:      %{name} < %{version}-%{release}

%description -n vamp-%{name}-plugins %{_description}

This package provides a VAMP plugin.


%prep
%autosetup -p1


%build
%meson \
  -Dfft=fftw \
  -Djni=disabled \
  -Dresampler=libsamplerate
%meson_build


%install
%meson_install
find %{buildroot} -name '*.la' -exec rm -f {} ';'
rm -rf %{buildroot}%{_libdir}/*.a


%if %{with check}
%check
%meson_test
%endif


%files
%license COPYING
%doc README.md
%{_bindir}/rubberband
%{_bindir}/rubberband-r3

%files libs
%license COPYING
%{_libdir}/*.so.%{so_version}*

%files devel
%doc CHANGELOG
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/rubberband.pc

%files -n ladspa-%{name}-plugins
%license COPYING
%doc README.md
%{_libdir}/ladspa/ladspa-rubberband.*
%{_datadir}/ladspa/rdf/ladspa-rubberband.rdf

%files -n lv2-%{name}-plugins
%license COPYING
%doc README.md
%dir %{_libdir}/lv2/rubberband.lv2
%{_libdir}/lv2/rubberband.lv2/*

%files -n vamp-%{name}-plugins
%license COPYING
%doc README.md
%{_libdir}/vamp/vamp-rubberband.*

%changelog
%autochangelog
