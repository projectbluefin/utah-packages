# %global gitcommit_full a34e143c22ca99107c4b4efac0ce266f5e93d79a
# %global gitcommit %(c=%{gitcommit_full}; echo ${c:0:7})
# %global date 20200117

Name:           svt-vp9
Version:        0.3.0
Release:        18%{?dist}
Summary:        Scalable Video Technology for VP9 Encoder

# ISC license for Source/Lib/ASM_SSE2/x86inc.asm
License:        BSD-2-Clause-Patent and ISC
URL:            https://github.com/OpenVisualCloud/SVT-VP9
Source0:        %url/archive/v%{version}/%{name}-%{version}.tar.gz
# Source0:        %url/tarball/%{gitcommit_full}
# https://github.com/OpenVisualCloud/SVT-VP9/pull/133
Patch0:         cmake.patch

BuildRequires:  gcc
BuildRequires:  cmake
BuildRequires:  meson
BuildRequires:  nasm
BuildRequires:  gstreamer1-devel
BuildRequires:  gstreamer1-plugins-base-devel

Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

ExclusiveArch:  x86_64

%description
The Scalable Video Technology for VP9 Encoder (SVT-VP9 Encoder)
is a VP9-compliant encoder library core. The SVT-VP9 Encoder development
is a work-in-progress targeting performance levels applicable to both VOD
and Live encoding/transcoding video applications.

%package        libs
Summary:        Libraries for svt-hevc

%description    libs
Libraries for development svt-hevc.

%package        devel
Summary:        Include files and mandatory libraries for development svt-vp9
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description    devel
Include files and mandatory libraries for development svt-vp9.

%package -n     gstreamer1-%{name}
Summary:        GStreamer 1.0 %{name}-based plug-in
Requires:       gstreamer1-plugins-base%{?_isa}

%description -n gstreamer1-%{name}
This package provides %{name}-based GStreamer plug-in.

%prep
%autosetup -p1 -n SVT-VP9-%{version}
#-n OpenVisualCloud-SVT-VP9-%{gitcommit}
# Patch build gstreamer plugin
sed -e "s|install: true,|install: true, include_directories : [ include_directories('../Source/API') ], link_args : '-lSvtVp9Enc',|" \
-e "/svtvp9enc_dep =/d" -e 's|, svtvp9enc_dep||' -e "s|svtvp9enc_dep.found()|true|" -i gstreamer-plugin/meson.build


%build
# TODO: Please submit an issue to upstream (rhbz#2380809)
export CMAKE_POLICY_VERSION_MINIMUM=3.5
%cmake -G Ninja \
    -DCMAKE_SKIP_BUILD_RPATH=TRUE
%cmake_build

pushd gstreamer-plugin
    export LIBRARY_PATH="$PWD/../Bin/Release:$LIBRARY_PATH"
    %meson
    %meson_build
popd


%install
%cmake_install
pushd gstreamer-plugin
    %meson_install
popd

%files
%doc Docs/svt-vp9_encoder_user_guide.md
%{_bindir}/SvtVp9EncApp


%files libs
%license LICENSE.md
%doc README.md
%{_libdir}/libSvtVp9Enc.so.1*

%files devel
%{_includedir}/%{name}
%{_libdir}/libSvtVp9Enc.so
%{_libdir}/pkgconfig/*.pc

%files -n gstreamer1-%{name}
%{_libdir}/gstreamer-1.0/libgstsvtvp9enc.so

%changelog
* Fri Jul 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-18
- Rebuilt for https://fedoraproject.org/wiki/Fedora_45_Mass_Rebuild

* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Tue Nov 11 2025 Cristian Le <git@lecris.dev> - 0.3.0-16
- Allow to build with CMake 4.0 (rhbz#2380809)

* Tue Jul 29 2025 Dominik Mierzejewski <dominik@greysector.net> - 0.3.0-15
- use nasm instead of unmaintained yasm, see:
  https://fedoraproject.org/wiki/Changes/DeprecateYASM

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Sun Jan 19 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Sat Jul 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sat Jan 27 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jul 22 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat Jan 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Sat Jul 23 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sat Jan 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Tue Aug 10 2021 Vasiliy Glazov <vascom2@gmail.com> - 0.3.0-6
- Move documentation to main subpackage

* Wed Jul 28 2021 Vasiliy Glazov <vascom2@gmail.com> - 0.3.0-5
- Fix FTBFS

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Sun Jan 31 2021 Vasiliy N. Glazov <vascom2@gmail.com> - 0.3.0-3
- Fix build with GCC 11

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Sat Nov 07 2020 Vasiliy N. Glazov <vascom2@gmail.com> - 0.3.0-1
- Update to 0.3.0

* Wed Sep 23 2020 Vasiliy N. Glazov <vascom2@gmail.com> - 0.2.2-1
- Update to 0.2.2

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Thu May 07 2020 Vasiliy Glazov <vascom2@gmail.com> - 0.2.0-2
- Update from upstream

* Tue May 05 2020 Vasiliy Glazov <vascom2@gmail.com> - 0.2.0-1
- Update to 0.2.0

* Fri Jan 31 2020 Vasiliy N. Glazov <vascom2@gmail.com> - 0.1.1-0.3.20200117gita34e143
- Update to latest git

* Fri Jan 31 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Fri Oct 11 2019 Vasiliy Glazov <vascom2@gmail.com> - 0.1.1-1
- Update to 0.1.1

* Mon Sep 23 2019 Vasiliy Glazov <vascom2@gmail.com> - 0-1.20190919git68b81bd
- Fixed exit call and executable stack
- Added libs subpackage

* Fri Sep 13 2019 Vasiliy Glazov <vascom2@gmail.com> - 0-1.20190906gite9653d9
- Initial release
