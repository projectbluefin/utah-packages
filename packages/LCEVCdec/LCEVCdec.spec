# Tests require network, as described in src/func_tests/README.md, and each test type
# (Qualcomm dev kit, Ubuntu, etc.) requires the download of a few gigabytes of videos
# from https://lcevcdec.nbg1.your-objectstorage.com. The videos used for testing
# are described in the "Content attribution" paragraph of the README.md file.
# So disable tests by default:
%bcond tests 0

# python3-sphinxcontrib-plantuml currently missing from Fedora:
%bcond docs 0

Name:           LCEVCdec
Version:        4.3.1
Release:        2%{?dist}
Summary:        MPEG-5 LCEVC Decoder
License:        BSD-3-Clause-Clear
URL:            https://docs.v-nova.com/v-nova/lcevc/lcevc-sdk-overview

Source0:        https://github.com/v-novaltd/%{name}/archive/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  cmake(CLI11)
BuildRequires:  cli11-devel
BuildRequires:  cmake(fmt)
BuildRequires:  cmake(glfw3)
BuildRequires:  cmake(nlohmann_json)
BuildRequires:  cmake(range-v3)
BuildRequires:  gcc-c++
BuildRequires:  git
BuildRequires:  glslang
BuildRequires:  gmock-devel
BuildRequires:  pkgconfig(libavcodec)
BuildRequires:  pkgconfig(libavdevice)
BuildRequires:  pkgconfig(libavfilter)
BuildRequires:  pkgconfig(libavformat)
BuildRequires:  pkgconfig(libavutil)
BuildRequires:  pkgconfig(libxxhash)
BuildRequires:  pkgconfig(gtest)
BuildRequires:  pkgconfig(vulkan)
# CMake and the Vulkan shader compiler require Python even without functional tests.
BuildRequires:  python3

%if %{with docs}
BuildRequires:  doxygen
BuildRequires:  sphinx
BuildRequires:  plantuml
BuildRequires:  python3-breathe
BuildRequires:  python3-sphinx
BuildRequires:  python3-sphinx_rtd_theme
BuildRequires:  python3-sphinxcontrib-plantuml
%endif

%if %{with tests}
BuildRequires:  python3
BuildRequires:  python3-GitPython
BuildRequires:  python3-numpy
BuildRequires:  python3-requests
%endif

%description
Low Complexity Enhancement Video Codec Decoder (LCEVCdec) is the primary MPEG-5
Part 2 decoder SDK repository maintained by V-Nova.

Features:
 - Decode LCEVC compliant bitstreams
 - Support for a range of formats including YUV, NV12 and RGBA
 - Support for a range of colour formats including BT709 and BT2020
 - Support for HDR and 10-bit streams
 - Support for ABR ladders
 - CPU pixel processing stage
 - Extensive API

%package        devel
Summary:        Development files for %{name}
Provides:       %{name}-static = %{version}-%{release}
Obsoletes:      %{name}-static < %{version}-%{release}
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       plutovg-devel%{?_isa}       

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%package        samples
Summary:        Sample programs for %{name}

%description    samples
Sample programs that use %{name}.

%prep
%autosetup -p1

%if %{with tests}
# Adjust configuration file for tests:
sed -i \
    -e 's/BIN_DIR = build/BIN_DIR = %{_vpath_builddir}/g' \
    src/func_tests/config.ini
%endif

%build
%cmake \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DVN_SDK_EXECUTABLES=ON \
  -DVN_SDK_UNIT_TESTS=ON \
  -DVN_SDK_API_LAYER=ON \
  -DVN_SDK_JSON_CONFIG=ON \
%if %{with docs}
  -DVN_SDK_DOCS=ON \
%else
  -DVN_SDK_DOCS=OFF \
%endif
  -DVN_SDK_PIPELINE_VULKAN=ON

%cmake_build

%install
%cmake_install

# Let RPM pick up docs in the files section
rm -fr %{buildroot}%{_docdir} %{buildroot}%{_prefix}/licenses

%if %{with tests}
%check
python3 src/func_tests/run_tests.py
%endif

%files
%license LICENSE.md COPYING
%doc README.md
%{_libdir}/liblcevc_dec_api.so.4
%{_libdir}/liblcevc_dec_api.so.%{version}
%{_libdir}/liblcevc_dec_pipeline_cpu.so.1
%{_libdir}/liblcevc_dec_pipeline_vulkan.so.1

%files devel
%{_includedir}/LCEVC
%{_libdir}/liblcevc_dec_api.so
%{_libdir}/liblcevc_dec_pipeline_cpu.so
%{_libdir}/liblcevc_dec_pipeline_vulkan.so
# Static:
%{_libdir}/liblcevc_dec_api_utility.a
%{_libdir}/liblcevc_dec_extract.a
%{_libdir}/liblcevc_dec_unit_test_utilities.a
%{_libdir}/liblcevc_dec_utility.a
%{_libdir}/pkgconfig/lcevc_dec.pc
%{_libdir}/pkgconfig/lcevc_dec_extract.pc
%{_libdir}/pkgconfig/lcevc_dec_utility.pc

%files samples
%{_bindir}/lcevc_dec_common_test_unit
%{_bindir}/lcevc_dec_enhancement_sample
%{_bindir}/lcevc_dec_enhancement_test_unit
%{_bindir}/lcevc_dec_extract_test_unit
%{_bindir}/lcevc_dec_pipeline_cpu_test_unit
%{_bindir}/lcevc_dec_pipeline_test_unit
%{_bindir}/lcevc_dec_pipeline_vulkan_test_unit
%{_bindir}/lcevc_dec_pixel_processing_test_unit
%{_bindir}/lcevc_dec_sample
%{_bindir}/lcevc_dec_test_harness
%{_bindir}/lcevc_dec_test_unit
%{_bindir}/lcevc_dec_utility_test_unit

%changelog
* Mon Nov 09 2026 Danathar <Danathar@users.noreply.github.com> - 4.3.1-2
- Declare Python and all FFmpeg libraries used by the build.

* Thu Oct 29 2026 Simone Caronni <negativo17@gmail.com> - 4.3.1-1
- Update to 4.3.1.

* Wed Oct 07 2026 Simone Caronni <negativo17@gmail.com> - 4.2.2-3
- Rebuild for updated dependencies.

* Sun Sep 20 2026 Simone Caronni <negativo17@gmail.com> - 4.2.2-2
- Rebuild for updated dependencies.

* Fri Sep 11 2026 Simone Caronni <negativo17@gmail.com> - 4.2.2-1
- Update to 4.2.2.

* Sun Aug 16 2026 Simone Caronni <negativo17@gmail.com> - 4.2.1-1
- Update to 4.2.1.
- Enable the Vulkan pipeline.

* Wed Jun 17 2026 Simone Caronni <negativo17@gmail.com> - 4.2.0-1
- Update to 4.2.0.

* Mon May 04 2026 Simone Caronni <negativo17@gmail.com> - 4.1.0-1
- Update to 4.1.0.

* Wed Feb 11 2026 Simone Caronni <negativo17@gmail.com> - 4.0.5-1
- Update to 4.0.5.

* Thu Nov 27 2025 Simone Caronni <negativo17@gmail.com> - 4.0.4-1
- Update to 4.0.4.

* Fri Oct 31 2025 Simone Caronni <negativo17@gmail.com> - 4.0.3-1
- Update to 4.0.3.
- Clean up SPEC file.

* Wed Oct 15 2025 Simone Caronni <negativo17@gmail.com> - 4.0.2-1
- Update to 4.0.2.

* Mon Sep 08 2025 Simone Caronni <negativo17@gmail.com> - 4.0.1-2
- Do not hardcode AVX instruction set requirement
  (https://github.com/ublue-os/aurora/issues/828).

* Fri Aug 01 2025 Simone Caronni <negativo17@gmail.com> - 4.0.1-1
- Update to 4.0.1.

* Fri Jul 11 2025 Simone Caronni <negativo17@gmail.com> - 4.0.0-1
- Update to 4.0.0.

* Tue Jun 24 2025 Simone Caronni <negativo17@gmail.com> - 3.3.8-2
- Move static libraries into devel, it can't be used without the static
  libraries.

* Thu Jun 19 2025 Simone Caronni <negativo17@gmail.com> - 3.3.8-1
- Update to 3.3.8.

* Wed May 07 2025 Simone Caronni <negativo17@gmail.com> - 3.3.7-1
- Update to 3.3.7.

* Sat Mar 22 2025 Simone Caronni <negativo17@gmail.com> - 3.3.5-1
- First build.
