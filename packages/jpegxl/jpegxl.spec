# epel 8 need this other already have it
%undefine __cmake_in_source_build

# developper recommendation
%global toolchain clang

# Uncomment for special build to rebuild aom on bumped soname.
#global new_soname 1
%global sover_old 0.10
%global sover 0.11

%bcond_with gimp_plugin
%if 0%{?fedora}
%bcond_without tcmalloc
%endif

%global common_description %{expand:
This package contains a reference implementation of JPEG XL (encoder and
decoder).}

Name:           jpegxl
Epoch:          1
Version:        0.11.2
Release:        %autorelease %{?new_soname:-p -e 0~sonamebump}
Summary:        JPEG XL image format reference implementation

# Main library: BSD
# lodepng: zlib
# sjpeg: ASL 2.0
# skcms: BSD
License:        BSD-3-Clause AND Apache-2.0 AND Zlib
URL:            https://jpeg.org/jpegxl/
Source0:        https://github.com/libjxl/libjxl/archive/v%{version}/%{name}-%{version}.tar.gz

# set VERSION and run ./update_third_party.sh to get Source1 and Source2
Source1:        third_party-%{version}.tar.gz
Source2:        testdata-%{version}.tar.gz

BuildRequires:  asciidoc
BuildRequires:  cmake
BuildRequires:  doxygen
BuildRequires:  clang
BuildRequires:  giflib-devel
%if %{with tcmalloc}
BuildRequires:  gperftools-devel
%endif
BuildRequires:  ninja-build
%if %{with gimp_plugin}
BuildRequires:  pkgconfig(gimp-3.0)
%endif
## sjpeg examples are not built
#BuildRequires:  (pkgconfig(glut) or pkgconfig(freeglut))
BuildRequires:  gtest-devel
BuildRequires:  gflags-devel
BuildRequires:  gmock-devel
BuildRequires:  pkgconfig(libhwy)
BuildRequires:  pkgconfig(libbrotlicommon)
BuildRequires:  pkgconfig(lcms2)
BuildRequires:  pkgconfig(libjpeg)
BuildRequires:  pkgconfig(libpng)
## benchmark tools are not built
#BuildRequires:  pkgconfig(libwebp)
BuildRequires:  pkgconfig(OpenEXR)
## viewers are not built
#BuildRequires:  extra-cmake-modules
#BuildRequires:  pkgconfig(Qt5)
#BuildRequires:  pkgconfig(Qt5X11Extras)
BuildRequires:  pkgconfig(zlib)
# epel 8 need this other already have it
BuildRequires:  python3-devel
%if 0%{?new_soname}
BuildRequires:  libjxl < %{epoch}:%{version}
%endif

# No official release
Provides:       bundled(sjpeg) = 0-0.1.20250403git94e0df6
# Build system is Bazel, which is not packaged by Fedora
Provides:       bundled(skcms) = 0-0.1.20250916git96d9171

%description
%common_description

%package     -n libjxl-utils
Summary:        Utilities for manipulating JPEG XL images
Recommends:     gimp-jxl-plugin   = %{epoch}:%{version}-%{release}
Provides:       jpegxl-utils = %{epoch}:%{version}-%{release}
Obsoletes:      jpegxl-utils < 0.3.7-5

%description -n libjxl-utils
%{common_description}

%package     -n libjxl-devtools
Summary:        Development tools for JPEG-XL
Requires:       libjxl%{?_isa} = %{epoch}:%{version}-%{release}

%description -n libjxl-devtools
%{common_description}

Development tools for JPEG-XL

%package        doc
Summary:        Documentation for JPEG-XL
BuildArch:      noarch

%description    doc
%{common_description}

Documentation for JPEG-XL.

%package     -n libjxl
Summary:        Library files for JPEG-XL
Requires:       shared-mime-info
Provides:       jpegxl-libs = %{epoch}:%{version}-%{release}
Obsoletes:      jpegxl-libs < 0.3.7-5
Obsoletes:      jxl-pixbuf-loader < %{epoch}:%{version}-%{release}
%if %{without gimp_plugin}
Obsoletes:      gimp-jxl-plugin < 1:0.10.3-4
%endif

%description -n libjxl
%{common_description}

Library files for JPEG-XL.

%package     -n libjxl-devel
Summary:        Development files for JPEG-XL
Requires:       libjxl%{?_isa} = %{epoch}:%{version}-%{release}
Provides:       jpegxl-devel = %{epoch}:%{version}-%{release}
Obsoletes:      jpegxl-devel < 0.3.7-5

%description -n libjxl-devel
%{common_description}

Development files for JPEG-XL.

%if %{with gimp_plugin}
%package     -n gimp-jxl-plugin
Summary:        A plugin for loading and saving JPEG-XL images
Requires:       gimp

%description -n gimp-jxl-plugin
This is a GIMP plugin for loading and saving JPEG-XL images.
%endif

%prep
%autosetup -p1 -n libjxl-%{version}
rm -rf testdata/ third_party/
%setup -q -T -D -a 1 -a 2 -n libjxl-%{version}

%build
export CC=clang CXX=clang++
%cmake  -DENABLE_CCACHE=1 \
        -DBUILD_TESTING=ON \
        -DINSTALL_GTEST:BOOL=OFF \
        -DJPEGXL_ENABLE_BENCHMARK:BOOL=OFF \
        -DJPEGXL_ENABLE_PLUGINS:BOOL=ON \
        -DJPEGXL_ENABLE_PLUGIN_GDKPIXBUF:BOOL=OFF \
        -DJPEGXL_FORCE_SYSTEM_BROTLI:BOOL=ON \
        -DJPEGXL_FORCE_SYSTEM_GTEST:BOOL=ON \
        -DJPEGXL_FORCE_SYSTEM_HWY:BOOL=ON \
        -DJPEGXL_WARNINGS_AS_ERRORS:BOOL=OFF \
        -DBUILD_SHARED_LIBS:BOOL=ON \
        -DBUNDLE_LIBPNG_DEFAULT:BOOL=OFF \
        -DBUNDLE_GFLAGS_DEFAULT:BOOL=OFF \
        -DJPEGXL_ENABLE_DEVTOOLS=ON
%cmake_build -- all doc

%install
%cmake_install
#rm -v %{buildroot}%{_libdir}/*.a

%if 0%{?new_soname}
cp -p %{_libdir}/libjxl.so.%{sover_old}*     \
  %{_libdir}/libjxl_threads.so.%{sover_old}* \
  %{_libdir}/libjxl_cms.so.%{sover_old}* \
  %{buildroot}%{_libdir}
%endif

%check
%ifnarch s390x
# * encoding / decoding test failures on big-endian architectures:
#   https://github.com/libjxl/libjxl/issues/3629
# * corrupted generated CMake target names for parametrized gtest tests:
#   https://github.com/google/googletest/issues/4985
#   https://gitlab.kitware.com/cmake/cmake/-/work_items/27846
%ctest
%endif

%files -n libjxl-utils
%doc CONTRIBUTING.md CONTRIBUTORS README.md
%{_bindir}/cjxl
%{_bindir}/djxl
%{_bindir}/jxlinfo
%{_mandir}/man1/cjxl.1*
%{_mandir}/man1/djxl.1*

%files -n libjxl-devtools
%{_bindir}/djxl_fuzzer_corpus
%{_bindir}/butteraugli_main
%{_bindir}/decode_and_encode
%{_bindir}/display_to_hlg
%{_bindir}/exr_to_pq
%{_bindir}/icc_simplify
%{_bindir}/pq_to_hlg
%{_bindir}/render_hlg
%{_bindir}/tone_map
%{_bindir}/texture_to_cube
%{_bindir}/generate_lut_template
%{_bindir}/ssimulacra_main
%{_bindir}/ssimulacra2
%{_bindir}/xyb_range
%{_bindir}/jxl_from_tree
%{_bindir}/local_tone_map

%files doc
%doc doc/*.md
%doc %{_vpath_builddir}/html
%license LICENSE

%files -n libjxl
%license LICENSE
%{_libdir}/libjxl.so.%{sover}*
%{_libdir}/libjxl_threads.so.%{sover}*
%{_libdir}/libjxl_cms.so.%{sover}*
%if 0%{?new_soname}
%{_libdir}/libjxl.so.%{sover_old}*
%{_libdir}/libjxl_threads.so.%{sover_old}*
%{_libdir}/libjxl_cms.so.%{sover_old}*
%endif
%{_datadir}/mime/packages/image-jxl.xml

%files -n libjxl-devel
%doc CONTRIBUTING.md
%{_includedir}/jxl/
%{_libdir}/libjxl.so
%{_libdir}/libjxl_threads.so
%{_libdir}/libjxl_cms.so
%{_libdir}/libjxl_extras_codec.a
%{_libdir}/pkgconfig/libjxl.pc
%{_libdir}/pkgconfig/libjxl_threads.pc
%{_libdir}/pkgconfig/libjxl_cms.pc

%if %{with gimp_plugin}
%files -n gimp-jxl-plugin
%license LICENSE
%{_libdir}/gimp/2.0/plug-ins/file-jxl/
%endif

%changelog
%autochangelog
