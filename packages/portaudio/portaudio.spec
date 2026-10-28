Name:           portaudio
Version:        19.7.0
Release:        %autorelease
Summary:        Free, cross platform, open-source, audio I/O library
License:        MIT
URL:            http://www.portaudio.com/

VCS:            https://github.com/PortAudio/portaudio
Source:         %{VCS}/archive/v%{version}/%{name}-%{version}.tar.gz
Patch:          portaudio-pkgconfig-alsa.patch
# Add some extra API needed by audacity
# http://audacity.googlecode.com/svn/audacity-src/trunk/lib-src/portmixer/portaudio.patch
Patch:          portaudio-audacity.patch

BuildRequires:  alsa-lib-devel
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  doxygen
BuildRequires:  gcc-c++
BuildRequires:  libtool
BuildRequires:  make
%if 0%{?fedora} || 0%{?rhel} >= 9
BuildRequires:  pipewire-jack-audio-connection-kit-devel
%else
BuildRequires:  jack-audio-connection-kit-devel
%endif

%description
PortAudio is a portable audio I/O library designed for cross-platform
support of audio. It uses a callback mechanism to request audio processing.
Audio can be generated in various formats, including 32 bit floating point,
and will be converted to the native format internally.


%package devel
Summary:        Development files for the portaudio audio I/O library
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}


%description devel
PortAudio is a portable audio I/O library designed for cross-platform
support of audio. It uses a callback mechanism to request audio processing.
Audio can be generated in various formats, including 32 bit floating point,
and will be converted to the native format internally.

This package contains files required to build applications that will use the
portaudio library.


%prep
%autosetup -p1 -n %{name}-%{version}
# Needed for patch3
autoreconf -fiv
# With autoconf-2.71 we need to run this twice for things to work ?? (rhbz#1943118)
autoreconf -fiv


%build
%configure --disable-static --enable-cxx
sed -i 's|^hardcode_libdir_flag_spec=.*|hardcode_libdir_flag_spec=""|g' bindings/cpp/libtool
sed -i 's|^runpath_var=LD_RUN_PATH|runpath_var=DIE_RPATH_DIE|g' bindings/cpp/libtool
# no -j# because building with -j# is broken
make
# Build html devel documentation
doxygen


%install
%make_install

%files
%license LICENSE.txt
%doc README.md
%{_libdir}/libportaudio.so.2*
%{_libdir}/libportaudiocpp.so.0*

%files devel
%doc doc/html/*
%{_includedir}/portaudiocpp/
%{_includedir}/portaudio.h
%{_includedir}/pa_jack.h
%{_includedir}/pa_linux_alsa.h
%{_includedir}/pa_unix_oss.h
%{_libdir}/libportaudio.so
%{_libdir}/libportaudiocpp.so
%{_libdir}/pkgconfig/portaudio-2.0.pc
%{_libdir}/pkgconfig/portaudiocpp.pc


%changelog
%autochangelog
