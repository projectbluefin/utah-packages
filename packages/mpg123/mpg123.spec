%global out out123
%global fmt fmt123
%global syn syn123

Name: mpg123
Version: 1.33.6
Release: %autorelease

Summary: Real time MPEG 1.0/2.0/2.5 audio player/decoder for layers 1, 2 and 3
License: GPL-2.0-or-later
URL: https://mpg123.org

Source0: %{url}/download/%{name}-%{version}.tar.bz2

BuildRequires: autoconf
BuildRequires: automake
BuildRequires: gcc
BuildRequires: libtool
BuildRequires: make
BuildRequires: pkgconfig(alsa)

Requires: %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%if 0%{?fedora}
%global enable_jack 1
%global enable_portaudio 1
%endif

%global _summary %{summary}

%global _description \
Real time MPEG 1.0/2.0/2.5 audio player/decoder for layers 1, 2 and 3 (most \
commonly MPEG 1.0 layer 3 aka MP3), as well as re-usable decoding and output \
libraries.

%description %{_description}

%package plugins-pulseaudio
Summary: Pulseaudio output plug-in for %{name}
BuildRequires: pkgconfig(libpulse-simple)
Requires: %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Supplements: (mpg123%{?_isa} and pulseaudio%{?_isa})

%description plugins-pulseaudio %{_description}

Pulseaudio output plug-in.

%if 0%{?enable_jack}
%package plugins-jack
Summary: JACK output plug-in for %{name}
BuildRequires: pkgconfig(jack)
Requires: %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Supplements: (mpg123%{?_isa} and jack-audio-connection-kit%{?_isa})
Obsoletes: %{name}-plugins-extras < 1.23.4-1

%description plugins-jack %{_description}

JACK output plug-in.
%endif

%if 0%{?enable_portaudio}
%package plugins-portaudio
Summary: PortAudio output plug-in for %{name}
BuildRequires: pkgconfig(portaudio-2.0)
Requires: %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Supplements: (mpg123%{?_isa} and portaudio%{?_isa})

%description plugins-portaudio %{_description}

PortAudio output plug-in.
%endif

%package libs
Summary: %{_summary}
Provides: lib%{name} = %{?epoch:%{epoch}:}%{version}-%{release}
Provides: lib%{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Obsoletes: lib%{name} < 1.23.4-1

%description libs %{_description}

%package devel
Summary: %{_summary}
BuildRequires: /usr/bin/doxygen
Requires: %{name}-libs%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Provides: lib%{name}-devel = %{?epoch:%{epoch}:}%{version}-%{release}
Provides: lib%{name}-devel%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}
Obsoletes: lib%{name}-devel < 1.23.4-1
Obsoletes: %{name}-libs-devel < 1.23.8-3

%description devel %{_description}

Development files for decoding and output libraries.

%prep
%autosetup -p1

%build
autoreconf -vfi
%configure --enable-modules=yes --with-default-audio=alsa \
  --with-audio=alsa,%{?enable_jack:jack},pulse,oss,%{?enable_portaudio:portaudio}
%make_build
pushd doc
  doxygen doxygen.conf
popd

%install
%make_install
rm %{buildroot}%{_libdir}/*.la

%check
%make_build check

%files
%doc doc/README.remote
%{_bindir}/%{name}
%{_bindir}/%{name}-id3dump
%{_bindir}/%{name}-strip
%{_bindir}/%{out}
%doc %{_mandir}/man1/%{name}.1*
%doc %{_mandir}/man1/%{out}.1*
%dir %{_libdir}/%{name}/
%{_libdir}/%{name}/output_alsa.*
%{_libdir}/%{name}/output_dummy.*
%{_libdir}/%{name}/output_oss.*

%files plugins-pulseaudio
%{_libdir}/%{name}/output_pulse.*

%if 0%{?enable_jack}
%files plugins-jack
%{_libdir}/%{name}/output_jack.*
%endif

%if 0%{?enable_portaudio}
%files plugins-portaudio
%{_libdir}/%{name}/output_portaudio.*
%endif

%files libs
%license COPYING
%doc NEWS
%{_libdir}/lib%{name}.so.0*
%{_libdir}/lib%{out}.so.0*
%{_libdir}/lib%{syn}.so.0*

%files devel
%doc NEWS.lib%{name} doc/html doc/examples doc/BENCHMARKING doc/README.gain
%{_includedir}/%{name}.h
%{_includedir}/%{out}.h
%{_includedir}/%{fmt}.h
%{_includedir}/%{syn}.h
%{_libdir}/lib%{name}.so
%{_libdir}/lib%{out}.so
%{_libdir}/lib%{syn}.so
%{_libdir}/pkgconfig/lib%{name}.pc
%{_libdir}/pkgconfig/lib%{out}.pc
%{_libdir}/pkgconfig/lib%{syn}.pc

%changelog
%autochangelog
