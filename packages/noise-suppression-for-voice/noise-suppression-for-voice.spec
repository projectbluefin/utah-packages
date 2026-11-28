# noise-suppression-for-voice, the RNNoise LADSPA filter, as GNOME OS and
# Project Bluefin Dakota ship it.
#
# Fedora has no recipe. Written from gnome-build-meta's
# gnomeos-deps/noise-suppression-for-voice.bst (8a89846d, which Dakota
# bf271777 tracks): tag v1.21 (commit 4b0a6f76), CMake with the VST, VST3,
# LV2, AU and AUv3 plugins off, which leaves the LADSPA plugin (the one
# PipeWire's filter-chain loads) and the unit tests.
#
# The release bundles RNNoise (with its model weights) and Catch2 under
# external/ and links RNNoise statically; JUCE and FST are only used by the
# plugin formats that are off.

Name:           noise-suppression-for-voice
Version:        1.22
Release:        1%{?dist}
Summary:        Real-time noise suppression LADSPA plugin based on RNNoise

License:        GPL-3.0-only AND BSD-3-Clause
URL:            https://github.com/werman/noise-suppression-for-voice
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake >= 3.22
BuildRequires:  gcc
BuildRequires:  gcc-c++

Provides:       bundled(rnnoise)

%description
A real-time noise suppression plugin for voice, based on Xiph's RNNoise
recurrent neural network. This package ships the LADSPA plugin, which
PipeWire's filter-chain module and other LADSPA hosts can load to remove
background noise from a microphone.

%prep
%autosetup

%build
%cmake \
    -DBUILD_VST_PLUGIN:BOOL=OFF \
    -DBUILD_VST3_PLUGIN:BOOL=OFF \
    -DBUILD_LV2_PLUGIN:BOOL=OFF \
    -DBUILD_AU_PLUGIN:BOOL=OFF \
    -DBUILD_AUV3_PLUGIN:BOOL=OFF
%cmake_build

%install
%cmake_install

%check
# include(CTest) sits in src/common, so the Catch2 tests register there and
# not in the top-level build directory %%ctest searches.
ctest --test-dir %{__cmake_builddir}/src/common --output-on-failure

%files
%license LICENSE external/rnnoise/COPYING
%doc README.md
%dir %{_libdir}/ladspa
%{_libdir}/ladspa/librnnoise_ladspa.so

%changelog
* Wed Nov 25 2026 github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com> - 1.22-1
- Update to 1.22

* Mon Nov 16 2026 Utah Packages <packages@projectbluefin.io> - 1.21-1
- Initial recipe from gnome-build-meta gnomeos-deps/noise-suppression-for-voice.bst
