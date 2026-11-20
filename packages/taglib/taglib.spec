%bcond mingw %{undefined rhel}
%bcond tests 1
%bcond doc 0

%global apidocdir __api-doc_fedora

%global common_description %{expand:
TagLib is a library for reading and editing the meta-data of several
popular audio formats. Currently it supports both ID3v1 and ID3v2 for MP3
files, Ogg Vorbis comments and ID3 tags and Vorbis comments in FLAC, MPC,
Speex, WavPack, TrueAudio files, as well as APE Tags.}

Name:       taglib
Summary:    Audio Meta-Data Library
Version:    2.3
Release:    %autorelease

License:    (LGPL-2.1-only OR MPL-1.1) AND BSD-2-Clause AND LGPL-2.1-only
URL:        https://taglib.github.io/
Source0:    https://taglib.github.io/releases/taglib-%{version}%{?beta}.tar.gz

# http://bugzilla.redhat.com/343241
# fix multilib, and drop -lz flag to consumers (probably only needed for static linking)
Patch0:     taglib-2.2.1-multilib.patch

BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: cmake
BuildRequires: pkgconfig
%if %{defined fedora}
BuildRequires: utf8cpp-static
%else
Provides:      bundled(utf8cpp) = 4.0.9
%endif
BuildRequires: zlib-devel
%if %{with tests}
BuildRequires: cppunit-devel
%endif
%if %{with doc}
BuildRequires: doxygen
BuildRequires: graphviz
%endif

%if %{with mingw}
BuildRequires:  mingw32-filesystem >= 95
BuildRequires:  mingw32-gcc
BuildRequires:  mingw32-gcc-c++
BuildRequires:  mingw32-zlib

BuildRequires:  mingw64-filesystem >= 95
BuildRequires:  mingw64-gcc
BuildRequires:  mingw64-gcc-c++
BuildRequires:  mingw64-zlib
%endif

%description
%{common_description}

%package doc
Summary: API Documentation for %{name}
BuildArch: noarch

%description doc
This is API documentation generated from the TagLib source code.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
%if ! %{with doc}
Obsoletes: %{name}-doc < %{version}-%{release}
%endif

%description devel
Files needed when building software with %{name}.

%if %{with mingw}
%package -n mingw32-%{name}
Summary:        %{summary}
BuildArch:      noarch
Provides:       bundled(utf8cpp) = 4.0.9

%description -n mingw32-%{name}
%{common_description}

This is the MinGW version, built for the win32 target.

%package -n mingw64-%{name}
Summary:        %{summary}
BuildArch:      noarch
Provides:       bundled(utf8cpp) = 4.0.9

%description -n mingw64-%{name}
%{common_description}

This is the MinGW version, built for the win64 target.

%{?mingw_debug_package}
%endif

%prep
%autosetup -n taglib-%{version}%{?beta} -p1

%build
%{cmake} \
%if %{with tests}
  -DBUILD_TESTS:BOOL=ON \
%endif
  -DCMAKE_BUILD_TYPE:STRING="Release"

%cmake_build

%if %{with doc}
%cmake_build --target docs
%endif

%if %{with mingw}
%mingw_cmake \
%if %{with tests}
  -DBUILD_TESTS:BOOL=ON \
%endif
  -DCMAKE_BUILD_TYPE:STRING="Release"
%mingw_make_build
%endif

%install
%cmake_install

%if %{undefined fedora}
# do not ship bundled utf8cpp
find %{buildroot}%{_includedir}/utf8cpp %{buildroot}%{_datadir}/utf8cpp -delete
%endif

%if %{with doc}
rm -fr %{apidocdir} ; mkdir %{apidocdir}
cp -a %{_vpath_builddir}/doc/html/ %{apidocdir}/
ln -s html/index.html %{apidocdir}
find %{apidocdir} -name '*.md5' | xargs rm -fv
%endif

%if %{with mingw}
%mingw_make_install

%{?mingw_debug_install_post}
%endif

%check
export PKG_CONFIG_PATH=%{buildroot}%{_libdir}/pkgconfig
test "$(pkg-config --modversion taglib)" = "%{version}"
test "$(pkg-config --modversion taglib_c)" = "%{version}"
%if %{with tests}
#ln -s ../../tests/data %{_target_platform}/tests/
%ctest
%endif

%files
%doc AUTHORS CHANGELOG.md
%license COPYING.LGPL COPYING.MPL
%{_libdir}/libtag.so.2*
%{_libdir}/libtag_c.so.2*

%files devel
%doc examples
%{_bindir}/taglib-config
%{_includedir}/taglib/
%{_libdir}/cmake/taglib/
%{_libdir}/libtag.so
%{_libdir}/libtag_c.so
%{_libdir}/pkgconfig/taglib.pc
%{_libdir}/pkgconfig/taglib_c.pc

%if %{with doc}
%files doc
%doc %{apidocdir}/*
%endif

%if %{with mingw}
%files -n mingw32-%{name}
%doc AUTHORS CHANGELOG.md
%license COPYING.LGPL COPYING.MPL
%{mingw32_bindir}/libtag.dll
%{mingw32_bindir}/libtag_c.dll
%{mingw32_bindir}/taglib-config.cmd
%{mingw32_includedir}/taglib/
%{mingw32_includedir}/utf8cpp/
%{mingw32_datadir}/utf8cpp/
%{mingw32_libdir}/cmake/taglib/
%{mingw32_libdir}/libtag.dll.a
%{mingw32_libdir}/libtag_c.dll.a
%{mingw32_libdir}/pkgconfig/taglib.pc
%{mingw32_libdir}/pkgconfig/taglib_c.pc

%files -n mingw64-%{name}
%doc AUTHORS CHANGELOG.md
%license COPYING.LGPL COPYING.MPL
%{mingw64_bindir}/libtag.dll
%{mingw64_bindir}/libtag_c.dll
%{mingw64_bindir}/taglib-config.cmd
%{mingw64_includedir}/taglib/
%{mingw64_includedir}/utf8cpp/
%{mingw64_datadir}/utf8cpp/
%{mingw64_libdir}/cmake/taglib/
%{mingw64_libdir}/libtag.dll.a
%{mingw64_libdir}/libtag_c.dll.a
%{mingw64_libdir}/pkgconfig/taglib.pc
%{mingw64_libdir}/pkgconfig/taglib_c.pc
%endif

%changelog
%autochangelog
