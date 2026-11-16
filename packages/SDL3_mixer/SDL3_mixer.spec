Name: SDL3_mixer
Summary: Audio mixer for Simple Directmedia Layer

# SDL3_mixer itself is Zlib.
#
# Bundled timidity is "GPLv2 or LGPLv2 or Artistic-Perl", the last of which is disallowed in Fedora.
# https://lists.fedoraproject.org/archives/list/legal@lists.fedoraproject.org/thread/OW4G5IHVBELDYGOFC66G72CHPJTCEHLG/
License: Zlib AND (GPL-2.0-or-later OR LGPL-2.0-or-later)

%global ver_major 3
%global ver_minor 2
%global ver_micro 4

Version: %{ver_major}.%{ver_minor}.%{ver_micro}
Release: 3%{?dist}

%global so_major 0
%global so_version %{so_major}.%{ver_minor}.%{ver_micro}

URL: https://github.com/libsdl-org/SDL_mixer/
Source0: %{URL}archive/release-%{version}/SDL_mixer-release-%{version}.tar.gz

# Clarify licensing of bundled timidity. Backport from upstream.
# https://github.com/libsdl-org/SDL_mixer/commit/cfa8d2c106caf89c585a5aae9eae9d75939eaf2f
Patch0: 0000-timidity-license.patch

BuildRequires: cmake
BuildRequires: diffutils
BuildRequires: gcc
BuildRequires: python3

BuildRequires: cmake(flac)
BuildRequires: cmake(FluidSynth) >= 2.2.0
BuildRequires: cmake(SDL3) >= 3.4.0
BuildRequires: cmake(Vorbis)
BuildRequires: cmake(wavpack)

BuildRequires: pkgconfig(libgme)
BuildRequires: pkgconfig(libmpg123)
BuildRequires: pkgconfig(libxmp)
BuildRequires: pkgconfig(opus)
BuildRequires: pkgconfig(opusfile)

Provides: bundled(timidity)

%description
SDL3_mixer is an audio management library. It provides decoding of many
popular audio file formats, mixing, various DSP processing effects and
positional audio. Audio data can be preloaded, or streamed on-the-fly
into the mixer.

SDL3_mixer supports multiple audio devices, and can even mix to a memory
buffer instead of feeding audio hardware in real time. It is a complete
redesign, rewritten almost from scratch to address deficiencies in SDL2_mixer.


%package devel
Summary: Development files for SDL3_mixer
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The SDL3_mixer-devel package contains libraries and header files
for developing applications that use SDL3_mixer.


%package doc
Summary: Documentation for SDL3_mixer
BuildArch: noarch

Requires: %{name}-devel = %{version}-%{release}

%description doc
This package contains documentation (in man page format) for developing
applications that use SDL3_mixer.


%prep
%autosetup -p1 -n SDL_mixer-release-%{version}

# Remove bundled libs that we don't want to use
rm -rf src/dr_libs/
rm -rf src/stb_vorbis/

# Confusingly, the *_SHARED defines do not control static/dynamic linking,
# but whether a library is dynamically linked at compile-time (OFF)
# or dlopen()'ed at run-time (ON).
#
# Building tests is disabled as those rely on opening an audio device,
# which cannot be done in mock/koji.
%cmake \
	-DSDLMIXER_FLAC=ON \
	-DSDLMIXER_FLAC_DRFLAC=OFF \
	-DSDLMIXER_FLAC_LIBFLAC=ON \
	-DSDLMIXER_FLAC_LIBFLAC_SHARED=OFF \
	-DSDLMIXER_GME=ON \
	-DSDLMIXER_GME_SHARED=OFF \
	-DSDLMIXER_MIDI=ON \
	-DSDLMIXER_MIDI_FLUIDSYNTH=ON \
	-DSDLMIXER_MIDI_FLUIDSYNTH_SHARED=OFF \
	-DSDLMIXER_MIDI_TIMIDITY=ON \
	-DSDLMIXER_MOD=ON \
	-DSDLMIXER_MOD_XMP=ON \
	-DSDLMIXER_MOD_XMP_SHARED=OFF \
	-DSDLMIXER_MP3=ON \
	-DSDLMIXER_MP3_DRMP3=OFF \
	-DSDLMIXER_MP3_MPG123=ON \
	-DSDLMIXER_MP3_MPG123_SHARED=OFF \
	-DSDLMIXER_OPUS=ON \
	-DSDLMIXER_OPUS_SHARED=OFF \
	-DSDLMIXER_VORBIS_STB=OFF \
	-DSDLMIXER_VORBIS_VORBISFILE=ON \
	-DSDLMIXER_VORBIS_VORBISFILE_SHARED=OFF \
	-DSDLMIXER_WAVPACK=ON \
	-DSDLMIXER_WAVPACK_DSD=ON \
	-DSDLMIXER_WAVPACK_SHARED=OFF \
	-DSDLMIXER_EXAMPLES=OFF \
	-DSDLMIXER_INSTALL_MAN=ON \
	-DSDLMIXER_TESTS=OFF \
	-DSDLMIXER_VENDORED=OFF \
	-DCMAKE_POSITION_INDEPENDENT_CODE=ON


%build
%cmake_build


%install
%cmake_install

# Remove pre-installed licence files and use the %%license macro instead
rm -rf %{builddir}%{_datadir}/licenses/


%check
cp -a src/SDL_mixer.sym{,.orig}
cp -a src/SDL_mixer.exports{,.orig}
python3 src/genexports.py
diff -U4 src/SDL_mixer.sym{,.orig}
diff -U4 src/SDL_mixer.exports{,.orig}


%files
%license LICENSE.txt
%license src/timidity/COPYING src/timidity/COPYING.LGPL
%{_libdir}/lib%{name}.so.%{so_major}
%{_libdir}/lib%{name}.so.%{so_version}


%files devel
%{_includedir}/%{name}/
%{_libdir}/lib%{name}.so
%{_libdir}/cmake/%{name}/
%{_libdir}/pkgconfig/sdl3-mixer.pc


%files doc
%{_mandir}/man3/MIX_*.3*
%{_mandir}/man3/SDL_MIXER_*.3*


%changelog
* Mon Oct 19 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.4-3
- Backport upstream commit clarifying timidity license
- Build position-independent code
- Verify exported symbols in %%check

* Tue Aug 18 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.4-2
- Change license tag per discussion on legal mailing list
- Prefer dependencies to be linked dynamically instead of dlopen()'ed

* Wed Jun 03 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.4-1
- Update to v3.2.4
- Move man pages to -doc subpackage

* Thu May 14 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.2-1
- Update to v3.2.2

* Thu Apr 02 2026 Artur Frenszek-Iwicki <fedora@svgames.pl> - 3.2.0-1
- Initial packaging
