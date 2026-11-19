Name:           openal-soft
Version:        1.25.2
Release:        %autorelease
Summary:        Software implementation of the OpenAL 3D audio API

# LGPL-2.0-or-later: Main library
# BSD-3-Clause:
#  - alc/effects/compressor.cpp
#  - alc/effects/vmorpher.cpp
# CC-BY-NC-SA-3.0 : -> NOT FREE
#  - utils/SCUT_KEMAR.def
# GPL-2.0-or-later:
#  - utils/sofa-info.cpp
#  - utils/sofa-support.cpp
#  - utils/makemhr/loaddef.cpp
#  - utils/makemhr/loadsofa.cpp
#  - utils/makemhr/makemhr.cpp
# Apache-2.0:
#  - alc/backends/opensl.cpp
# (LGPL-2.0-or-later AND BSD-3-Clause):
#  - alc/alu.cpp
# NCL:
#  - common/pffft.cpp
#  - common/pffft.h
# MIT:
#  - common/filesystem.cpp
#  - common/filesystem.h
#  - common/ghc_filesystem.h
#  - core/bs2b.cpp
#  - core/bs2b.h
#  - core/rtkit.cpp
#  - core/rtkit.h
#  - examples/
#  - utils/openal-info.c
#  - utils/uhjdecoder.cpp
#  - utils/uhjencoder.cpp
#  - support/docopt.py
#  - support/printable.py
# LicenseRef-Fedora-Public-Domain
#  - core/cubic_tables.cpp
# source of claim:
# These gaussian filter tables are inspired by the gaussian-like filter found
# in the SNES. This is based on the public domain code developed by Near, with
# the help of Ryphecha and nocash, from the nesdev.org forums.
# 
# https://forums.nesdev.org/viewtopic.php?p=251534#p251534>
# Archival:
#  - https://archive.is/wViJG
#  - https://web.archive.org/web/20250130174430/https://forums.nesdev.org/viewtopic.php?p=251534#p251534
# Close license review regarding datasets:
# https://gitlab.com/fedora/legal/fedora-license-data/-/issues/629
# https://gitlab.com/fedora/legal/fedora-license-data/-/issues/635
# https://gitlab.com/fedora/legal/fedora-license-data/-/issues/636
# https://gitlab.com/fedora/legal/fedora-license-data/-/issues/638
License:        LGPL-2.0-or-later AND BSD-3-Clause AND GPL-2.0-or-later AND Apache-2.0 AND (LGPL-2.0-or-later AND BSD-3-Clause) AND (MIT WITH fmt-exception) AND NCL AND MIT AND LicenseRef-Fedora-Public-Domain
URL:            https://openal-soft.org/
VCS:            https://github.com/kcat/openal-soft
# Source without non free datasets
# Run ./make_tarball.sh
# Then don't forget to upload it with:
# fedpkg new-sources *.tar.xz
Source:         openal-soft-%{version}-clean.tar.xz
Source:         make_tarball.sh
# Patch to unbundle fmt
Patch:          0001-Unbundle-fmt.diff

# Implicit dependencies for the unbundling script: curl, rpm-build, tar.
BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(alsa)
BuildRequires:  pkgconfig(fmt)
BuildRequires:  pkgconfig(jack)
BuildRequires:  pkgconfig(libavcodec)
BuildRequires:  pkgconfig(libpulse)
BuildRequires:  pkgconfig(sdl2)
BuildRequires:  pkgconfig(sndfile)
%if 0%{?fedora}
BuildRequires:  pkgconfig(libavcodec)
BuildRequires:  pkgconfig(libmysofa)
BuildRequires:  pkgconfig(portaudio-2.0)
%endif
%if 0%{?fedora} || 0%{?rhel} >= 9
BuildRequires:  pkgconfig(libpipewire-0.3)
%endif
%if 0%{?fedora} || 0%{?rhel} <= 9
BuildRequires:  pkgconfig(Qt6Widgets)
%endif

%description
OpenAL Soft is an LGPL-licensed, cross-platform, software implementation of the 
OpenAL 3D audio API. It's forked from the open-sourced Windows version available 
originally from openal.org's SVN repository (now defunct). OpenAL provides 
capabilities for playing audio in a virtual 3D environment. Distance 
attenuation, doppler shift, and directional sound emitters are among the 
features handled by the API. More advanced effects, including air absorption, 
occlusion, and environmental reverb, are available through the EFX extension. It 
also facilitates streaming audio, multi-channel buffers, and audio capture.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description    devel 
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package        examples
Summary:        Sample applications for OpenAl Soft
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description	examples
Sample applications for OpenAl Soft.

%if 0%{?fedora} || 0%{?rhel} <= 9
%package        qt
Summary:        Qt frontend for configuring OpenAL Soft
Requires:       %{name}%{?_isa} = %{?epoch:%{epoch}:}%{version}-%{release}

%description    qt
The %{name}-qt package contains alsoft-config, a Qt-based tool
for configuring OpenAL features.
%endif

%prep
%autosetup -p1

%build
%cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DALSOFT_CPUEXT_NEON:BOOL=OFF \
    -DALSOFT_EXAMPLES:BOOL=ON \
    -DALSOFT_UTILS:BOOL=ON \
    -DALSOFT_INSTALL_CONFIG:BOOL=ON \
    -DALSOFT_INSTALL_EXAMPLES:BOOL=ON \
    -DALSOFT_INSTALL_HRTF_DATA:BOOL=ON \
    -DALSOFT_INSTALL_UTILS:BOOL=ON
%cmake_build

%install
%cmake_install

install -Dpm644 alsoftrc.sample %{buildroot}%{_sysconfdir}/openal/alsoft.conf
# Don't pin the pulseaudio stream to a specific output device
sed -i 's/#allow-moves = false/allow-moves = true/' \
  %{buildroot}%{_sysconfdir}/openal/alsoft.conf

%files
%license BSD-3Clause COPYING LICENSE-pffft
%doc README.md ChangeLog
%dir %{_sysconfdir}/openal
%config(noreplace) %{_sysconfdir}/openal/alsoft.conf
%{_bindir}/openal-info
%{_datadir}/openal
%exclude %{_datadir}/openal/alsoftrc.sample
%exclude %{_datadir}/openal/presets/presets.txt
%{_libdir}/libopenal.so.1*

%files devel
%if 0%{?fedora}
%{_bindir}/makemhr
%endif
%{_includedir}/AL
%{_libdir}/cmake/OpenAL
%{_libdir}/libopenal.so
%{_libdir}/pkgconfig/openal.pc

%files examples
%{_bindir}/aldebug
%{_bindir}/aldirect
%{_bindir}/alhrtf
%{_bindir}/allafplay
%{_bindir}/allatency
%{_bindir}/almultireverb
%{_bindir}/alplay
%{_bindir}/alrecord
%{_bindir}/alreverb
%{_bindir}/alstream
%{_bindir}/altonegen

%if 0%{?fedora} || 0%{?rhel} <= 9
%files qt
%{_bindir}/alsoft-config
%endif

%changelog
%autochangelog
